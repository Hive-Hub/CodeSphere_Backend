import pytest
from app import create_app
from app.extensions import db as _db, socketio

@pytest.fixture(scope="session")
def app():
    """Session-wide application configured for testing."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app

@pytest.fixture(scope="function")
def db(app):
    """Database fixture providing clean isolated tables for each test."""
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()

@pytest.fixture(scope="function")
def client(app, db):
    """Flask test client fixture with initialized database tables."""
    return app.test_client()

@pytest.fixture(scope="function")
def socket_client(app, db):
    """Flask-SocketIO test client fixture."""
    return socketio.test_client(app)
