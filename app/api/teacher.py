from datetime import datetime, timezone
from flask import request, send_file, Response
from flask_restx import Namespace, Resource, fields
from app.extensions import db, socketio, limiter
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.code_snapshot import CodeSnapshot
from app.schemas.session_schema import TeacherSessionCreateSchema, ProblemCreateSchema
from app.utils.auth import generate_session_code, generate_teacher_token, teacher_token_required
from app.services.presence_service import get_online_count
from app.services.code_service import get_student_live_code, get_student_live_cursor
from app.services.report_service import ReportService
from app.services.excel_report_service import ExcelReportService
from app.services.cleanup_service import CleanupService
from app.utils.response import api_response, api_error

teacher_ns = Namespace("teacher", description="Teacher Session Operations")

session_create_model = teacher_ns.model("TeacherSessionCreate", {
    "teacher_name": fields.String(required=True, example="Dr. Smith"),
    "teacher_email": fields.String(required=True, example="smith@university.edu"),
    "college": fields.String(required=True, example="Engineering College"),
    "department": fields.String(required=True, example="Computer Science"),
    "subject": fields.String(required=True, example="Data Structures"),
    "title": fields.String(required=True, example="Python Basics Lab 1"),
    "language": fields.String(required=True, example="python"),
    "mode": fields.String(required=True, example="practice")
})

problem_create_model = teacher_ns.model("ProblemCreate", {
    "title": fields.String(required=True, example="Two Sum"),
    "description": fields.String(required=True, example="Find indices of two numbers that add up to target."),
    "constraints": fields.String(required=False, example="1 <= N <= 10^5"),
    "input_format": fields.String(required=False, example="Array of N integers"),
    "output_format": fields.String(required=False, example="Indices array"),
    "sample_input": fields.String(required=False, example="[2, 7, 11, 15]\n9"),
    "sample_output": fields.String(required=False, example="[0, 1]"),
    "reference_solution": fields.String(required=False, example="def two_sum(nums, target): ...")
})

@teacher_ns.route("/session/create")
class TeacherSessionCreateResource(Resource):
    @limiter.limit("10 per minute")
    @teacher_ns.expect(session_create_model)
    def post(self):
        """Create a new temporary coding session."""
        data = request.get_json() or {}
        errors = TeacherSessionCreateSchema().validate(data)
        if errors:
            return api_error("Validation failed", error_code="VALIDATION_ERROR", status_code=400, details=errors)
        
        session_code = generate_session_code()
        while Session.query.filter_by(session_code=session_code, status="active").first():
            session_code = generate_session_code()

        session = Session(
            session_code=session_code,
            teacher_name=data["teacher_name"],
            teacher_email=data["teacher_email"],
            college=data["college"],
            department=data["department"],
            subject=data["subject"],
            title=data["title"],
            language=data["language"].lower(),
            mode=data["mode"].lower(),
            status="active"
        )
        session.save()
        
        teacher_token = generate_teacher_token(session.id, session_code)
        session.teacher_token = teacher_token
        db.session.commit()

        return api_response(
            data={
                "teacher_token": teacher_token,
                "session": session.to_dict(include_private=True)
            },
            message="Coding session created successfully",
            status_code=201
        )

from app.services.dashboard_service import DashboardService

@teacher_ns.route("/session/<int:session_id>")
class TeacherSessionDetailResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Get teacher session dashboard details."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)
        
        session.is_active()
        student_count = Student.query.filter_by(session_id=session.id).count()
        online_count = get_online_count(session.id)
        
        now = datetime.now(timezone.utc)
        exp = session.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        remaining_seconds = max(0, int((exp - now).total_seconds())) if session.status == "active" else 0

        return api_response(
            data={
                "session": session.to_dict(include_private=True),
                "student_count": student_count,
                "online_count": online_count,
                "status": session.status,
                "remaining_seconds": remaining_seconds,
                "mode": session.mode,
                "language": session.language
            },
            message="Teacher session details retrieved"
        )

@teacher_ns.route("/session/<int:session_id>/dashboard")
class TeacherSessionDashboardResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Get complete aggregated live dashboard payload."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session dashboard", error_code="FORBIDDEN", status_code=403)

        dashboard_data = DashboardService.get_teacher_dashboard(session_id)
        if not dashboard_data:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        return api_response(
            data=dashboard_data,
            message="Teacher dashboard data retrieved"
        )

@teacher_ns.route("/session/<int:session_id>/students")
class TeacherSessionStudentsResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Get list of joined students for a session."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        students = Student.query.filter_by(session_id=session.id).order_by(Student.joined_at.asc()).all()
        return api_response(
            data={"students": [s.to_dict() for s in students], "total": len(students)},
            message="Student list retrieved"
        )

