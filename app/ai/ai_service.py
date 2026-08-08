import hashlib
import json
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db, socketio
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.code_snapshot import CodeSnapshot
from app.models.code_execution import CodeExecution
from app.models.activity_event import ActivityEvent
from app.models.ai_review import AIReview
from app.services.code_service import get_student_live_code, get_student_live_cursor
from app.services.redis_service import get_redis_client
from app.ai.providers.base import AIProvider
from app.ai.providers.mock_provider import MockAIProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.validator import (
    validate_code_quality_output, validate_progress_output,
    validate_error_analysis_output, validate_hint_output
)
from app.logger import api_logger, error_logger

class AIService:
    """Core AI Intelligence Service for CodeSphere."""
    _provider = None

    @classmethod
    def get_provider(cls) -> AIProvider:
        """Get or initialize configured AI provider."""
        if cls._provider is not None:
            return cls._provider

        import os
        if os.getenv("OPENAI_API_KEY"):
            cls._provider = OpenAIProvider()
        elif os.getenv("GEMINI_API_KEY"):
            cls._provider = GeminiProvider()
        else:
            cls._provider = MockAIProvider()

        return cls._provider

    @classmethod
    def set_provider(cls, provider: AIProvider):
        """Inject custom/mock provider for testing."""
        cls._provider = provider

    @classmethod
    def _compute_fingerprint(cls, code: str, problem_title: str = "", compiler_err: str = "") -> str:
        """Compute SHA256 fingerprint for request deduplication."""
        raw = f"{code}:{problem_title}:{compiler_err}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def analyze_student_code(cls, session_id: int, student_id: int):
        """Analyze student code quality and structure."""
        session = Session.query.get(session_id)
        student = Student.query.filter_by(id=student_id, session_id=session_id).first()
        if not session or not student:
            return None

        code = get_student_live_code(student_id)
        if not code or len(code.strip()) == 0:
            return None

        problem = Problem.query.filter_by(session_id=session_id).order_by(Problem.created_at.desc()).first()
        prob_dict = problem.to_dict(include_reference=False) if problem else {}

        # 1. Fingerprint deduplication check in Redis
        fp = cls._compute_fingerprint(code, prob_dict.get("title", ""))
        redis_key = f"ai:fingerprint:{session_id}:{student_id}:{fp}"
        try:
            r = get_redis_client()
            cached = r.get(redis_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # 2. Call provider
        provider = cls.get_provider()
        raw_res = provider.analyze_code(prob_dict, code, session.language, session.mode)
        validated = validate_code_quality_output(raw_res)

        # 3. Save AIReview DB record
        latest_snap = CodeSnapshot.query.filter_by(student_id=student_id).order_by(CodeSnapshot.version.desc()).first()
        review = AIReview(
            session_id=session_id,
            student_id=student_id,
            problem_id=problem.id if problem else None,
            code_snapshot_id=latest_snap.id if latest_snap else None,
            analysis_type="code_review",
            code_quality=validated["overall"],
            confidence=90,
            summary=validated["summary"],
            logic_analysis_json=json.dumps({"logic": validated["logic"]}),
            complexity_analysis_json=json.dumps({"efficiency": validated["efficiency"]}),
            suggestions_json=json.dumps(validated["suggestions"])
        )
        review.save()

        # 4. Cache in Redis for 60 seconds
        try:
            r = get_redis_client()
            r.set(redis_key, json.dumps(validated), ex=60)
        except Exception:
            pass

        # 5. Broadcast Socket.IO event
        room_name = f"session:{session_id}"
        socketio.emit("ai_analysis_completed", {
            "event": "ai_analysis_completed",
            "session_id": session_id,
            "student_id": student_id,
            "analysis_type": "code_review",
            "data": validated,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, to=room_name)

        return validated

    @classmethod
    def estimate_progress(cls, session_id: int, student_id: int):
        """Estimate student progress toward completing problem (problem_solving mode only)."""
        session = Session.query.get(session_id)
        student = Student.query.filter_by(id=student_id, session_id=session_id).first()
        if not session or not student:
            return None

        if session.mode != "problem_solving":
            return {"progress": None, "confidence": 0, "reasoning_summary": "Progress estimation only active in problem_solving mode"}

        code = get_student_live_code(student_id)
        problem = Problem.query.filter_by(session_id=session_id).order_by(Problem.created_at.desc()).first()
        
        # Pass reference_solution internally to AI provider
        ref_solution = problem.reference_solution if problem else ""
        prob_dict = problem.to_dict(include_reference=False) if problem else {}

        provider = cls.get_provider()
        raw_res = provider.analyze_progress(prob_dict, code, session.language, reference_solution=ref_solution)
        validated = validate_progress_output(raw_res)

        # Save AIReview DB record
        review = AIReview(
            session_id=session_id,
            student_id=student_id,
            problem_id=problem.id if problem else None,
            analysis_type="progress",
            progress=validated["progress"],
            confidence=validated["confidence"],
            summary=validated["reasoning_summary"]
        )
        review.save()

        # Broadcast ai_progress_updated to teacher room
        room_name = f"session:{session_id}"
        socketio.emit("ai_progress_updated", {
            "event": "ai_progress_updated",
            "session_id": session_id,
            "student_id": student_id,
            "progress": validated["progress"],
            "confidence": validated["confidence"],
            "stage": validated["stage"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, to=room_name)

        return validated

    @classmethod
    def analyze_compiler_error(cls, session_id: int, student_id: int, compiler_output: str):
        """Explain compiler/runtime errors with conceptual hints."""
        session = Session.query.get(session_id)
        if not session:
            return None

        code = get_student_live_code(student_id)
        provider = cls.get_provider()
        raw_res = provider.analyze_error(code, session.language, compiler_output)
        validated = validate_error_analysis_output(raw_res)

        review = AIReview(
            session_id=session_id,
            student_id=student_id,
            analysis_type="error_analysis",
            summary=validated["explanation"],
            bug_analysis_json=json.dumps({"likely_cause": validated["likely_cause"]}),
            suggestions_json=json.dumps([validated["concept_hint"]])
        )
        review.save()

        return validated

    @classmethod
    def generate_student_hint(cls, session_id: int, student_id: int):
        """Generate mode-restricted hint for a student."""
        session = Session.query.get(session_id)
        if not session:
            return None

        code = get_student_live_code(student_id)
        problem = Problem.query.filter_by(session_id=session_id).order_by(Problem.created_at.desc()).first()
        prob_dict = problem.to_dict(include_reference=False) if problem else {}

        provider = cls.get_provider()
        raw_res = provider.generate_hint(prob_dict, code, session.language, session.mode)
        validated = validate_hint_output(raw_res)

        # Enforce problem_solving mode strict safety check (no direct code solutions)
        if session.mode == "problem_solving":
            hint_text = validated.get("hint", "")
            if "def " in hint_text or "class " in hint_text or "return " in hint_text or "int main()" in hint_text:
                validated["hint"] = "Consider reviewing your algorithm logic and loop conditions carefully."
                validated["hint_type"] = "conceptual"

        review = AIReview(
            session_id=session_id,
            student_id=student_id,
            analysis_type="hint",
            summary=validated["hint"],
            suggestions_json=json.dumps([validated["hint"]])
        )
        review.save()

        return validated

    @classmethod
    def detect_stuck_student(cls, session_id: int, student_id: int):
        """Detect if student is stuck based on code snapshots & compiler errors."""
        session = Session.query.get(session_id)
        if not session:
            return None

        code = get_student_live_code(student_id)
        snapshots = CodeSnapshot.query.filter_by(session_id=session_id, student_id=student_id).all()
        compiler_executions = CodeExecution.query.filter_by(session_id=session_id, student_id=student_id).all()
        activity_events = ActivityEvent.query.filter_by(session_id=session_id, student_id=student_id).all()

        snap_list = [s.to_dict() for s in snapshots]
        exec_list = [e.to_dict() for e in compiler_executions]
        act_list = [a.to_dict() for a in activity_events]

        provider = cls.get_provider()
        stuck_res = provider.detect_stuck(code, snap_list, exec_list, act_list)

        if stuck_res.get("stuck"):
            room_name = f"session:{session_id}"
            student = Student.query.get(student_id)
            socketio.emit("ai_warning", {
                "event": "ai_warning",
                "session_id": session_id,
                "student_id": student_id,
                "student_name": student.name if student else "Student",
                "roll_number": student.roll_number if student else "",
                "stuck": True,
                "reason": stuck_res.get("reason", "Student appears stuck"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, to=room_name)

        return stuck_res

    @classmethod
    def generate_teacher_insight(cls, session_id: int):
        """Generate aggregated session AI insights for teacher overview."""
        session = Session.query.get(session_id)
        if not session:
            return None

        students = Student.query.filter_by(session_id=session_id).all()
        student_stats = [{"id": s.id, "name": s.name} for s in students]

        provider = cls.get_provider()
        summary = provider.generate_session_summary(session.to_dict(), student_stats)

        stuck_students = []
        for s in students:
            stuck_res = cls.detect_stuck_student(session_id, s.id)
            if stuck_res and stuck_res.get("stuck"):
                stuck_students.append({
                    "student_id": s.id,
                    "student_name": s.name,
                    "roll_number": s.roll_number,
                    "reason": stuck_res.get("reason", "")
                })

        return {
            "session_id": session_id,
            "summary": summary,
            "stuck_students": stuck_students,
            "stuck_count": len(stuck_students)
        }
