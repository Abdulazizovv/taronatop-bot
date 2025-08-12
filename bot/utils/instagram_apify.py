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

# Apify Instagram Scraper Actor ID - bu public actor
INSTAGRAM_SCRAPER_ACTOR_ID = "apify/instagram-scraper"

# === Apify Instagram Scraper Integration ===
class ApifyInstagramDownloader:
    """
    Apify Instagram Scraper API bilan ishlash uchun klass
    """
    
    def __init__(self):
        self.api_token = APIFY_API_TOKEN
        self.base_url = "https://api.apify.com/v2"
        self.session = None
        
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN environment variable not set")
        
        logging.info("Apify Instagram downloader initialized")
    
    async def __aenter__(self):
        await self._setup_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _setup_session(self):
        """Setup aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
        
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
        Instagram mediasini Apify scraper orqali yuklab oladi
        
        Args:
            instagram_url (str): Instagram post/reel URL
            
        Returns:
            tuple: (file_path, title, media_id) yoki None
        """
        try:
            # 1. Apify actor orqali data olish
            scraper_data = await self._scrape_instagram_post(instagram_url)
            if not scraper_data:
                logging.error("Failed to scrape Instagram data")
                return None
            
            # 2. Video URL ni topish
            video_url = self._extract_video_url(scraper_data)
            if not video_url:
                logging.error("No video URL found in scraped data")
                return None
            
            # 3. Video faylni yuklab olish
            file_path = await self._download_video_file(video_url, scraper_data)
            if not file_path:
                logging.error("Failed to download video file")
                return None
            
            # 4. Metadata tayyorlash
            title = self._extract_title(scraper_data)
            media_id = self._extract_media_id(scraper_data, instagram_url)
            
            return file_path, title, media_id
            
        except Exception as e:
            logging.error(f"Apify Instagram download failed: {str(e)}")
            return None
    
    async def _scrape_instagram_post(self, instagram_url: str) -> Optional[dict]:
        """
        Apify Instagram Scraper actor orqali post ma'lumotlarini oladi
        """
        try:
            # Actor input parametrlari
            input_data = {
                "directUrls": [instagram_url],
                "resultsType": "posts",
                "resultsLimit": 1,
                "searchLimit": 1,
                "includeVideo": True,
                "addParentData": False
            }
            
            # Actor ni ishga tushirish
            run_url = f"{self.base_url}/acts/{INSTAGRAM_SCRAPER_ACTOR_ID}/runs"
            
            async with self.session.post(run_url, json=input_data) as response:
                if response.status != 201:
                    logging.error(f"Failed to start Apify actor: {response.status}")
                    return None
                
                run_info = await response.json()
                run_id = run_info["data"]["id"]
            
            # Run tugashini kutish
            result_data = await self._wait_for_run_completion(run_id)
            
            if result_data and len(result_data) > 0:
                return result_data[0]  # Birinchi natijani qaytaramiz
            
            return None
            
        except Exception as e:
            logging.error(f"Error scraping Instagram post: {str(e)}")
            return None
    
    async def _wait_for_run_completion(self, run_id: str, max_wait_time: int = 180) -> Optional[List[dict]]:
        """
        Apify run tugashini kutadi va natijalarni qaytaradi
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                # Run holatini tekshirish
                status_url = f"{self.base_url}/actor-runs/{run_id}"
                
                async with self.session.get(status_url) as response:
                    if response.status != 200:
                        await asyncio.sleep(5)
                        continue
                    
                    run_info = await response.json()
                    status = run_info["data"]["status"]
                    
                    if status == "SUCCEEDED":
                        # Natijalarni olish
                        items_url = f"{self.base_url}/actor-runs/{run_id}/dataset-items"
                        
                        async with self.session.get(items_url) as items_response:
                            if items_response.status == 200:
                                return await items_response.json()
                    
                    elif status in ["FAILED", "TIMED-OUT", "ABORTED"]:
                        logging.error(f"Apify run failed with status: {status}")
                        return None
                    
                    # Hali tugamagan bo'lsa, kutamiz
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logging.error(f"Error waiting for run completion: {str(e)}")
                await asyncio.sleep(5)
        
        logging.error("Apify run timed out")
        return None
    
    def _extract_video_url(self, data: dict) -> Optional[str]:
        """
        Scraped data dan video URL ni ajratib oladi
        """
        try:
            # Video URLs ni topish
            if "videoUrl" in data and data["videoUrl"]:
                return data["videoUrl"]
            
            if "videos" in data and data["videos"]:
                return data["videos"][0] if isinstance(data["videos"], list) else data["videos"]
            
            if "videoUrls" in data and data["videoUrls"]:
                return data["videoUrls"][0] if isinstance(data["videoUrls"], list) else data["videoUrls"]
            
            # Alternate fields
            if "url" in data and "video" in str(data["url"]).lower():
                return data["url"]
            
            return None
            
        except Exception as e:
            logging.error(f"Error extracting video URL: {str(e)}")
            return None
    
    def _extract_title(self, data: dict) -> str:
        """
        Scraped data dan title ni ajratib oladi
        """
        try:
            # Caption yoki text ni topish
            if "caption" in data and data["caption"]:
                caption = data["caption"]
                # Caption ni 50 belgiga qisqartirish
                if len(caption) > 50:
                    caption = caption[:50] + "..."
                return sanitize_filename(caption)
            
            if "text" in data and data["text"]:
                text = data["text"]
                if len(text) > 50:
                    text = text[:50] + "..."
                return sanitize_filename(text)
            
            if "description" in data and data["description"]:
                desc = data["description"]
                if len(desc) > 50:
                    desc = desc[:50] + "..."
                return sanitize_filename(desc)
            
            # Fallback
            if "id" in data:
                return f"instagram_{data['id']}"
            
            return f"instagram_media_{uuid4().hex[:8]}"
            
        except Exception as e:
            logging.error(f"Error extracting title: {str(e)}")
            return f"instagram_media_{uuid4().hex[:8]}"
    
    def _extract_media_id(self, data: dict, url: str) -> str:
        """
        Scraped data dan media ID ni ajratib oladi
        """
        try:
            if "id" in data and data["id"]:
                return str(data["id"])
            
            if "pk" in data and data["pk"]:
                return str(data["pk"])
            
            if "shortcode" in data and data["shortcode"]:
                return data["shortcode"]
            
            # URL dan ID ajratib olishga harakat qilish
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) >= 2:
                return path_parts[1]  # /p/SHORTCODE/ yoki /reel/SHORTCODE/
            
            return uuid4().hex[:12]
            
        except Exception as e:
            logging.error(f"Error extracting media ID: {str(e)}")
            return uuid4().hex[:12]
    
    async def _download_video_file(self, video_url: str, data: dict) -> Optional[str]:
        """
        Video faylni yuklab oladi
        """
        try:
            # Fayl nomini yaratish
            title = self._extract_title(data)
            file_extension = "mp4"  # Default to mp4
            
            # URL dan extension topishga harakat qilish
            if "." in video_url.split("?")[0]:  # Query parametrlarni olib tashlash
                url_ext = video_url.split("?")[0].split(".")[-1].lower()
                if url_ext in ["mp4", "mov", "avi", "webm"]:
                    file_extension = url_ext
            
            filename = f"{title}.{file_extension}"
            file_path = os.path.join(TEMP_DIR, filename)
            
            # Video faylni yuklab olish
            async with self.session.get(video_url) as response:
                if response.status != 200:
                    logging.error(f"Failed to download video: HTTP {response.status}")
                    return None
                
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
            
            # Fayl mavjudligini tekshirish
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logging.info(f"Successfully downloaded video: {file_path}")
                return file_path
            else:
                logging.error("Downloaded file is empty or doesn't exist")
                return None
                
        except Exception as e:
            logging.error(f"Error downloading video file: {str(e)}")
            return None
    
    async def get_instagram_media_info(self, instagram_url: str) -> Optional[dict]:
        """
        Instagram media haqida ma'lumot oladi (yuklab olmasdan)
        """
        try:
            scraper_data = await self._scrape_instagram_post(instagram_url)
            if not scraper_data:
                return None
            
            return {
                "title": self._extract_title(scraper_data),
                "description": scraper_data.get("caption", ""),
                "thumbnail": scraper_data.get("displayUrl", ""),
                "uploader": scraper_data.get("ownerUsername", "Unknown"),
                "upload_date": scraper_data.get("timestamp", ""),
                "duration": scraper_data.get("videoDuration", 0),
                "id": self._extract_media_id(scraper_data, instagram_url),
                "likes": scraper_data.get("likesCount", 0),
                "comments": scraper_data.get("commentsCount", 0),
                "views": scraper_data.get("videoViewCount", 0),
            }
            
        except Exception as e:
            logging.error(f"Error getting media info: {str(e)}")
            return None


# === Compatibility functions for existing code ===
async def download_instagram_media(insta_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Apify Instagram Scraper ishlatib media yuklab oladi
    """
    try:
        async with ApifyInstagramDownloader() as downloader:
            return await downloader.download_instagram_media(insta_url)
    except Exception as e:
        logging.error(f"Failed to download Instagram media: {str(e)}")
        return None

