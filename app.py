"""
SimVid - Python Slideshow Video Generator with YouTube Audio
A complete Python application for creating slideshow videos from images with background music
"""

import os
import json
import uuid
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, url_for, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
# Import moviepy components
try:
    from moviepy import *
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, concatenate_audioclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: MoviePy not properly installed. Video generation may not work.")
import yt_dlp
from PIL import Image
import numpy as np

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['AUDIO_FOLDER'] = 'audio'

# Allowed extensions
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac', 'ogg', 'webm', 'opus'}

# Create necessary folders
for folder in ['uploads', 'output', 'audio', 'static']:
    os.makedirs(folder, exist_ok=True)

def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

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
    """Download audio from YouTube URL"""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    audio_id = str(uuid.uuid4())
    output_path = os.path.join(app.config['AUDIO_FOLDER'], audio_id)

    # Simplified options - let yt-dlp handle the format without forcing conversion
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{output_path}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'extractaudio': True,
        # Don't force MP3 conversion if ffmpeg is not available
        # The audio will be downloaded in its original format
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)

            # Find the downloaded file
            audio_files = list(Path(app.config['AUDIO_FOLDER']).glob(f"{audio_id}.*"))
            if audio_files:
                audio_file = str(audio_files[0])
                return jsonify({
                    'success': True,
                    'audio_id': audio_id,
                    'title': title,
                    'duration': duration,
                    'filename': os.path.basename(audio_file)
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

if __name__ == '__main__':
    # Get port from environment variable for Railway/production
    port = int(os.environ.get('PORT', 5000))
    # Debug mode only in development
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'

    print(f"""
    ========================================
    SimVid Python - Slideshow Video Generator
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