import os
import logging
import subprocess
from typing import Dict, Optional, Tuple

from shazamio import Shazam
from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename
from django.utils.text import slugify
from uuid import uuid4
from instagrapi import Client


# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
COOKIE_FILE = os.path.join("/usr/src/app", "cookies.txt")
os.makedirs(TEMP_DIR, exist_ok=True)


# === Convert Instagram video to audio ===
# Instagram credentials (should be in environment variables)
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

async def convert_instagram_video_to_audio(insta_url: str) -> Optional[str]:
    """
    Main function that tries multiple methods to convert Instagram video to audio
    """
    # First try with instagrapi (private API)
    result = await _convert_with_instagrapi(insta_url)
    if result:
        return result
    
    # Fallback to yt-dlp if instagrapi fails
    return await _convert_with_ytdlp(insta_url)

async def _convert_with_instagrapi(url: str) -> Optional[str]:
    """Convert using instagrapi private API"""
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        logging.warning("Instagram credentials not configured")
        return None

    cl = Client()
    try:
        # Login with credentials
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        
        # Get media PK from URL
        media_pk = cl.media_pk_from_url(url)
        
        
        # Download video
        video_path = cl.video_download(media_pk)
        
        # Convert to audio
        audio_path = os.path.splitext(video_path)[0] + ".mp3"
        await _convert_to_audio_ffmpeg(video_path, audio_path)
        
        return audio_path if os.path.exists(audio_path) else None
        
    except Exception as e:
        logging.error(f"instagrapi failed: {str(e)}")
        return None
    finally:
        try:
            cl.logout()
        except:
            pass

async def _convert_with_ytdlp(url: str) -> Optional[str]:
    """Fallback method using yt-dlp"""
    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "extractaudio": True,
            "audioformat": "mp3",
            "outtmpl": os.path.join(TEMP_DIR, "%(title)s.%(ext)s"),
            "quiet": True,
            "force_generic_extractor": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = sanitize_filename(info.get("title", "audio"))
            ext = info.get("ext", "mp3")
            return os.path.join(TEMP_DIR, f"{title}.{ext}")

    except Exception as e:
        logging.error(f"yt-dlp fallback failed: {str(e)}")
        return None

