def test_health_summary_endpoint(client):
    """Test GET /api/v1/health summary endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert "status" in json_data["data"]

def test_health_detailed_endpoint(client):
    """Test GET /api/v1/health/detailed breakdown endpoint."""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "overall_status" in data
    assert "dependencies" in data
    
    deps = data["dependencies"]
    expected_deps = ["postgres", "supabase", "redis", "socketio", "celery", "online_compiler"]
    for dep in expected_deps:
        assert dep in deps
        assert "status" in deps[dep]
        assert "message" in deps[dep]
