from flask_restx import Namespace, Resource
from app.utils.health_checks import get_full_health_status
from app.utils.response import api_response, api_error

health_ns = Namespace("health", description="System & dependency health check operations")

@health_ns.route("")
class HealthSummaryResource(Resource):
    @health_ns.doc("get_health_summary")
    def get(self):
        """Get high-level summary of system and critical dependency health."""
        health = get_full_health_status()
        status_code = 200 if health["overall_status"] == "healthy" else 530
        return api_response(
            data={"status": health["overall_status"]},
            message="Health check completed",
            status_code=status_code if status_code == 200 else 200 # Always return 200 with payload for health monitors
        )

@health_ns.route("/detailed")
class DetailedHealthResource(Resource):
    @health_ns.doc("get_detailed_health")
    def get(self):
        """Get comprehensive health status breakdown of every dependency."""
        health = get_full_health_status()
        return api_response(
            data=health,
            message="Detailed health check completed",
            status_code=200
        )