@teacher_ns.route("/session/<int:session_id>/students/<int:student_id>")
class TeacherStudentDetailResource(Resource):
    @teacher_token_required
    def get(self, session_id, student_id):
        """Get comprehensive single student dashboard details."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        detail_data = DashboardService.get_student_dashboard_details(session_id, student_id)
        if not detail_data:
            return api_error("Student or session not found", error_code="NOT_FOUND", status_code=404)

        return api_response(
            data=detail_data,
            message="Student detail retrieved"
        )

@teacher_ns.route("/session/<int:session_id>/students/<int:student_id>/activity")
class TeacherStudentActivityResource(Resource):
    @teacher_token_required
    def get(self, session_id, student_id):
        """Get paginated activity event history for a student."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        student = Student.query.filter_by(id=student_id, session_id=session_id).first()
        if not student:
            return api_error("Student not found in this session", error_code="NOT_FOUND", status_code=404)

        try:
            page = int(request.args.get("page", 1))
            limit = int(request.args.get("limit", 20))
        except ValueError:
            return api_error("Invalid page or limit query parameters", error_code="BAD_REQUEST", status_code=400)

        history = DashboardService.get_student_activity_history(session_id, student_id, page=page, limit=limit)
        return api_response(
            data=history,
            message="Student activity history retrieved"
        )

@teacher_ns.route("/session/<int:session_id>/students/<int:student_id>/executions")
class TeacherStudentExecutionsResource(Resource):
    @teacher_token_required
    def get(self, session_id, student_id):
        """Get paginated execution history for a student."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        student = Student.query.filter_by(id=student_id, session_id=session_id).first()
        if not student:
            return api_error("Student not found in this session", error_code="NOT_FOUND", status_code=404)

        try:
            page = int(request.args.get("page", 1))
            limit = int(request.args.get("limit", 20))
        except ValueError:
            return api_error("Invalid page or limit query parameters", error_code="BAD_REQUEST", status_code=400)

        history = DashboardService.get_student_execution_history(session_id, student_id, page=page, limit=limit)
        return api_response(
            data=history,
            message="Student execution history retrieved"
        )

@teacher_ns.route("/session/<int:session_id>/analytics")
class TeacherSessionAnalyticsResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Get session-level real metrics and analytics."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        analytics_data = DashboardService.get_session_analytics(session_id)
        if not analytics_data:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        return api_response(
            data=analytics_data,
            message="Session analytics retrieved"
        )

@teacher_ns.route("/session/<int:session_id>/students/<int:student_id>/code")
class TeacherStudentCodeResource(Resource):
    @teacher_token_required
    def get(self, session_id, student_id):
        """Retrieve live or latest saved code of a specific student."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        student = Student.query.filter_by(id=student_id, session_id=session.id).first()
        if not student:
            return api_error("Student not found in this session", error_code="NOT_FOUND", status_code=404)

        code = get_student_live_code(student_id)
        cursor = get_student_live_cursor(student_id)
        latest_snapshot = CodeSnapshot.query.filter_by(student_id=student_id).order_by(CodeSnapshot.version.desc()).first()

        return api_response(
            data={
                "student": student.to_dict(),
                "language": session.language,
                "code": code,
                "cursor": cursor,
                "version": latest_snapshot.version if latest_snapshot else 0,
                "updated_at": latest_snapshot.created_at.isoformat() if latest_snapshot else None
            },
            message="Student code retrieved successfully"
        )

@teacher_ns.route("/session/<int:session_id>/problem")
class TeacherProblemCreateResource(Resource):
    @teacher_token_required
    @teacher_ns.expect(problem_create_model)
    def post(self, session_id):
        """Create problem for a problem_solving session."""
        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        if not session.is_active():
            return api_error("Cannot create problem for inactive or ended session", error_code="SESSION_INACTIVE", status_code=400)

        if session.mode != "problem_solving":
            return api_error("Problem creation is only permitted in problem_solving mode", error_code="INVALID_MODE", status_code=400)

        data = request.get_json() or {}
        errors = ProblemCreateSchema().validate(data)
        if errors:
            return api_error("Validation failed", error_code="VALIDATION_ERROR", status_code=400, details=errors)

        problem = Problem(
            session_id=session.id,
            title=data["title"],
            description=data["description"],
            constraints=data.get("constraints", ""),
            input_format=data.get("input_format", ""),
            output_format=data.get("output_format", ""),
            sample_input=data.get("sample_input", ""),
            sample_output=data.get("sample_output", ""),
            reference_solution=data.get("reference_solution", "")
        )
        problem.save()

        return api_response(
            data={"problem": problem.to_dict(include_reference=True)},
            message="Problem created successfully",
            status_code=201
        )

