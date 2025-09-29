"""
RQ Worker for Background Video Generation
This worker processes video generation jobs from the Redis queue
"""

import os
import sys
from redis import Redis
from rq import Worker, Queue, Connection

# Get Redis URL from environment
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Connect to Redis
redis_conn = Redis.from_url(redis_url)

# Define the queues to listen on
listen = ['video_generation', 'default']

if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(list(map(Queue, listen)))
        print(f"🚀 RQ Worker starting...")
        print(f"📡 Connected to Redis: {redis_url}")
        print(f"📋 Listening on queues: {', '.join(listen)}")
        worker.work()