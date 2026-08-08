from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

class CodeSnapshot(BaseModel):
    """Persisted periodic code snapshot model."""
    __tablename__ = "code_snapshots"

    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    language = db.Column(db.String(20), nullable=False)
    code = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)

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
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
