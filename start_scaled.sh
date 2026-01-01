#!/bin/bash
# Scaled startup script for handling 100s of concurrent users

# Configuration
NUM_WEB_WORKERS=${WEB_WORKERS:-4}
NUM_VIDEO_WORKERS=${VIDEO_WORKERS:-2}
NUM_AUDIO_WORKERS=${AUDIO_WORKERS:-1}
PORT=${PORT:-5000}

echo "========================================"
echo "  Aiezzy Simvid - Scaled Deployment"
echo "========================================"
echo "Web Workers: $NUM_WEB_WORKERS"
echo "Video Workers: $NUM_VIDEO_WORKERS"
echo "Audio Workers: $NUM_AUDIO_WORKERS"
echo "========================================"

# Check if Celery should be used
if [ "$USE_CELERY" = "true" ]; then
    echo "Starting Celery workers for distributed processing..."

    # Start video processing workers (CPU-intensive, fewer workers)
    celery -A celery_app worker \
        --queues=video \
        --concurrency=$NUM_VIDEO_WORKERS \
        --loglevel=info \
        --hostname=video@%h \
        --max-tasks-per-child=20 &

    # Start audio processing workers
    celery -A celery_app worker \
        --queues=audio \
        --concurrency=$NUM_AUDIO_WORKERS \
        --loglevel=info \
        --hostname=audio@%h &

    # Start maintenance workers
    celery -A celery_app worker \
        --queues=maintenance \
        --concurrency=1 \
        --loglevel=info \
        --hostname=maintenance@%h &

    # Start Celery Beat for scheduled tasks (cleanup)
    celery -A celery_app beat --loglevel=info &

    echo "Celery workers started"
else
    echo "Starting RQ workers..."

    # Start multiple RQ workers for parallel video processing
    for i in $(seq 1 $NUM_VIDEO_WORKERS); do
        echo "Starting RQ worker $i..."
        python worker.py &
    done

    echo "RQ workers started"
fi

# Start Gunicorn with multiple workers for handling concurrent requests
echo "Starting Gunicorn with $NUM_WEB_WORKERS workers..."

# Calculate threads per worker (2-4 is optimal for I/O bound operations)
THREADS_PER_WORKER=2

gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers $NUM_WEB_WORKERS \
    --threads $THREADS_PER_WORKER \
    --worker-class gthread \
    --timeout 300 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output
