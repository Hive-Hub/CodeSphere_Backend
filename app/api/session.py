from flask_restx import Namespace, Resource
from app.models.session import Session
from app.utils.response import api_response, api_error

session_ns = Namespace("session", description="Public Session Status Verification")

@session_ns.route("/<string:session_code>/status")
class SessionStatusResource(Resource):
    def get(self, session_code):
        """Check status of a session by 6-digit code."""
        code = session_code.strip()
        session = Session.query.filter_by(session_code=code).first()

        if not session:
            return api_response(
                data={
                    "session_code": code,
                    "exists": False,
                    "is_active": False,
                    "is_expired": False,
                    "is_ended": False
                },
                message="Session code does not exist",
                status_code=200
            )

        # Trigger auto-expiration check if active
        is_active = session.is_active()

        return api_response(
            data={
                "session_code": session.session_code,
                "exists": True,
                "is_active": is_active,
                "is_expired": session.status == "expired",
                "is_ended": session.status == "ended",
                "mode": session.mode,
                "language": session.language,
                "title": session.title,
                "college": session.college,
                "department": session.department,
                "subject": session.subject
            },
            message="Session status retrieved"
        )
