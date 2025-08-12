import os
import logging
import asyncio
import aiohttp
import aiofiles
import json
import time
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlparse
from yt_dlp.utils import sanitize_filename
from uuid import uuid4
from shazamio import Shazam

# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)

# Apify credentials
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

# Alternative Instagram scraper actors IDs - updated working actors
SCRAPER_ACTORS = [
    "shu8hvrXbJbY3Eb9W",  # Instagram Scraper (working)
    "heLL6fUofdAS7gRqf",  # Instagram Posts Scraper  
    "hMTVqz8ZTL5KPe7vJ",  # Social Media Scraper
]

# === Simple Instagram Downloader with Apify ===
class SimpleApifyInstagramDownloader:
    """
    Oddiy va ishonchli Apify Instagram downloader
    """
    
    def __init__(self):
        self.api_token = APIFY_API_TOKEN
        self.base_url = "https://api.apify.com/v2"
        self.session = None
        
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN environment variable not set")
        
        logging.info("Simple Apify Instagram downloader initialized")
    
    async def __aenter__(self):
        await self._setup_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _setup_session(self):
        """Setup aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=120)  # 2 minutes
        
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout
        )
    
    async def download_instagram_media(self, instagram_url: str) -> Optional[Tuple[str, str, str]]:
        """
        Instagram mediasini Apify orqali yuklab oladi
        """
        try:
            # Try different actors
            for actor_id in SCRAPER_ACTORS:
                try:
                    result = await self._try_actor(actor_id, instagram_url)
                    if result:
                        return result
                except Exception as e:
                    logging.warning(f"Actor {actor_id} failed: {str(e)}")
                    continue
            
            logging.error("All Apify actors failed")
            return None
            
        except Exception as e:
            logging.error(f"Apify Instagram download failed: {str(e)}")
            return None
    
    async def _try_actor(self, actor_id: str, instagram_url: str) -> Optional[Tuple[str, str, str]]:
        """
        Specific actor bilan sinab ko'radi
        """
        try:
            # Different input formats for different actors
            input_variants = [
                # Format 1: Standard format
                {
                    "directUrls": [instagram_url],
                    "resultsType": "posts",
                    "resultsLimit": 1,
                    "includeVideo": True
                },
                # Format 2: Simple format
                {
                    "urls": [instagram_url],
                    "limit": 1,
                    "includeVideo": True
                },
                # Format 3: Basic format
                {
                    "startUrls": [{"url": instagram_url}],
                    "maxItems": 1
                }
            ]
            
            # Try different input formats
            for i, input_data in enumerate(input_variants):
                try:
                    # Start actor run
                    run_url = f"{self.base_url}/acts/{actor_id}/runs"
                    
                    async with self.session.post(run_url, json=input_data) as response:
                        if response.status == 201:
                            run_info = await response.json()
                            run_id = run_info["data"]["id"]
                            
                            # Wait for completion
                            result_data = await self._wait_for_run(run_id, max_wait=90)
                            
                            if result_data and len(result_data) > 0:
                                # Process result
                                item = result_data[0]
                                
                                # Extract video URL
                                video_url = self._extract_video_url(item)
                                if not video_url:
                                    continue
                                
                                # Download video
                                file_path = await self._download_video(video_url, item)
                                if not file_path:
                                    continue
                                
                                # Extract metadata
                                title = self._extract_title(item)
                                media_id = self._extract_media_id(item, instagram_url)
                                
                                return file_path, title, media_id
                        else:
                            logging.warning(f"Actor {actor_id} format {i+1} failed: HTTP {response.status}")
                            continue
                            
                except Exception as format_error:
                    logging.warning(f"Actor {actor_id} format {i+1} error: {str(format_error)}")
                    continue
            
            logging.error(f"All input formats failed for actor {actor_id}")
            return None
            
        except Exception as e:
            logging.error(f"Actor {actor_id} error: {str(e)}")
            return None
    
    async def _wait_for_run(self, run_id: str, max_wait: int = 90) -> Optional[List[dict]]:
        """
        Run tugashini kutadi
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                status_url = f"{self.base_url}/actor-runs/{run_id}"
                
                async with self.session.get(status_url) as response:
                    if response.status != 200:
                        await asyncio.sleep(3)
                        continue
                    
                    run_info = await response.json()
                    status = run_info["data"]["status"]
                    
                    if status == "SUCCEEDED":
                        # Get results
                        items_url = f"{self.base_url}/actor-runs/{run_id}/dataset-items"
                        
                        async with self.session.get(items_url) as items_response:
                            if items_response.status == 200:
                                return await items_response.json()
                    
                    elif status in ["FAILED", "TIMED-OUT", "ABORTED"]:
                        logging.error(f"Run failed with status: {status}")
                        return None
                    
                    await asyncio.sleep(3)
                    
            except Exception as e:
                logging.error(f"Error waiting for run: {str(e)}")
                await asyncio.sleep(3)
        
        logging.error("Run timed out")
        return None
    
    def _extract_video_url(self, data: dict) -> Optional[str]:
        """
        Video URL ni topadi
        """
        try:
            # Multiple possible fields
            video_fields = [
                "videoUrl", "video_url", "url", "videoPlayUrl", 
                "video", "media_url", "download_url"
            ]
            
            for field in video_fields:
                if field in data and data[field]:
                    return data[field]
            
            # Check in nested structures
            if "video" in data and isinstance(data["video"], dict):
                for field in video_fields:
                    if field in data["video"] and data["video"][field]:
                        return data["video"][field]
            
            return None
            
        except Exception as e:
            logging.error(f"Error extracting video URL: {str(e)}")
            return None
    
    def _extract_title(self, data: dict) -> str:
        """
        Title ajratib oladi
        """
        try:
            title_fields = ["caption", "text", "title", "description"]
            
            for field in title_fields:
                if field in data and data[field]:
                    title = str(data[field])
                    if len(title) > 50:
                        title = title[:50] + "..."
                    return sanitize_filename(title)
            
            if "id" in data:
                return f"instagram_{data['id']}"
            
            return f"instagram_media_{uuid4().hex[:8]}"
            
        except Exception:
            return f"instagram_media_{uuid4().hex[:8]}"
    
    def _extract_media_id(self, data: dict, url: str) -> str:
        """
        Media ID ajratib oladi
        """
        try:
            id_fields = ["id", "pk", "shortcode", "code"]
            
            for field in id_fields:
                if field in data and data[field]:
                    return str(data[field])
            
            # URL dan shortcode ajratib olish
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) >= 2:
                return path_parts[1]
            
            return uuid4().hex[:12]
            
        except Exception:
            return uuid4().hex[:12]
    
    async def _download_video(self, video_url: str, data: dict) -> Optional[str]:
        """
        Video yuklab oladi
        """
        try:
            title = self._extract_title(data)
            filename = f"{title}.mp4"
            file_path = os.path.join(TEMP_DIR, filename)
            
            # Download video
            async with self.session.get(video_url) as response:
                if response.status != 200:
                    logging.error(f"Failed to download video: HTTP {response.status}")
                    return None
                
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logging.info(f"Downloaded video: {file_path}")
                return file_path
            else:
                logging.error("Downloaded file is empty")
                return None
                
        except Exception as e:
            logging.error(f"Error downloading video: {str(e)}")
            return None


