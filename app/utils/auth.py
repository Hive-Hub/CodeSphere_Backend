import secrets
from functools import wraps
from flask import request, current_app
from flask_jwt_extended import create_access_token, decode_token
from app.utils.response import api_error

def generate_session_code():
    """Generate a cryptographically secure 6-digit numeric session code."""
    return str(secrets.randbelow(900000) + 100000)

def generate_teacher_profile_token(teacher_id, email):
    """Generate persistent JWT access token for a Teacher profile."""
    claims = {
        "role": "teacher",
        "teacher_id": teacher_id,
        "email": email
    }
    return create_access_token(identity=f"teacher_user_{teacher_id}", additional_claims=claims)

def generate_teacher_token(session_id, session_code):
    """Generate temporary JWT token for session teacher (V1 & V2 compatible)."""
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
    """Decorator to validate teacher tokens (supports session-specific and profile tokens)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_auth_token()
        if not token:
            return api_error("Teacher authorization token required", error_code="UNAUTHORIZED", status_code=401)
        try:
            decoded = decode_token(token)
            if decoded.get("role") != "teacher":
                return api_error("Invalid teacher authorization token", error_code="FORBIDDEN", status_code=403)
            request.teacher_claims = decoded
        except Exception as e:
            return api_error(f"Invalid or expired token: {str(e)}", error_code="UNAUTHORIZED", status_code=401)
        return f(*args, **kwargs)
    return decorated

def student_token_required(f):
    """Decorator to validate student session token."""
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

def verify_teacher_session_access(session, claims):
    """Verify if token claims grant access to a specific session."""
    if not session or not claims:
        return False
    # If token has session_id claim matching session.id
    if claims.get("session_id") and claims.get("session_id") == session.id:
        return True
    # If token has teacher_id matching session.teacher_id
    if claims.get("teacher_id") and session.teacher_id and claims.get("teacher_id") == session.teacher_id:
        return True
    # If token email matches session teacher_email
    if claims.get("email") and session.teacher_email and claims.get("email").lower() == session.teacher_email.lower():
        return True
    return False
