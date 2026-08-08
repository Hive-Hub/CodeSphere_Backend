from datetime import datetime, timezone
from app.extensions import db

class TimestampMixin:
    """Mixin for adding created_at and updated_at timestamps."""
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class BaseModel(db.Model, TimestampMixin):
    """Abstract base model with auto-increment integer ID and helper CRUD methods."""
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    def save(self):
        """Save model instance to database."""
        db.session.add(self)
        db.session.commit()
        return self

    def delete(self):
        """Delete model instance from database."""
        db.session.delete(self)
        db.session.commit()
