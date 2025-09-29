"""
Background Tasks for Video Generation
These tasks run in RQ workers
"""

import os
import uuid
from datetime import datetime
# MoviePy 2.x compatible imports
try:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips
except ImportError:
    # Fallback for MoviePy 1.x
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    from moviepy.audio.AudioClip import concatenate_audioclips
from PIL import Image
import json
from redis import Redis

# Import configuration from app
# Match app.py folder configuration logic
RAILWAY_VOLUME = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
if RAILWAY_VOLUME:
    UPLOAD_FOLDER = os.path.join(RAILWAY_VOLUME, 'uploads')
    AUDIO_FOLDER = os.path.join(RAILWAY_VOLUME, 'audio')
    OUTPUT_FOLDER = os.path.join(RAILWAY_VOLUME, 'output')
    print(f"✅ [Worker] Using Railway volume: {RAILWAY_VOLUME}")
else:
    UPLOAD_FOLDER = 'uploads'
    AUDIO_FOLDER = 'audio'
    OUTPUT_FOLDER = 'output'
    print("⚠️ [Worker] No Railway volume found, using local folders")

# Create folders if they don't exist
for folder in [UPLOAD_FOLDER, AUDIO_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Redis connection for progress updates
redis_conn = None
redis_url = os.environ.get('REDIS_URL')
if redis_url:
    try:
        redis_conn = Redis.from_url(redis_url, decode_responses=True)
        print("[Worker] ✅ Connected to Redis for progress updates")
    except Exception as e:
        print(f"[Worker] ⚠️ Failed to connect to Redis: {e}")

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


def fix_image_orientation(img):
    """Fix image orientation based on EXIF data"""
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        print(f"Could not fix orientation: {e}")
    return img


def get_image_files(session_id):
    """Get all image files for a session"""
    session_path = safe_join_path(UPLOAD_FOLDER, session_id)
    if not os.path.exists(session_path):
        return []

    images = []
    for filename in os.listdir(session_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            images.append(os.path.join(session_path, filename))

    # Sort by filename to maintain order
    images.sort()
    return images


def generate_video_job(job_id, session_id, audio_id, duration, transition, resolution):
    """
    Background job to generate video

    Args:
        job_id: Unique job identifier
        session_id: User session ID with uploaded images
        audio_id: Audio file ID (optional)
        duration: Duration per image in seconds
        transition: Transition effect ('fade', 'none', etc.)
        resolution: Video resolution (e.g., '1920x1080')

    Returns:
        dict: Job result with success status and file paths
    """
    try:
        print(f"[{job_id}] Starting video generation...")
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

        # Update progress: Processing images
        clips = []
        for idx, img_path in enumerate(image_files):
            progress = 10 + int((idx / total_images) * 50)
            update_progress(job_id, 'processing', progress, f'Processing image {idx + 1}/{total_images}')
            print(f"[{job_id}] Processing image {idx + 1}/{total_images} ({progress}%)")

            try:
                # Load and fix orientation
                img = Image.open(img_path)
                img = fix_image_orientation(img)
                img = img.convert('RGB')

                # Get target resolution
                width, height = map(int, resolution.split('x'))

                # Calculate scaling to fit within resolution while maintaining aspect ratio
                img_ratio = img.width / img.height
                video_ratio = width / height

                if img_ratio > video_ratio:
                    # Image is wider - fit to width
                    new_width = width
                    new_height = int(width / img_ratio)
                else:
                    # Image is taller - fit to height
                    new_height = height
                    new_width = int(height * img_ratio)

                # Resize image maintaining aspect ratio
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Create black background at target resolution
                background = Image.new('RGB', (width, height), (0, 0, 0))

                # Center the resized image on background (letterboxing)
                x = (width - new_width) // 2
                y = (height - new_height) // 2
                background.paste(img, (x, y))

                # Save to temporary file
                temp_path = img_path + '.temp.jpg'
                background.save(temp_path, 'JPEG')

                # Create clip from processed image
                clip = ImageClip(temp_path, duration=duration)

                # Note: Transitions are complex in MoviePy 2.x, skipping for now
                # The fade transition would be applied during concatenation

                clips.append(clip)

                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            except Exception as e:
                print(f"[{job_id}] Error processing image {idx + 1}: {e}")
                continue

        if len(clips) == 0:
            return {
                'success': False,
                'error': 'Failed to process any images',
                'stage': 'error',
                'progress': 0
            }

        # Concatenate clips
        update_progress(job_id, 'concatenating', 60, f'Combining {len(clips)} clips...')
        print(f"[{job_id}] Concatenating {len(clips)} clips...")
        final_video = concatenate_videoclips(clips, method="compose")

        # Add audio if provided
        if audio_id:
            update_progress(job_id, 'audio', 70, 'Adding background music...')
            print(f"[{job_id}] Adding audio: {audio_id}")
            audio_path = safe_join_path(AUDIO_FOLDER, f"{audio_id}.webm")

            if os.path.exists(audio_path):
                try:
                    audio_clip = AudioFileClip(audio_path)
                    video_duration = final_video.duration

                    # Trim or loop audio to match video duration
                    if audio_clip.duration > video_duration:
                        # Trim audio
                        audio_clip = audio_clip.subclipped(0, video_duration)
                    elif audio_clip.duration < video_duration:
                        # Loop audio
                        loops_needed = int(video_duration / audio_clip.duration) + 1
                        from moviepy.audio.AudioClip import concatenate_audioclips
                        audio_clips = [audio_clip] * loops_needed
                        audio_clip = concatenate_audioclips(audio_clips).subclipped(0, video_duration)

                    final_video = final_video.set_audio(audio_clip)
                    print(f"[{job_id}] Audio added successfully")
                except Exception as e:
                    print(f"[{job_id}] Warning: Could not add audio: {e}")
            else:
                print(f"[{job_id}] Warning: Audio file not found: {audio_path}")

        # Resolution is already set correctly for each image (letterboxed)
        # No need to resize the final video

        # Generate output path
        output_path = safe_join_path(OUTPUT_FOLDER, f"{job_id}.mp4")

        # Write video file
        update_progress(job_id, 'encoding', 75, 'Encoding video file...')
        print(f"[{job_id}] Encoding video to {output_path}...")
        final_video.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            preset='medium',
            threads=4,
            logger=None  # Suppress MoviePy progress bars in worker
        )

        # Clean up
        print(f"[{job_id}] Cleaning up clips...")
        final_video.close()
        for clip in clips:
            try:
                clip.close()
            except:
                pass

        # Get file size
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        print(f"[{job_id}] ✅ Video generation complete! Size: {file_size} bytes")

        result = {
            'success': True,
            'video_id': job_id,
            'video_path': output_path,
            'file_size': file_size,
            'download_url': f'/download/{job_id}',
            'stage': 'completed',
            'progress': 100,
            'message': 'Video generation complete!'
        }

        update_progress(job_id, 'completed', 100, 'Video ready for download!')

        return result

    except Exception as e:
        error_msg = str(e)
        print(f"[{job_id}] ❌ Error: {error_msg}")
        update_progress(job_id, 'error', 0, f'Error: {error_msg}')
        return {
            'success': False,
            'error': error_msg,
            'stage': 'error',
            'progress': 0
        }