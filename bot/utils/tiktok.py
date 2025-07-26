import os
import logging
from typing import Dict, Optional, Tuple

from shazamio import Shazam
from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename
from uuid import uuid4


# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)


# === Convert TikTok video to audio ===
async def convert_tiktok_video_to_audio(tiktok_url: str) -> Optional[str]:
    """
    TikTok video URL'dan audio fayl yaratadi va lokalga saqlaydi.
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
            info = ydl.extract_info(tiktok_url, download=True)
            title = sanitize_filename(info.get("title", "audio"))
            ext = info.get("ext", "mp3")
            filename = os.path.join(TEMP_DIR, f"{title}.{ext}")
            return filename

    except Exception as e:
        logging.error(f"[TikTok Audio Extraction Error] {e}")
        return None


# === Shazam audio recognition ===
async def find_music_name(audio_file: str) -> Optional[str]:
    """
    Audio fayldan Shazam yordamida musiqa nomini aniqlaydi.
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


# === Download TikTok video ===
async def download_tiktok_media(tiktok_url: str) -> Optional[Tuple[str, str, str]]:
    """
    TikTok video URL orqali media yuklab olinadi.
    
    Returns:
        tuple: (file_path, title, media_id)
    """
    try:
        ydl_opts = {
            "format": "best",
            "quiet": True,
            "outtmpl": os.path.join(TEMP_DIR, "%(title)s.%(ext)s"),
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(tiktok_url, download=True)
            title = sanitize_filename(info.get("title", "TikTok Video"))
            ext = info.get("ext", "mp4")
            file_path = os.path.join(TEMP_DIR, f"{title}.{ext}")
            media_id = info.get("id")

            return file_path, title, media_id

    except Exception as e:
        logging.error(f"[TikTok Download Error] {e}")
        return None


# === Download YouTube audio by title ===
async def download_youtube_audio_by_title(title: str) -> Optional[Tuple[str, str, dict]]:
    """
    Musiqa nomi orqali YouTube'dan mp3 audio yuklab oladi.
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
        logging.error(f"[YouTube Audio Download Error] {e}")
        return None
