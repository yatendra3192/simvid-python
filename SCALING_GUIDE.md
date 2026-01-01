# Scaling Guide: Handling 100s of Concurrent Users

This guide explains how to scale Aiezzy Simvid to handle hundreds of concurrent users.

## Architecture Overview

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  (Load      │
                    │  Balancer)  │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼─────┐  ┌──────▼─────┐  ┌──────▼─────┐
    │   Web 1    │  │   Web 2    │  │   Web 3    │
    │ (Gunicorn) │  │ (Gunicorn) │  │ (Gunicorn) │
    └──────┬─────┘  └──────┬─────┘  └──────┬─────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │    Redis    │
                    │  (Queue +   │
                    │   Cache)    │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼─────┐  ┌──────▼─────┐  ┌──────▼─────┐
    │  Video     │  │  Video     │  │  Audio     │
    │  Worker 1  │  │  Worker 2  │  │  Worker    │
    │ (Celery)   │  │ (Celery)   │  │ (Celery)   │
    └────────────┘  └────────────┘  └────────────┘
```

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start all services with scaling
docker-compose up -d --scale web=3 --scale video-worker=4

# Monitor with Flower
open http://localhost:5555
```

### Option 2: Railway Deployment

1. Set environment variables:
```env
USE_CELERY=true
REDIS_URL=redis://your-redis-url
WEB_WORKERS=4
VIDEO_WORKERS=3
```

2. Deploy both services:
- Web service: Uses `Procfile` → `web` process
- Worker service: Uses `Procfile` → `worker` process

### Option 3: Manual Deployment

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2-4: Start multiple Celery workers
celery -A celery_app worker --queues=video --concurrency=2

# Terminal 5: Start web server
gunicorn app:app --workers 4 --threads 2 --bind 0.0.0.0:5000
```

## Scaling Recommendations

### For 100 Concurrent Users

| Component | Instances | Resources |
|-----------|-----------|-----------|
| Web (Gunicorn) | 2 instances × 4 workers | 1 CPU, 1GB RAM each |
| Video Workers | 3 instances × 2 concurrency | 2 CPU, 2GB RAM each |
| Audio Workers | 2 instances × 2 concurrency | 0.5 CPU, 512MB RAM each |
| Redis | 1 instance | 1 CPU, 512MB RAM |

### For 500 Concurrent Users

| Component | Instances | Resources |
|-----------|-----------|-----------|
| Web (Gunicorn) | 4 instances × 4 workers | 2 CPU, 2GB RAM each |
| Video Workers | 8 instances × 2 concurrency | 2 CPU, 4GB RAM each |
| Audio Workers | 4 instances × 3 concurrency | 1 CPU, 1GB RAM each |
| Redis | 1 instance (clustered) | 2 CPU, 2GB RAM |

## Key Configuration Options

### Environment Variables

```env
# Scaling
USE_CELERY=true          # Enable Celery (required for scale)
WEB_WORKERS=4            # Gunicorn workers per instance
VIDEO_WORKERS=2          # Video processing workers
AUDIO_WORKERS=2          # Audio processing workers

# Redis
REDIS_URL=redis://...    # Redis connection URL

# Performance
FLASK_ENV=production
```

### Celery Tuning

The `celery_app.py` file contains optimized settings:

- `worker_prefetch_multiplier=1`: Prevents worker hoarding
- `task_acks_late=True`: Ensures fault tolerance
- `worker_max_tasks_per_child=50`: Prevents memory leaks
- Rate limiting: 10 videos/minute per worker

## Performance Optimizations Applied

1. **Distributed Rate Limiting**: Redis-backed rate limiting works across all instances
2. **Connection Pooling**: PostgreSQL connections are pooled (max 10)
3. **Video Encoding**: Uses `veryfast` preset for 3x faster encoding
4. **Memory Management**: Workers restart after 50 tasks to prevent leaks
5. **Health Checks**: `/health` endpoint for load balancer monitoring

## Monitoring

### Flower Dashboard (Celery)

```bash
# Access at http://localhost:5555
celery -A celery_app flower --port=5555
```

Shows:
- Active workers and their status
- Task queue lengths
- Processing times
- Success/failure rates

### Key Metrics to Watch

1. **Queue Length**: If consistently high, add more workers
2. **Task Duration**: Video generation should be < 5 minutes
3. **Memory Usage**: Workers should stay under 2GB
4. **Error Rate**: Should be < 1%

## Troubleshooting

### High Queue Backlog
- Add more video workers
- Check for slow/stuck tasks

### Memory Issues
- Reduce `worker_max_tasks_per_child`
- Add more RAM to worker instances

### Timeouts
- Increase `task_time_limit` in celery_app.py
- Check network latency to Redis

## Cost Estimates (Railway/Cloud)

| Scale | Monthly Cost (Est.) |
|-------|---------------------|
| 100 users | $50-100 |
| 500 users | $200-400 |
| 1000 users | $500-800 |

Note: Actual costs depend on usage patterns and cloud provider.
