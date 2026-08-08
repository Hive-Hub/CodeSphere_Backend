# CodeSphere Backend Agent Skills Registry

This repository contains workspace skills designed for standard, enterprise-ready Python Flask backend engineering.

## Installed Backend Skills

| Skill Name | Path | Description |
| :--- | :--- | :--- |
| **`python-flask-basics`** | [`skills/python-flask-basics/SKILL.md`](file:///c:/projects/CodeSphere_Backend/.agents/skills/python-flask-basics/SKILL.md) | Application factory pattern (`create_app`), directory structure, config management, and extensions. |
| **`flask-rest-api`** | [`skills/flask-rest-api/SKILL.md`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-rest-api/SKILL.md) | REST API standards, Marshmallow validation, JSON error handlers, and HTTP status codes. |
| **`flask-sqlalchemy-orm`** | [`skills/flask-sqlalchemy-orm/SKILL.md`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-sqlalchemy-orm/SKILL.md) | SQLAlchemy models, base mixins, relationships, eager loading, transactions, and Alembic migrations. |
| **`flask-auth-security`** | [`skills/flask-auth-security/SKILL.md`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-auth-security/SKILL.md) | JWT authentication, Argon2/Werkzeug password hashing, RBAC decorators, CORS, rate limiting, and security headers. |
| **`flask-testing-pytest`** | [`skills/flask-testing-pytest/SKILL.md`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-testing-pytest/SKILL.md) | Pytest fixtures, test database isolation, API client testing, mocking, and coverage reporting. |

---

## Usage Instructions

Skills in `.agents/skills/<skill-name>/SKILL.md` are automatically discovered by the agent during conversation and task execution.

When building or updating backend endpoints, models, authentication, or test cases in `CodeSphere_Backend`, refer to the specific skill documentation for standard patterns.
