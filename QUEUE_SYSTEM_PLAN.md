# Queue System Implementation Plan

## Overview
This document outlines the plan for implementing a job queue system for Aiezzy Simvid to handle multiple concurrent video generation requests efficiently.

## Problem Statement

### Current Limitations
1. **Blocking Requests**: Video generation is synchronous - each request blocks the server
2. **No Concurrency Control**: Multiple users can trigger CPU/memory intensive operations simultaneously
3. **No Job Persistence**: If server restarts, in-progress jobs are lost
4. **Poor Resource Management**: No way to limit concurrent video generation processes
5. **Limited Scalability**: Can't scale horizontally without shared state

### Why We Need a Queue System
- Handle multiple video generation requests without blocking the server
- Limit concurrent processing to prevent resource exhaustion
- Persist job state across server restarts
- Enable background processing
- Provide job status tracking and history
- Allow horizontal scaling with multiple worker processes

## Proposed Solution: Celery + Redis

### Architecture Overview

```
┌─────────────────┐
│   Flask API     │  (Receives requests, enqueues jobs)
│   app.py        │
└────────┬────────┘
         │
         ├─► Redis (Message Broker + Result Backend)
         │   - Job queue
         │   - Job results
         │   - Progress tracking
         │
         ▼
┌─────────────────┐
│ Celery Workers  │  (Process video generation)
│ (1-N instances) │
└─────────────────┘
```

## Implementation Steps

### Phase 1: Setup Infrastructure (Redis + Celery)

#### 1.1 Install Dependencies
```bash
pip install celery redis
```

#### 1.2 Update requirements.txt
```txt
celery==5.4.0
redis==5.2.1
```

#### 1.3 Create Celery Configuration (celery_app.py)
```python
from celery import Celery
import os

# Configure Celery
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery(
    'aiezzy_simvid',
    broker=redis_url,
    backend=redis_url,
    include=['tasks']
)

# Celery Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max
    task_soft_time_limit=1500,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
    result_expires=86400,  # Keep results for 24 hours
)
```

### Phase 2: Create Background Tasks

#### 2.1 Create Tasks Module (tasks.py)
```python
from celery_app import celery_app
from celery import Task
from moviepy.editor import *
import os
from app import (
    fix_image_orientation, optimize_image,
    get_image_files, safe_join_path
)

class VideoGenerationTask(Task):
    """Custom task with progress tracking"""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        print(f"Task {task_id} failed: {exc}")
        # Update progress with error state
        self.update_state(
            task_id=task_id,
            state='FAILURE',
            meta={'error': str(exc)}
        )

@celery_app.task(
    bind=True,
    base=VideoGenerationTask,
    name='tasks.generate_video'
)
def generate_video_task(
    self,
    session_id,
    audio_id,
    duration,
    transition,
    resolution,
    output_path
):
    """
    Background task for video generation

    Args:
        self: Task instance (for progress updates)
        session_id: User session ID
        audio_id: Audio file ID (optional)
        duration: Duration per image
        transition: Transition effect
        resolution: Video resolution
        output_path: Where to save the video

    Returns:
        dict: {success: bool, video_path: str, error: str}
    """
    try:
        # Update progress: Starting
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'initializing',
                'progress': 0,
                'message': 'Starting video generation...'
            }
        )

        # Get image files
        image_files = get_image_files(session_id)
        total_images = len(image_files)

        if total_images == 0:
            return {'success': False, 'error': 'No images found'}

        # Update progress: Found images
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'processing',
                'progress': 10,
                'message': f'Found {total_images} images'
            }
        )

        # Process images into clips
        clips = []
        for idx, img_path in enumerate(image_files):
            # Update progress for each image
            progress = 10 + int((idx / total_images) * 50)
            self.update_state(
                state='PROGRESS',
                meta={
                    'stage': 'processing',
                    'progress': progress,
                    'message': f'Processing image {idx + 1}/{total_images}'
                }
            )

            # Create image clip
            clip = ImageClip(img_path, duration=duration)

            # Apply transition if not first clip
            if transition == 'fade' and idx > 0:
                clip = clip.crossfadein(0.5)

            clips.append(clip)

        # Update progress: Concatenating
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'concatenating',
                'progress': 60,
                'message': 'Combining images into video...'
            }
        )

        # Concatenate clips
        final_video = concatenate_videoclips(clips, method="compose")

        # Add audio if provided
        if audio_id:
            self.update_state(
                state='PROGRESS',
                meta={
                    'stage': 'audio',
                    'progress': 65,
                    'message': 'Adding audio to video...'
                }
            )

            audio_path = safe_join_path(AUDIO_FOLDER, f"{audio_id}.webm")
            if os.path.exists(audio_path):
                audio_clip = AudioFileClip(audio_path)

                # Trim or loop audio to match video duration
                if audio_clip.duration > final_video.duration:
                    audio_clip = audio_clip.subclip(0, final_video.duration)
                elif audio_clip.duration < final_video.duration:
                    # Loop audio
                    loops_needed = int(final_video.duration / audio_clip.duration) + 1
                    audio_clip = audio_clip.loop(n=loops_needed).subclip(0, final_video.duration)

                final_video = final_video.set_audio(audio_clip)

        # Update progress: Encoding
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'encoding',
                'progress': 75,
                'message': 'Encoding video file...'
            }
        )

        # Parse resolution
        width, height = map(int, resolution.split('x'))
        final_video = final_video.resize(newsize=(width, height))

        # Write video file
        final_video.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            preset='medium',
            threads=4
        )

        # Cleanup
        final_video.close()
        for clip in clips:
            clip.close()

        # Update progress: Complete
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'message': 'Video generation complete!'
            }
        )

        return {
            'success': True,
            'video_path': output_path
        }

    except Exception as e:
        # Update progress: Error
        self.update_state(
            state='FAILURE',
            meta={
                'stage': 'error',
                'progress': 0,
                'message': str(e)
            }
        )
        return {'success': False, 'error': str(e)}
```

