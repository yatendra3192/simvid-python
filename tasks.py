"""
Background Tasks for Video Generation
These tasks run in RQ workers - OPTIMIZED with FFmpeg concat demuxer
"""

import os
import glob
import subprocess
import json
from datetime import datetime
from redis import Redis

# Configuration - match app.py folder logic
RAILWAY_VOLUME = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
if RAILWAY_VOLUME:
    UPLOAD_FOLDER = os.path.join(RAILWAY_VOLUME, 'uploads')
    AUDIO_FOLDER = os.path.join(RAILWAY_VOLUME, 'audio')
    OUTPUT_FOLDER = os.path.join(RAILWAY_VOLUME, 'output')
    print(f"[OK] [Worker] Using Railway volume: {RAILWAY_VOLUME}")
else:
    UPLOAD_FOLDER = 'uploads'
    AUDIO_FOLDER = 'audio'
    OUTPUT_FOLDER = 'output'
    print("[WARN] [Worker] No Railway volume found, using local folders")

# Create folders if they don't exist
for folder in [UPLOAD_FOLDER, AUDIO_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Redis connection for progress updates
redis_conn = None
redis_url = os.environ.get('REDIS_URL')
if redis_url:
    try:
        redis_conn = Redis.from_url(redis_url, decode_responses=True)
        print("[Worker] [OK] Connected to Redis for progress updates")
    except Exception as e:
        print(f"[Worker] [WARN] Failed to connect to Redis: {e}")


def update_progress(job_id, stage, progress, message=""):
    """Update job progress in Redis"""
    if redis_conn:
        try:
            progress_data = {
                'stage': stage,
                'progress': progress,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
            redis_conn.setex(
                f"job_progress:{job_id}",
                3600,  # Expire after 1 hour
                json.dumps(progress_data)
            )
            print(f"[{job_id}] Progress: {stage} - {progress}% - {message}")
        except Exception as e:
            print(f"[{job_id}] Failed to update progress: {e}")


def safe_join_path(base_path, *paths):
    """Safely join paths and prevent directory traversal attacks"""
    final_path = os.path.abspath(os.path.join(base_path, *paths))
    base_path = os.path.abspath(base_path)
    if not final_path.startswith(base_path):
        raise ValueError("Invalid path: directory traversal detected")
    return final_path


def get_image_files(session_id):
    """Get all image files for a session"""
    session_path = safe_join_path(UPLOAD_FOLDER, session_id)
    if not os.path.exists(session_path):
        return []

    images = []
    for filename in os.listdir(session_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
            images.append(os.path.join(session_path, filename))

    # Sort by filename to maintain order
    images.sort()
    return images


def get_ffmpeg_path():
    """Get FFmpeg path - use system ffmpeg on Linux/Railway"""
    # On Railway/Linux, ffmpeg is in PATH
    return 'ffmpeg'


def generate_video_job(job_id, session_id, audio_id, duration, transition, resolution):
    """
    Background job to generate video using FFmpeg concat demuxer (FAST!)

    This bypasses MoviePy entirely for 40x faster encoding.
    """
    try:
        print(f"[{job_id}] Starting video generation (FFmpeg mode)...")
        print(f"[{job_id}] Session: {session_id}, Duration: {duration}s, Resolution: {resolution}")
        update_progress(job_id, 'initializing', 5, 'Starting video generation...')

        # Get image files
        image_files = get_image_files(session_id)
        total_images = len(image_files)

        if total_images == 0:
            update_progress(job_id, 'error', 0, 'No images found')
            return {
                'success': False,
                'error': 'No images found for this session',
                'stage': 'error',
                'progress': 0
            }

        print(f"[{job_id}] Found {total_images} images")
        update_progress(job_id, 'processing', 10, f'Found {total_images} images')

        # Get target resolution
        width, height = map(int, resolution.split('x'))

        # Create concat file for FFmpeg (MUCH faster than MoviePy)
        update_progress(job_id, 'processing', 20, 'Preparing images for encoding...')

        concat_file = os.path.join(OUTPUT_FOLDER, f"{job_id}_concat.txt")
        with open(concat_file, 'w') as f:
            for idx, img_path in enumerate(image_files):
                # Use absolute path
                abs_path = os.path.abspath(img_path)
                f.write(f"file '{abs_path}'\n")
                f.write(f"duration {duration}\n")
            # Add last image again (required by concat demuxer)
            last_abs_path = os.path.abspath(image_files[-1])
            f.write(f"file '{last_abs_path}'\n")

        update_progress(job_id, 'processing', 40, f'Processing {total_images} images...')

        # Output path
        output_path = safe_join_path(OUTPUT_FOLDER, f"{job_id}.mp4")

        # Get FFmpeg path
        ffmpeg_path = get_ffmpeg_path()

        # Check for audio
        audio_path = None
        if audio_id:
            audio_files = glob.glob(os.path.join(AUDIO_FOLDER, f"{audio_id}.*"))
            audio_files = [f for f in audio_files if not f.endswith('_trim.json')]
            if audio_files:
                audio_path = audio_files[0]
                print(f"[{job_id}] Found audio: {os.path.basename(audio_path)}")

        update_progress(job_id, 'encoding', 60, 'Encoding video with FFmpeg...')

        # Build FFmpeg command - optimized for speed
        # Use filter_complex with explicit stream mapping when audio is present
        video_filter = f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black'

        ffmpeg_cmd = [
            ffmpeg_path, '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
        ]

        if audio_path:
            # With audio: use filter_complex for explicit stream selection
            ffmpeg_cmd.extend(['-i', audio_path])
            ffmpeg_cmd.extend([
                '-filter_complex', f'[0:v]{video_filter}[outv]',
                '-map', '[outv]',
                '-map', '1:a',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'stillimage',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-r', '30',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-shortest',
            ])
        else:
            # No audio: simple -vf filter is fine
            ffmpeg_cmd.extend([
                '-vf', video_filter,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'stillimage',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-r', '30',
            ])

        ffmpeg_cmd.append(output_path)

        print(f"[{job_id}] Running FFmpeg: {' '.join(ffmpeg_cmd[:10])}...")

        # Run FFmpeg
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Clean up concat file
        try:
            os.remove(concat_file)
        except:
            pass

        if result.returncode != 0:
            error_msg = result.stderr[-500:] if result.stderr else 'Unknown FFmpeg error'
            print(f"[{job_id}] FFmpeg error: {error_msg}")
            update_progress(job_id, 'error', 0, f'Encoding failed: {error_msg[:100]}')
            return {
                'success': False,
                'error': f'FFmpeg encoding failed: {error_msg[:200]}',
                'stage': 'error',
                'progress': 0
            }

        # Verify output exists
        if not os.path.exists(output_path):
            update_progress(job_id, 'error', 0, 'Output file not created')
            return {
                'success': False,
                'error': 'Video file was not created',
                'stage': 'error',
                'progress': 0
            }

        file_size = os.path.getsize(output_path)
        print(f"[{job_id}] [OK] Video generation complete! Size: {file_size} bytes")

        # Save project metadata for admin panel
        try:
            meta_path = os.path.join(OUTPUT_FOLDER, f"{job_id}_meta.json")
            with open(meta_path, 'w') as f:
                json.dump({
                    'session_id': session_id,
                    'audio_id': audio_id,
                    'duration_per_image': duration,
                    'transition': transition,
                    'resolution': resolution,
                    'image_count': total_images,
                    'created': datetime.now().isoformat(),
                    'file_size': file_size
                }, f)
            print(f"[{job_id}] Project metadata saved")
        except Exception as meta_error:
            print(f"[{job_id}] Warning: Could not save metadata: {meta_error}")

        update_progress(job_id, 'completed', 100, 'Video ready for download!')

        return {
            'success': True,
            'video_id': job_id,
            'video_path': output_path,
            'file_size': file_size,
            'download_url': f'/download/{job_id}',
            'stage': 'completed',
            'progress': 100,
            'message': 'Video generation complete!'
        }

    except subprocess.TimeoutExpired:
        print(f"[{job_id}] [ERROR] FFmpeg timed out")
        update_progress(job_id, 'error', 0, 'Video encoding timed out')
        return {
            'success': False,
            'error': 'Video encoding timed out after 5 minutes',
            'stage': 'error',
            'progress': 0
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[{job_id}] [ERROR] Error: {error_msg}")
        update_progress(job_id, 'error', 0, f'Error: {error_msg}')
        return {
            'success': False,
            'error': error_msg,
            'stage': 'error',
            'progress': 0
        }
