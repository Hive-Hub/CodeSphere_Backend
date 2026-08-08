# Workspace Agent Rules for CodeSphere_Backend

## Automatic Backend Skill Enforcement

Whenever building, editing, or refactoring code in this workspace, Antigravity MUST automatically load and strictly follow the workspace skills defined in `.agents/skills/`:

1. **Flask Application Architecture**: Refer to [`python-flask-basics`](file:///c:/projects/CodeSphere_Backend/.agents/skills/python-flask-basics/SKILL.md). Use the Application Factory pattern (`create_app`), modular Blueprints, and isolated extension objects.
2. **RESTful API Standards**: Refer to [`flask-rest-api`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-rest-api/SKILL.md). Use uniform JSON responses (`success`, `data`, `error`), Marshmallow validation schemas, and global error handlers.
3. **Database ORM & Migrations**: Refer to [`flask-sqlalchemy-orm`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-sqlalchemy-orm/SKILL.md). Use base timestamp mixins, transactional session scopes, eager loading (`joinedload`), and Alembic (`flask db`).
4. **Authentication & Security**: Refer to [`flask-auth-security`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-auth-security/SKILL.md). Use Flask-JWT-Extended, secure password hashing, `@roles_required` RBAC, CORS, and rate limiting.
5. **Automated Pytest Suite**: Refer to [`flask-testing-pytest`](file:///c:/projects/CodeSphere_Backend/.agents/skills/flask-testing-pytest/SKILL.md). Maintain Pytest fixtures in `tests/conftest.py` with isolated test database sessions.
