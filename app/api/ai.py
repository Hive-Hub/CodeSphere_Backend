from flask import request
from flask_restx import Namespace, Resource
from app.models.session import Session
from app.models.student import Student
from app.models.ai_review import AIReview
from app.ai.ai_service import AIService
from app.utils.auth import teacher_token_required, student_token_required
from app.utils.response import api_response, api_error
from app.services.redis_service import get_redis_client

ai_ns = Namespace("ai", description="AI Intelligence & Code Analysis Operations")

def check_ai_rate_limit(key_prefix: str, identifier: int, limit: int = 5, window_seconds: int = 60) -> bool:
    """Redis rate limiter helper for AI endpoints."""
    try:
        r = get_redis_client()
        rate_key = f"ratelimit:ai:{key_prefix}:{identifier}"
        current = r.incr(rate_key)
        if current == 1:
            r.expire(rate_key, window_seconds)
        return current <= limit
    except Exception:
        return True # Fallback if Redis unavailable

@ai_ns.route("/teacher/session/<int:session_id>/ai/overview")
class TeacherAIOverviewResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Get AI classroom overview, session insights, and stuck student alerts."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        insight = AIService.generate_teacher_insight(session_id)
        if not insight:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        return api_response(data=insight, message="AI session overview retrieved")

@ai_ns.route("/teacher/session/<int:session_id>/students/<int:student_id>/ai")
class TeacherStudentAIResource(Resource):
    @teacher_token_required
    def get(self, session_id, student_id):
        """Get latest AI reviews, code analysis, and progress for a student."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        student = Student.query.filter_by(id=student_id, session_id=session_id).first()
        if not student:
            return api_error("Student not found in this session", error_code="NOT_FOUND", status_code=404)

        reviews = AIReview.query.filter_by(session_id=session_id, student_id=student_id)\
            .order_by(AIReview.created_at.desc()).limit(10).all()

        return api_response(
            data={"reviews": [r.to_dict() for r in reviews]},
            message="Student AI analysis retrieved"
        )

@ai_ns.route("/teacher/session/<int:session_id>/students/<int:student_id>/ai/analyze")
class TeacherStudentAIAnalyzeResource(Resource):
    @teacher_token_required
    def post(self, session_id, student_id):
        """Manually trigger full AI code quality & progress analysis."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        if not check_ai_rate_limit("teacher_analyze", session_id, limit=10):
            return api_error("Teacher AI analysis rate limit hit", error_code="AI_RATE_LIMITED", status_code=429)

        analysis = AIService.analyze_student_code(session_id, student_id)
        progress = AIService.estimate_progress(session_id, student_id)

        return api_response(
            data={"analysis": analysis, "progress": progress},
            message="AI analysis triggered successfully"
        )

@ai_ns.route("/student/session/<int:session_id>/ai/explain-error")
class StudentAIExplainErrorResource(Resource):
    @student_token_required
    def post(self, session_id):
        """Request AI explanation for a compiler/runtime error."""
        session = Session.query.get(session_id)
        if not session or not session.is_active():
            return api_error("Session is ended or expired", error_code="SESSION_INACTIVE", status_code=400)

        claims = getattr(request, "student_claims", {})
        student_id = claims.get("student_id")

        if not check_ai_rate_limit("student_explain", student_id, limit=5):
            return api_error("AI request rate limit exceeded. Please wait.", error_code="AI_RATE_LIMITED", status_code=429)

        data = request.get_json() or {}
        compiler_output = data.get("compiler_output", "")

        explanation = AIService.analyze_compiler_error(session_id, student_id, compiler_output)
        return api_response(data=explanation, message="Compiler error explained")

@ai_ns.route("/student/session/<int:session_id>/ai/hint")
class StudentAIHintResource(Resource):
    @student_token_required
    def post(self, session_id):
        """Request AI hint (respects practice vs problem_solving mode)."""
        session = Session.query.get(session_id)
        if not session or not session.is_active():
            return api_error("Session is ended or expired", error_code="SESSION_INACTIVE", status_code=400)

        claims = getattr(request, "student_claims", {})
        student_id = claims.get("student_id")

        if not check_ai_rate_limit("student_hint", student_id, limit=5):
            return api_error("AI request rate limit exceeded. Please wait.", error_code="AI_RATE_LIMITED", status_code=429)

        hint = AIService.generate_student_hint(session_id, student_id)
        return api_response(data=hint, message="AI hint generated")

@ai_ns.route("/student/session/<int:session_id>/ai/review")
class StudentAIReviewResource(Resource):
    @student_token_required
    def post(self, session_id):
        """Request AI code review (permitted in practice mode only)."""
        session = Session.query.get(session_id)
        if not session or not session.is_active():
            return api_error("Session is ended or expired", error_code="SESSION_INACTIVE", status_code=400)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        if session.mode != "practice":
            return api_error("Full AI code review is only available in practice mode", error_code="FORBIDDEN", status_code=403)

        if not check_ai_rate_limit("student_review", student_id, limit=3):
            return api_error("AI request rate limit exceeded. Please wait.", error_code="AI_RATE_LIMITED", status_code=429)

        review = AIService.analyze_student_code(session_id, student_id)
        return api_response(data=review, message="AI code review generated")
