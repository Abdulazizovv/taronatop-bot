import os
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict
from uuid import uuid4
import yt_dlp
import subprocess
import tempfile

from aiogram import Bot

from bot.data.config import PRIVATE_CHANNEL_ID
from bot.utils.media_analyzer import check_media_has_audio
from bot.utils.audio_db_utils import update_instagram_media_audio_info
from bot.utils.shazam_service import shazam_service
from botapp.models import InstagramMedia
from asgiref.sync import sync_to_async
import aiofiles

TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)


async def update_instagram_telegram_file_id(media_id: str, file_id: str) -> bool:
    """Update Instagram media with Telegram file ID"""
    try:
        @sync_to_async
        def update_file_id():
            try:
                media = InstagramMedia.objects.get(media_id=media_id)
                media.telegram_file_id = file_id
                media.save()
                return True
            except InstagramMedia.DoesNotExist:
                logging.warning(f"[DB] Media not found for update: {media_id}")
                return False
            except Exception as e:
                logging.error(f"[DB] Error updating file_id: {e}")
                return False
        
        result = await update_file_id()
        if result:
            logging.info(f"[DB] Updated file_id for {media_id}: {file_id}")
        return result
    except Exception as e:
        logging.error(f"[DB] Error in update_instagram_telegram_file_id: {e}")
        return False


@dataclass
class MediaResult:
    success: bool
    message: str
    media_id: Optional[str] = None
    title: Optional[str] = None
    telegram_file_id: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    from_cache: bool = False
    has_audio: Optional[bool] = None
    song_info: Optional[Dict] = None


async def ensure_instagram_media(url: str, bot: Bot, user_id: Optional[int] = None) -> MediaResult:
    """End-to-end: check DB, download if needed (yt-dlp), upload to channel to get file_id, save and return."""
    try:
        # Extract media ID from URL
        media_id = _extract_media_id_from_url(url)
        if not media_id:
            return MediaResult(False, "❌ Instagram URL noto'g'ri formatda")

        # 1) Check DB first
        existing = await _check_database(media_id)
        if existing and existing.telegram_file_id:
            logging.info(f"[IG] Cache hit for {media_id}")
            # Check if we have audio info and song info cached
            cached_has_audio = getattr(existing, 'has_audio', None)
            cached_track = getattr(existing, 'track', None)
            cached_artist = getattr(existing, 'artist', None)
            
            # Create song_info if available
            cached_song_info = None
            if cached_track and cached_artist:
                cached_song_info = {
                    'title': cached_track,
                    'artist': cached_artist
                }
            
            return MediaResult(
                success=True,
                message="✅ Media tayyor (cache)",
                media_id=media_id,
                title=existing.title or "Instagram Media",
                telegram_file_id=existing.telegram_file_id,
                duration=existing.duration,
                from_cache=True,
                has_audio=cached_has_audio,
                song_info=cached_song_info
            )

        # 2) Download with yt-dlp
        logging.info(f"[IG] Downloading new media: {media_id}")
        download_result = await _download_with_ytdlp(url)
        
        if not download_result['success']:
            return MediaResult(False, f"❌ Yuklab olishda xatolik: {download_result['message']}")
        
        local_path = download_result['file_path']
        title = download_result.get('title', 'Instagram Media')
        duration = download_result.get('duration')

        # 3) Validate and convert video if needed
        video_path = await _validate_and_convert_video(local_path)
        if not video_path:
            return MediaResult(False, "❌ Video format xatoligi")

        # 4) Check for audio
        has_audio = await _check_audio_presence(video_path)
        logging.info(f"[IG] Audio detection for {media_id}: {has_audio}")
        
        # 5) Music recognition if audio present
        song_info = None
        if has_audio:
            logging.info(f"[IG] Attempting music recognition for {media_id}")
            song_info = await _recognize_music(video_path)
            if song_info:
                logging.info(f"[IG] Music recognized: {song_info['artist']} - {song_info['title']}")

        # 6) Upload to private channel
        upload_result = await _upload_to_private_channel(bot, video_path, title)
        if not upload_result['success']:
            return MediaResult(False, f"❌ Telegram'ga yuklashda xatolik: {upload_result['message']}")

        file_id = upload_result['file_id']
        thumbnail = upload_result.get('thumbnail')

        # 7) Save to database
        await _save_to_database(
            media_id=media_id,
            title=title,
            file_id=file_id,
            duration=duration,
            has_audio=has_audio,
            song_info=song_info,
            user_id=user_id,
            video_url=url  # Original Instagram URL
        )

        # 8) Cleanup
        _cleanup_file(video_path)
        if video_path != local_path:
            _cleanup_file(local_path)

        return MediaResult(
            success=True,
            message="✅ Media muvaffaqiyatli yuklandi",
            media_id=media_id,
            title=title,
            telegram_file_id=file_id,
            thumbnail=thumbnail,
            duration=duration,
            from_cache=False,
            has_audio=has_audio,
            song_info=song_info
        )

    except Exception as e:
        logging.error(f"[IG] Error in ensure_instagram_media: {e}")
        return MediaResult(False, f"❌ Umumiy xatolik: {str(e)}")


