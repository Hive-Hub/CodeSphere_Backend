from app.utils.response import api_error
from app.logger import error_logger

class APIException(Exception):
    """Custom API Exception for operational errors."""
    def __init__(self, message, status_code=400, error_code="API_ERROR", details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or []

def register_error_handlers(app):
    """Register global error handlers on Flask app."""
    
    @app.errorhandler(APIException)
    def handle_api_exception(error):
        error_logger.warning(f"APIException [{error.error_code}]: {error.message}")
        return api_error(
            message=error.message,
            error_code=error.error_code,
            status_code=error.status_code,
            details=error.details
        )

    @app.errorhandler(400)
    def handle_bad_request(e):
        return api_error("Bad Request", error_code="BAD_REQUEST", status_code=400)

    @app.errorhandler(401)
    def handle_unauthorized(e):
        return api_error("Unauthorized access", error_code="UNAUTHORIZED", status_code=401)

    @app.errorhandler(403)
    def handle_forbidden(e):
        return api_error("Forbidden resource", error_code="FORBIDDEN", status_code=403)

    @app.errorhandler(404)
    def handle_not_found(e):
        return api_error("Resource not found", error_code="NOT_FOUND", status_code=404)

    @app.errorhandler(429)
    def handle_rate_limit(e):
        return api_error("Rate limit exceeded", error_code="RATE_LIMIT_EXCEEDED", status_code=429)

    @app.errorhandler(500)
    def handle_server_error(e):
        error_logger.exception(f"Internal Server Error: {str(e)}")
        return api_error("Internal server error", error_code="INTERNAL_SERVER_ERROR", status_code=500)
