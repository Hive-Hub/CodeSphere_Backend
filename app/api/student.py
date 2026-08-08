from datetime import datetime, timezone
from flask import request
from flask_restx import Namespace, Resource, fields
from app.extensions import db, limiter
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.code_snapshot import CodeSnapshot
from app.models.code_execution import CodeExecution
from app.schemas.session_schema import StudentJoinSchema
from app.utils.auth import generate_student_token, student_token_required
from app.services.presence_service import set_student_online
from app.services.code_service import (
    get_student_live_code, set_student_live_code, save_code_snapshot, record_activity_event, MAX_CODE_SIZE_BYTES
)
from app.services.compiler_service import OnlineCompilerService, MAX_INPUT_SIZE_BYTES
from app.utils.response import api_response, api_error

student_ns = Namespace("student", description="Student Session & Real-Time Workspace Operations")

student_join_model = student_ns.model("StudentJoin", {
    "session_code": fields.String(required=True, example="483921"),
    "name": fields.String(required=True, example="John Doe"),
    "roll_number": fields.String(required=True, example="CS2026_042"),
    "department": fields.String(required=True, example="Computer Science"),
    "year": fields.String(required=True, example="3rd Year"),
    "section": fields.String(required=True, example="A")
})

code_save_model = student_ns.model("CodeSaveRequest", {
    "code": fields.String(required=True, example="print('Hello World')"),
    "language": fields.String(required=True, example="python")
})

code_run_model = student_ns.model("CodeRunRequest", {
    "language": fields.String(required=True, example="python"),
    "code": fields.String(required=True, example="print('Hello World')"),
    "stdin": fields.String(required=False, example="")
})

@student_ns.route("/session/join")
class StudentJoinResource(Resource):
    @limiter.limit("20 per minute")
    @student_ns.expect(student_join_model)
    def post(self):
        """Join an active coding session using 6-digit session code."""
        data = request.get_json() or {}
        errors = StudentJoinSchema().validate(data)
        if errors:
            return api_error("Validation failed", error_code="VALIDATION_ERROR", status_code=400, details=errors)

        session_code = data["session_code"].strip()
        session = Session.query.filter_by(session_code=session_code).first()
        
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        if not session.is_active():
            msg = "Session is ended" if session.status == "ended" else "Session has expired"
            return api_error(f"Cannot join: {msg}", error_code="SESSION_INACTIVE", status_code=400)

        existing_student = Student.query.filter_by(
            session_id=session.id,
            roll_number=data["roll_number"].strip()
        ).first()
        
        if existing_student:
            return api_error(
                f"Student with roll number '{data['roll_number']}' has already joined this session",
                error_code="DUPLICATE_ROLL_NUMBER",
                status_code=400
            )

        student = Student(
            session_id=session.id,
            name=data["name"].strip(),
            roll_number=data["roll_number"].strip(),
            department=data["department"].strip(),
            year=data["year"].strip(),
            section=data["section"].strip(),
            status="online"
        )
        student.save()

        student_token = generate_student_token(student.id, session.id)
        student.student_token = student_token
        db.session.commit()

        set_student_online(session.id, student.id)

        return api_response(
            data={
                "student_token": student_token,
                "student": student.to_dict(),
                "session": {
                    "session_id": session.id,
                    "session_code": session.session_code,
                    "mode": session.mode,
                    "language": session.language,
                    "title": session.title,
                    "college": session.college,
                    "department": session.department,
                    "subject": session.subject
                }
            },
            message="Joined session successfully",
            status_code=200
        )

@student_ns.route("/session/<int:session_id>")
class StudentSessionDetailResource(Resource):
    @student_token_required
    def get(self, session_id):
        """Get student session details and problem/editor configuration."""
        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        session_info = {
            "session_id": session.id,
            "session_code": session.session_code,
            "title": session.title,
            "subject": session.subject,
            "college": session.college,
            "department": session.department,
            "mode": session.mode,
            "language": session.language,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None
        }

        response_data = {"session": session_info}

        if session.mode == "practice":
            response_data["editor_config"] = {
                "language": session.language,
                "mode": "practice",
                "allow_execution": True,
                "starter_code": ""
            }
        elif session.mode == "problem_solving":
            problem = Problem.query.filter_by(session_id=session.id).order_by(Problem.created_at.desc()).first()
            if problem:
                response_data["problem"] = problem.to_dict(include_reference=False)
            else:
                response_data["problem"] = None

        return api_response(data=response_data, message="Student session info retrieved")