def _extract_media_id_from_url(url: str) -> Optional[str]:
    """Extract media ID from Instagram URL"""
    try:
        import re
        patterns = [
            r"/p/([A-Za-z0-9_-]+)",
            r"/reel/([A-Za-z0-9_-]+)",
            r"/tv/([A-Za-z0-9_-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    except Exception as e:
        logging.error(f"[IG] Error extracting media ID: {e}")
        return None


@sync_to_async
def _check_database(media_id: str) -> Optional[InstagramMedia]:
    """Check if media exists in database"""
    try:
        return InstagramMedia.objects.get(media_id=media_id)
    except InstagramMedia.DoesNotExist:
        return None
    except Exception as e:
        logging.error(f"[DB] Error checking database: {e}")
        return None


async def _download_with_ytdlp(url: str) -> Dict:
    """Download Instagram media using yt-dlp"""
    try:
        logging.info(f"[IG Download] Starting yt-dlp download: {url}")
        
        temp_filename = f"ig_{uuid4().hex}"
        temp_path = os.path.join(TEMP_DIR, temp_filename)
        
        ydl_opts = {
            'outtmpl': f'{temp_path}.%(ext)s',
            'format': 'best[height<=1080]/best',
            'noplaylist': True,
            'no_warnings': True,
            'quiet': True,
            'extractaudio': False,
            'writeinfojson': False,
            'writethumbnail': False,
        }
        
        def download_sync():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info
        
        # Run yt-dlp in thread to avoid blocking
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, download_sync)
        
        if not info:
            return {'success': False, 'message': 'yt-dlp ma\'lumot ololmadi'}
        
        # Find downloaded file
        downloaded_file = None
        for ext in ['mp4', 'mkv', 'webm', 'mov']:
            candidate = f"{temp_path}.{ext}"
            if os.path.exists(candidate):
                downloaded_file = candidate
                break
        
        if not downloaded_file:
            return {'success': False, 'message': 'Yuklab olingan fayl topilmadi'}
        
        # Use newest file if multiple exist
        pattern = temp_path + "*"
        import glob
        files = glob.glob(pattern)
        if files:
            downloaded_file = max(files, key=os.path.getmtime)
            logging.info(f"[IG Download] Using newest file: {downloaded_file}")
        
        return {
            'success': True,
            'file_path': downloaded_file,
            'title': info.get('title', 'Instagram Media'),
            'duration': info.get('duration')
        }
        
    except Exception as e:
        logging.error(f"[IG Download] yt-dlp error: {e}")
        return {'success': False, 'message': f'Yuklab olishda xatolik'}


async def _validate_and_convert_video(video_path: str) -> Optional[str]:
    """Validate video format and convert if needed"""
    try:
        if not os.path.exists(video_path):
            logging.error(f"[IG] Video file not found: {video_path}")
            return None
        
        # Check video properties
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
            video_path
        ]
        
        def run_ffprobe():
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_ffprobe)
        
        if result.returncode != 0:
            logging.error(f"[IG] ffprobe failed for {video_path}")
            return None
        
        import json
        info = json.loads(result.stdout)
        
        # Check video stream
        video_stream = None
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        if not video_stream:
            logging.error(f"[IG] No video stream found in {video_path}")
            return None
        
        codec = video_stream.get('codec_name', '').lower()
        width = video_stream.get('width', 0)
        height = video_stream.get('height', 0)
        
        logging.info(f"[IG] Video validation passed: {codec}, {width}x{height}")
        
        # If video is already good, return as-is
        if codec in ['h264', 'avc'] and width > 0 and height > 0:
            return video_path
        
        # Convert if needed
        output_path = video_path.replace('.', '_converted.')
        if not output_path.endswith('.mp4'):
            output_path = os.path.splitext(output_path)[0] + '.mp4'
        
        convert_cmd = [
            'ffmpeg', '-i', video_path, '-c:v', 'libx264', '-c:a', 'aac',
            '-movflags', '+faststart', '-y', output_path
        ]
        
        def run_ffmpeg():
            return subprocess.run(convert_cmd, capture_output=True, timeout=120)
        
        convert_result = await loop.run_in_executor(None, run_ffmpeg)
        
        if convert_result.returncode == 0 and os.path.exists(output_path):
            logging.info(f"[IG] Video converted successfully: {output_path}")
            return output_path
        else:
            logging.error(f"[IG] Video conversion failed")
            return video_path  # Return original if conversion fails
        
    except Exception as e:
        logging.error(f"[IG] Video validation error: {e}")
        return video_path  # Return original on error