# === Compatibility functions ===
async def download_instagram_media(insta_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Apify orqali Instagram media yuklab oladi
    """
    try:
        async with SimpleApifyInstagramDownloader() as downloader:
            return await downloader.download_instagram_media(insta_url)
    except Exception as e:
        logging.error(f"Failed to download Instagram media: {str(e)}")
        return None

async def get_instagram_media_info(insta_url: str) -> Optional[dict]:
    """
    Media haqida ma'lumot oladi (yuklab olmasdan)
    """
    # For now, we'll use download method and then delete the file
    # This can be optimized later to just get metadata
    try:
        result = await download_instagram_media(insta_url)
        if result:
            file_path, title, media_id = result
            
            # Delete the downloaded file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return {
                "title": title,
                "id": media_id,
                "description": title,
                "thumbnail": "",
                "uploader": "Unknown",
                "duration": 0,
            }
        return None
    except Exception as e:
        logging.error(f"Failed to get Instagram media info: {str(e)}")
        return None

async def convert_instagram_video_to_audio(insta_url: str) -> Optional[str]:
    """
    Instagram videosini audio ga o'giradi
    """
    try:
        # Download video
        result = await download_instagram_media(insta_url)
        if not result:
            return None
        
        video_path, title, media_id = result
        
        # Convert to audio
        audio_path = os.path.splitext(video_path)[0] + ".mp3"
        
        import subprocess
        try:
            subprocess.run([
                "ffmpeg",
                "-i", video_path,
                "-q:a", "2",
                "-y",
                audio_path
            ], check=True, capture_output=True)
            
            # Remove video file
            os.remove(video_path)
            
            return audio_path if os.path.exists(audio_path) else None
            
        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
            return None
            
    except Exception as e:
        logging.error(f"Failed to convert Instagram video to audio: {str(e)}")
        return None

# === Shazam integration ===
async def find_music_name(audio_file: str) -> Optional[str]:
    """
    Audio fayldan Shazam yordamida musiqa nomini aniqlaydi
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
