import os
import logging
from typing import Dict, Optional, Tuple

from shazamio import Shazam
from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename
from django.utils.text import slugify
from uuid import uuid4


# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
COOKIE_FILE = os.path.join("/usr/src/app", "cookies.txt")
os.makedirs(TEMP_DIR, exist_ok=True)


# === Convert Instagram video to audio ===
async def convert_instagram_video_to_audio(insta_url: str) -> Optional[str]:
    """
    Convert Instagram video to audio with robust error handling
    """
    try:
        # First verify cookie file exists and is valid
        if not os.path.exists(COOKIE_FILE):
            logging.error(f"Cookie file not found at {COOKIE_FILE}")
            return None
            
        try:
            with open(COOKIE_FILE) as f:
                content = f.read()
                if "instagram.com" not in content or "sessionid" not in content:
                    logging.error("Invalid Instagram cookies")
                    return None
        except Exception as e:
            logging.error(f"Cookie file read error: {str(e)}")
            return None

        ydl_opts = {
            "format": "bestaudio/best",
            "extractaudio": True,
            "audioformat": "mp3",
            "outtmpl": os.path.join(TEMP_DIR, "%(title)s.%(ext)s"),
            "quiet": False,  # Set to False to see more debug info
            "no_warnings": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "Referer": "https://www.instagram.com/",
                "X-IG-App-ID": "936619743392459",
            },
            "extractor_args": {
                "instagram": {
                    "skip_auth_warning": True,
                    "wait_for_approval": True,
                }
            },
            "sleep_interval": 5,
            "max_sleep_interval": 10,
            "ratelimit": "1M",
            "retries": 3,
            "cookiefile": COOKIE_FILE,
            "force_generic_extractor": True,
            "ignoreerrors": False,  # Show all errors
        }

        with YoutubeDL(ydl_opts) as ydl:
            # First try with standard extractor
            try:
                info = ydl.extract_info(insta_url, download=True)
            except Exception as e:
                logging.warning(f"Standard extraction failed, trying fallback: {str(e)}")
                # Try with embed page fallback
                ydl_opts['extractor_args']['instagram']['use_embed_page'] = True
                info = ydl.extract_info(insta_url, download=True)

            if not info:
                logging.error("No media info extracted")
                return None

            # Safely handle title and extension
            title = "instagram_audio"
            if 'title' in info:
                try:
                    title = sanitize_filename(str(info['title']))
                except:
                    title = "instagram_audio"
            
            ext = info.get('ext', 'mp3')
            filename = os.path.join(TEMP_DIR, f"{title}.{ext}")
            
            # Verify file was actually created
            if not os.path.exists(filename):
                logging.error(f"Output file not created: {filename}")
                return None
                
            return filename

    except Exception as e:
        logging.error(f"[Audio Extraction Error] {str(e)}", exc_info=True)
        return None


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
async def get_instagram_media_info(insta_url: str) -> Optional[Dict[str, str]]:
    """
    Instagram media havolasi orqali metama’lumotlarni qaytaradi.
    
    Args:
        insta_url (str): Instagram post yoki reel URL

    Returns:
        dict: Media haqida ma’lumot (sarlavha, tasvir, thumbnail, uploader, sana, davomiylik)
    """
    try:
        ydl_opts = {
            "quiet": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "Referer": "https://www.instagram.com/",
            },
            "sleep_interval": 5,
            "max_sleep_interval": 10,
            "ratelimit": "1M",
            "retries": 3,
            "skip_download": True,
            "force_generic_extractor": True,
            "cookiefile": COOKIE_FILE,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(insta_url, download=False)

        return {
            "title": info.get("title", "Instagram Media"),
            "description": info.get("description", ""),
            "thumbnail": info.get("thumbnail", ""),
            "uploader": info.get("uploader", "Unknown"),
            "upload_date": info.get("upload_date", ""),
            "duration": info.get("duration", 0),
        }

    except Exception as e:
        logging.error(f"[Metadata Extraction Error] {e}")
        return None


# === Download Instagram media ===
async def download_instagram_media(insta_url: str) -> Optional[tuple[str, str, str]]:
    """
    Instagram post yoki video URL orqali media yuklab olinadi.
    
    Args:
        insta_url (str): Instagram post yoki reel URL

    Returns:
        tuple: (file_path, file_name, title) yoki None agar xatolik yuz bersa
    """
    try:
        # First verify cookie file exists
        if not os.path.exists(COOKIE_FILE):
            logging.error(f"Cookie file not found at {COOKIE_FILE}")
            return None
            
        # Verify cookie file is readable
        try:
            with open(COOKIE_FILE) as f:
                if "instagram.com" not in f.read():
                    logging.error("Cookie file doesn't contain Instagram cookies")
                    return None
        except Exception as e:
            logging.error(f"Error reading cookie file: {str(e)}")
            return None

        ydl_opts = {
            "format": "best",
            "quiet": False,  # Temporarily set to False for debugging
            "outtmpl": os.path.join(TEMP_DIR, "%(title)s.%(ext)s"),
            "cookiefile": COOKIE_FILE,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "Referer": "https://www.instagram.com/",
                "X-IG-App-ID": "936619743392459",  # Important Instagram header
            },
            "extractor_args": {
                "instagram": {
                    "skip_auth_warning": True,
                }
            },
            "sleep_interval": 10,
            "max_sleep_interval": 30,
            "retries": 3,
            "ignoreerrors": False,  # Set to False to see actual errors
        }

        with YoutubeDL(ydl_opts) as ydl:
            # Add verbose logging
            ydl.add_default_info_extractors()
            info = ydl.extract_info(insta_url, download=True)
            
            if not info:
                logging.error("No info extracted from URL")
                return None
                
            title = sanitize_filename(info.get("title", "Instagram Media"))
            ext = info.get("ext", "mp4")
            file_path = os.path.join(TEMP_DIR, f"{title}.{ext}")
            
            return file_path, title, info.get("id")

    except Exception as e:
        logging.error(f"[Instagram Download Error] {str(e)}", exc_info=True)
        return None