### Phase 3: Update Flask API

#### 3.1 Modify app.py
```python
from celery_app import celery_app
from tasks import generate_video_task
from celery.result import AsyncResult

# New endpoint: Enqueue video generation
@app.route('/generate_video', methods=['POST'])
@limiter.limit("5 per hour")
def generate_video():
    """Enqueue video generation job"""
    try:
        data = request.json
        session_id = data.get('session_id')
        audio_id = data.get('audio_id')
        duration = float(data.get('duration', 3))
        transition = data.get('transition', 'fade')
        resolution = data.get('resolution', '1920x1080')

        # Validate inputs
        if not session_id or not is_valid_uuid(session_id):
            return jsonify({'success': False, 'error': 'Invalid session ID'}), 400

        # Generate output file path
        output_id = str(uuid.uuid4())
        output_path = safe_join_path(OUTPUT_FOLDER, f"{output_id}.mp4")

        # Enqueue task
        task = generate_video_task.apply_async(
            args=[session_id, audio_id, duration, transition, resolution, output_path],
            task_id=output_id  # Use output_id as task_id for tracking
        )

        app.logger.info(f"Enqueued video generation task: {task.id}")

        return jsonify({
            'success': True,
            'job_id': task.id,
            'status_url': f'/job_status/{task.id}',
            'message': 'Video generation started'
        })

    except Exception as e:
        app.logger.error(f"Error enqueuing video generation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# New endpoint: Check job status
@app.route('/job_status/<job_id>')
def job_status(job_id):
    """Get status of a video generation job"""
    if not is_valid_uuid(job_id):
        return jsonify({'error': 'Invalid job ID'}), 400

    result = AsyncResult(job_id, app=celery_app)

    response = {
        'job_id': job_id,
        'state': result.state,
        'ready': result.ready(),
        'successful': result.successful() if result.ready() else None
    }

    if result.state == 'PROGRESS':
        # Get progress info
        response.update(result.info)
    elif result.state == 'SUCCESS':
        # Get result
        response['result'] = result.result
        response['download_url'] = f"/download/{job_id}"
    elif result.state == 'FAILURE':
        # Get error
        response['error'] = str(result.info)

    return jsonify(response)

# Update SSE endpoint to use Celery task state
@app.route('/progress/<job_id>')
def get_progress(job_id):
    """Server-Sent Events endpoint for real-time progress updates"""
    def generate():
        if not is_valid_uuid(job_id):
            yield f"data: {json.dumps({'error': 'Invalid job ID'})}\n\n"
            return

        yield f"data: {json.dumps({'connected': True})}\n\n"

        result = AsyncResult(job_id, app=celery_app)
        last_state = None
        timeout = 1800  # 30 minutes
        start_time = datetime.now()

        while True:
            if (datetime.now() - start_time).total_seconds() > timeout:
                yield f"data: {json.dumps({'error': 'Timeout'})}\n\n"
                break

            current_state = result.state
            current_info = result.info if result.info else {}

            if current_state != last_state or current_info != last_state:
                if result.state == 'PROGRESS':
                    yield f"data: {json.dumps(result.info)}\n\n"
                elif result.state == 'SUCCESS':
                    yield f"data: {json.dumps({'stage': 'completed', 'progress': 100})}\n\n"
                    break
                elif result.state == 'FAILURE':
                    yield f"data: {json.dumps({'stage': 'error', 'error': str(result.info)})}\n\n"
                    break

                last_state = current_state

            import time
            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')
```

