import os
import re
import asyncio
import aiohttp
import aiofiles
import logging
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import time
import random

from yt_dlp import YoutubeDL
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bot.data.config import YOUTUBE_API_KEYS

# === Constants ===
TEMP_DIR = '/var/tmp/taronatop_bot'
MAX_DURATION = 3600  # 1 hour
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB for Telegram

# === Enhanced YouTube API Manager ===
class YouTubeAPIManager:
    """Manages multiple YouTube API keys with automatic rotation and quota management"""
    
    def __init__(self):
        self.api_keys = YOUTUBE_API_KEYS.copy()
        self.current_key_index = 0
        self.key_quota_used = {}  # Track quota usage per key
        self.key_last_used = {}  # Track when each key was last used
        self.daily_quota_limit = 10000  # Daily quota per key
        
        if not self.api_keys:
            raise ValueError("No YouTube API keys available")
        
        logging.info(f"Initialized YouTube API Manager with {len(self.api_keys)} keys")
    
    def get_current_api_key(self) -> str:
        """Get the current API key with rotation logic"""
        current_time = time.time()
        
        # Reset daily quota if needed (check if 24 hours passed)
        for key in self.api_keys:
            last_used = self.key_last_used.get(key, 0)
            if current_time - last_used > 86400:  # 24 hours
                self.key_quota_used[key] = 0
                logging.info(f"Reset quota for API key {key[:10]}...")
        
        # Find a key with available quota
        for _ in range(len(self.api_keys)):
            current_key = self.api_keys[self.current_key_index]
            quota_used = self.key_quota_used.get(current_key, 0)
            
            if quota_used < self.daily_quota_limit:
                self.key_last_used[current_key] = current_time
                logging.debug(f"Using API key {current_key[:10]}... (quota: {quota_used}/{self.daily_quota_limit})")
                return current_key
            
            # Try next key
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        
        # All keys exhausted, use the least used one
        least_used_key = min(self.api_keys, key=lambda k: self.key_quota_used.get(k, 0))
        logging.warning(f"All API keys near quota limit, using least used: {least_used_key[:10]}...")
        return least_used_key
    
    def rotate_api_key(self):
        """Manually rotate to next API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logging.info(f"Rotated to API key index {self.current_key_index}")
    
    def mark_key_quota_exceeded(self, api_key: str):
        """Mark an API key as quota exceeded"""
        self.key_quota_used[api_key] = self.daily_quota_limit
        logging.warning(f"Marked API key {api_key[:10]}... as quota exceeded")
        self.rotate_api_key()
    
    def increment_quota_usage(self, api_key: str, cost: int = 1):
        """Increment quota usage for a key"""
        self.key_quota_used[api_key] = self.key_quota_used.get(api_key, 0) + cost

    async def search_videos(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search for videos using YouTube API with key rotation"""
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        api_key = self.get_current_api_key()
        
        try:
            youtube = build('youtube', 'v3', developerKey=api_key)
            
            search_response = youtube.search().list(
                q=query,
                part='id,snippet',
                type='video',
                maxResults=max_results,
                order='relevance'
            ).execute()
            
            self.increment_quota_usage(api_key, 100)  # Search costs 100 quota units
            
            videos = []
            for search_result in search_response.get('items', []):
                video_info = {
                    'video_id': search_result['id']['videoId'],
                    'title': search_result['snippet']['title'],
                    'channel': search_result['snippet']['channelTitle'],
                    'description': search_result['snippet']['description'],
                    'thumbnail': search_result['snippet']['thumbnails'].get('default', {}).get('url'),
                    'url': f"https://www.youtube.com/watch?v={search_result['id']['videoId']}"
                }
                videos.append(video_info)
            
            return videos
            
        except HttpError as e:
            if e.resp.status == 403:  # Quota exceeded
                self.mark_key_quota_exceeded(api_key)
                if len(self.api_keys) > 1:
                    # Try with next key
                    return await self.search_videos(query, max_results)
            
            logging.error(f"YouTube API search error: {e}")
            return []
        except Exception as e:
            logging.error(f"YouTube search error: {e}")
            return []

