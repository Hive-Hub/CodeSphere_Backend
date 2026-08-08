from functools import wraps
from flask import request
from app.utils.response import api_error

def validate_schema(schema_cls):
    """Decorator to validate incoming JSON payload against a Marshmallow schema class."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            schema = schema_cls()
            data = request.get_json() or {}
            errors = schema.validate(data)
            if errors:
                return api_error(
                    message="Validation failed",
                    error_code="VALIDATION_ERROR",
                    status_code=400,
                    details=errors
                )
            return f(*args, **kwargs)
        return wrapper
    return decorator