### Phase 4: Railway Deployment Configuration

#### 4.1 Add Redis to Railway
1. In Railway project, click **"+ New"** → **"Database"** → **"Add Redis"**
2. Railway automatically creates `REDIS_URL` environment variable
3. Your app will auto-detect this and use it

#### 4.2 Create Procfile for Multiple Services
```procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
worker: celery -A celery_app worker --loglevel=info --concurrency=2
```

#### 4.3 Update Railway Configuration
- Add two services in Railway:
  1. **Web Service**: Runs Flask API (existing service)
  2. **Worker Service**: Runs Celery workers (new service)

Both services use the same codebase but different start commands.

#### 4.4 Environment Variables
```
REDIS_URL=(auto-created by Railway)
DATABASE_URL=(auto-created by Railway PostgreSQL)
ADMIN_PASSWORD=your_secure_password
PORT=(auto-created by Railway)
```

### Phase 5: Testing

#### 5.1 Local Testing
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A celery_app worker --loglevel=info

# Terminal 3: Start Flask app
python app.py
```

#### 5.2 Test Queue System
```bash
# Make multiple requests
curl -X POST http://localhost:5000/generate_video \
  -H "Content-Type: application/json" \
  -d '{"session_id":"...", "duration":3, "resolution":"1920x1080"}'

# Check job status
curl http://localhost:5000/job_status/JOB_ID

# Monitor with SSE
curl http://localhost:5000/progress/JOB_ID
```

## Benefits of This Implementation

### 1. **Scalability**
- Add more Celery workers to handle more concurrent jobs
- Workers can run on different machines/containers
- Redis provides distributed job queue

### 2. **Reliability**
- Jobs persisted in Redis survive server restarts
- Failed jobs can be retried automatically
- Task timeouts prevent hung processes

### 3. **Performance**
- Flask API responds immediately (non-blocking)
- Background processing doesn't tie up web server
- Concurrent job limits prevent resource exhaustion

### 4. **Monitoring**
- Track job progress in real-time
- Job history and statistics
- Failed job tracking and debugging

### 5. **User Experience**
- Users can submit job and close browser
- Multiple users can generate videos simultaneously
- Real-time progress updates via SSE

## Alternative: Simpler Solution (RQ - Redis Queue)

If Celery is too complex, consider **RQ (Redis Queue)** - a simpler alternative:

```python
from redis import Redis
from rq import Queue

redis_conn = Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
video_queue = Queue('video_generation', connection=redis_conn)

# Enqueue job
job = video_queue.enqueue(
    generate_video_sync,
    session_id, audio_id, duration, transition, resolution,
    job_timeout='30m'
)

# Check status
job = Job.fetch(job_id, connection=redis_conn)
print(job.get_status())
```

### RQ Pros:
- Much simpler than Celery
- Easier to understand and debug
- Good for small to medium scale

### RQ Cons:
- Fewer features than Celery
- Less mature ecosystem
- Limited scheduling capabilities

## Cost Considerations

### Railway Pricing for Redis
- **Free/Trial**: Not included
- **Hobby ($5/mo)**: 256MB Redis included
- **Pro ($20/mo)**: 1GB Redis included

### Alternative: External Redis Providers
- **Upstash**: Free tier (10,000 commands/day)
- **Redis Cloud**: Free 30MB
- **Railway Redis**: Upgrade to Hobby plan

## Migration Path

### Phase 1 (MVP - Current)
✅ In-memory progress tracking
✅ Synchronous video generation
✅ Server-Sent Events for progress

### Phase 2 (Next - Queue System)
- Add Redis + Celery
- Background job processing
- Job persistence
- Multiple workers

### Phase 3 (Future - Advanced)
- Job scheduling (generate at specific time)
- Batch processing
- Video quality presets
- Template system
- Cloud storage integration (S3, CloudFlare R2)

## Recommended Next Steps

1. **Start Small**: Implement with RQ first (simpler)
2. **Test Locally**: Ensure it works with Redis on local machine
3. **Deploy to Railway**: Add Redis database, update Procfile
4. **Monitor**: Watch logs and job success rates
5. **Optimize**: Adjust worker count and concurrency based on usage

## Conclusion

Implementing a queue system is essential for scaling Aiezzy Simvid beyond a few concurrent users. The proposed Celery + Redis solution provides:
- Non-blocking API
- Background processing
- Job persistence
- Real-time progress tracking
- Horizontal scalability

This investment will enable the application to handle production-level traffic and provide a professional user experience.