# Global API manager instance
api_manager = YouTubeAPIManager()

# === Enhanced YouTube Downloader ===
class YouTubeDownloader:
    """Enhanced YouTube downloader with multiple fallback methods and anti-bot protection"""
    
    def __init__(self):
        self.session = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0'
        ]
        self.rate_limit_delay = 1  # Start with 1 second delay
        self.max_delay = 30  # Maximum delay between requests
        
        os.makedirs(TEMP_DIR, exist_ok=True)
    
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=300, connect=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': random.choice(self.user_agents)}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([^\s&]+)",
            r"youtube\.com/embed/([^\s&]+)",
            r"youtube\.com/v/([^\s&]+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def clean_filename(self, name: str) -> str:
        """Clean filename for safe storage"""
        return re.sub(r'[\\/*?:"<>|]', "", name)
    
    def get_enhanced_ydl_opts(self, base_opts: dict = None) -> dict:
        """Get enhanced yt-dlp options with anti-bot measures"""
        enhanced_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extract_flat": False,
            
            # Anti-bot measures
            "extractor_retries": 5,
            "fragment_retries": 5,
            "retries": 5,
            "sleep_interval_requests": random.uniform(1, 3),
            "sleep_interval_subtitles": random.uniform(1, 2),
            "sleep_interval": random.uniform(0.5, 1.5),
            
            # Headers to appear more like a browser
            "http_headers": {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            },
            
            # Additional anti-detection measures
            "prefer_free_formats": True,
            "youtube_include_dash_manifest": False,
            "no_check_certificate": True,
        }
        
        # Add cookies if available
        cookies_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt"),
            "cookies.txt",
            os.path.join(TEMP_DIR, "cookies.txt")
        ]
        
        for cookies_file in cookies_paths:
            if os.path.exists(cookies_file):
                enhanced_opts["cookiefile"] = cookies_file
                logging.info(f"Using cookies file: {cookies_file}")
                break
        
        # Merge with base options
        if base_opts:
            enhanced_opts.update(base_opts)
        
        return enhanced_opts
    
    async def _download_with_api_info(self, video_url: str, format_type: str) -> Optional[Tuple[BytesIO, str, str]]:
        """Method 1: Download using YouTube API for info + yt-dlp for download"""
        try:
            video_id = self.extract_video_id(video_url)
            if not video_id:
                return None
            
            # Get video info using API
            api_key = api_manager.get_current_api_key()
            youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
            
            try:
                request = youtube.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=video_id
                )
                response = request.execute()
                api_manager.increment_quota_usage(api_key, 1)
                
                if not response.get("items"):
                    return None
                
                video_info = response["items"][0]
                title = video_info["snippet"]["title"]
                
            except HttpError as e:
                if e.resp.status == 403:  # Quota exceeded
                    api_manager.mark_key_quota_exceeded(api_key)
                raise
            
            # Download using enhanced yt-dlp
            if format_type == "audio":
                base_opts = {
                    "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
                    "outtmpl": os.path.join(TEMP_DIR, f"{video_id}_api.%(ext)s"),
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192"
                    }]
                }
            else:  # video
                base_opts = {
                    "format": "best[height<=720][ext=mp4]/best[ext=mp4]/best",
                    "outtmpl": os.path.join(TEMP_DIR, f"{video_id}_api.%(ext)s"),
                    "merge_output_format": "mp4"
                }
            
            ydl_opts = self.get_enhanced_ydl_opts(base_opts)
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                
                # Find the downloaded file
                extension = "mp3" if format_type == "audio" else "mp4"
                filename = os.path.join(TEMP_DIR, f"{video_id}_api.{extension}")
                
                if not os.path.exists(filename):
                    # Try to find the actual filename
                    for file in os.listdir(TEMP_DIR):
                        if file.startswith(f"{video_id}_api"):
                            filename = os.path.join(TEMP_DIR, file)
                            break
                
                if os.path.exists(filename):
                    # Check file size
                    file_size = os.path.getsize(filename)
                    if file_size > MAX_FILE_SIZE:
                        os.remove(filename)
                        raise Exception(f"File too large: {file_size} bytes")
                    
                    with open(filename, 'rb') as f:
                        data = BytesIO(f.read())
                    
                    clean_title = self.clean_filename(title)
                    return data, filename, f"{clean_title}.{extension}"
            
            return None
            
        except Exception as e:
            logging.error(f"API info download method failed: {e}")
            return None
    
    async def _download_with_enhanced_ytdlp(self, video_url: str, format_type: str) -> Optional[Tuple[BytesIO, str, str]]:
        """Method 2: Enhanced yt-dlp with maximum anti-bot protection"""
        try:
            video_id = self.extract_video_id(video_url) or "unknown"
            
            # Add random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            if format_type == "audio":
                base_opts = {
                    "format": "bestaudio[abr<=192]/bestaudio",
                    "outtmpl": os.path.join(TEMP_DIR, f"{video_id}_enhanced.%(ext)s"),
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "128"  # Lower quality for faster download
                    }]
                }
            else:  # video
                base_opts = {
                    "format": "best[height<=480][ext=mp4]/best[height<=720][ext=mp4]/best[ext=mp4]",
                    "outtmpl": os.path.join(TEMP_DIR, f"{video_id}_enhanced.%(ext)s"),
                    "merge_output_format": "mp4"
                }
            
            ydl_opts = self.get_enhanced_ydl_opts(base_opts)
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get("title", "Unknown")
                
                # Find the downloaded file
                extension = "mp3" if format_type == "audio" else "mp4"
                filename = os.path.join(TEMP_DIR, f"{video_id}_enhanced.{extension}")
                
                if not os.path.exists(filename):
                    # Try to find the actual filename
                    for file in os.listdir(TEMP_DIR):
                        if file.startswith(f"{video_id}_enhanced"):
                            filename = os.path.join(TEMP_DIR, file)
                            break
                
                if os.path.exists(filename):
                    # Check file size
                    file_size = os.path.getsize(filename)
                    if file_size > MAX_FILE_SIZE:
                        os.remove(filename)
                        raise Exception(f"File too large: {file_size} bytes")
                    
                    with open(filename, 'rb') as f:
                        data = BytesIO(f.read())
                    
                    clean_title = self.clean_filename(title)
                    return data, filename, f"{clean_title}.{extension}"
            
            return None
            
        except Exception as e:
            logging.error(f"Enhanced yt-dlp method failed: {e}")
            return None
    
    async def _download_with_basic_ytdlp(self, video_url: str, format_type: str) -> Optional[Tuple[BytesIO, str, str]]:
        """Method 3: Basic yt-dlp as last resort"""
        try:
            video_id = self.extract_video_id(video_url) or "unknown"
            
            if format_type == "audio":
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(TEMP_DIR, f"{video_id}_basic.%(ext)s"),
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "128"
                    }],
                    "quiet": True
                }
            else:  # video
                ydl_opts = {
                    "format": "worst[ext=mp4]/worst",
                    "outtmpl": os.path.join(TEMP_DIR, f"{video_id}_basic.%(ext)s"),
                    "quiet": True
                }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get("title", "Unknown")
                
                # Find the downloaded file
                extension = "mp3" if format_type == "audio" else "mp4"
                filename = os.path.join(TEMP_DIR, f"{video_id}_basic.{extension}")
                
                if not os.path.exists(filename):
                    # Try to find the actual filename
                    for file in os.listdir(TEMP_DIR):
                        if file.startswith(f"{video_id}_basic"):
                            filename = os.path.join(TEMP_DIR, file)
                            break
                
                if os.path.exists(filename):
                    with open(filename, 'rb') as f:
                        data = BytesIO(f.read())
                    
                    clean_title = self.clean_filename(title)
                    return data, filename, f"{clean_title}.{extension}"
            
            return None
            
        except Exception as e:
            logging.error(f"Basic yt-dlp method failed: {e}")
            return None
    
    async def download_media(self, video_url: str, format_type: str) -> Optional[Tuple[BytesIO, str, str]]:
        """
        Main download method with fallbacks
        
        Args:
            video_url: YouTube URL
            format_type: "audio" or "video"
            
        Returns:
            Tuple of (BytesIO data, filepath, filename) or None if failed
        """
        methods = [
            ("API + Enhanced yt-dlp", self._download_with_api_info),
            ("Enhanced yt-dlp", self._download_with_enhanced_ytdlp),
            ("Basic yt-dlp", self._download_with_basic_ytdlp),
        ]
        
        for method_name, method in methods:
            try:
                logging.info(f"Trying YouTube download method: {method_name}")
                result = await method(video_url, format_type)
                
                if result:
                    logging.info(f"YouTube download successful using method: {method_name}")
                    return result
                    
            except Exception as e:
                logging.warning(f"YouTube method '{method_name}' failed: {e}")
                continue
        
        logging.error("All YouTube download methods failed")
        return None
    
    async def get_video_info(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Get video information using API with fallback to yt-dlp"""
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return None
        
        # Try API first
        try:
            api_key = api_manager.get_current_api_key()
            youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
            
            request = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id
            )
            response = request.execute()
            api_manager.increment_quota_usage(api_key, 1)
            
            if response.get("items"):
                video = response["items"][0]
                snippet = video["snippet"]
                stats = video["statistics"]
                duration = video["contentDetails"]["duration"]
                
                return {
                    "video_id": video_id,
                    "title": snippet["title"],
                    "description": snippet.get("description", ""),
                    "channel_title": snippet["channelTitle"],
                    "publish_date": snippet["publishedAt"],
                    "thumbnail_url": snippet["thumbnails"]["high"]["url"],
                    "view_count": stats.get("viewCount"),
                    "like_count": stats.get("likeCount"),
                    "duration": duration
                }
        except Exception as e:
            logging.warning(f"API video info failed: {e}")
        
        # Fallback to yt-dlp
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return {
                    "video_id": video_id,
                    "title": info.get("title", "Unknown"),
                    "description": info.get("description", ""),
                    "channel_title": info.get("uploader", "Unknown"),
                    "publish_date": info.get("upload_date", ""),
                    "thumbnail_url": info.get("thumbnail", ""),
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "duration": info.get("duration")
                }
        except Exception as e:
            logging.error(f"yt-dlp video info failed: {e}")
        
        return None

# === Public API Functions ===
async def download_youtube_music(video_url: str) -> Optional[Tuple[BytesIO, str, str]]:
    """Download YouTube video as audio"""
    async with YouTubeDownloader() as downloader:
        return await downloader.download_media(video_url, "audio")

async def download_youtube_video(video_url: str) -> Optional[Tuple[BytesIO, str, str]]:
    """Download YouTube video"""
    async with YouTubeDownloader() as downloader:
        return await downloader.download_media(video_url, "video")

async def get_youtube_video_info(video_url: str) -> Optional[Dict[str, Any]]:
    """Get YouTube video information"""
    async with YouTubeDownloader() as downloader:
        return await downloader.get_video_info(video_url)

async def safely_remove_file(filepath: str) -> None:
    """Safely remove a file"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Removed temporary file: {filepath}")
    except Exception as e:
        logging.error(f"Failed to remove temporary file {filepath}: {str(e)}")