async def _convert_to_audio_ffmpeg(video_path: str, audio_path: str) -> bool:
    """Convert video file to audio using FFmpeg"""
    try:
        subprocess.run([
            "ffmpeg",
            "-i", video_path,
            "-q:a", "2",
            "-y",  # Overwrite if exists
            audio_path
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
        return False


# === Shazam audio recognition ===
async def find_music_name(audio_file: str) -> Optional[str]:
    """
    Audio fayldan Shazam yordamida musiqa nomini aniqlaydi.
    
    Args:
        audio_file (str): Audio faylning to‘liq yo‘li

    Returns:
        str: Musiqa nomi (title + artist) yoki None
    """
    try:
        shazam = Shazam()
        result = await shazam.recognize(audio_file)

        if result and "track" in result:
            track = result["track"]
            title = track.get("title", "Unknown")
            artist = track.get("subtitle", "Unknown")
            return f"{title} – {artist}"

    except Exception as e:
        logging.error(f"[Shazam Error] {e}")
    
    return None


# === Download audio by title ===
async def download_youtube_audio_by_title(title: str) -> Optional[Tuple[str, str, dict]]:
    """
    Berilgan musiqa nomi asosida YouTube'dan audio yuklab oladi.

    Args:
        title (str): Musiqa nomi (masalan: "Eminem Lose Yourself")

    Returns:
        tuple: (file_path, file_name, video_info_dict) yoki None agar xatolik bo‘lsa
    """
    try:
        search_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": "in_playlist"
        }

        with YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{title}", download=False)

        if not info or "entries" not in info or not info["entries"]:
            logging.warning(f"No entries found for title: {title}")
            return None

        video = info["entries"][0]
        video_id = video.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_title = video.get("title", title)

        filename = f"{uuid4().hex}"
        output_template = os.path.join(TEMP_DIR, filename + ".%(ext)s")

        download_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        with YoutubeDL(download_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            real_path = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")

        return real_path, filename, {
            "id": video_id,
            "title": video_title,
            "url": video_url
        }

    except Exception as e:
        logging.error(f"[download_youtube_audio_by_title Error] {e}")
        return None


# === Get Instagram media metadata ===
# async def get_instagram_media_info(insta_url: str) -> Optional[Dict[str, str]]:
#     """
#     Instagram media havolasi orqali metama’lumotlarni qaytaradi.
    
#     Args:
#         insta_url (str): Instagram post yoki reel URL

#     Returns:
#         dict: Media haqida ma’lumot (sarlavha, tasvir, thumbnail, uploader, sana, davomiylik)
#     """
#     try:
#         ydl_opts = {
#             "quiet": True,
#             "http_headers": {
#                 "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
#                 "Referer": "https://www.instagram.com/",
#             },
#             "sleep_interval": 5,
#             "max_sleep_interval": 10,
#             "ratelimit": "1M",
#             "retries": 3,
#             "skip_download": True,
#             "force_generic_extractor": True,
#             "cookiefile": COOKIE_FILE,
#         }

#         with YoutubeDL(ydl_opts) as ydl:
#             info = ydl.extract_info(insta_url, download=False)

#         return {
#             "title": info.get("title", "Instagram Media"),
#             "description": info.get("description", ""),
#             "thumbnail": info.get("thumbnail", ""),
#             "uploader": info.get("uploader", "Unknown"),
#             "upload_date": info.get("upload_date", ""),
#             "duration": info.get("duration", 0),
#         }

#     except Exception as e:
#         logging.error(f"[Metadata Extraction Error] {e}")
#         return None


# === Download Instagram media ===
async def download_instagram_media(insta_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Download Instagram media using best available method with fallbacks
    Returns: (file_path, title, media_id)
    """
    # Try instagrapi first (most reliable)
    result = await _download_with_instagrapi(insta_url)
    if result:
        return result
    
    # Fallback to yt-dlp with cookies
    result = await _download_with_ytdlp(insta_url)
    if result:
        return result
    
    # Final fallback to yt-dlp without cookies
    return await _download_with_ytdlp(insta_url, use_cookies=False)

async def _download_with_instagrapi(url: str) -> Optional[Tuple[str, str, str]]:
    """Download using instagrapi private API"""
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        return None

    cl = Client()
    try:
        # Configure client
        cl.delay_range = [2, 5]  # More natural request timing
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        
        # Get media info
        media_pk = cl.media_pk_from_url(url)
        media_info = cl.media_info(media_pk)
        
        # Download video
        video_path = cl.video_download(media_pk)
        title = sanitize_filename(media_info.caption_text or f"instagram_{media_pk}")
        
        # Generate output filename
        ext = os.path.splitext(video_path)[1][1:] or "mp4"
        output_path = os.path.join(TEMP_DIR, f"{title}.{ext}")
        os.rename(video_path, output_path)
        
        return output_path, title, str(media_pk)
        
    except Exception as e:
        logging.error(f"instagrapi download failed: {str(e)}")
        return None
    finally:
        try:
            cl.logout()
        except:
            pass

async def _download_with_ytdlp(url: str, use_cookies: bool = True) -> Optional[Tuple[str, str, str]]:
    """Download using yt-dlp with optional cookie support"""
    try:
        ydl_opts = {
            "format": "best",
            "outtmpl": os.path.join(TEMP_DIR, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "X-IG-App-ID": "936619743392459",
            },
            "extractor_args": {"instagram": {"skip_auth_warning": True}},
            "sleep_interval": 5,
            "retries": 3,
        }

        if use_cookies and os.path.exists(COOKIE_FILE):
            ydl_opts["cookiefile"] = COOKIE_FILE
            ydl_opts["extractor_args"]["instagram"]["wait_for_approval"] = False

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
                
            title = sanitize_filename(info.get("title", f"instagram_{info.get('id', 'media')}"))
            ext = info.get("ext", "mp4")
            file_path = os.path.join(TEMP_DIR, f"{title}.{ext}")
            
            return file_path, title, info.get("id")
            
    except Exception as e:
        logging.error(f"yt-dlp download failed: {str(e)}")
        return None

async def get_instagram_media_info(insta_url: str) -> Optional[dict]:
    """Get media info using best available method"""
    # Try instagrapi first
    if INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
        cl = Client()
        try:
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            media_pk = cl.media_pk_from_url(insta_url)
            media_info = cl.media_info(media_pk)
            
            return {
                "title": media_info.caption_text or "Instagram Media",
                "description": media_info.caption_text,
                "thumbnail": media_info.thumbnail_url,
                "uploader": media_info.user.username,
                "duration": media_info.video_duration,
                "id": str(media_pk)
            }
        except Exception:
            pass
        finally:
            try:
                cl.logout()
            except:
                pass
    
    # Fallback to yt-dlp
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "force_generic_extractor": True,
        }
        
        if os.path.exists(COOKIE_FILE):
            ydl_opts["cookiefile"] = COOKIE_FILE

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(insta_url, download=False)
            return {
                "title": info.get("title", "Instagram Media"),
                "description": info.get("description"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
                "duration": info.get("duration"),
                "id": info.get("id"),
            }
    except Exception as e:
        logging.error(f"Failed to get media info: {str(e)}")
        return None