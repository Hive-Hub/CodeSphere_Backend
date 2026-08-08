import json
from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel

ANALYSIS_TYPES = [
    "progress",
    "code_review",
    "error_analysis",
    "hint",
    "session_summary"
]

class AIReview(BaseModel):
    """AI analysis, code review, and hint log model."""
    __tablename__ = "ai_reviews"

    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True, index=True)
    problem_id = db.Column(db.Integer, db.ForeignKey("problems.id"), nullable=True, index=True)
    code_snapshot_id = db.Column(db.Integer, db.ForeignKey("code_snapshots.id"), nullable=True, index=True)

    analysis_type = db.Column(db.String(50), nullable=False, index=True) # progress, code_review, error_analysis, hint, session_summary

    progress = db.Column(db.Integer, nullable=True) # 0-100 or null if low confidence
    code_quality = db.Column(db.Integer, nullable=True) # 0-100 overall score
    confidence = db.Column(db.Integer, nullable=True) # 0-100 confidence level

    summary = db.Column(db.Text, nullable=True)
    logic_analysis_json = db.Column(db.Text, nullable=True)
    complexity_analysis_json = db.Column(db.Text, nullable=True)
    bug_analysis_json = db.Column(db.Text, nullable=True)
    suggestions_json = db.Column(db.Text, nullable=True)

    # Relationships
    session = db.relationship("Session")
    student = db.relationship("Student")

    def to_dict(self):
        def parse_json(val):
            if not val:
                return None
            try:
                return json.loads(val)
            except Exception:
                return val

        return {
            "id": self.id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "problem_id": self.problem_id,
            "code_snapshot_id": self.code_snapshot_id,
            "analysis_type": self.analysis_type,
            "progress": self.progress,
            "code_quality": self.code_quality,
            "confidence": self.confidence,
            "summary": self.summary or "",
            "logic_analysis": parse_json(self.logic_analysis_json),
            "complexity_analysis": parse_json(self.complexity_analysis_json),
            "bug_analysis": parse_json(self.bug_analysis_json),
            "suggestions": parse_json(self.suggestions_json),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
