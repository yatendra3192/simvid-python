# Railway Setup - Quick Visual Guide

## Current Railway UI (2025)

### Step 1: Add PostgreSQL Database

1. In your Railway project dashboard
2. Click **"+ New"** button (top right or in canvas)
3. Select **"Database"**
4. Choose **"Add PostgreSQL"**
5. Done! `DATABASE_URL` is automatically created

### Step 2: Add Volume (ONE per service)

**IMPORTANT**: Railway only allows **1 volume per service**

#### Method 1: Right-click Menu
1. Right-click on your **"web"** service (the one showing `video.aiezzy.com`)
2. Select **"Add Variable"** section → Look for volume options
3. OR look for a **"Volume"** or **"Storage"** menu option

#### Method 2: Command Palette
1. Press **Cmd+K** (Mac) or **Ctrl+K** (Windows)
2. Type "volume" or "create volume"
3. Select your service
4. Set mount path: `/app/data`

#### Method 3: Service Settings
1. Click on your **"web"** service
2. Look for **"Settings"** or **"Data"** tab
3. Find **"Volume"** section
4. Click **"Add Volume"** or **"Create"**
5. Set **Mount Path**: `/app/data`

### Step 3: Push Code

```bash
git add .
git commit -m "Add PostgreSQL + Railway volume support"
git push
```

## What the Updated Code Does

### Automatic Detection
The app now automatically detects Railway environment:

```python
# Checks for Railway volume
RAILWAY_VOLUME = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')

if RAILWAY_VOLUME:
    # Uses: /app/data/uploads, /app/data/audio, /app/data/output
    print("✅ Using Railway volume")
else:
    # Uses: ./uploads, ./audio, ./output
    print("⚠️ Using local folders")
```

### Database Detection
```python
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Connects to PostgreSQL for admin tokens
    print("✅ Connected to PostgreSQL")
else:
    # Uses in-memory storage (resets on restart)
    print("⚠️ Using in-memory tokens")
```

## Expected Logs After Deploy

Success logs should show:
```
✅ Connected to PostgreSQL for admin sessions
✅ Using Railway volume: /app/data
Aiezzy Simvid - Slideshow Video Generator
Server starting at: http://0.0.0.0:8080
```

## Railway Volume Limits

| Plan | Volume Size | PostgreSQL |
|------|------------|------------|
| Free/Trial | 0.5 GB | 0.5 GB |
| Hobby ($5/mo) | 5 GB | 5 GB |
| Pro ($20/mo) | 50 GB | 50 GB |

**Note**: Video files can be large! 0.5GB fills up VERY quickly.

## Alternative: No Persistence

If you don't want to deal with volumes/costs:
- Skip adding PostgreSQL
- Skip adding Volume
- App works fine, but:
  - Admin sessions reset on each deploy
  - Uploaded files deleted on each deploy
  - Good for testing, not for production

## Troubleshooting

### "I don't see volume option"
- Make sure you're on the **web service** (not database)
- Try the Command Palette: **Cmd+K** → "create volume"
- Railway UI changes often - look for "Storage", "Data", or "Volumes"

### "Volume already exists error"
- You can only have 1 volume per service
- Delete existing volume first
- OR change mount path of existing volume to `/app/data`

### "Database connection failed"
- Check `DATABASE_URL` exists in Variables tab
- Verify PostgreSQL service is running (green status)
- Check Railway logs for connection errors

### "Still losing data on restart"
- Verify logs show: `✅ Using Railway volume: /app/data`
- Check volume is mounted to correct service
- Try restarting service after adding volume

## Quick Test

After deployment:
1. Login to admin panel
2. Upload images and generate a video
3. Trigger a manual redeploy in Railway
4. Check if you're still logged in (admin session)
5. Check if files are still there in admin panel

If both work → SUCCESS! ✅
If not → Check logs for warning messages

## Need Help?

Check Railway docs:
- https://docs.railway.com/reference/volumes
- https://docs.railway.com/guides/volumes

Or Railway Discord/Support for UI-specific questions.