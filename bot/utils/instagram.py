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
os.makedirs(TEMP_DIR, exist_ok=True)


# === Convert Instagram video to audio ===
async def convert_instagram_video_to_audio(insta_url: str) -> Optional[str]:
    """
    Instagram video URL'dan audio fayl yaratadi va lokalga saqlaydi.
    
    Args:
        insta_url (str): Instagram video URL
    
    Returns:
        str: Audio faylning lokal yo'li yoki None agar xatolik yuz bersa
    """
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
            info = ydl.extract_info(insta_url, download=True)
            title = sanitize_filename(info.get("title", "audio"))
            ext = info.get("ext", "mp3")
            filename = os.path.join(TEMP_DIR, f"{title}.{ext}")
            return filename

    except Exception as e:
        logging.error(f"[Audio Extraction Error] {e}")
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
            "skip_download": True,
            "force_generic_extractor": True
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
        ydl_opts = {
            "format": "best",
            "quiet": True,
            "outtmpl": os.path.join(TEMP_DIR, "%(title)s.%(ext)s"),
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(insta_url, download=True)
            title = sanitize_filename(info.get("title", "Instagram Media"))
            ext = info.get("ext", "mp4")
            file_path = os.path.join(TEMP_DIR, f"{title}.{ext}")

            if os.path.exists(file_path):
                # Fayl allaqachon mavjud bo'lsa, uni yuklab o'tirmaymiz
                return file_path, title, info.get("id")

            return file_path, title, info.get("id")

    except Exception as e:
        logging.error(f"[Download Error] {e}")
        return None
    return None, None, None