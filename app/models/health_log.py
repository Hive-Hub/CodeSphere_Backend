from app.extensions import db
from app.models.base import BaseModel

class HealthLog(BaseModel):
    """Model used for logging dependency health checks and database CRUD testing."""
    __tablename__ = "health_logs"

    service_name = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "service_name": self.service_name,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
