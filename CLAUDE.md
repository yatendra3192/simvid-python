# CLAUDE.md - Project Context for SimVid Python

## Project Overview
**SimVid Python** - A web-based slideshow video generator that creates MP4 videos from images with background music. Built with Flask (Python) backend and vanilla JavaScript frontend.

## Current Status (As of 2025-09-28 - Evening Update)

### What's Working ✅
- Python Flask server running successfully at http://localhost:5000
- Deployed to Railway at https://simvid-python-5b632.up.railway.app
- GitHub repository at https://github.com/yatendra3192/simvid-python
- YouTube audio download working (using yt-dlp)
- Drag & drop image upload interface
- Click to browse file selection
- Image preview with remove functionality
- Wake Lock API to prevent mobile screen sleep
- Basic UI with responsive design

### Issues to Fix ⚠️
1. **Video Generation** - MoviePy v2.x compatibility issues
   - Error: `'AudioFileClip' object has no attribute 'subclip'`
   - Need to either fix for v2.x or downgrade to v1.0.3

2. **Image Upload on Deployment** - Works locally but issues on Railway
   - File picker opens but images don't load properly
   - Added extensive console logging for debugging

3. **FFmpeg Dependency** - Not in system PATH
   - Currently working without conversion
   - Need to bundle or ensure availability on Railway

## Today's Development Session (2025-09-28)

### Deployment to Railway
1. **Initial Deployment Issues**
   - Pillow version conflict (11.3.0 vs MoviePy requirement <11.0)
   - Fixed by downgrading Pillow to 10.4.0

2. **Mobile Screen Sleep Issue**
   - Problem: "Failed to fetch" error when mobile screen sleeps
   - Solution implemented:
     - Added Wake Lock API to prevent screen sleep
     - Added AbortController with 5-minute timeout for video, 2-minute for audio
     - Added keepalive flag to fetch requests
     - Better error handling with specific timeout messages

3. **Drag & Drop Not Working**
   - Problem: Click and drag weren't triggering file picker
   - Solutions implemented:
     - Wrapped event listeners in DOMContentLoaded
     - Moved file input outside upload area
     - Added explicit "Select Images" button as fallback
     - Added pointer-events: none to child elements
     - Simplified click event handlers

4. **Image Upload Issues**
   - Problem: File picker opens but images don't load
   - Debugging added:
     - Extensive console logging at every step
     - File type validation and logging
     - Server response logging
     - DOM element existence checks

### Code Changes Made Today

#### Frontend (templates/index.html)
- Added Wake Lock API implementation
- Improved drag & drop event handling
- Added AbortController for timeout management
- Enhanced error messages for better UX
- Added console logging for debugging
- Fixed event listener attachment issues
- Added fallback "Select Images" button

#### Backend (app.py)
- Added timeout configuration
- Improved error handling
- Added signal and threading imports for future timeout handling

#### Dependencies (requirements.txt)
- Downgraded Pillow from 11.3.0 to 10.4.0 for MoviePy compatibility
- Added gunicorn for Railway deployment

## File Structure
```
simvid-python/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Web interface with JS
├── audio/                # Downloaded YouTube audio
├── uploads/              # User uploaded images
├── output/               # Generated videos
├── static/               # Static assets (empty)
├── Procfile             # Railway deployment config
├── nixpacks.toml        # Railway build config
├── railway.json         # Railway project config
├── push-to-github.bat   # Windows deployment script
├── run.bat              # Local run script
└── CLAUDE.md           # This documentation file
```

## Key Technical Details

### Wake Lock Implementation
```javascript
// Prevents screen sleep during processing
let wakeLock = null;
async function requestWakeLock() {
    if ('wakeLock' in navigator) {
        wakeLock = await navigator.wakeLock.request('screen');
    }
}
```

### Timeout Handling
```javascript
// 5-minute timeout for video generation
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 300000);
```

### Console Debugging
- Open browser DevTools (F12)
- Check Console tab for detailed logs
- Every step of file handling is logged

## Testing Checklist

### Local Testing
- [x] Server starts on port 5000
- [x] Image upload via click
- [x] Image upload via drag & drop
- [x] YouTube audio download
- [x] Image preview display
- [ ] Video generation (MoviePy issues)

### Deployment Testing
- [x] Railway deployment successful
- [x] Server accessible via public URL
- [x] Mobile screen sleep prevention
- [ ] Image upload functionality (debugging in progress)
- [ ] Video generation

## Tomorrow's Priority Tasks

1. **Fix Image Upload on Deployment**
   - Check console logs from user testing
   - Verify CORS settings
   - Check file size limits on Railway
   - Test with different image formats

2. **Fix MoviePy Video Generation**
   - Option 1: Fix code for MoviePy v2.x compatibility
   - Option 2: Downgrade to MoviePy v1.0.3
   - Option 3: Switch to OpenCV for video generation

3. **Add Progress Indicators**
   - Real-time upload progress
   - Video generation progress
   - Better loading states

4. **Error Recovery**
   - Add retry mechanisms
   - Better error messages
   - Graceful degradation

## Useful Commands

### Local Development
```bash
# Navigate to project
cd C:/Users/User/Desktop/simvid-python

# Run locally
python app.py
# OR
run.bat

# Access at: http://localhost:5000
```

### Deployment
```bash
# Push to GitHub (auto-deploys to Railway)
git add -A
git commit -m "Your message"
git push

# Check Railway logs
# Visit Railway dashboard for logs
```

### Debugging
```javascript
// In browser console
// Check if elements exist
document.getElementById('imageUploadArea')
document.getElementById('imageInput')

// Check file input
document.getElementById('imageInput').click()

// Check console logs
// Look for "handleImageFiles called" message
```

## Environment Variables (Railway)
- PORT: Automatically set by Railway
- No other env vars currently needed

## Dependencies
- Flask 3.1.2
- flask-cors 6.0.1
- moviepy 2.1.2 (has issues, consider downgrade)
- yt-dlp 2025.9.26
- Pillow 10.4.0 (downgraded for compatibility)
- numpy 2.3.3
- werkzeug 3.1.3
- gunicorn 21.2.0 (production server)

## Known Issues & Solutions

### Issue: "Failed to fetch" on mobile
**Solution:** Wake Lock API implemented to prevent screen sleep

### Issue: Drag & drop not working
**Solution:** Event listeners wrapped in DOMContentLoaded, added fallback button

### Issue: Images not loading after selection
**Status:** Debugging in progress with extensive console logging

### Issue: MoviePy video generation fails
**Status:** Needs MoviePy version fix or alternative library

## Contact & Resources
- GitHub Repo: https://github.com/yatendra3192/simvid-python
- Railway App: https://simvid-python-5b632.up.railway.app
- Local Dev: http://localhost:5000

## Session Notes
- Started with deployment to Railway
- Fixed multiple frontend issues (mobile sleep, drag & drop)
- Added comprehensive debugging
- Project is live but needs image upload fix for full functionality

---
*Last updated: 2025-09-28 Evening - Deployment and bug fixing session*