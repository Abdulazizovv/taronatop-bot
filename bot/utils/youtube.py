from yt_dlp import YoutubeDL
from typing import List, Dict, Any
import logging
import os
from io import BytesIO
from bot.loader import db
import re
from googleapiclient.discovery import build
from bot.data.config import YOUTUBE_API_KEY

PRIVATE_CHANNEL_ID = "-1002616385121"  # Replace with your private channel ID


TEMP_DIR = '/var/tmp/taronatop_bot'
MAX_DURATION = 3600  # 1 hour in seconds


# class YouTubeSearch:
#     """
#     A class to search YouTube videos using yt-dlp.
    
#     Attributes:
#         query (str): The search query string.
#         max_results (int): Maximum number of results to return (default: 50).
#         results (List[Dict]): List of video results from the search.
#     """
    
#     def __init__(self, query: str, max_results: int = 50):
#         """
#         Initialize the YouTube search object.
        
#         Args:
#             query: The search query string.
#             max_results: Maximum number of results to return (default: 50).
#         """
#         if not query or not isinstance(query, str):
#             raise ValueError("Query must be a non-empty string")
#         if not isinstance(max_results, int) or max_results <= 0:
#             raise ValueError("max_results must be a positive integer")
            
#         self.query = query.strip()
#         self.max_results = min(max_results, 100)  # Limit to 100 results max
#         self.results = self._search_youtube()

#     def _search_youtube(self) -> List[Dict[str, Any]]:
#         """
#         Perform the YouTube search using yt-dlp with optimized settings.
        
#         Returns:
#             List of video entries from the search.
            
#         Raises:
#             RuntimeError: If the search fails.
#         """
#         ydl_opts = {
#             "noplaylist": True,
#             "quiet": True,
#             "skip_download": True,
#             "extract_flat": True,
#             "format": "bestaudio/best",
#             "socket_timeout": 5,
#             "extract_retries": 3,
#             "no_cache_dir": False,
#             "cachedir": "/tmp/yt_dlp_cache",
#             "ignoreerrors": True,
#             "extractor_args": {
#                 "youtube": {
#                     "skip": ["dash", "hls"],
#                     "player_skip": ["js"],
#                 }
#             }
#         }
        
#         try:
#             with YoutubeDL(ydl_opts) as ydl:
#                 result = ydl.extract_info(
#                     f"ytsearch{self.max_results}:{self.query}", 
#                     download=False
#                 )
#                 return result.get("entries", [])
#         except Exception as e:
#             logging.error(f"Failed to search YouTube: {str(e)}")
#             raise RuntimeError(f"YouTube search failed: {str(e)}")

#     def to_dict(self) -> List[Dict[str, Any]]:
#         """
#         Convert search results to a list of standardized dictionaries.
        
#         Returns:
#             List of dictionaries containing video information.
#         """
#         formatted_results = []
        
#         for entry in self.results:
#             if not entry:
#                 continue
                
#             try:
#                 video_data = {
#                     "title": entry.get("title", "No title"),
#                     "url": entry.get("url") or f"https://youtu.be/{entry.get('id', '')}",
#                     "video_id": entry.get("id", ""),
#                     "duration": entry.get("duration"),
#                     "duration_formatted": self._format_duration(entry.get("duration")),
#                 }
#                 formatted_results.append(video_data)
#             except Exception as e:
#                 logging.warning(f"Failed to process video entry: {str(e)}")
#                 continue
                
#         return formatted_results
    
#     def _format_duration(self, duration: Optional[int]) -> str:
#         """
#         Format duration in seconds to HH:MM:SS format.
        
#         Args:
#             duration: Duration in seconds or None
            
#         Returns:
#             Formatted duration string or "Unknown duration"
#         """
#         if not duration or not isinstance(duration, (int, float)):
#             return "Unknown duration"
            
#         try:
#             hours = int(duration // 3600)
#             minutes = int((duration % 3600) // 60)
#             seconds = int(duration % 60)
            