# === Search Functions ===
class YouTubeSearcher:
    """YouTube search with API rotation"""
    
    def __init__(self):
        pass
    
    async def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search YouTube videos with API fallback"""
        if not query.strip():
            return []
        
        # Try API search first
        try:
            api_key = api_manager.get_current_api_key()
            youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
            
            response = youtube.search().list(
                q=query,
                part="snippet",
                maxResults=min(max_results, 50),
                type="video",
                safeSearch="strict"
            ).execute()
            api_manager.increment_quota_usage(api_key, 100)  # Search costs 100 quota units
            
            results = []
            for item in response.get("items", []):
                try:
                    video_id = item["id"]["videoId"]
                    snippet = item["snippet"]
                    results.append({
                        "title": snippet.get("title", "No title"),
                        "video_id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "thumbnail_url": snippet["thumbnails"]["high"]["url"],
                        "channel_title": snippet.get("channelTitle", "Unknown"),
                        "description": snippet.get("description", "")
                    })
                except Exception as e:
                    logging.warning(f"Failed to process search item: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logging.warning(f"YouTube API search failed: {e}")
        
        # Fallback to yt-dlp search (limited functionality)
        try:
            search_url = f"ytsearch{max_results}:{query}"
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                search_results = ydl.extract_info(search_url, download=False)
                
                results = []
                for entry in search_results.get("entries", []):
                    results.append({
                        "title": entry.get("title", "No title"),
                        "video_id": entry.get("id", ""),
                        "url": entry.get("url", ""),
                        "thumbnail_url": entry.get("thumbnail", ""),
                        "channel_title": entry.get("uploader", "Unknown"),
                        "description": ""
                    })
                
                return results
                
        except Exception as e:
            logging.error(f"yt-dlp search fallback failed: {e}")
        
        return []

async def search_youtube(query: str, max_results: int = 20) -> List[Dict[str, Any]]:
    """Search YouTube videos"""
    searcher = YouTubeSearcher()
    return await searcher.search(query, max_results)

# === Testing ===
if __name__ == '__main__':
    async def test_enhanced_youtube():
        """Test the enhanced YouTube downloader"""
        test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # Short test video
        
        print("🧪 Testing Enhanced YouTube Downloader")
        print("=" * 50)
        
        # Test video info
        print("📋 Testing video info...")
        try:
            info = await get_youtube_video_info(test_url)
            if info:
                print(f"✅ Title: {info['title']}")
                print(f"✅ Channel: {info['channel_title']}")
            else:
                print("❌ Failed to get video info")
        except Exception as e:
            print(f"❌ Video info error: {e}")
        
        print()
        
        # Test audio download
        print("🎵 Testing audio download...")
        try:
            result = await download_youtube_music(test_url)
            if result:
                audio_data, filepath, filename = result
                print(f"✅ Audio downloaded: {filename}")
                print(f"✅ Size: {len(audio_data.getvalue())} bytes")
                await safely_remove_file(filepath)
            else:
                print("❌ Audio download failed")
        except Exception as e:
            print(f"❌ Audio download error: {e}")
        
        print()
        
        # Test video download
        print("🎥 Testing video download...")
        try:
            result = await download_youtube_video(test_url)
            if result:
                video_data, filepath, filename = result
                print(f"✅ Video downloaded: {filename}")
                print(f"✅ Size: {len(video_data.getvalue())} bytes")
                await safely_remove_file(filepath)
            else:
                print("❌ Video download failed")
        except Exception as e:
            print(f"❌ Video download error: {e}")
        
        print()
        
        # Test search
        print("🔍 Testing search...")
        try:
            results = await search_youtube("test song", 3)
            if results:
                print(f"✅ Found {len(results)} search results:")
                for i, result in enumerate(results, 1):
                    print(f"  {i}. {result['title']}")
            else:
                print("❌ Search failed")
        except Exception as e:
            print(f"❌ Search error: {e}")
        
        print("\n🏁 Test completed!")
    
    # Run tests
    import asyncio
    asyncio.run(test_enhanced_youtube())
