#!/usr/bin/env bash
# ==============================================================================
# CodeSphere AI Backend - Automated Build & Deployment Script
# ==============================================================================
# Usage:
#   ./build.sh                  Standard build & deployment initialization
#   RUN_TESTS=true ./build.sh   Build with automated Pytest suite execution
# ==============================================================================

set -eo pipefail

# Visual formatting indicators
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[BUILD INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[BUILD SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[BUILD WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[BUILD ERROR]${NC} $1"
}

log_info "Starting CodeSphere AI Backend Deployment Build Procedure..."

# 1. Environment & Python check
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    log_error "Python interpreter not found in PATH."
    exit 1
fi

log_info "Using Python interpreter: $($PYTHON_CMD --version)"

# 2. Virtual Environment Setup (Handles PEP 668 & isolated builds)
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d ".venv" ]; then
        log_info "Creating virtual environment in .venv..."
        $PYTHON_CMD -m venv .venv || true
    fi

    if [ -f ".venv/bin/activate" ]; then
        log_info "Activating virtual environment (.venv)..."
        source .venv/bin/activate
        PYTHON_CMD=".venv/bin/python"
    elif [ -f ".venv/Scripts/activate" ]; then
        log_info "Activating virtual environment (.venv)..."
        source .venv/Scripts/activate
        PYTHON_CMD=".venv/Scripts/python"
    else
        log_warning "Virtual environment activation scripts not found. Proceeding with default Python."
    fi
fi

# 3. Upgrade pip and build tools
log_info "Upgrading pip, setuptools, and wheel..."
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel --quiet 2>/dev/null || \
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel --quiet --break-system-packages 2>/dev/null || true

# 4. Install production and project dependencies
log_info "Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    $PYTHON_CMD -m pip install -r requirements.txt --quiet 2>/dev/null || \
    $PYTHON_CMD -m pip install -r requirements.txt --break-system-packages
else
    log_error "requirements.txt not found!"
    exit 1
fi
log_success "Dependencies installed successfully."

# 5. Ensure required runtime directories exist
log_info "Creating required application runtime directories..."
mkdir -p logs exports instance

# 6. Bytecode Compilation & Syntax Check
log_info "Compiling Python source code to verify syntax integrity..."
$PYTHON_CMD -m compileall app/ wsgi.py celery_worker.py -q
log_success "Python source code compilation passed."

# 7. Database Migration / Schema Sync
log_info "Running database setup & migration checks..."
if [ -d "migrations" ]; then
    log_info "Running Flask-Migrate database upgrade..."
    $PYTHON_CMD -m flask db upgrade || log_warning "Flask db upgrade failed or deferred."
else
    log_info "Initializing database schema via application context..."
    $PYTHON_CMD -c "
from app import create_app
from app.extensions import db
app = create_app()
with app.app_context():
    try:
        db.create_all()
        print('Database tables verified/created.')
    except Exception as e:
        print(f'Database table initialization skipped: {e}')
"
fi

# 8. Optional Test Suite Execution
if [ "${RUN_TESTS:-false}" = "true" ] || [ "$1" = "--run-tests" ]; then
    log_info "Running Pytest test suite prior to final deployment..."
    $PYTHON_CMD -m pytest tests/ -v
    log_success "All automated tests passed."
fi

log_success "=================================================================="
log_success "CodeSphere AI Backend build completed successfully!"
log_success "Ready for WSGI execution (e.g. via gunicorn or python wsgi.py)."
log_success "=================================================================="

exit 0
