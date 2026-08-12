import json
from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

class ReportJob(BaseModel):
    """Async Report Generation Job Model."""
    __tablename__ = "report_jobs"

    job_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=True, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True, index=True)
    
    filter_type = db.Column(db.String(30), nullable=False) # today, monthly, custom, session, student
    filter_params_json = db.Column(db.Text, nullable=True)
    report_format = db.Column(db.String(20), default="pdf", nullable=False) # pdf, excel, both
    
    status = db.Column(db.String(20), default="pending", nullable=False, index=True) # pending, processing, ready, failed
    error_message = db.Column(db.Text, nullable=True)
    
    file_path_pdf = db.Column(db.String(255), nullable=True)
    file_path_excel = db.Column(db.String(255), nullable=True)
    
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        meta = {}
        if self.filter_params_json:
            try:
                meta = json.loads(self.filter_params_json)
            except Exception:
                meta = {}
        return {
            "id": self.id,
            "job_id": self.job_id,
            "teacher_id": self.teacher_id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "filter_type": self.filter_type,
            "filter_params": meta,
            "report_format": self.report_format,
            "status": self.status,
            "error_message": self.error_message,
            "has_pdf": bool(self.file_path_pdf),
            "has_excel": bool(self.file_path_excel),
            "downloads": {
                "pdf": f"/api/v1/teacher/reports/download/{self.job_id}?format=pdf" if self.file_path_pdf else None,
                "excel": f"/api/v1/teacher/reports/download/{self.job_id}?format=excel" if self.file_path_excel else None
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
