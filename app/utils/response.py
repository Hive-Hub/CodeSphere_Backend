from flask import jsonify

def api_response(data=None, message=None, status_code=200, meta=None):
    """Generate uniform success payload dictionary for Flask & Flask-RESTX."""
    payload = {
        "success": True,
        "message": message,
        "data": data,
        "meta": meta,
        "error": None
    }
    return payload, status_code

def api_error(message, error_code="BAD_REQUEST", status_code=400, details=None):
    """Generate uniform error payload dictionary for Flask & Flask-RESTX."""
    payload = {
        "success": False,
        "data": None,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or []
        }
    }
    return payload, status_code
