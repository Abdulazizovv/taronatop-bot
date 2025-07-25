import os
import re
import logging
from io import BytesIO
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

from yt_dlp import YoutubeDL
from googleapiclient.discovery import build

from bot.loader import db
from bot.data.config import YOUTUBE_API_KEY

# === Constants ===
TEMP_DIR = '/var/tmp/taronatop_bot'
MAX_DURATION = 3600  # 1 hour
PRIVATE_CHANNEL_ID = "-1002616385121"

# === Helpers ===
def extract_video_id(url: str) -> str | None:
    """
    YouTube URL dan video ID ajratib olish.
    """
    regex = (
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([^\s&]+)"
    )
    match = re.search(regex, url)
    return match.group(1) if match else None

def clean_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)

def safely_remove(filepath: str) -> None:
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Removed temporary file: {filepath}")
    except Exception as e:
        logging.error(f"Failed to remove temporary file {filepath}: {str(e)}")

# === YouTube Search using API ===
class YouTubeSearch:
    def __init__(self, query: str, max_results: int = 50):
        if not query:
            raise ValueError("Query must be a non-empty string")
        self.query = query.strip()
        self.max_results = min(max_results, 50)
        self.youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY, cache_discovery=False)
        self.results = self._search_youtube()

    def _search_youtube(self) -> List[Dict]:
        try:
            response = self.youtube.search().list(
                q=self.query,
                part="snippet",
                maxResults=self.max_results,
                type="video",
                safeSearch="strict"
            ).execute()
            return response.get("items", [])
        except Exception as e:
            logging.error(f"Failed to search YouTube: {str(e)}")
            raise RuntimeError("YouTube search failed")

    def to_dict(self) -> List[Dict]:
        formatted = []
        for item in self.results:
            try:
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]
                formatted.append({
                    "title": snippet.get("title", "No title"),
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail_url": snippet["thumbnails"]["high"]["url"]
                })
            except Exception as e:
                logging.warning(f"Failed to process item: {str(e)}")
                continue
        return formatted

# === YouTube Info ===
def get_video_info(video_url: str):
    video_id = extract_video_id(video_url)
    if not video_id:
        return None

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id
    )
    response = request.execute()


    if "items" not in response or not response["items"]:
        return None

    video = response["items"][0]
    snippet = video["snippet"]
    stats = video["statistics"]
    duration = video["contentDetails"]["duration"]

    return {
        "video_id": video_id,
        "title": snippet["title"],
        "description": snippet["description"],
        "channel_title": snippet["channelTitle"],
        "publish_date": snippet["publishedAt"],
        "thumbnail_url": snippet["thumbnails"]["high"]["url"],
        "view_count": stats.get("viewCount"),
        "like_count": stats.get("likeCount"),
        "duration": duration
    }

# === Downloaders ===
async def download_music(youtube_watch_url: str):
    video_id = extract_video_id(youtube_watch_url)
    filepath = os.path.join(TEMP_DIR, f"{video_id}.mp3")

    os.makedirs(TEMP_DIR, exist_ok=True)

    audio_info = await db.get_youtube_audio(video_id)
    if audio_info and audio_info.get("telegram_file_id"):
        with open(filepath, 'rb') as f:
            return BytesIO(f.read()), filepath, f"{audio_info['title']}.mp3"

    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": os.path.join(TEMP_DIR, "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_watch_url, download=True)
            filename = os.path.join(TEMP_DIR, f"{info['id']}.mp3")
        with open(filename, 'rb') as f:
            return BytesIO(f.read()), filename, clean_filename(info.get("title", "Unknown")) + ".mp3"
    except Exception as e:
        logging.error(f"Failed to download music: {str(e)}")
        raise RuntimeError(f"Music download failed: {str(e)}")

async def download_video(youtube_watch_url: str):
    video_id = extract_video_id(youtube_watch_url)
    filepath = os.path.join(TEMP_DIR, f"{video_id}.mp4")

    os.makedirs(TEMP_DIR, exist_ok=True)

    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            return BytesIO(f.read()), filepath, f"{video_id}.mp4"

    ydl_opts = {
        "format": "best[ext=mp4][height<=480]",
        "outtmpl": os.path.join(TEMP_DIR, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4"
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_watch_url, download=True)
            filename = os.path.join(TEMP_DIR, f"{info['id']}.mp4")
        with open(filename, 'rb') as f:
            return BytesIO(f.read()), filename, clean_filename(info.get("title", "Unknown")) + ".mp4"
    except Exception as e:
        logging.error(f"Failed to download video: {str(e)}")
        raise RuntimeError(f"Video download failed: {str(e)}")

# === CLI Debug Tool ===
def display_results(results: List[Dict[str, Any]]) -> None:
    if not results:
        print("No results found.")
        return

    print(f"\nFound {len(results)} videos:")
    print("-" * 80)

    for idx, video in enumerate(results, 1):
        print(f"{idx}. {video['title']}")
        print(f"   URL: {video['url']}")
        print(f"   Thumbnail: {video['thumbnail_url']}")
        print("-" * 80)

if __name__ == '__main__':
    try:
        query = input("Enter YouTube search query: ").strip()
        if not query:
            print("Error: Search query cannot be empty.")
            exit(1)

        max_results = input("Maximum results to return (default 10): ").strip()
        max_results = int(max_results) if max_results.isdigit() else 10

        print(f"\nSearching YouTube for '{query}'...")
        search = YouTubeSearch(query, max_results)
        results = search.to_dict()
        display_results(results)

    except ValueError as ve:
        print(f"Input error: {str(ve)}")
    except RuntimeError as re:
        print(f"Search error: {str(re)}")
    except KeyboardInterrupt:
        print("\nSearch cancelled by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")