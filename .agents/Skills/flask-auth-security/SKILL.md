---
name: flask-auth-security
description: Security standards for Flask applications, covering JWT authentication, password hashing, Role-Based Access Control (RBAC), CORS, rate limiting, and security headers.
---

# Flask Authentication & Security Standards

This skill provides implementation patterns for securing Flask API backends.

## 1. Password Hashing

Never store plain text passwords. Use standard cryptographic hashing functions (`generate_password_hash` with pbkdf2/scrypt/argon2).

### `app/services/auth_service.py`
```python
from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password: str) -> str:
    return generate_password_hash(password, method="scrypt")

def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)
```

---

## 2. JWT Authentication Setup

Integrate **Flask-JWT-Extended** for state-free token-based authentication.

### `app/blueprints/auth/routes.py`
```python
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity
)
from app.models.user import User
from app.services.auth_service import verify_password
from app.utils.response import api_response, api_error

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        return api_error("Invalid email or password", status_code=401)

    additional_claims = {"role": user.role}
    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=str(user.id))

    return api_response({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username, "role": user.role}
    })

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    new_token = create_access_token(identity=identity)
    return api_response({"access_token": new_token})
```

---

## 3. Role-Based Access Control (RBAC) Decorator

Implement custom authorization decorators to enforce role constraints.

### `app/utils/decorators.py`
```python
from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from app.utils.response import api_error

def roles_required(*required_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_role = claims.get("role", "user")

            if user_role not in required_roles:
                return api_error(
                    message="Insufficient permissions for this resource",
                    error_code="FORBIDDEN",
                    status_code=403
                )
            return f(*args, **kwargs)
        return wrapper
    return decorator
```

### Usage Example
```python
@admin_bp.route("/dashboard", methods=["GET"])
@roles_required("admin", "superadmin")
def admin_dashboard():
    return api_response({"data": "Confidential admin metrics"})
```

---

## 4. Security Middleware (CORS & Rate Limiting)

### CORS Configuration (`app/extensions.py`)
```python
from flask_cors import CORS

def configure_cors(app):
    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://your-frontend-domain.com"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
```

### Rate Limiting (Flask-Limiter)
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Apply specifically to login endpoint
@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def rate_limited_login():
    ...
```

---

## 5. Defense-in-Depth Checklist

1. **Max Content Length**: Limit payload body size in `config.py`: `MAX_CONTENT_LENGTH = 16 * 1024 * 1024` (16MB).
2. **Environment Secrets**: Ensure `SECRET_KEY` and `JWT_SECRET_KEY` are retrieved strictly from OS environment variables.
3. **HTTP-Only Cookies**: If storing tokens in cookies, set `JWT_COOKIE_SECURE=True`, `JWT_COOKIE_CSRF_PROTECT=True`, and `JWT_TOKEN_LOCATION=['cookies']`.
