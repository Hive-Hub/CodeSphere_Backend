from flask import Blueprint
from flask_restx import Api
from app.api.health import health_ns
from app.api.sample import sample_ns
from app.api.teacher import teacher_ns
from app.api.student import student_ns
from app.api.session import session_ns
from app.api.ai import ai_ns

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
api_legacy_bp = Blueprint("api_legacy", __name__, url_prefix="/api")

# V1 API definition
api = Api(
    api_bp,
    title="CodeSphere AI API",
    version="1.0",
    description="Core backend RESTful API services for CodeSphere AI platform",
    doc="/docs"
)

# Legacy / Direct /api definition for backward compatibility
api_legacy = Api(
    api_legacy_bp,
    title="CodeSphere AI API (Direct)",
    version="1.0",
    description="Direct /api alias namespace",
    doc=False
)

# Add Namespaces
api.add_namespace(health_ns, path="/health")
api.add_namespace(sample_ns, path="/sample")
api.add_namespace(teacher_ns, path="/teacher")
api.add_namespace(student_ns, path="/student")
api.add_namespace(session_ns, path="/session")
api.add_namespace(ai_ns, path="/ai")

api_legacy.add_namespace(teacher_ns, path="/teacher")
api_legacy.add_namespace(student_ns, path="/student")
api_legacy.add_namespace(session_ns, path="/session")
api_legacy.add_namespace(ai_ns, path="/ai")
