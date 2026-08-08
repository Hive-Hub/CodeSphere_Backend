from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

class CodeExecution(BaseModel):
    """Temporary execution audit log model."""
    __tablename__ = "code_executions"

    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=True, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True, index=True)
    language = db.Column(db.String(20), nullable=False)
    code = db.Column(db.Text, nullable=False)
    stdin = db.Column(db.Text, nullable=True)
    output = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False) # success, failed, timeout, error
    exit_code = db.Column(db.Integer, default=0)
    execution_time = db.Column(db.String(50), nullable=True)
    memory = db.Column(db.String(50), nullable=True)

    # Relationships
    session = db.relationship("Session")
    student = db.relationship("Student")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "language": self.language,
            "code": self.code,
            "stdin": self.stdin or "",
            "output": self.output or "",
            "error": self.error or "",
            "status": self.status,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time or "0.0s",
            "memory": self.memory or "0KB",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
