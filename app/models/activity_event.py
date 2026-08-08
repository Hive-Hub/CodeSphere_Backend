import json
from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

SUPPORTED_EVENT_TYPES = [
    "copy_attempt",
    "paste_attempt",
    "cut_attempt",
    "tab_blur",
    "tab_focus",
    "typing_start",
    "typing_stop",
    "run_code",
    "submit_code"
]

class ActivityEvent(BaseModel):
    """Student editor activity event model."""
    __tablename__ = "activity_events"

    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    metadata_json = db.Column(db.Text, nullable=True)

    # Relationships
    session = db.relationship("Session")
    student = db.relationship("Student")

    def to_dict(self):
        meta = {}
        if self.metadata_json:
            try:
                meta = json.loads(self.metadata_json)
            except Exception:
                meta = {"raw": self.metadata_json}
        return {
            "id": self.id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "event_type": self.event_type,
            "metadata": meta,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