@teacher_ns.route("/session/<int:session_id>/end")
class TeacherEndSessionResource(Resource):
    @teacher_token_required
    def post(self, session_id):
        """End session, freeze activity, generate report, and return PDF or status."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        if session.status not in ["ended", "expired"]:
            now = datetime.now(timezone.utc)
            session.status = "ended"
            session.ended_at = now
            db.session.commit()

            room_name = f"session:{session.id}"
            socketio.emit("session_ended", {
                "event": "session_ended",
                "session_id": session.id,
                "session_code": session.session_code,
                "timestamp": now.isoformat(),
                "reason": "teacher_ended"
            }, to=room_name)

        # Generate PDF and Excel reports
        try:
            pdf_bytes, pdf_filename = ReportService.generate_session_report(session_id)
            excel_bytes, excel_filename = ExcelReportService.generate_excel_report(session_id)

            if request.headers.get("Accept") == "application/pdf" or request.args.get("download") == "pdf":
                import io
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name=pdf_filename
                )

            if request.headers.get("Accept") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or request.args.get("download") == "excel":
                import io
                return send_file(
                    io.BytesIO(excel_bytes),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    as_attachment=True,
                    download_name=excel_filename
                )

            return api_response(
                data={
                    "session": session.to_dict(include_private=True),
                    "report_status": "ready",
                    "downloads": {
                        "pdf": f"/api/v1/teacher/session/{session_id}/report/pdf",
                        "excel": f"/api/v1/teacher/session/{session_id}/report/excel"
                    }
                },
                message="Session ended and reports generated successfully"
            )
        except Exception as e:
            return api_error(f"Failed to generate session reports: {str(e)}", error_code="INTERNAL_SERVER_ERROR", status_code=500)

@teacher_ns.route("/session/<int:session_id>/report/status")
class TeacherReportStatusResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Get report generation status for PDF and Excel reports."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        status_info = ReportService.get_report_status(session_id)
        return api_response(data=status_info, message="Report status retrieved")

@teacher_ns.route("/session/<int:session_id>/report/summary")
class TeacherReportSummaryResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Get report summary payload contract for frontend UI."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        summary_data = ReportService.generate_report_summary(session_id)
        if not summary_data:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        return api_response(data=summary_data, message="Report summary retrieved")

@teacher_ns.route("/session/<int:session_id>/report/pdf")
@teacher_ns.route("/session/<int:session_id>/report/download")
class TeacherReportPDFResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Download generated session PDF report directly."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        try:
            import io
            pdf_bytes, filename = ReportService.get_cached_report(session_id)
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            return api_error(f"PDF download failed: {str(e)}", error_code="NOT_FOUND", status_code=404)

@teacher_ns.route("/session/<int:session_id>/report/excel")
class TeacherReportExcelResource(Resource):
    @teacher_token_required
    def get(self, session_id):
        """Download generated session Excel report (.xlsx) directly."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        try:
            import io
            excel_bytes, filename = ExcelReportService.get_cached_excel_report(session_id)
            return send_file(
                io.BytesIO(excel_bytes),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            return api_error(f"Excel download failed: {str(e)}", error_code="NOT_FOUND", status_code=404)

@teacher_ns.route("/session/<int:session_id>/report/retry")
class TeacherReportRetryResource(Resource):
    @teacher_token_required
    def post(self, session_id):
        """Retry report generation for ended/expired session if previous generation failed."""
        claims = getattr(request, "teacher_claims", {})
        if claims.get("session_id") != session_id:
            return api_error("Unauthorized access to this session", error_code="FORBIDDEN", status_code=403)

        session = Session.query.get(session_id)
        if not session:
            return api_error("Session not found", error_code="NOT_FOUND", status_code=404)

        try:
            ReportService.generate_session_report(session_id)
            ExcelReportService.generate_excel_report(session_id)
            return api_response(
                data={
                    "session_id": session_id,
                    "report_status": "ready",
                    "downloads": {
                        "pdf": f"/api/v1/teacher/session/{session_id}/report/pdf",
                        "excel": f"/api/v1/teacher/session/{session_id}/report/excel"
                    }
                },
                message="Reports regenerated successfully"
            )
        except Exception as e:
            return api_error(f"Report retry failed: {str(e)}", error_code="INTERNAL_SERVER_ERROR", status_code=500)
