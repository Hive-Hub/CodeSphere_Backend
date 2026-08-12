from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

class Teacher(BaseModel):
    """Persistent Teacher Profile Model."""
    __tablename__ = "teachers"

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    college = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    teacher_token = db.Column(db.String(512), nullable=False, unique=True, index=True)

    # Relationships
    sessions = db.relationship("Session", back_populates="teacher", cascade="all, delete-orphan", lazy="select")

    def to_dict(self, include_token=False):
        data = {
            "teacher_id": self.id,
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "college": self.college,
            "department": self.department,
            "subject": self.subject,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_token:
            data["teacher_token"] = self.teacher_token
        return data
