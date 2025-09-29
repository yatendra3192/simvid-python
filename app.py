"""
Aiezzy Simvid - Slideshow Video Generator with YouTube Audio
A complete Python application for creating slideshow videos from images with background music
"""

import os
import json
import uuid
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, url_for, send_from_directory, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
import signal
import threading
# Import moviepy components
try:
    from moviepy import *
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, concatenate_audioclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: MoviePy not properly installed. Video generation may not work.")
import yt_dlp
from PIL import Image, ExifTags
import numpy as np

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Use Railway volume if available, otherwise use local folders
# Railway only allows one volume per service, so we organize everything under /data
RAILWAY_VOLUME = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', None)
if RAILWAY_VOLUME:
    # Production: Use Railway volume
    app.config['UPLOAD_FOLDER'] = os.path.join(RAILWAY_VOLUME, 'uploads')
    app.config['OUTPUT_FOLDER'] = os.path.join(RAILWAY_VOLUME, 'output')
    app.config['AUDIO_FOLDER'] = os.path.join(RAILWAY_VOLUME, 'audio')
    print(f"✅ Using Railway volume: {RAILWAY_VOLUME}")
else:
    # Development: Use local folders
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['OUTPUT_FOLDER'] = 'output'
    app.config['AUDIO_FOLDER'] = 'audio'
    print("⚠️ No Railway volume found, using local folders")

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for development
app.config['REQUEST_TIMEOUT'] = 300  # 5 minute timeout

# Allowed extensions
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac', 'ogg', 'webm', 'opus'}

# Create necessary folders (using the configured paths)
for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'], app.config['AUDIO_FOLDER'], 'static']:
    os.makedirs(folder, exist_ok=True)
    print(f"✅ Created/verified folder: {folder}")

def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def fix_image_orientation(img):
    """Fix image orientation based on EXIF data"""
    try:
        # Get EXIF data
        exif = img._getexif()
        if exif is None:
            return img

        # Find orientation tag
        orientation_key = None
        for key, value in ExifTags.TAGS.items():
            if value == 'Orientation':
                orientation_key = key
                break

        if orientation_key is None:
            return img

        orientation = exif.get(orientation_key)

        # Apply rotation based on orientation
        if orientation == 3:
            img = img.rotate(180, expand=True)
        elif orientation == 6:
            img = img.rotate(270, expand=True)
        elif orientation == 8:
            img = img.rotate(90, expand=True)

    except (AttributeError, KeyError, IndexError):
        # No EXIF data or orientation info
        pass

    return img

def clean_old_files():
    """Clean files older than 1 hour"""
    import time
    current_time = time.time()

    for folder in ['uploads', 'output', 'audio']:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.getmtime(filepath) < current_time - 3600:  # 1 hour
                    try:
                        if os.path.isfile(filepath):
                            os.remove(filepath)
                        elif os.path.isdir(filepath):
                            shutil.rmtree(filepath)
                    except:
                        pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_images', methods=['POST'])
def upload_images():
    """Handle multiple image uploads"""
    if 'images' not in request.files:
        return jsonify({'error': 'No images provided'}), 400

    files = request.files.getlist('images')
    session_id = str(uuid.uuid4())
    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    os.makedirs(session_folder, exist_ok=True)

    uploaded_files = []

    for file in files:
        if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
            filename = secure_filename(file.filename)
            filepath = os.path.join(session_folder, filename)
            file.save(filepath)
            uploaded_files.append({
                'filename': filename,
                'path': filepath
            })

    if not uploaded_files:
        return jsonify({'error': 'No valid images uploaded'}), 400

    return jsonify({
        'success': True,
        'session_id': session_id,
        'images': uploaded_files,
        'count': len(uploaded_files)
    })

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """Handle audio file upload"""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    file = request.files['audio']

    if file and allowed_file(file.filename, ALLOWED_AUDIO_EXTENSIONS):
        audio_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        audio_filename = f"{audio_id}.{ext}"
        filepath = os.path.join(app.config['AUDIO_FOLDER'], audio_filename)
        file.save(filepath)

        # Get audio duration
        try:
            audio_clip = AudioFileClip(filepath)
            duration = audio_clip.duration
            audio_clip.close()
        except:
            duration = 0

        return jsonify({
            'success': True,
            'audio_id': audio_id,
            'filename': filename,
            'duration': duration
        })

    return jsonify({'error': 'Invalid audio file'}), 400

