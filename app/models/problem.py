from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

class Problem(BaseModel):
    """Problem Model for problem_solving Session Mode."""
    __tablename__ = "problems"

    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    constraints = db.Column(db.Text, nullable=True)
    input_format = db.Column(db.Text, nullable=True)
    output_format = db.Column(db.Text, nullable=True)
    sample_input = db.Column(db.Text, nullable=True)
    sample_output = db.Column(db.Text, nullable=True)
    reference_solution = db.Column(db.Text, nullable=True) # RESTRICTED - Teacher ONLY

    # Relationship
    session = db.relationship("Session", back_populates="problems")

    def to_dict(self, include_reference=False):
        """Convert problem object to dictionary. Excludes reference_solution by default."""
        data = {
            "id": self.id,
            "session_id": self.session_id,
            "title": self.title,
            "description": self.description,
            "constraints": self.constraints or "",
            "input_format": self.input_format or "",
            "output_format": self.output_format or "",
            "sample_input": self.sample_input or "",
            "sample_output": self.sample_output or "",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if include_reference:
            data["reference_solution"] = self.reference_solution or ""
        return data
