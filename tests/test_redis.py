from app.services.redis_service import (
    redis_set, redis_get, redis_delete, check_redis_connection
)

def test_redis_service_operations(app, mocker):
    """Test Redis set, get, delete, and health check with mock fallback if Redis server offline."""
    # Mock redis ping/client if real Redis service is not active
    mock_redis = mocker.patch("redis.Redis.from_url")
    mock_instance = mock_redis.return_value
    mock_instance.ping.return_value = True
    mock_instance.set.return_value = True
    mock_instance.get.return_value = "cached_value"
    mock_instance.delete.return_value = 1

    with app.app_context():
        # Set
        assert redis_set("my_key", "cached_value") is True
        # Get
        assert redis_get("my_key") == "cached_value"
        # Delete
        assert redis_delete("my_key") is True
        # Health check
        health = check_redis_connection()
        assert health["status"] == "healthy"

def test_redis_sample_endpoint(client, mocker):
    """Test POST /api/v1/sample/redis endpoint."""
    mocker.patch("app.api.sample.redis_set", return_value=True)
    mocker.patch("app.api.sample.redis_get", return_value="test_value")
    mocker.patch("app.api.sample.redis_delete", return_value=True)

    response = client.post("/api/v1/sample/redis", json={
        "key": "test_key",
        "value": "test_value"
    })
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["value"] == "test_value"
