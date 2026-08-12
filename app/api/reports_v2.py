import os
import io
from flask import request, send_file
from flask_restx import Namespace, Resource, fields
from app.extensions import limiter, db
from app.models.session import Session
from app.models.student import Student
from app.models.report_job import ReportJob
from app.utils.auth import teacher_token_required, verify_teacher_session_access
from app.services.report_v2_service import ReportV2Service
from app.tasks.report_tasks import generate_report_job_async
from app.utils.response import api_response, api_error

reports_v2_ns = Namespace("teacher/reports", description="Teacher Report V2 Generation & Downloads")

report_generate_model = reports_v2_ns.model("ReportGenerateRequest", {
    "filter_type": fields.String(required=True, example="today", description="today | monthly | custom | session | student"),
    "month": fields.String(required=False, example="2026-08"),
    "start_date": fields.String(required=False, example="2026-08-01"),
    "end_date": fields.String(required=False, example="2026-08-12"),
    "session_id": fields.Integer(required=False, example=1),
    "student_id": fields.Integer(required=False, example=1),
    "format": fields.String(required=False, example="pdf", description="pdf | excel | both")
})

@reports_v2_ns.route("/generate")
class ReportGenerateResource(Resource):
    @teacher_token_required
    @reports_v2_ns.expect(report_generate_model)
    def post(self):
        """Generate report for Today, Monthly, Custom Date Range, Session, or Student."""
        claims = getattr(request, "teacher_claims", {})
        teacher_id = claims.get("teacher_id")
        email = claims.get("email")

        data = request.get_json() or {}
        filter_type = (data.get("filter_type") or "today").lower().strip()
        report_format = (data.get("format") or "pdf").lower().strip()

        if filter_type not in ["today", "monthly", "custom", "session", "student"]:
            return api_error("Invalid filter_type. Supported: today, monthly, custom, session, student", error_code="VALIDATION_ERROR", status_code=400)

        # Ownership / Security Validation
        session_id = data.get("session_id")
        if filter_type == "session" and session_id:
            session = Session.query.get(session_id)
            if not session:
                return api_error("Session not found", error_code="NOT_FOUND", status_code=404)
            if not verify_teacher_session_access(session, claims):
                return api_error("Unauthorized report access for session", error_code="FORBIDDEN", status_code=403)

        student_id = data.get("student_id")
        if filter_type == "student" and student_id:
            student = Student.query.get(student_id)
            if not student:
                return api_error("Student not found", error_code="NOT_FOUND", status_code=404)

        # Date validation for custom range
        if filter_type == "custom":
            start_date = data.get("start_date")
            end_date = data.get("end_date")
            if not start_date or not end_date:
                return api_error("start_date and end_date required for custom report", error_code="VALIDATION_ERROR", status_code=400)
            if start_date > end_date:
                return api_error("start_date cannot be after end_date", error_code="VALIDATION_ERROR", status_code=400)

        filter_params = {
            "session_id": session_id,
            "student_id": student_id,
            "month": data.get("month"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date")
        }

        # Create ReportJob
        job = ReportV2Service.create_report_job(filter_type, filter_params, teacher_id=teacher_id, report_format=report_format)

        # Execute report generation (asynchronously or synchronous fallback)
        try:
            generate_report_job_async.delay(job.job_id)
        except Exception:
            ReportV2Service.execute_report_job(job.job_id)

        # Refresh job
        job = ReportJob.query.filter_by(job_id=job.job_id).first()

        return api_response(
            data=job.to_dict(),
            message="Report generation initiated",
            status_code=202
        )

@reports_v2_ns.route("/job/<string:job_id>/status")
class ReportJobStatusResource(Resource):
    @teacher_token_required
    def get(self, job_id):
        """Get report generation job status and download links."""
        job = ReportJob.query.filter_by(job_id=job_id).first()
        if not job:
            return api_error("Report job not found", error_code="NOT_FOUND", status_code=404)

        return api_response(data=job.to_dict(), message="Report job status retrieved")

@reports_v2_ns.route("/download/<string:job_id>")
class ReportJobDownloadResource(Resource):
    @teacher_token_required
    def get(self, job_id):
        """Download generated PDF or Excel report for a job."""
        fmt = (request.args.get("format") or "pdf").lower()
        job = ReportJob.query.filter_by(job_id=job_id).first()
        if not job:
            return api_error("Report job not found", error_code="NOT_FOUND", status_code=404)

        if job.status != "ready":
            return api_error(f"Report is not ready (status: {job.status})", error_code="REPORT_NOT_READY", status_code=400)

        file_path = job.file_path_excel if fmt == "excel" else job.file_path_pdf
        if not file_path or not os.path.exists(file_path):
            # Fallback inline generation if file not found
            ReportV2Service.execute_report_job(job_id)
            job = ReportJob.query.filter_by(job_id=job_id).first()
            file_path = job.file_path_excel if fmt == "excel" else job.file_path_pdf

        if not file_path or not os.path.exists(file_path):
            return api_error("Report file unavailable", error_code="NOT_FOUND", status_code=404)

        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "excel" else "application/pdf"
        filename = f"CodeSphere_Report_{job.filter_type}_{job_id[:8]}.{'xlsx' if fmt == 'excel' else 'pdf'}"

        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )

@reports_v2_ns.route("/history")
class ReportHistoryResource(Resource):
    @teacher_token_required
    def get(self):
        """Get history of generated report jobs for teacher."""
        claims = getattr(request, "teacher_claims", {})
        teacher_id = claims.get("teacher_id")

        query = ReportJob.query
        if teacher_id:
            query = query.filter(ReportJob.teacher_id == teacher_id)

        jobs = query.order_by(ReportJob.created_at.desc()).limit(50).all()
        return api_response(
            data={"reports": [j.to_dict() for j in jobs]},
            message="Report history retrieved"
        )
