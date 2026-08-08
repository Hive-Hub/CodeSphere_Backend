import secrets
from functools import wraps
from flask import request, current_app
from flask_jwt_extended import create_access_token, decode_token
from app.utils.response import api_error

def generate_session_code():
    """Generate a cryptographically secure 6-digit numeric session code."""
    return str(secrets.randbelow(900000) + 100000)

def generate_teacher_token(session_id, session_code):
    """Generate temporary JWT token for session teacher."""
    claims = {
        "role": "teacher",
        "session_id": session_id,
        "session_code": session_code
    }
    return create_access_token(identity=f"teacher_{session_id}", additional_claims=claims)

def generate_student_token(student_id, session_id):
    """Generate temporary JWT token for joined student."""
    claims = {
        "role": "student",
        "student_id": student_id,
        "session_id": session_id
    }
    return create_access_token(identity=f"student_{student_id}", additional_claims=claims)

def get_auth_token():
    """Extract token from X-Teacher-Token, X-Student-Token, or Authorization Bearer header."""
    token = request.headers.get("X-Teacher-Token") or request.headers.get("X-Student-Token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    return token

def teacher_token_required(f):
    """Decorator to validate temporary teacher session token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_auth_token()
        if not token:
            return api_error("Teacher authorization token required", error_code="UNAUTHORIZED", status_code=401)
        try:
            decoded = decode_token(token)
            claims = decoded.get("sub", "")
            if decoded.get("role") != "teacher":
                return api_error("Invalid teacher session token", error_code="FORBIDDEN", status_code=403)
            # Pass token claims to handler if needed
            request.teacher_claims = decoded
        except Exception as e:
            return api_error(f"Invalid or expired token: {str(e)}", error_code="UNAUTHORIZED", status_code=401)
        return f(*args, **kwargs)
    return decorated

def student_token_required(f):
    """Decorator to validate temporary student session token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_auth_token()
        if not token:
            return api_error("Student authorization token required", error_code="UNAUTHORIZED", status_code=401)
        try:
            decoded = decode_token(token)
            if decoded.get("role") != "student":
                return api_error("Invalid student session token", error_code="FORBIDDEN", status_code=403)
            request.student_claims = decoded
        except Exception as e:
            return api_error(f"Invalid or expired token: {str(e)}", error_code="UNAUTHORIZED", status_code=401)
        return f(*args, **kwargs)
    return decorated
