from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

class SessionStudent(BaseModel):
    """Student Session Participation Model (V2)."""
    __tablename__ = "session_students"
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_session_student_participation"),
    )

    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    
    joined_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    left_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    progress = db.Column(db.Integer, default=0, nullable=False) # 0 to 100
    score = db.Column(db.Float, default=0.0, nullable=False)
    ai_score = db.Column(db.Float, default=0.0, nullable=False)
    code_quality = db.Column(db.Float, default=0.0, nullable=False)
    completion_status = db.Column(db.String(30), default="in_progress", nullable=False) # in_progress, completed, abandoned
    status = db.Column(db.String(20), default="online", nullable=False, index=True) # online, offline
    student_token = db.Column(db.String(512), nullable=True)

    # Relationships
    session = db.relationship("Session", backref=db.backref("session_participations", cascade="all, delete-orphan"))
    student = db.relationship("Student", backref=db.backref("session_participations", cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "roll_number": self.student.roll_number if self.student else None,
            "department": self.student.department if self.student else None,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "left_at": self.left_at.isoformat() if self.left_at else None,
            "progress": self.progress,
            "score": self.score,
            "ai_score": self.ai_score,
            "code_quality": self.code_quality,
            "completion_status": self.completion_status,
            "status": self.status
        }
