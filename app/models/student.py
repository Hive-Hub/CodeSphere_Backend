from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

class Student(BaseModel):
    """Student Session Member Model."""
    __tablename__ = "students"
    __table_args__ = (
        db.UniqueConstraint("session_id", "roll_number", name="uq_session_roll_number"),
    )

    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    roll_number = db.Column(db.String(50), nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    section = db.Column(db.String(20), nullable=False)
    student_token = db.Column(db.String(255), nullable=True)
    
    joined_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    last_active = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    status = db.Column(db.String(20), default="online", nullable=False, index=True) # online, offline

    # Relationship
    session = db.relationship("Session", back_populates="students")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "name": self.name,
            "roll_number": self.roll_number,
            "department": self.department,
            "year": self.year,
            "section": self.section,
            "status": self.status,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None
        }
