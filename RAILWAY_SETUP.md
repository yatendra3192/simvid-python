# Railway Setup Guide - Fix Data Loss on Restart

## Problem
When Railway redeploys your app, all data (admin sessions, uploaded files, audio, videos) is lost because Railway uses **ephemeral storage**.

## Solution: PostgreSQL + Volumes

### Step 1: Add PostgreSQL Database

1. Go to your Railway project dashboard
2. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
3. Railway will automatically create a `DATABASE_URL` environment variable
4. Your app will auto-detect this and use it for admin sessions

### Step 2: Add Persistent Volume (for files)

**IMPORTANT**: Railway only allows **ONE volume per service**

#### Solution: Use a single volume for all data

1. Go to your service → Right-click or press `⌘K` (Command Palette)
2. Select **"Create Volume"**
3. Set **Mount Path** = `/app/data`
4. We'll reorganize folders to use this single volume

### Step 3: Update Code for Single Volume

The code has been updated to automatically detect and use Railway's volume:
- Checks for `RAILWAY_VOLUME_MOUNT_PATH` environment variable
- Creates subdirectories: `uploads/`, `audio/`, `output/` inside the volume
- Falls back to local folders for development

### Step 4: Deploy Changes

```bash
git add .
git commit -m "Add PostgreSQL support and Railway volume for persistent storage"
git push
```

Railway will automatically:
- Install PostgreSQL library (`psycopg2-binary`)
- Detect `DATABASE_URL` and create admin_tokens table
- Detect `RAILWAY_VOLUME_MOUNT_PATH` and use it for file storage
- Persist both admin sessions and files across restarts

## How It Works

### Admin Sessions (DATABASE)
- ✅ Admin login tokens stored in PostgreSQL
- ✅ Survives restarts and redeploys
- ✅ Auto-cleanup of expired tokens (24h)
- ✅ Fallback to in-memory if DB unavailable

### User Files (VOLUME - Single Mount Point)
- ✅ All files stored in single volume at `/app/data`
- ✅ Organized into subdirectories:
  - `/app/data/uploads` - Uploaded images
  - `/app/data/audio` - Downloaded audio
  - `/app/data/output` - Generated videos
- ✅ Files survive restarts and redeploys
- ✅ Auto-created on first use

## Verification

After deployment, check Railway logs for:
```
✅ Connected to PostgreSQL for admin sessions
✅ Using Railway volume: /app/data
```

If you see warnings:
```
⚠️ No DATABASE_URL found, using in-memory admin tokens (will reset on restart)
⚠️ No Railway volume found, using local folders
```
Then PostgreSQL or Volume is not configured properly.

## Cost

Railway Free/Trial Tier includes:
- **PostgreSQL**: 0.5GB storage
- **Volume**: 0.5GB storage (only 1 volume per service allowed)
- **Important**: Railway limits on free tier may fill up quickly with videos!

Railway Hobby Plan ($5/month):
- **PostgreSQL**: 5GB storage
- **Volume**: 5GB storage
- Much better for video generation app

Railway Pro Plan ($20/month):
- **PostgreSQL**: 50GB storage
- **Volume**: 50GB storage (can grow up to 250GB)

## Alternative: Clean Slate on Each Deploy

If you DON'T want persistence (fresh start each deploy), you can:
1. Skip PostgreSQL setup
2. Skip volumes setup
3. App will work but data resets on restart

This might be okay if users only do one-time video generation and don't need admin persistence.

## Recommended Environment Variables

In Railway → Variables tab:
```
ADMIN_PASSWORD=your_secure_password_here  # Change from default "admin123"
DATABASE_URL=(auto-created by Railway)
PORT=(auto-created by Railway)
```

## Troubleshooting

### Database connection errors
- Check PostgreSQL is provisioned in Railway
- Verify DATABASE_URL exists in environment variables
- Check Railway logs for connection errors

### Files still disappearing
- Verify volume is created and mounted to `/app/data`
- Check logs for: `✅ Using Railway volume: /app/data`
- Restart service after adding volume
- Remember: Only ONE volume per service in Railway!

### Admin sessions lost
- Check if `✅ Connected to PostgreSQL` appears in logs
- Verify psycopg2-binary is installed
- Try manually running: `pip install psycopg2-binary`