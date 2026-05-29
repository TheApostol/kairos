#!/bin/bash
# Backend startup script for Plesk / production
set -e

cd "$(dirname "$0")"

# Install/update dependencies
pip install -r requirements.txt --quiet

# Start with gunicorn (production) or uvicorn (dev)
PORT=${PORT:-8000}
WORKERS=${WEB_CONCURRENCY:-2}

exec gunicorn main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "$WORKERS" \
  --bind "0.0.0.0:$PORT" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