async def get_instagram_media_info(insta_url: str) -> Optional[dict]:
    """
    Apify Instagram Scraper ishlatib media ma'lumotini oladi
    """
    try:
        async with ApifyInstagramDownloader() as downloader:
            return await downloader.get_instagram_media_info(insta_url)
    except Exception as e:
        logging.error(f"Failed to get Instagram media info: {str(e)}")
        return None

async def convert_instagram_video_to_audio(insta_url: str) -> Optional[str]:
    """
    Instagram videosini audio ga o'giradi Apify orqali
    """
    try:
        # Videoni yuklab olish
        result = await download_instagram_media(insta_url)
        if not result:
            return None
        
        video_path, title, media_id = result
        
        # Audio ga o'girish
        audio_path = os.path.splitext(video_path)[0] + ".mp3"
        
        import subprocess
        try:
            subprocess.run([
                "ffmpeg",
                "-i", video_path,
                "-q:a", "2",
                "-y",  # Overwrite if exists
                audio_path
            ], check=True, capture_output=True)
            
            # Original video faylni o'chirish (space tejash uchun)
            os.remove(video_path)
            
            return audio_path if os.path.exists(audio_path) else None
            
        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
            return None
            
    except Exception as e:
        logging.error(f"Failed to convert Instagram video to audio: {str(e)}")
        return None

# === Shazam integration (existing function) ===
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