async def _check_audio_presence(video_path: str) -> bool:
    """Check if video has audio"""
    try:
        return await check_media_has_audio(video_path)
    except Exception as e:
        logging.error(f"[IG] Audio check error: {e}")
        return False


async def _recognize_music(video_path: str) -> Optional[Dict]:
    """Recognize music in video using Shazam"""
    try:
        return await shazam_service.recognize_music_from_video(video_path)
    except Exception as e:
        logging.error(f"[IG] Music recognition error: {e}")
        return None


async def _upload_to_private_channel(bot: Bot, video_path: str, title: str) -> Dict:
    """Upload video to private channel and get file_id"""
    try:
        with open(video_path, 'rb') as video_file:
            message = await bot.send_video(
                chat_id=PRIVATE_CHANNEL_ID,
                video=video_file,
                caption=f"📱 {title}",
                supports_streaming=True
            )
        
        file_id = message.video.file_id
        thumbnail = message.video.thumb.file_id if message.video.thumb else None
        
        return {
            'success': True,
            'file_id': file_id,
            'thumbnail': thumbnail
        }
        
    except Exception as e:
        logging.error(f"[IG] Upload to channel error: {e}")
        return {'success': False, 'message': str(e)}


@sync_to_async
def _save_to_database(media_id: str, title: str, file_id: str, duration: Optional[int] = None,
                     has_audio: Optional[bool] = None, song_info: Optional[Dict] = None,
                     user_id: Optional[int] = None, video_url: Optional[str] = None):
    """Save media info to database"""
    try:
        from botapp.models import BotUser
        
        # Get user instance if user_id provided
        user_instance = None
        if user_id:
            user_instance = BotUser.objects.filter(user_id=str(user_id)).first()
        
        media, created = InstagramMedia.objects.get_or_create(
            media_id=media_id,
            defaults={
                'title': title,
                'telegram_file_id': file_id,
                'duration': duration,
                'has_audio': has_audio,
                'video_url': video_url,  # Save original Instagram URL
                'user': user_instance
            }
        )
        
        if not created:
            # Update existing
            media.telegram_file_id = file_id
            media.title = title
            if duration is not None:
                media.duration = duration
            if has_audio is not None:
                media.has_audio = has_audio
            if video_url:
                media.video_url = video_url
            if user_instance and not media.user:
                media.user = user_instance
        
        # Save song info if available - Fix empty track field
        if song_info:
            media.track = song_info.get('title')  # This should fix empty track field
            media.artist = song_info.get('artist')
        
        media.save()
        logging.info(f"[DB] Saved media to database: {media_id} (track: {media.track}, artist: {media.artist})")
        
    except Exception as e:
        logging.error(f"[DB] Error saving to database: {e}")


