# CodeSphere AI Backend

CodeSphere AI is an intelligent real-time coding classroom platform. This repository contains the production-ready Flask backend featuring temporary session management, real-time collaborative coding, AI code intelligence engine, ReportLab PDF & openpyxl Excel reporting, direct teacher download workflow, automatic session cleanup, fast Redis state tracking, debounced Celery database persistence, online code execution (Python, C, Java), teacher live classroom dashboard analytics, and Supabase PostgreSQL storage.

---

## Production Deployment on Render (Phase 7)

### 1. Render Components Architecture
- **Web Service (`codesphere-api`)**: Hosts Flask REST APIs & Flask-SocketIO real-time server using `wsgi.py`.
- **Background Worker (`codesphere-worker`)**: Runs Celery task queue processor (`celery -A celery_worker.celery_app worker`).
- **Cron Job (`codesphere-expiration`)**: Executes hourly session expiration scanner (`check_session_expirations`).

### 2. Environment Variables Configuration
Set the following environment variables in your Render Blueprint or dashboard:
```text
FLASK_ENV=production
DEBUG=false
SECRET_KEY=<random-secret-key>
JWT_SECRET_KEY=<random-jwt-secret>
DATABASE_URL=postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres
REDIS_URL=rediss://default:<password>@<host>.upstash.io:6379/0?ssl_cert_reqs=none
CELERY_BROKER_URL=rediss://default:<password>@<host>.upstash.io:6379/0?ssl_cert_reqs=none
CELERY_RESULT_BACKEND=rediss://default:<password>@<host>.upstash.io:6379/1?ssl_cert_reqs=none
ONLINE_COMPILER_API_KEY=<your-onlinecompiler-key>
ONLINE_COMPILER_BASE_URL=https://api.onlinecompiler.io
OPENAI_API_KEY=<your-openai-key>
GEMINI_API_KEY=<your-gemini-key>
FRONTEND_URL=https://codesphere.ai
CORS_ALLOWED_ORIGINS=https://codesphere.ai
```

### 3. Production Health Check
Verify API status at:
`GET https://codesphere-api.onrender.com/api/v1/health`

Expected Response (HTTP 200):
```json
{
  "status": "healthy",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "online_compiler": "healthy",
    "application": "healthy"
  }
}
```

---

## Running Production Smoke Tests

- **REST API Smoke Test**:
  ```bash
  PRODUCTION_URL="https://codesphere-api.onrender.com" python scripts/smoke_test_production.py
  ```

- **WebSocket Socket.IO Smoke Test**:
  ```bash
  PRODUCTION_URL="https://codesphere-api.onrender.com" python scripts/test_production_socket.py
  ```

---

## Local Development & Automated Tests

Run the complete Pytest suite (Phases 0–6):
```bash
python -m pytest -v
```
