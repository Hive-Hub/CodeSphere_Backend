from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.base import BaseModel

class Session(BaseModel):
    """Temporary Coding Session Model."""
    __tablename__ = "sessions"

    session_code = db.Column(db.String(6), nullable=False, index=True)
    teacher_name = db.Column(db.String(100), nullable=False)
    teacher_email = db.Column(db.String(120), nullable=False)
    college = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    language = db.Column(db.String(20), nullable=False)  # python, c, java
    mode = db.Column(db.String(30), nullable=False)      # practice, problem_solving
    status = db.Column(db.String(20), default="active", nullable=False, index=True) # active, ended, expired
    teacher_token = db.Column(db.String(255), nullable=True)
    
    expires_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24),
        nullable=False
    )
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    students = db.relationship("Student", back_populates="session", cascade="all, delete-orphan", lazy="select")
    problems = db.relationship("Problem", back_populates="session", cascade="all, delete-orphan", lazy="select")

    def is_active(self):
        """Check if session is currently active and not expired."""
        if self.status != "active":
            return False
        now = datetime.now(timezone.utc)
        if self.expires_at and self.expires_at.tzinfo is None:
            now = datetime.now()
        if now >= self.expires_at:
            self.status = "expired"
            self.ended_at = now
            db.session.commit()
            return False
        return True

    def to_dict(self, include_private=False):
        """Convert session object to dictionary."""
        data = {
            "id": self.id,
            "session_code": self.session_code,
            "title": self.title,
            "subject": self.subject,
            "college": self.college,
            "department": self.department,
            "language": self.language,
            "mode": self.mode,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
        if include_private:
            data["teacher_name"] = self.teacher_name
            data["teacher_email"] = self.teacher_email
        return data
