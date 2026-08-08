---
name: flask-testing-pytest
description: Unit and integration testing strategies for Flask backends using Pytest, fixtures, test client, isolated database sessions, and mocking.
---

# Flask Testing with Pytest

This skill provides guidelines and patterns for writing fast, isolated, and comprehensive automated test suites for Flask applications using Pytest.

## 1. Pytest Configuration

### `pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
```

---

## 2. Test Fixtures Setup

Create modular test fixtures in `tests/conftest.py`.

### `tests/conftest.py`
```python
import pytest
from app import create_app
from app.extensions import db as _db

@pytest.fixture(scope="session")
def app():
    """Create application configured for testing."""
    app = create_app("testing")
    with app.app_context():
        yield app

@pytest.fixture(scope="function")
def client(app):
    """A test client for sending HTTP requests."""
    return app.test_client()

@pytest.fixture(scope="function")
def db(app):
    """Database fixture providing clean database state per test."""
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()

@pytest.fixture
def auth_headers(client, db):
    """Fixture to produce authenticated request headers."""
    from app.models.user import User
    from flask_jwt_extended import create_access_token
    
    user = User(username="testuser", email="test@example.com", password_hash="hashed")
    db.session.add(user)
    db.session.commit()
    
    token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}"}
```

---

## 3. Integration Testing API Endpoints

Test HTTP routes, status codes, and response JSON contents.

### `tests/test_auth_routes.py`
```python
def test_login_success(client, db):
    from app.models.user import User
    from werkzeug.security import generate_password_hash
    
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash=generate_password_hash("password123")
    )
    db.session.add(user)
    db.session.commit()

    response = client.post("/api/v1/auth/login", json={
        "email": "testuser@example.com",
        "password": "password123"
    })

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert "access_token" in json_data["data"]

def test_protected_route_unauthorized(client):
    response = client.get("/api/v1/protected")
    assert response.status_code == 401
```

---

## 4. Unit Testing Services with Mocking

Use `mocker` (pytest-mock) to mock external HTTP calls or heavy third-party services.

### `tests/test_services.py`
```python
def test_external_payment_service(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "SUCCESS", "transaction_id": "tx_123"}

    from app.services.payment_service import process_payment
    result = process_payment(amount=100)

    assert result["status"] == "SUCCESS"
    mock_post.assert_called_once()
```

---

## 5. Running Tests & Coverage

Execute tests using pytest CLI with coverage tracking:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_auth_routes.py

# Run tests with coverage report
pytest --cov=app --cov-report=term-missing
```
