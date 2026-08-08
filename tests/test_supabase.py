from app.services.supabase_service import (
    check_supabase_connection,
    test_supabase_crud
)

def test_supabase_health_check(app):
    """Test Supabase connection health verification helper."""
    with app.app_context():
        res = check_supabase_connection()
        assert "status" in res
        assert res["status"] in ("healthy", "degraded", "unhealthy")

def test_supabase_crud_operation(app):
    """Test Supabase CRUD execution helper."""
    with app.app_context():
        res = test_supabase_crud()
        assert res["success"] is True
        assert "operation" in res
