"""
Celery Configuration for Scalable Video Processing
Replaces RQ with Celery for better horizontal scaling
"""

import os
from celery import Celery

# Redis URL from environment
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'video_tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['celery_tasks']
)

# Celery Configuration for high throughput
celery_app.conf.update(
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Concurrency settings - crucial for handling 100s of users
    worker_prefetch_multiplier=1,  # Prevent workers from grabbing too many tasks
    task_acks_late=True,  # Only ack after task completion (fault tolerance)

    # Task time limits
    task_soft_time_limit=1800,  # 30 minutes soft limit
    task_time_limit=2400,  # 40 minutes hard limit

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Rate limiting (per worker)
    task_annotations={
        'celery_tasks.generate_video_task': {
            'rate_limit': '10/m'  # Max 10 videos per minute per worker
        }
    },

    # Queue routing for different priority levels
    task_routes={
        'celery_tasks.generate_video_task': {'queue': 'video'},
        'celery_tasks.download_youtube_audio': {'queue': 'audio'},
        'celery_tasks.cleanup_old_files': {'queue': 'maintenance'},
    },

    # Retry settings
    task_default_retry_delay=60,  # Wait 60 seconds before retry
    task_max_retries=3,

    # Memory management - restart worker after processing N tasks
    worker_max_tasks_per_child=50,

    # Visibility timeout (for long-running tasks)
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 hour
    }
)

# Define queues with priorities
celery_app.conf.task_queues = {
    'video': {
        'exchange': 'video',
        'routing_key': 'video',
    },
    'audio': {
        'exchange': 'audio',
        'routing_key': 'audio',
    },
    'maintenance': {
        'exchange': 'maintenance',
        'routing_key': 'maintenance',
    },
}