@student_ns.route("/session/<int:session_id>/workspace")
class StudentWorkspaceResource(Resource):
    @student_token_required
    def get(self, session_id):
        """Get student workspace details for active session."""
        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        data = {
            "session_id": session.id,
            "mode": session.mode,
            "language": session.language
        }

        if session.mode == "practice":
            data["editor_config"] = {
                "language": session.language,
                "mode": "practice",
                "allow_execution": True
            }
        elif session.mode == "problem_solving":
            problem = Problem.query.filter_by(session_id=session.id).order_by(Problem.created_at.desc()).first()
            if problem:
                data["problem"] = problem.to_dict(include_reference=False)
            else:
                data["problem"] = None

        return api_response(data=data, message="Workspace configuration retrieved")

@student_ns.route("/session/<int:session_id>/code/save")
class StudentCodeSaveResource(Resource):
    @student_token_required
    @student_ns.expect(code_save_model)
    def post(self, session_id):
        """Explicitly save a student code snapshot."""
        claims = getattr(request, "student_claims", {})
        student_id = claims.get("student_id")
        
        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        if not session.is_active():
            return api_error("Session is inactive or ended", error_code="SESSION_INACTIVE", status_code=400)

        data = request.get_json() or {}
        code = data.get("code", "")
        language = data.get("language", session.language).lower()

        if len(code.encode("utf-8")) > MAX_CODE_SIZE_BYTES:
            return api_error("Code payload exceeds 100KB size limit", error_code="PAYLOAD_TOO_LARGE", status_code=400)

        set_student_live_code(student_id, session_id, code)
        snapshot = save_code_snapshot(session.id, student_id, language, code)

        return api_response(
            data={
                "version": snapshot.version,
                "saved_at": snapshot.created_at.isoformat()
            },
            message="Code saved successfully"
        )

@student_ns.route("/session/<int:session_id>/code")
class StudentCurrentCodeResource(Resource):
    @student_token_required
    def get(self, session_id):
        """Get student's latest code."""
        claims = getattr(request, "student_claims", {})
        student_id = claims.get("student_id")

        code = get_student_live_code(student_id)
        latest_snapshot = CodeSnapshot.query.filter_by(student_id=student_id).order_by(CodeSnapshot.version.desc()).first()

        return api_response(
            data={
                "code": code,
                "version": latest_snapshot.version if latest_snapshot else 0,
                "updated_at": latest_snapshot.created_at.isoformat() if latest_snapshot else None
            },
            message="Student code retrieved"
        )

@student_ns.route("/session/<int:session_id>/code/run")
class StudentCodeRunResource(Resource):
    @student_token_required
    @student_ns.expect(code_run_model)
    def post(self, session_id):
        """Run student code using OnlineCompiler.io REST API."""
        claims = getattr(request, "student_claims", {})
        student_id = claims.get("student_id")

        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        if not session.is_active():
            msg = "Session is ended" if session.status == "ended" else "Session has expired"
            return api_error(f"Cannot run code: {msg}", error_code="SESSION_INACTIVE", status_code=400)

        data = request.get_json() or {}
        language = (data.get("language") or session.language).lower().strip()
        code = data.get("code", "")
        stdin = data.get("stdin", "")

        # Validation: language must match session language
        if language != session.language.lower():
            return api_error(
                f"Language '{language}' does not match session language '{session.language}'",
                error_code="LANGUAGE_MISMATCH",
                status_code=400
            )

        # Size validations (100 KB max limit)
        if len(code.encode("utf-8")) > MAX_CODE_SIZE_BYTES:
            return api_error("Code payload exceeds 100KB limit", error_code="CODE_TOO_LARGE", status_code=413)
        if len(stdin.encode("utf-8")) > MAX_INPUT_SIZE_BYTES:
            return api_error("Input payload exceeds 100KB limit", error_code="INPUT_TOO_LARGE", status_code=413)

        # Execute code via OnlineCompilerService
        result = OnlineCompilerService.execute_code(language, code, stdin)

        # Log temporary CodeExecution audit record
        execution_log = CodeExecution(
            session_id=session.id,
            student_id=student_id,
            language=language,
            code=code,
            stdin=stdin,
            output=result.get("output", ""),
            error=result.get("error", ""),
            status=result.get("status", "unknown"),
            exit_code=result.get("exit_code", 0),
            execution_time=result.get("execution_time", "0.0s"),
            memory=result.get("memory", "0KB")
        )
        execution_log.save()

        # Record activity event
        record_activity_event(session.id, student_id, "run_code", {"language": language})

        if not result.get("success"):
            return api_error(
                message=result.get("error", "Code execution failed"),
                error_code=result.get("error_code", "EXECUTION_ERROR"),
                status_code=result.get("status_code", 400),
                details=result
            )

        return api_response(data=result, message="Code executed successfully")
