from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

class ProgressOutputSchema(BaseModel):
    progress: Optional[int] = Field(None, ge=0, le=100)
    confidence: int = Field(50, ge=0, le=100)
    stage: str = Field("In Progress")
    completed_components: List[str] = Field(default_factory=list)
    remaining_components: List[str] = Field(default_factory=list)
    reasoning_summary: str = Field("")

    @model_validator(mode="after")
    def validate_confidence_progress(self):
        if self.confidence < 50:
            self.progress = None
        return self

class CodeQualityOutputSchema(BaseModel):
    overall: int = Field(50, ge=0, le=100)
    logic: int = Field(5, ge=0, le=10)
    readability: int = Field(5, ge=0, le=10)
    structure: int = Field(5, ge=0, le=10)
    efficiency: int = Field(5, ge=0, le=10)
    error_handling: int = Field(5, ge=0, le=10)
    summary: str = Field("")
    suggestions: List[str] = Field(default_factory=list)

class ErrorAnalysisOutputSchema(BaseModel):
    error_type: str = Field("Error")
    explanation: str = Field("")
    likely_cause: str = Field("")
    concept_hint: str = Field("")

class HintOutputSchema(BaseModel):
    hint: str = Field("")
    hint_type: str = Field("conceptual")
    mode: str = Field("practice")

class StuckOutputSchema(BaseModel):
    stuck: bool = Field(False)
    confidence: int = Field(50, ge=0, le=100)
    reason: str = Field("")

def validate_progress_output(data: dict) -> dict:
    """Validate and sanitize progress estimation JSON output."""
    try:
        validated = ProgressOutputSchema(**data)
        return validated.model_dump()
    except Exception:
        return {
            "progress": None,
            "confidence": 30,
            "stage": "Uncertain",
            "completed_components": [],
            "remaining_components": [],
            "reasoning_summary": "Analysis confidence below threshold."
        }

def validate_code_quality_output(data: dict) -> dict:
    """Validate and sanitize code quality JSON output."""
    try:
        validated = CodeQualityOutputSchema(**data)
        return validated.model_dump()
    except Exception:
        return {
            "overall": 50,
            "logic": 5,
            "readability": 5,
            "structure": 5,
            "efficiency": 5,
            "error_handling": 5,
            "summary": "Basic code structure evaluated.",
            "suggestions": []
        }

def validate_error_analysis_output(data: dict) -> dict:
    """Validate and sanitize compiler error analysis JSON output."""
    try:
        validated = ErrorAnalysisOutputSchema(**data)
        return validated.model_dump()
    except Exception:
        return {
            "error_type": "CompilerError",
            "explanation": "Execution error detected.",
            "likely_cause": "Syntax or logic mismatch.",
            "concept_hint": "Review error log details."
        }

def validate_hint_output(data: dict) -> dict:
    """Validate and sanitize hint JSON output."""
    try:
        validated = HintOutputSchema(**data)
        return validated.model_dump()
    except Exception:
        return {
            "hint": "Focus on the core algorithm logic.",
            "hint_type": "conceptual",
            "mode": "practice"
        }
