# Railway Queue System Setup Guide

## Overview
This guide shows how to deploy Aiezzy Simvid with Redis Queue (RQ) on Railway for background video processing.

## Architecture

```
┌─────────────────┐
│   Web Service   │  (Flask API - handles HTTP requests)
│   Port: 8080    │
└─────────┬───────┘
          │
          ├──► Redis Database (Message broker)
          │
          ▼
┌─────────────────┐
│ Worker Service  │  (RQ Worker - processes video jobs)
│  (Background)   │
└─────────────────┘
```

## Step-by-Step Setup

### Step 1: Add Redis Database

1. Go to your Railway project dashboard
2. Click **"+ New"** → **"Database"** → **"Add Redis"**
3. Railway automatically creates `REDIS_URL` environment variable
4. Both services will use this Redis instance

### Step 2: Configure Web Service (Existing)

Your existing "web" service will automatically detect Redis:
- If `REDIS_URL` exists → Uses RQ (background jobs)
- If `REDIS_URL` is missing → Falls back to synchronous processing

**No changes needed** to your existing web service!

### Step 3: Create Worker Service

Railway requires a separate service for the RQ worker:

#### Option A: Using Railway Dashboard
1. In project dashboard, click **"+ New"** → **"Empty Service"**
2. Name it **"worker"**
3. Connect to same GitHub repository
4. Go to service **Settings** → **Deploy**
5. Set **Custom Start Command**: `python worker.py`
6. Deploy!

#### Option B: Using Procfile (Automatic)
Railway should automatically detect the `Procfile` and create both services:
- `web`: Flask API
- `worker`: RQ Worker

### Step 4: Verify Deployment

Check logs for each service:

**Web Service logs should show**:
```
✅ Connected to Redis Queue: redis://...
🚀 Server starting at: http://0.0.0.0:8080
```

**Worker Service logs should show**:
```
🚀 RQ Worker starting...
📡 Connected to Redis: redis://...
📋 Listening on queues: video_generation, default
```

### Step 5: Test the Queue System

1. Go to your app and upload images
2. Click "Generate Video"
3. Check **Worker logs** - you should see:
   ```
   [job-id] Starting video generation...
   [job-id] Found 5 images
   [job-id] Processing image 1/5 (20%)
   ...
   [job-id] ✅ Video generation complete!
   ```

## Environment Variables

Both services need access to:
- `REDIS_URL` (auto-created by Railway Redis)
- `DATABASE_URL` (if using PostgreSQL)
- `ADMIN_PASSWORD` (your secure password)
- `RAILWAY_VOLUME_MOUNT_PATH` (if using volume)

Railway automatically shares environment variables across services in the same project.

## How It Works

### With Redis Queue (Production Mode)
1. User clicks "Generate Video"
2. Flask API validates request
3. Job is enqueued in Redis
4. API returns immediately with `job_id`
5. Worker picks up job from queue
6. Worker processes video in background
7. User polls `/job_status/{job_id}` to check progress
8. When done, user downloads video

### Without Redis (Fallback Mode)
1. User clicks "Generate Video"
2. Flask API processes video synchronously
3. User waits 30-60 seconds for response
4. Video is ready immediately

## Benefits of Queue System

✅ **Non-blocking**: API responds instantly, no timeout issues
✅ **Scalable**: Add more workers to handle more concurrent jobs
✅ **Reliable**: Jobs persist in Redis even if worker restarts
✅ **Multiple users**: Many users can generate videos simultaneously
✅ **Better UX**: Progress updates work properly

## Cost

### Railway Pricing
- **Redis Database**:
  - Hobby ($5/mo): 256MB included
  - Pro ($20/mo): 1GB included
- **Worker Service**: Runs in background, uses same compute credits

### Alternative: Free Tier
If you don't add Redis:
- App runs in synchronous mode
- Still works, but:
  - Users must wait for video to finish
  - Only one video at a time
  - May hit Railway timeouts with large videos

## Monitoring

### Check Queue Status
You can check job status via API:
```bash
curl https://your-app.railway.app/job_status/{job_id}
```

### Watch Worker Logs
In Railway dashboard:
1. Click on **"worker"** service
2. View **Logs** tab
3. See real-time job processing

### Check Redis
```bash
# In Railway CLI or worker container
redis-cli -u $REDIS_URL
> LLEN rq:queue:video_generation  # Check queue length
> KEYS *  # List all keys
```

## Troubleshooting

### "Job not found" error
- Worker may not be running
- Check worker service logs
- Verify `REDIS_URL` is set

### Worker not processing jobs
- Check worker logs for errors
- Verify worker service is running (not crashed)
- Check Redis connection

### Videos still slow
- Add more worker services for parallel processing
- Each worker can process one video at a time
- 2-3 workers = handle 2-3 videos simultaneously

### Out of memory errors
- Reduce worker concurrency
- Add more RAM to worker service in Railway
- Enable swap if available

## Scaling

### Horizontal Scaling (More Workers)
1. Duplicate the worker service in Railway
2. Name them: worker-1, worker-2, worker-3
3. All listen to same Redis queue
4. Jobs distributed automatically

### Example with 3 Workers
```
Web Service → Redis Queue
                 ↓
            ┌────┴────┬────────┐
            ↓         ↓        ↓
        Worker 1  Worker 2  Worker 3
```

### Vertical Scaling (Bigger Workers)
- Increase RAM for video processing
- Set in Railway service settings
- Recommended: 2GB RAM per worker

## Local Development

### Start Redis locally
```bash
# Windows (using Docker)
docker run -d -p 6379:6379 redis

# Or install Redis locally
```

### Start Worker
```bash
python worker.py
```

### Start Flask App
```bash
python app.py
```

### Test
```bash
# Upload images and generate video
# Check worker terminal for job processing logs
```

## Production Checklist

- [ ] Redis database added
- [ ] Worker service created
- [ ] Both services showing green status
- [ ] Web logs show "Connected to Redis Queue"
- [ ] Worker logs show "RQ Worker starting"
- [ ] Test video generation works
- [ ] Check worker logs show job processing
- [ ] Verify `/job_status/{id}` endpoint works

## Next Steps

1. **Monitor Usage**: Watch Redis memory usage
2. **Scale Workers**: Add more if queue is backing up
3. **Set Alerts**: Get notified if worker crashes
4. **Optimize**: Profile video generation to make it faster

## Support

If you encounter issues:
1. Check Railway logs for both services
2. Verify environment variables are set
3. Test locally first
4. Check Redis connection from both services

---

**Note**: The app automatically falls back to synchronous mode if Redis is unavailable, so it will always work even without the queue system.