def _cleanup_file(file_path: str):
    """Clean up temporary file"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logging.debug(f"[IG] Cleaned up: {file_path}")
    except Exception as e:
        logging.error(f"[IG] Cleanup error: {e}")


async def download_video_from_telegram(bot: Bot, file_id: str) -> Optional[str]:
    """Download a Telegram file by file_id into TEMP_DIR and return path."""
    try:
        file = await bot.get_file(file_id)
        dst = os.path.join(TEMP_DIR, f"tg_{uuid4().hex}.mp4")
        await bot.download_file(file.file_path, dst)
        return dst if os.path.exists(dst) else None
    except Exception as e:
        logging.error(f"[IG] Telegram download failed: {e}")
        return None


async def extract_audio_with_ffmpeg(video_path: str) -> Optional[str]:
    """Extract mp3 audio from video using ffmpeg with comprehensive error handling and validation."""
    try:
        import shutil
        if not shutil.which("ffmpeg"):
            logging.error("[IG Service] ffmpeg not found")
            return None
        
        # First validate input file
        if not os.path.exists(video_path) or os.path.getsize(video_path) < 1000:
            logging.error(f"[IG Service] Input video file invalid: {video_path}")
            return None
        
        # Check if video actually has audio streams
        if shutil.which("ffprobe"):
            try:
                # Detailed audio stream check
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-select_streams", "a",
                    "-show_entries", "stream=codec_name,channels,sample_rate,duration",
                    "-of", "json",
                    video_path
                ]
                
                probe_proc = await asyncio.create_subprocess_exec(
                    *probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await probe_proc.communicate()
                
                if probe_proc.returncode == 0:
                    import json
                    data = json.loads(stdout.decode())
                    streams = data.get("streams", [])
                    
                    if not streams:
                        logging.info("[IG Service] No audio streams detected in video")
                        return None
                    
                    # Validate audio stream quality
                    audio_stream = streams[0]
                    channels = audio_stream.get("channels", 0)
                    sample_rate = audio_stream.get("sample_rate")
                    codec_name = audio_stream.get("codec_name", "")
                    
                    if channels == 0 or not sample_rate or not codec_name:
                        logging.warning("[IG Service] Audio stream present but incomplete or damaged")
                        # Continue anyway, might still be extractable
                    else:
                        logging.info(f"[IG Service] Valid audio stream found: {codec_name}, {channels}ch, {sample_rate}Hz")
                        
            except Exception as e:
                logging.warning(f"[IG Service] Audio stream validation failed, proceeding anyway: {e}")
        
        audio_path = os.path.splitext(video_path)[0] + ".mp3"
        
        # Multiple extraction strategies for maximum compatibility
        strategies = [
            # Strategy 1: High quality with explicit stream mapping and error recovery
            {
                "name": "High Quality",
                "cmd": [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn",  # No video
                    "-map", "0:a:0",  # Map first audio stream
                    "-acodec", "libmp3lame", 
                    "-b:a", "192k", 
                    "-ar", "44100",
                    "-ac", "2",  # Force stereo
                    "-avoid_negative_ts", "make_zero",
                    "-fflags", "+genpts",
                    audio_path
                ]
            },
            # Strategy 2: More compatible settings with auto-detection
            {
                "name": "Compatible",
                "cmd": [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn",
                    "-acodec", "libmp3lame", 
                    "-ab", "128k", 
                    "-ar", "44100",
                    "-ac", "2",
                    audio_path
                ]
            },
            # Strategy 3: Basic extraction with quality parameter
            {
                "name": "Quality Auto",
                "cmd": [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn", 
                    "-q:a", "2",  # High quality
                    "-ar", "44100",
                    audio_path
                ]
            },
            # Strategy 4: Minimal settings for problematic files
            {
                "name": "Minimal",
                "cmd": [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn", 
                    "-acodec", "mp3",
                    "-f", "mp3",
                    audio_path
                ]
            }
        ]
        
        for i, strategy in enumerate(strategies, 1):
            try:
                strategy_name = strategy["name"]
                cmd = strategy["cmd"]
                
                logging.info(f"[IG Service] Trying audio extraction strategy {i}: {strategy_name}")
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd, 
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await proc.communicate()
                
                # Validate extraction result
                if (proc.returncode == 0 and 
                    os.path.exists(audio_path) and 
                    os.path.getsize(audio_path) > 1000):  # At least 1KB
                    
                    # Additional validation: check if extracted audio is valid
                    if await _validate_extracted_audio(audio_path):
                        logging.info(f"[IG Service] Audio extracted successfully with strategy {i}: {strategy_name}")
                        return audio_path
                    else:
                        logging.warning(f"[IG Service] Strategy {i} produced invalid audio file")
                else:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    logging.warning(f"[IG Service] Strategy {i} ({strategy_name}) failed: {error_msg}")
                
                # Clean up failed attempt
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass
                        
            except Exception as e:
                logging.warning(f"[IG Service] Strategy {i} exception: {e}")
                continue
        
        logging.error("[IG Service] All audio extraction strategies failed")
        return None
        
    except Exception as e:
        logging.error(f"[IG Service] Audio extraction critical error: {e}")
        return None


async def _validate_extracted_audio(audio_path: str) -> bool:
    """Validate that extracted audio file is valid and usable."""
    try:
        import shutil
        if not shutil.which("ffprobe") or not os.path.exists(audio_path):
            return os.path.getsize(audio_path) > 1000  # Basic size check
        
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size:stream=codec_name,sample_rate,channels",
            "-of", "json",
            audio_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        
        if proc.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            
            # Check format
            format_info = data.get("format", {})
            duration = format_info.get("duration")
            size = format_info.get("size")
            
            # Check streams
            streams = data.get("streams", [])
            
            if duration and size and streams:
                try:
                    duration_float = float(duration)
                    size_int = int(size)
                    
                    if duration_float > 0.1 and size_int > 1000:  # At least 0.1 seconds and 1KB
                        audio_stream = streams[0]
                        codec = audio_stream.get("codec_name", "")
                        sample_rate = audio_stream.get("sample_rate")
                        channels = audio_stream.get("channels")
                        
                        if codec and sample_rate and channels:
                            logging.info(f"[IG Service] Audio validation passed: {codec}, {sample_rate}Hz, {channels}ch, {duration_float:.1f}s")
                            return True
                except (ValueError, TypeError, IndexError):
                    pass
        
        logging.warning(f"[IG Service] Audio validation failed for {audio_path}")
        return False
        
    except Exception as e:
        logging.warning(f"[IG Service] Audio validation error: {e}")
        return os.path.getsize(audio_path) > 1000  # Fallback to size check