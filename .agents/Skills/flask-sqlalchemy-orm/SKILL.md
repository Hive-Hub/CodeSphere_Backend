---
name: flask-sqlalchemy-orm
description: Database design guidelines using Flask-SQLAlchemy, Alembic migrations, repository query patterns, relationships, indexes, and session management.
---

# Flask-SQLAlchemy ORM Best Practices

This skill outlines guidelines for managing databases with Flask-SQLAlchemy, handling migrations, and writing optimized database queries.

## 1. Base Model & Timestamp Mixin

Define standard columns (IDs, timestamps, soft-deletes) in a base mixin class.

### `app/models/base.py`
```python
from datetime import datetime, timezone
from app.extensions import db

class TimestampMixin:
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class BaseModel(db.Model, TimestampMixin):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()
```

---

## 2. Declarative Model & Relationship Definitions

### `app/models/user.py` & `app/models/post.py`
```python
from app.extensions import db
from app.models.base import BaseModel

class User(BaseModel):
    __tablename__ = "users"

    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # One-to-Many Relationship
    posts = db.relationship("Post", back_populates="author", cascade="all, delete-orphan", lazy="select")

class Post(BaseModel):
    __tablename__ = "posts"

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    author = db.relationship("User", back_populates="posts")
```

---

## 3. Transaction & Session Context Manager

Always ensure transactions roll back on error. Use context managers or repository layer wrappers.

### Transaction Helper (`app/utils/db.py`)
```python
from contextlib import contextmanager
from app.extensions import db

@contextmanager
def transaction_scope():
    """Provide a transactional scope around a series of operations."""
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
```

---

## 4. Preventing N+1 Query Anti-Patterns

Avoid lazy querying in loops. Explicitly use `joinedload` or `selectinload`.

### Bad Pattern (N+1 Queries)
```python
posts = Post.query.all()
for post in posts:
    print(post.author.username)  # Causes N extra SQL SELECT queries!
```

### Good Pattern (Eager Loading)
```python
from sqlalchemy.orm import joinedload
from app.models.post import Post

def get_posts_with_authors():
    return Post.query.options(joinedload(Post.author)).all()
```

---

## 5. Alembic Migration Workflow

Use Flask-Migrate CLI commands for database schema changes.

```bash
# 1. Initialize migration environment (first time only)
flask db init

# 2. Auto-generate migration script after changing models
flask db migrate -m "Add post model and user index"

# 3. Apply migration to target database
flask db upgrade

# 4. Rollback last migration if needed
flask db downgrade
```
