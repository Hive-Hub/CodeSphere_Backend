from app.tasks.sample_tasks import ping_task, execute_code_async

def test_celery_ping_task(app):
    """Test Celery ping task execution in eager testing mode."""
    with app.app_context():
        res = ping_task.apply(args=["Unit Test"]).get()
        assert res["status"] == "SUCCESS"
        assert res["response"] == "pong: Unit Test"

def test_celery_execute_code_async_task(app):
    """Test Celery async code execution task."""
    with app.app_context():
        res = execute_code_async.apply(args=["python", "print('Async Hello')"]).get()
        assert res["success"] is True
        assert "Hello" in res["output"] or "simulated" in res.get("mode", "")

def test_celery_sample_endpoint(client):
    """Test POST /api/v1/sample/celery endpoint."""
    response = client.post("/api/v1/sample/celery", json={"message": "Test Task"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert "task_id" in json_data["data"]