#             if hours > 0:
#                 return f"{hours}:{minutes:02d}:{seconds:02d}"
#             return f"{minutes}:{seconds:02d}"
#         except Exception:
#             return "Unknown duration"
    
#     def _process_thumbnails(self, thumbnails: List[Dict]) -> List[Dict]:
#         """
#         Process and filter thumbnail data.
        
#         Args:
#             thumbnails: List of raw thumbnail dictionaries
            
#         Returns:
#             List of processed thumbnail dictionaries
#         """
#         processed = []
#         for thumb in thumbnails:
#             if not isinstance(thumb, dict):
#                 continue
                
#             try:
#                 processed.append({
#                     "url": thumb.get("url", ""),
#                     "width": thumb.get("width", 0),
#                     "height": thumb.get("height", 0),
#                     "resolution": f"{thumb.get('width', 0)}x{thumb.get('height', 0)}"
#                 })
#             except Exception:
#                 continue
                
#         return sorted(
#             processed,
#             key=lambda x: (x["width"], x["height"]),
#             reverse=True
#         )


class YouTubeSearch:
    """
    A class to search YouTube videos using YouTube Data API.
    """

    def __init__(self, query: str, max_results: int = 50):
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        if not isinstance(max_results, int) or max_results <= 0:
            raise ValueError("max_results must be a positive integer")

        self.query = query.strip()
        self.max_results = min(max_results, 50)  # API limit
        self.api_key = YOUTUBE_API_KEY
        self.youtube = build("youtube", "v3", developerKey=self.api_key, cache_discovery=False)
        self.results = self._search_youtube()

    def _search_youtube(self) -> List[Dict]:
        """
        Search videos using the YouTube API.
        """
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
        """
        Convert search results into standardized list of dicts.
        """
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

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

async def download_music(youtube_watch_url: str):
    if not youtube_watch_url.startswith("https://www.youtube.com/watch?v="):
        raise ValueError("Invalid YouTube watch URL")

    os.makedirs(TEMP_DIR, exist_ok=True)

    # Extract YouTube video ID from URL
    video_id = youtube_watch_url.split("v=")[-1].split("&")[0]
    filepath = os.path.join(TEMP_DIR, f"{video_id}.mp3")

    # ✅ Fayl allaqachon mavjud bo‘lsa, qayta yuklab o‘tirmaymiz
    audio_info = await db.get_youtube_audio(video_id)
    if audio_info and audio_info.get("telegram_file_id"):
        with open(filepath, 'rb') as f:
            audio_data = BytesIO(f.read())
        return audio_data, filepath, f"{audio_info['title']}.mp3"

    # Fayl mavjud bo'lmasa, yuklab olamiz
    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": os.path.join(TEMP_DIR, "%(id)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_watch_url, download=True)
            title = info.get("title", "Unknown Title")
            filename = os.path.join(TEMP_DIR, f"{info.get('id')}.mp3")

        if not os.path.exists(filename):
            raise RuntimeError("Fayl yaratilmagan.")

        with open(filename, 'rb') as f:
            audio_data = BytesIO(f.read())

        return audio_data, filename, clean_filename(title)

    except Exception as e:
        logging.error(f"Failed to download music: {str(e)}")
        raise RuntimeError(f"Music download failed: {str(e)}")


# display_results function remains unchanged
def display_results(results: List[Dict[str, Any]]) -> None:
    """
    Display search results in a user-friendly format.
    
    Args:
        results: List of video dictionaries from to_dict()
    """
    if not results:
        print("No results found.")
        return
        
    print(f"\nFound {len(results)} videos:")
    print("-" * 80)
    
    for idx, video in enumerate(results, 1):
        print(f"{idx}. {video['title']}")
        print(f"   Channel: {video['channel']}")
        print(f"   Duration: {video['duration']}")
        print(f"   Views: {video.get('view_count', 'Unknown')}")
        print(f"   URL: {video['url']}")
        
        if video['thumbnails']:
            best_thumb = video['thumbnails'][0]
            print(f"   Thumbnail: {best_thumb['url']} ({best_thumb['resolution']})")
        else:
            print("   No thumbnails available.")
            
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