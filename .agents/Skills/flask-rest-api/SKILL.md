---
name: flask-rest-api
description: Standards for building RESTful APIs using Flask, Marshmallow validation schemas, consistent JSON response formatting, pagination, and error handlers.
---

# Flask REST API Design & Standards

This skill defines rules and templates for building standardized REST APIs in Flask.

## 1. Standard Response Format

All API endpoints MUST return JSON with a uniform structure.

### API Response Structure
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100
  }
}
```

### Helper Utility: `app/utils/response.py`
```python
from flask import jsonify

def api_response(data=None, message=None, status_code=200, meta=None):
    payload = {
        "success": True,
        "data": data,
        "message": message,
        "meta": meta
    }
    return jsonify(payload), status_code

def api_error(message, error_code="BAD_REQUEST", status_code=400, details=None):
    payload = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or []
        }
    }
    return jsonify(payload), status_code
```

---

## 2. Request Data Validation (Marshmallow)

Use **Marshmallow** schemas to validate incoming payloads before execution.

### `app/schemas/user_schema.py`
```python
from marshmallow import Schema, fields, validate

class UserCreateSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3, max=50))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))

class UserResponseSchema(Schema):
    id = fields.Integer()
    username = fields.String()
    email = fields.Email()
    created_at = fields.DateTime()
```

### Route Validation Decorator Pattern
```python
from functools import wraps
from flask import request
from app.utils.response import api_error

def validate_schema(schema_cls):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            schema = schema_cls()
            errors = schema.validate(request.get_json() or {})
            if errors:
                return api_error(
                    message="Validation failed",
                    error_code="VALIDATION_ERROR",
                    status_code=422,
                    details=errors
                )
            return f(*args, **kwargs)
        return wrapper
    return decorator
```

---

## 3. Route & Controller Design Pattern

### Example Endpoint Blueprint (`app/blueprints/users/routes.py`)
```python
from flask import Blueprint, request
from app.schemas.user_schema import UserCreateSchema, UserResponseSchema
from app.services.user_service import create_user, get_paginated_users
from app.utils.response import api_response, api_error
from app.utils.decorators import validate_schema

users_bp = Blueprint("users", __name__)

@users_bp.route("", methods=["GET"])
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    
    users, total = get_paginated_users(page, per_page)
    schema = UserResponseSchema(many=True)
    
    return api_response(
        data=schema.dump(users),
        meta={"page": page, "per_page": per_page, "total": total}
    )

@users_bp.route("", methods=["POST"])
@validate_schema(UserCreateSchema)
def add_user():
    data = request.get_json()
    user = create_user(data)
    schema = UserResponseSchema()
    return api_response(data=schema.dump(user), status_code=201)
```

---

## 4. Centralized Error Handling

Register global custom HTTP error handlers to avoid leaked stack traces.

### `app/utils/errors.py`
```python
from flask import jsonify
from app.utils.response import api_error

class APIException(Exception):
    def __init__(self, message, status_code=400, error_code="API_ERROR", details=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details

def register_error_handlers(app):
    @app.errorhandler(APIException)
    def handle_api_exception(error):
        return api_error(
            message=error.message,
            error_code=error.error_code,
            status_code=error.status_code,
            details=error.details
        )

    @app.errorhandler(404)
    def handle_not_found(e):
        return api_error("Resource not found", error_code="NOT_FOUND", status_code=404)

    @app.errorhandler(500)
    def handle_server_error(e):
        return api_error("Internal server error", error_code="SERVER_ERROR", status_code=500)
```
