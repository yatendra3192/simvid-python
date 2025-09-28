# CLAUDE.md - Project Context for Aiezzy Simvid

## Project Overview
**Aiezzy Simvid** - A web-based slideshow video generator that creates MP4 videos from images with background music. Built with Flask (Python) backend and vanilla JavaScript frontend.

## Current Status (As of 2025-09-28 - Late Evening Update)

### What's Working ✅
- ✅ Python Flask server running successfully at http://localhost:5000
- ✅ Deployed to Railway at https://web-production-5b632.up.railway.app
- ✅ GitHub repository at https://github.com/yatendra3192/simvid-python
- ✅ **IMAGE UPLOAD FIXED** - Complete rewrite, now working perfectly!
- ✅ Drag & drop image upload working
- ✅ Click to browse file selection working
- ✅ Image preview with remove functionality
- ✅ YouTube audio download (using yt-dlp)
- ✅ Auto-download YouTube audio on video generation
- ✅ Image orientation fixed (EXIF data handled)
- ✅ Wake Lock API prevents mobile screen sleep
- ✅ Clean, simplified UI with better UX

### Issues Still to Fix ⚠️
1. **Video Generation** - MoviePy v2.x compatibility issues
   - Error: `'AudioFileClip' object has no attribute 'subclip'`
   - Need to either fix for v2.x or downgrade to v1.0.3
   - Videos generate without audio currently

2. **FFmpeg Dependency** - Not in system PATH on Railway
   - Currently working without conversion
   - Need to bundle or ensure availability on Railway

## Today's Development Session (2025-09-28 - Second Session)

### Major Fixes Implemented

#### 1. **FIXED: Image Upload Not Working** ✅
- **Problem**: Multiple issues - reference errors, timing problems, complex broken code
- **Solution**: Complete rewrite of index.html
  - Removed all inline onclick handlers
  - All functions defined in DOMContentLoaded
  - Simplified handleImageFiles function
  - Used URL.createObjectURL for instant previews
  - Clean event listener setup
- **Result**: Upload now works perfectly via click and drag & drop

#### 2. **FIXED: Image Orientation Issue** ✅
- **Problem**: Vertical photos from phones appearing horizontal in videos
- **Solution**: Added EXIF orientation handling
  ```python
  def fix_image_orientation(img):
      # Reads EXIF orientation tag
      # Rotates image accordingly (90°, 180°, 270°)
  ```
- **Result**: Phone photos now maintain correct orientation

#### 3. **UI/UX Improvements** ✅
- **Simplified Audio Workflow**:
  - Removed separate "Download Audio" button
  - YouTube audio now downloads automatically during video generation
  - One-click process instead of two steps
- **Better Error Handling**:
  - Added warning status for non-critical issues
  - Graceful fallback if audio download fails
- **Clearer Instructions**:
  - Added helpful text explaining automatic features

### Earlier Session Fixes (From First Session)

1. **Deployment Issues**
   - Fixed Pillow version conflict (downgraded to 10.4.0)
   - Successfully deployed to Railway

2. **Mobile Screen Sleep**
   - Added Wake Lock API
   - Added timeout controls
   - Better connection handling

3. **Initial Upload Attempts**
   - Multiple debugging iterations with GPT-5 assistance
   - Added extensive console logging
   - Eventually led to complete rewrite

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

### Local Testing ✅
- [x] Server starts on port 5000
- [x] Image upload via click
- [x] Image upload via drag & drop
- [x] YouTube audio download
- [x] Image preview display
- [x] Image orientation preserved
- [x] Video generation (works but without audio)

### Deployment Testing ✅
- [x] Railway deployment successful
- [x] Server accessible via public URL
- [x] Mobile screen sleep prevention
- [x] Image upload functionality - FIXED!
- [x] Drag and drop working
- [x] YouTube URL auto-download
- [ ] Video generation with audio (MoviePy issue)

## Tomorrow's Priority Tasks

### CRITICAL - Must Fix
1. **Fix MoviePy Audio Integration**
   - Current issue: Videos generate without audio
   - Error: `'AudioFileClip' object has no attribute 'subclip'`
   - Solutions to try:
     ```python
     # Option 1: Use set_duration instead of subclip
     audio_clip = AudioFileClip(audio_path).set_duration(video.duration)

     # Option 2: Downgrade MoviePy
     pip install moviepy==1.0.3

     # Option 3: Use different audio method
     from moviepy.audio.io.AudioFileClip import AudioFileClip
     ```

2. **Add FFmpeg to Railway Deployment**
   - Create nixpacks.toml with ffmpeg
   - Or use buildpack with ffmpeg included
   - Required for proper audio/video processing

### Nice to Have
3. **Add Video Generation Progress**
   - Real-time progress updates during generation
   - Show estimated time remaining
   - Better user feedback during long operations

4. **Add More Transitions**
   - Currently only fade works
   - Add slide, zoom, dissolve effects
   - Make transition duration adjustable

5. **Optimize for Large Videos**
   - Add chunked processing for many images
   - Implement queue system for multiple requests
   - Add file size warnings

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

## Session Summary (2025-09-28)

### Major Achievements Today 🎉
1. **Image Upload - COMPLETELY FIXED**
   - Was the main blocker, now working perfectly
   - Complete rewrite with clean, simple code
   - Both click and drag & drop functional

2. **Image Orientation - FIXED**
   - EXIF data properly handled
   - Vertical photos stay vertical

3. **UI/UX - GREATLY IMPROVED**
   - Simplified workflow (auto-download YouTube audio)
   - Better error handling and user feedback
   - Cleaner, more intuitive interface

### What's Left
- **Main Issue**: MoviePy audio integration (videos work but no sound)
- **Minor**: FFmpeg on Railway deployment

### Development Stats
- **Commits Today**: 10+
- **Files Changed**: Primarily index.html (complete rewrite) and app.py
- **Lines Changed**: 1000+ lines
- **Deployment URL**: https://web-production-5b632.up.railway.app

### Key Learning
- Sometimes a complete rewrite is better than patching broken code
- Simple, direct implementations often work better than complex ones
- GPT-5 analysis was helpful in identifying the core issues

---
*Last updated: 2025-09-28 Late Evening - Major fixes completed, app is now functional!*