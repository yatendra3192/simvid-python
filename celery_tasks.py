"""
Celery Tasks for Video Processing
Scalable background task processing
"""

import os
import json
import time
import shutil
from datetime import datetime
from celery import shared_task, current_task
from celery.exceptions import SoftTimeLimitExceeded

# MoviePy imports
try:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips
except ImportError:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    from moviepy.audio.AudioClip import concatenate_audioclips

from PIL import Image, ImageOps
import numpy as np
from redis import Redis

# Configuration - match app.py folder logic
RAILWAY_VOLUME = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
if RAILWAY_VOLUME:
    UPLOAD_FOLDER = os.path.join(RAILWAY_VOLUME, 'uploads')
    AUDIO_FOLDER = os.path.join(RAILWAY_VOLUME, 'audio')
    OUTPUT_FOLDER = os.path.join(RAILWAY_VOLUME, 'output')
else:
    UPLOAD_FOLDER = 'uploads'
    AUDIO_FOLDER = 'audio'
    OUTPUT_FOLDER = 'output'

# Ensure folders exist
for folder in [UPLOAD_FOLDER, AUDIO_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Redis connection for progress updates
redis_url = os.environ.get('REDIS_URL')
redis_conn = Redis.from_url(redis_url, decode_responses=True) if redis_url else None


def update_progress(job_id, stage, progress, message=""):
    """Update job progress in Redis for real-time updates"""
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
        except Exception as e:
            print(f"[{job_id}] Progress update failed: {e}")


def safe_join_path(base_path, *paths):
    """Prevent directory traversal attacks"""
    final_path = os.path.abspath(os.path.join(base_path, *paths))
    base_path = os.path.abspath(base_path)
    if not final_path.startswith(base_path):
        raise ValueError("Invalid path: directory traversal detected")
    return final_path


def fix_image_orientation(img):
    """Fix EXIF orientation"""
    try:
        return ImageOps.exif_transpose(img)
    except:
        return img


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_video_task(self, job_id, session_id, audio_id, duration, transition, resolution):
    """
    Generate slideshow video from images - Celery task version

    This task is designed to scale horizontally across multiple workers
    """
    try:
        update_progress(job_id, 'initializing', 5, 'Starting video generation...')

        # Get image files
        session_path = safe_join_path(UPLOAD_FOLDER, session_id)
        if not os.path.exists(session_path):
            update_progress(job_id, 'error', 0, 'Session not found')
            return {'success': False, 'error': 'Session not found'}

        image_files = sorted([
            os.path.join(session_path, f)
            for f in os.listdir(session_path)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'))
        ])

        total_images = len(image_files)
        if total_images == 0:
            update_progress(job_id, 'error', 0, 'No images found')
            return {'success': False, 'error': 'No images found'}

        update_progress(job_id, 'processing', 10, f'Processing {total_images} images...')

        # Parse resolution
        width, height = map(int, resolution.split('x'))

        # Process images with progress tracking
        clips = []
        for idx, img_path in enumerate(image_files):
            progress = 10 + int((idx / total_images) * 50)
            update_progress(job_id, 'processing', progress, f'Processing image {idx + 1}/{total_images}')

            # Update Celery task state
            self.update_state(
                state='PROGRESS',
                meta={'current': idx + 1, 'total': total_images, 'stage': 'processing'}
            )

            try:
                img = Image.open(img_path)
                img = fix_image_orientation(img)
                img = img.convert('RGB')

                # Scale and letterbox
                img_ratio = img.width / img.height
                video_ratio = width / height

                if img_ratio > video_ratio:
                    new_width = width
                    new_height = int(width / img_ratio)
                else:
                    new_height = height
                    new_width = int(height * img_ratio)

                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Create background with letterboxing
                background = Image.new('RGB', (width, height), (0, 0, 0))
                x = (width - new_width) // 2
                y = (height - new_height) // 2
                background.paste(img, (x, y))

                # Convert to numpy array
                frame = np.array(background)
                clip = ImageClip(frame, duration=duration)
                clips.append(clip)

                # Free memory
                img.close()
                background.close()

            except Exception as e:
                print(f"[{job_id}] Error processing image {idx + 1}: {e}")
                continue

        if len(clips) == 0:
            update_progress(job_id, 'error', 0, 'Failed to process images')
            return {'success': False, 'error': 'Failed to process any images'}

        # Concatenate clips
        update_progress(job_id, 'concatenating', 60, 'Combining clips...')
        final_video = concatenate_videoclips(clips, method="compose")

        # Add audio if provided
        if audio_id:
            update_progress(job_id, 'audio', 70, 'Adding background music...')

            import glob
            audio_files = glob.glob(os.path.join(AUDIO_FOLDER, f"{audio_id}.*"))
            audio_files = [f for f in audio_files if not f.endswith('_trim.json')]

            if audio_files:
                try:
                    audio_clip = AudioFileClip(audio_files[0])
                    video_duration = final_video.duration

                    # Check for trim info
                    trim_file = os.path.join(AUDIO_FOLDER, f"{audio_id}_trim.json")
                    if os.path.exists(trim_file):
                        with open(trim_file, 'r') as f:
                            trim_info = json.load(f)
                            start_time = trim_info.get('start', 0) or 0
                            end_time = trim_info.get('end')

                            if start_time > 0 or end_time:
                                try:
                                    audio_clip = audio_clip.subclipped(
                                        start_time,
                                        end_time if end_time else audio_clip.duration
                                    )
                                except:
                                    pass

                    # Match audio to video duration
                    if audio_clip.duration > video_duration:
                        audio_clip = audio_clip.subclipped(0, video_duration)
                    elif audio_clip.duration < video_duration:
                        loops = int(video_duration / audio_clip.duration) + 1
                        audio_clip = concatenate_audioclips([audio_clip] * loops).subclipped(0, video_duration)

                    final_video = final_video.with_audio(audio_clip)

                except Exception as e:
                    print(f"[{job_id}] Audio error: {e}")

        # Write output
        output_path = safe_join_path(OUTPUT_FOLDER, f"{job_id}.mp4")

        # Calculate bitrate based on resolution
        total_pixels = width * height
        if total_pixels >= 3840 * 2160:
            bitrate = "20000k"
        elif total_pixels >= 1920 * 1080:
            bitrate = "8000k"
        elif total_pixels >= 1280 * 720:
            bitrate = "5000k"
        else:
            bitrate = "2500k"

        update_progress(job_id, 'encoding', 75, 'Encoding video...')

        # Get CPU count for threading - optimize for concurrent processing
        cpu_count = os.cpu_count() or 4
        # Use fewer threads per video when running multiple workers
        threads = min(cpu_count // 2, 4)  # 2-4 threads per video

        # Use FFmpeg parameters optimized for throughput
        ffmpeg_params = [
            '-movflags', '+faststart',  # Enable fast start for streaming
            '-pix_fmt', 'yuv420p',  # Best compatibility
            '-crf', '23',  # Constant rate factor for quality
        ]

        final_video.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            bitrate=bitrate,
            preset='veryfast',  # Use 'veryfast' for maximum throughput
            threads=threads,
            ffmpeg_params=ffmpeg_params,
            logger=None
        )

        # Cleanup
        final_video.close()
        for clip in clips:
            try:
                clip.close()
            except:
                pass

        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        update_progress(job_id, 'completed', 100, 'Video ready!')

        return {
            'success': True,
            'video_id': job_id,
            'download_url': f'/download/{job_id}',
            'file_size': file_size,
            'stage': 'completed',
            'progress': 100
        }

    except SoftTimeLimitExceeded:
        update_progress(job_id, 'error', 0, 'Task timed out')
        return {'success': False, 'error': 'Video generation timed out'}

    except Exception as e:
        error_msg = str(e)
        update_progress(job_id, 'error', 0, f'Error: {error_msg}')

        # Retry on transient failures
        if 'memory' in error_msg.lower() or 'timeout' in error_msg.lower():
            raise self.retry(exc=e)

        return {'success': False, 'error': error_msg}


@shared_task
def cleanup_old_files():
    """Periodic cleanup of old files - run via Celery Beat"""
    current_time = time.time()
    deleted_count = 0

    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, AUDIO_FOLDER]:
        if not os.path.exists(folder):
            continue

        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)
            try:
                # Delete files older than 1 hour
                if os.path.getmtime(item_path) < current_time - 3600:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        deleted_count += 1
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        deleted_count += 1
            except:
                pass

    return {'deleted': deleted_count}