@app.route('/download_youtube', methods=['POST'])
def download_youtube():
    """Download audio from YouTube URL with optional time trimming"""
    data = request.get_json()
    url = data.get('url')
    start_time = data.get('start_time')  # in seconds
    end_time = data.get('end_time')  # in seconds

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    audio_id = str(uuid.uuid4())
    output_path = os.path.join(app.config['AUDIO_FOLDER'], audio_id)

    # Build download options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{output_path}_full.%(ext)s",  # Download full first
        'quiet': True,
        'no_warnings': True,
        'extractaudio': True,
    }

    # Add download sections if times are specified
    # Note: yt-dlp supports download_sections for newer versions
    if start_time is not None or end_time is not None:
        sections = []
        if start_time is not None and end_time is not None:
            # Download specific section
            ydl_opts['download_ranges'] = lambda info_dict, ydl: [{'start_time': start_time, 'end_time': end_time}]
            # Store the times for later trimming
            trim_needed = True
            trim_start = start_time
            trim_end = end_time
        else:
            trim_needed = False
            trim_start = None
            trim_end = None
    else:
        trim_needed = False
        trim_start = None
        trim_end = None

    # For now, download full and trim after (more reliable)
    ydl_opts['outtmpl'] = f"{output_path}.%(ext)s"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown')
            full_duration = info.get('duration', 0)

            # Find the downloaded file
            audio_files = list(Path(app.config['AUDIO_FOLDER']).glob(f"{audio_id}.*"))
            if audio_files:
                audio_file = str(audio_files[0])
                duration = full_duration

                # Format time info for response if times were specified
                time_info = ""
                if start_time is not None or end_time is not None:
                    # Store trimming info in filename for later use during video generation
                    # Since MoviePy audio trimming has issues, we'll handle it during video generation
                    start_str = f"{int(start_time//60)}:{int(start_time%60):02d}" if start_time else "0:00"
                    end_str = f"{int(end_time//60)}:{int(end_time%60):02d}" if end_time else f"{int(full_duration//60)}:{int(full_duration%60):02d}"
                    time_info = f" ({start_str} - {end_str})"

                    # Save trim info for later use
                    trim_info_file = os.path.join(app.config['AUDIO_FOLDER'], f"{audio_id}_trim.json")
                    with open(trim_info_file, 'w') as f:
                        json.dump({'start': start_time, 'end': end_time}, f)

                    # Calculate trimmed duration
                    if start_time is not None and end_time is not None:
                        duration = end_time - start_time
                    elif end_time is not None:
                        duration = end_time
                    elif start_time is not None:
                        duration = full_duration - start_time

                return jsonify({
                    'success': True,
                    'audio_id': audio_id,
                    'title': title + time_info,
                    'duration': duration,
                    'filename': os.path.basename(audio_file),
                    'trimmed': (start_time is not None or end_time is not None)
                })
            else:
                return jsonify({'error': 'Audio file not created'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_video', methods=['POST'])
def generate_video():
    """Generate slideshow video from images with optional audio"""
    data = request.get_json()

    session_id = data.get('session_id')
    audio_id = data.get('audio_id')
    duration_per_image = float(data.get('duration', 2))
    transition = data.get('transition', 'fade')
    resolution = data.get('resolution', '1280x720')

    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400

    # Parse resolution
    width, height = map(int, resolution.split('x'))

    # Get images
    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_folder):
        return jsonify({'error': 'Session not found'}), 404

    image_files = sorted([
        os.path.join(session_folder, f)
        for f in os.listdir(session_folder)
        if allowed_file(f, ALLOWED_IMAGE_EXTENSIONS)
    ])

    if not image_files:
        return jsonify({'error': 'No images found'}), 400

    try:
        # Create video clips from images
        clips = []

        for img_path in image_files:
            # Load and resize image
            img = Image.open(img_path)

            # Fix orientation based on EXIF data
            img = fix_image_orientation(img)

            img = img.convert('RGB')

            # Calculate scaling to fit within resolution while maintaining aspect ratio
            img_ratio = img.width / img.height
            video_ratio = width / height

            if img_ratio > video_ratio:
                # Image is wider
                new_width = width
                new_height = int(width / img_ratio)
            else:
                # Image is taller
                new_height = height
                new_width = int(height * img_ratio)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Create black background
            background = Image.new('RGB', (width, height), (0, 0, 0))

            # Paste image centered
            x = (width - new_width) // 2
            y = (height - new_height) // 2
            background.paste(img, (x, y))

            # Convert to numpy array
            frame = np.array(background)

            # Create video clip
            clip = ImageClip(frame, duration=duration_per_image)

            # Apply transitions (simplified without effects for compatibility)
            # Transitions removed due to moviepy version compatibility

            clips.append(clip)

        # Concatenate all clips
        final_video = concatenate_videoclips(clips, method="compose")

        # Add audio if provided
        if audio_id:
            audio_files = list(Path(app.config['AUDIO_FOLDER']).glob(f"{audio_id}.*"))
            if audio_files:
                try:
                    audio_path = str(audio_files[0])
                    print(f"Loading audio from: {audio_path}")
                    audio_clip = AudioFileClip(audio_path)

                    # Check if there's trim information
                    trim_info_file = os.path.join(app.config['AUDIO_FOLDER'], f"{audio_id}_trim.json")
                    if os.path.exists(trim_info_file):
                        with open(trim_info_file, 'r') as f:
                            trim_info = json.load(f)
                            start_time = trim_info.get('start', 0) or 0
                            end_time = trim_info.get('end', None)

                            # Get actual audio duration and validate trim times
                            actual_duration = audio_clip.duration if hasattr(audio_clip, 'duration') else None

                            if actual_duration:
                                # Ensure start time is within bounds
                                start_time = min(max(0, start_time), actual_duration)

                                # Ensure end time is within bounds
                                if end_time is not None:
                                    end_time = min(max(start_time, end_time), actual_duration)

                                print(f"Audio duration: {actual_duration}, Applying trim: start={start_time}, end={end_time}")

                                # Only trim if there's actually something to trim
                                if start_time > 0 or (end_time is not None and end_time < actual_duration):
                                    # Apply trimming using MoviePy 2.x compatible method
                                    # Try different methods for compatibility
                                    try:
                                        if end_time:
                                            audio_clip = audio_clip.subclipped(start_time, end_time)
                                        elif start_time > 0:
                                            audio_clip = audio_clip.subclipped(start_time)
                                    except AttributeError:
                                        # Fallback for MoviePy 2.x
                                        try:
                                            if end_time:
                                                audio_clip = audio_clip.with_subclip(start_time, end_time)
                                            elif start_time > 0:
                                                audio_clip = audio_clip.with_subclip(start_time, None)
                                        except:
                                            # Last resort: create new clip with specific duration
                                            print(f"Using duration-based trimming")
                                            if end_time:
                                                new_duration = end_time - start_time
                                                # Use with_subclip for a safer approach
                                                try:
                                                    audio_clip = audio_clip.subclipped(0, new_duration)
                                                except:
                                                    audio_clip = audio_clip.with_duration(new_duration)
                                else:
                                    print(f"Trim times out of bounds or unnecessary, using full audio")
                            else:
                                print(f"Could not get audio duration, skipping trim")

                    # Get durations
                    video_duration = final_video.duration
                    audio_duration = audio_clip.duration if hasattr(audio_clip, 'duration') else None

                    print(f"Video duration: {video_duration}, Audio duration: {audio_duration}")

                    # MoviePy 2.x compatible audio handling
                    if audio_duration and video_duration:
                        if audio_duration > video_duration:
                            # Trim audio to match video length
                            audio_clip = audio_clip.with_duration(video_duration)
                        elif audio_duration < video_duration:
                            # Loop audio to match video length
                            n_loops = int(video_duration / audio_duration) + 1
                            audio_clips = [audio_clip] * n_loops
                            audio_clip = concatenate_audioclips(audio_clips).with_duration(video_duration)

                    # Set audio to video using MoviePy 2.x method
                    final_video = final_video.with_audio(audio_clip)
                    print("Audio successfully added to video")
                except Exception as e:
                    print(f"Warning: Could not add audio - {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue without audio

        # Generate output filename
        output_id = str(uuid.uuid4())
        output_filename = f"{output_id}.mp4"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

        # Calculate bitrate based on resolution
        total_pixels = width * height
        if total_pixels >= 3840 * 2160:  # 4K
            bitrate = "20000k"
        elif total_pixels >= 2560 * 1440:  # 1440p
            bitrate = "12000k"
        elif total_pixels >= 1920 * 1080:  # 1080p
            bitrate = "8000k"
        elif total_pixels >= 1280 * 720:  # 720p
            bitrate = "5000k"
        else:  # Lower resolutions
            bitrate = "2500k"

        # Write video file with optimized settings
        final_video.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            bitrate=bitrate,
            preset='medium',  # Balance between speed and compression
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            logger=None  # Disable moviepy console output
        )

        # Clean up
        final_video.close()

        return jsonify({
            'success': True,
            'video_id': output_id,
            'filename': output_filename,
            'download_url': f'/download/{output_id}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<video_id>')
def download_video(video_id):
    """Download generated video"""
    video_files = list(Path(app.config['OUTPUT_FOLDER']).glob(f"{video_id}.*"))
    if video_files:
        return send_file(
            str(video_files[0]),
            as_attachment=True,
            download_name=f'slideshow_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
        )
    return jsonify({'error': 'Video not found'}), 404

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

# Clean old files periodically
@app.before_request
def before_request():
    # Clean old files occasionally (1 in 100 requests)
    import random
    if random.randint(1, 100) == 1:
        clean_old_files()

# ==================== ADMIN ROUTES ====================
import hashlib
import secrets
import time

# Admin configuration
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Change this in production!

# Database setup for admin tokens (persistent across restarts)
DATABASE_URL = os.environ.get('DATABASE_URL', None)
admin_tokens = {}  # Fallback in-memory storage

# Initialize database if available
if DATABASE_URL:
    try:
        import psycopg2
        from urllib.parse import urlparse

        # Parse DATABASE_URL
        parsed = urlparse(DATABASE_URL)

        def get_db_connection():
            return psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password,
                sslmode='require'
            )

        # Create admin_tokens table if not exists
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_tokens (
                token VARCHAR(64) PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()

        print("✅ Connected to PostgreSQL for admin sessions")
    except Exception as e:
        print(f"⚠️ Database connection failed, using in-memory tokens: {e}")
        DATABASE_URL = None
else:
    print("⚠️ No DATABASE_URL found, using in-memory admin tokens (will reset on restart)")

def generate_token():
    """Generate a secure random token"""
    return secrets.token_hex(32)

def store_admin_token(token):
    """Store admin token (in database if available)"""
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO admin_tokens (token) VALUES (%s)", (token,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error storing token in DB: {e}")
            # Fallback to in-memory
            admin_tokens[token] = time.time()
    else:
        admin_tokens[token] = time.time()

def verify_admin_token(token):
    """Verify if the provided token is valid"""
    if not token:
        return False

    if DATABASE_URL:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            # Check if token exists and is not expired (24 hours)
            cur.execute("""
                SELECT created_at FROM admin_tokens
                WHERE token = %s
                AND created_at > NOW() - INTERVAL '24 hours'
            """, (token,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            return result is not None
        except Exception as e:
            print(f"Error verifying token in DB: {e}")
            # Fallback to in-memory
            pass

    # Fallback to in-memory check
    if token in admin_tokens:
        # Check if token is not expired (24 hours)
        if time.time() - admin_tokens[token] < 86400:
            return True
        else:
            del admin_tokens[token]
    return False

def cleanup_expired_tokens():
    """Remove expired tokens from database"""
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM admin_tokens WHERE created_at < NOW() - INTERVAL '24 hours'")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error cleaning expired tokens: {e}")

@app.route('/admin')
def admin_page():
    """Serve admin dashboard page"""
    return render_template('admin.html')

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Admin login endpoint"""
    data = request.get_json()
    password = data.get('password', '')

    if password == ADMIN_PASSWORD:
        token = generate_token()
        store_admin_token(token)  # Store in DB or memory
        cleanup_expired_tokens()  # Clean old tokens
        return jsonify({'success': True, 'token': token})
    return jsonify({'success': False, 'error': 'Invalid password'}), 401

@app.route('/admin/verify')
def admin_verify():
    """Verify admin token"""
    token = request.headers.get('Authorization')
    if verify_admin_token(token):
        return jsonify({'valid': True})
    return jsonify({'valid': False}), 401

@app.route('/admin/data')
def admin_data():
    """Get dashboard data for admin"""
    token = request.headers.get('Authorization')
    if not verify_admin_token(token):
        return jsonify({'error': 'Unauthorized'}), 401

    # Collect statistics
    stats = {
        'image_sessions': 0,
        'audio_files': 0,
        'videos': 0,
        'total_size': 0
    }

    # Get image sessions
    image_sessions = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for session_id in os.listdir(app.config['UPLOAD_FOLDER']):
            session_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
            if os.path.isdir(session_path):
                session_data = {
                    'session_id': session_id,
                    'created': os.path.getctime(session_path),
                    'images': [],
                    'image_count': 0,
                    'total_size': 0
                }

                for img_file in os.listdir(session_path):
                    img_path = os.path.join(session_path, img_file)
                    if os.path.isfile(img_path):
                        size = os.path.getsize(img_path)
                        session_data['images'].append({
                            'name': img_file,
                            'size': size
                        })
                        session_data['total_size'] += size
                        stats['total_size'] += size

                session_data['image_count'] = len(session_data['images'])
                if session_data['image_count'] > 0:
                    image_sessions.append(session_data)
                    stats['image_sessions'] += 1

    # Get audio files
    audio_files = []
    if os.path.exists(app.config['AUDIO_FOLDER']):
        for audio_file in os.listdir(app.config['AUDIO_FOLDER']):
            if audio_file.endswith('_trim.json'):
                continue  # Skip trim info files

            audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_file)
            if os.path.isfile(audio_path):
                audio_id = audio_file.rsplit('.', 1)[0]
                size = os.path.getsize(audio_path)

                # Check for trim info
                trim_file = os.path.join(app.config['AUDIO_FOLDER'], f"{audio_id}_trim.json")
                trimmed = os.path.exists(trim_file)

                # Try to get duration
                duration = None
                try:
                    if MOVIEPY_AVAILABLE:
                        audio_clip = AudioFileClip(audio_path)
                        duration = audio_clip.duration
                        audio_clip.close()
                except:
                    pass

                audio_files.append({
                    'id': audio_id,
                    'name': audio_file,
                    'size': size,
                    'created': os.path.getctime(audio_path),
                    'source': 'YouTube' if audio_id else 'Upload',
                    'duration': duration,
                    'trimmed': trimmed
                })
                stats['audio_files'] += 1
                stats['total_size'] += size

    # Get videos
    videos = []
    if os.path.exists(app.config['OUTPUT_FOLDER']):
        for video_file in os.listdir(app.config['OUTPUT_FOLDER']):
            video_path = os.path.join(app.config['OUTPUT_FOLDER'], video_file)
            if os.path.isfile(video_path) and video_file.endswith('.mp4'):
                video_id = video_file.rsplit('.', 1)[0]
                size = os.path.getsize(video_path)
                videos.append({
                    'id': video_id,
                    'name': video_file,
                    'size': size,
                    'created': os.path.getctime(video_path)
                })
                stats['videos'] += 1
                stats['total_size'] += size

    return jsonify({
        'stats': stats,
        'images': image_sessions,
        'audio': audio_files,
        'videos': videos
    })

@app.route('/admin/preview/image/<session_id>/<filename>')
def admin_preview_image(session_id, filename):
    """Serve image preview for admin"""
    # Accept token from header or query parameter
    token = request.headers.get('Authorization') or request.args.get('token')
    if not verify_admin_token(token):
        return 'Unauthorized', 401

    return send_from_directory(
        os.path.join(app.config['UPLOAD_FOLDER'], session_id),
        filename
    )

@app.route('/admin/preview/audio/<audio_id>')
def admin_preview_audio(audio_id):
    """Serve audio preview for admin"""
    # Accept token from header, query parameter, or cookie
    token = (request.headers.get('Authorization') or
             request.args.get('token') or
             request.cookies.get('adminToken'))

    if not verify_admin_token(token):
        return 'Unauthorized', 401

    # Find the audio file
    audio_files = list(Path(app.config['AUDIO_FOLDER']).glob(f"{audio_id}.*"))
    if audio_files:
        # Return with proper MIME type and headers for browser playback
        audio_path = str(audio_files[0])
        response = send_file(audio_path)

        # Add CORS headers for audio playback
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Access-Control-Allow-Origin'] = '*'

        return response
    return 'Not found', 404

@app.route('/admin/preview/video/<video_id>')
def admin_preview_video(video_id):
    """Serve video preview for admin"""
    # Accept token from header, query parameter, or cookie
    token = (request.headers.get('Authorization') or
             request.args.get('token') or
             request.cookies.get('adminToken'))

    if not verify_admin_token(token):
        return 'Unauthorized', 401

    video_files = list(Path(app.config['OUTPUT_FOLDER']).glob(f"{video_id}.*"))
    if video_files:
        # Return with proper MIME type and headers for browser playback
        video_path = str(video_files[0])
        response = send_file(video_path)

        # Add headers for video playback and seeking
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Content-Type'] = 'video/mp4'

        return response
    return 'Not found', 404

@app.route('/admin/download/audio/<audio_id>')
def admin_download_audio(audio_id):
    """Download audio file"""
    token = request.headers.get('Authorization')
    if not verify_admin_token(token):
        return 'Unauthorized', 401

    audio_files = list(Path(app.config['AUDIO_FOLDER']).glob(f"{audio_id}.*"))
    if audio_files:
        return send_file(str(audio_files[0]), as_attachment=True)
    return 'Not found', 404

@app.route('/admin/delete/session/<session_id>', methods=['DELETE'])
def admin_delete_session(session_id):
    """Delete an image session"""
    token = request.headers.get('Authorization')
    if not verify_admin_token(token):
        return jsonify({'error': 'Unauthorized'}), 401

    session_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if os.path.exists(session_path):
        shutil.rmtree(session_path)
        return jsonify({'success': True})
    return jsonify({'error': 'Session not found'}), 404

@app.route('/admin/delete/audio/<audio_id>', methods=['DELETE'])
def admin_delete_audio(audio_id):
    """Delete an audio file"""
    token = request.headers.get('Authorization')
    if not verify_admin_token(token):
        return jsonify({'error': 'Unauthorized'}), 401

    # Delete audio file and its trim info
    deleted = False
    audio_files = list(Path(app.config['AUDIO_FOLDER']).glob(f"{audio_id}.*"))
    for audio_file in audio_files:
        os.remove(str(audio_file))
        deleted = True

    # Delete trim info if exists
    trim_file = os.path.join(app.config['AUDIO_FOLDER'], f"{audio_id}_trim.json")
    if os.path.exists(trim_file):
        os.remove(trim_file)

    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Audio not found'}), 404

@app.route('/admin/delete/video/<video_id>', methods=['DELETE'])
def admin_delete_video(video_id):
    """Delete a video file"""
    token = request.headers.get('Authorization')
    if not verify_admin_token(token):
        return jsonify({'error': 'Unauthorized'}), 401

    video_files = list(Path(app.config['OUTPUT_FOLDER']).glob(f"{video_id}.*"))
    if video_files:
        for video_file in video_files:
            os.remove(str(video_file))
        return jsonify({'success': True})
    return jsonify({'error': 'Video not found'}), 404

@app.route('/admin/cleanup', methods=['POST'])
def admin_cleanup():
    """Clean up old files (older than 1 hour)"""
    token = request.headers.get('Authorization')
    if not verify_admin_token(token):
        return jsonify({'error': 'Unauthorized'}), 401

    deleted_count = 0
    current_time = time.time()

    # Clean uploads, audio, and output folders
    for folder in [app.config['UPLOAD_FOLDER'], app.config['AUDIO_FOLDER'], app.config['OUTPUT_FOLDER']]:
        if os.path.exists(folder):
            for item in os.listdir(folder):
                item_path = os.path.join(folder, item)
                try:
                    if os.path.getmtime(item_path) < current_time - 3600:  # 1 hour old
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                            deleted_count += 1
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                            deleted_count += 1
                except:
                    pass

    return jsonify({'success': True, 'deleted_count': deleted_count})

if __name__ == '__main__':
    # Get port from environment variable for Railway/production
    port = int(os.environ.get('PORT', 5000))
    # Debug mode only in development
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'

    print(f"""
    ========================================
    Aiezzy Simvid - Slideshow Video Generator
    ========================================
    Server starting at: http://localhost:{port}

    Features:
    - Drag & drop image upload
    - YouTube audio download
    - Local audio file upload
    - Multiple transition effects
    - Customizable video settings
    ========================================
    """)

    app.run(debug=debug_mode, host='0.0.0.0', port=port)