from sqlalchemy import text
from app.models.health_log import HealthLog

def test_postgres_direct_query(db):
    """Test executing direct SQL query against database session."""
    result = db.session.execute(text("SELECT 1")).scalar()
    assert result == 1

def test_postgres_orm_crud(db):
    """Test ORM creation, retrieval, update, and deletion with HealthLog model."""
    # 1. Create
    log = HealthLog(service_name="PostgreSQL_Test", status="healthy", message="ORM Test")
    db.session.add(log)
    db.session.commit()
    assert log.id is not None
    
    # 2. Read
    fetched = HealthLog.query.filter_by(service_name="PostgreSQL_Test").first()
    assert fetched is not None
    assert fetched.status == "healthy"
    
    # 3. Update
    fetched.status = "degraded"
    db.session.commit()
    updated = HealthLog.query.get(fetched.id)
    assert updated.status == "degraded"
    
    # 4. Delete
    db.session.delete(updated)
    db.session.commit()
    deleted = HealthLog.query.get(fetched.id)
    assert deleted is None
