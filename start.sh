#!/bin/bash
# Railway Web Service Startup Script

echo "========================================"
echo "  Aiezzy Simvid - Railway Deployment"
echo "========================================"

# Configuration from environment
WEB_WORKERS=${WEB_WORKERS:-2}
PORT=${PORT:-5000}

echo "Port: $PORT"
echo "Web Workers: $WEB_WORKERS"
echo "Redis URL: ${REDIS_URL:-NOT SET}"
echo "Use Celery: ${USE_CELERY:-false}"
echo "========================================"

# If not using separate worker service, start RQ worker in background
if [ "$USE_CELERY" != "true" ] && [ -n "$REDIS_URL" ]; then
    echo "Starting RQ worker in background..."
    python worker.py &
    sleep 2
fi

# Start Gunicorn
echo "Starting Gunicorn with $WEB_WORKERS workers..."
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers $WEB_WORKERS \
    --threads 2 \
    --worker-class gthread \
    --timeout 300 \
    --keep-alive 5 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
