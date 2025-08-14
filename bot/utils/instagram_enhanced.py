import os
import logging
import asyncio
import aiohttp
import aiofiles
import json
import time
import subprocess
import re
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlparse
from yt_dlp.utils import sanitize_filename
from uuid import uuid4
from shazamio import Shazam

# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)

# Multiple Apify API Tokens for load balancing
APIFY_API_TOKENS = [
    os.getenv("APIFY_API_TOKEN_1"),
    os.getenv("APIFY_API_TOKEN_2"),
    os.getenv("APIFY_API_TOKEN_3"),
    os.getenv("APIFY_API_TOKEN_4"),
    os.getenv("APIFY_API_TOKEN_5"),
]

# Filter out None values
APIFY_API_TOKENS = [token for token in APIFY_API_TOKENS if token]

# Backward compatibility
if not APIFY_API_TOKENS:
    # Try old environment variable
    old_token = os.getenv("APIFY_API_TOKEN")
    if old_token:
        APIFY_API_TOKENS = [old_token]
    else:
        logging.warning("No APIFY API tokens configured")

# Instagram Scraper Actor IDs - updated working actors
INSTAGRAM_SCRAPER_ACTORS = [
    "shu8hvrXbJbY3Eb9W",           # Main Instagram scraper - needs proper config
    "apify/instagram-post-scraper", # Working actor for posts
    "apify/instagram-scraper",      # Check if this exists
]

# User agents for anti-detection
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
]


class InstagramMediaDownloader:
    """
    Yangi Instagram media yuklab olish sistemi
    - Database tekshiruvi
    - yt-dlp (bepul kutubxona)
    - Apify (premium fallback)
    - Bir nechta API key'lar
    - User experience optimizatsiyasi
    """
    
    def __init__(self, db_instance):
        self.db = db_instance
        self.session = None
        self.apify_token_index = 0
        
    async def __aenter__(self):
        await self._setup_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def _setup_session(self):
        """HTTP session sozlash"""
        timeout = aiohttp.ClientTimeout(total=120)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
    def _get_next_apify_token(self) -> Optional[str]:
        """Keyingi Apify token ni olish (round-robin)"""
        if not APIFY_API_TOKENS:
            return None
            
        token = APIFY_API_TOKENS[self.apify_token_index]
        self.apify_token_index = (self.apify_token_index + 1) % len(APIFY_API_TOKENS)
        return token
        
    def _extract_shortcode_and_type(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        URL dan shortcode va media type ni ajratib olish
        """
        try:
            # Clean URL first
            url = url.split('?')[0]  # Remove query parameters
            url = url.rstrip('/')    # Remove trailing slash
            
            # Instagram URL patterns - more comprehensive
            patterns = [
                (r'instagram\.com/p/([A-Za-z0-9_-]+)', "post"),
                (r'instagram\.com/reel/([A-Za-z0-9_-]+)', "reel"),
                (r'instagram\.com/reels/([A-Za-z0-9_-]+)', "reel"),
                (r'instagram\.com/stories/([A-Za-z0-9_.]+)/([A-Za-z0-9_-]+)', "stories"),
                (r'instagram\.com/s/([A-Za-z0-9_-]+)', "stories"),
                (r'instagram\.com/tv/([A-Za-z0-9_-]+)', "igtv"),
                (r'instagram\.com/([A-Za-z0-9_.]+)/p/([A-Za-z0-9_-]+)', "post"),
                (r'instagram\.com/([A-Za-z0-9_.]+)/reel/([A-Za-z0-9_-]+)', "reel"),
            ]
            
            for pattern, media_type in patterns:
                match = re.search(pattern, url)
                if match:
                    if media_type == "stories" and len(match.groups()) == 2:
                        return match.group(2), media_type  # Stories shortcode
                    elif len(match.groups()) == 2 and media_type in ["post", "reel"]:
                        return match.group(2), media_type  # User/shortcode pattern
                    else:
                        return match.group(1), media_type  # Direct shortcode
                    
            # Fallback: extract any valid shortcode pattern
            shortcode_match = re.search(r'/([A-Za-z0-9_-]{11})/?', url)
            if shortcode_match:
                return shortcode_match.group(1), "post"
                    
            return None, None
            
        except Exception as e:
            logging.error(f"Error extracting shortcode: {e}")
            return None, None
            
    async def download_media(self, instagram_url: str, user_id: int = None) -> Optional[Tuple[str, str, str]]:
        """
        Instagram media yuklab olish - asosiy funksiya
        
        Args:
            instagram_url: Instagram URL
            user_id: Foydalanuvchi ID
            
        Returns:
            Tuple[file_path, title, media_id] yoki None
        """
        try:
            shortcode, media_type = self._extract_shortcode_and_type(instagram_url)
            if not shortcode:
                logging.error(f"Invalid Instagram URL: {instagram_url}")
                return None
                
            logging.info(f"Processing Instagram {media_type}: {shortcode}")
            
            # 1. Database tekshiruvi
            cached_media = await self._check_database_cache(instagram_url)
            if cached_media:
                logging.info(f"Media found in database cache: {shortcode}")
                return cached_media
                
            # 2. yt-dlp bilan sinab ko'rish (bepul, tez)
            logging.info("Trying yt-dlp method...")
            result = await self._download_with_ytdlp(instagram_url, shortcode, media_type)
            if result:
                # Cache ga saqlash
                await self._save_to_database(result, instagram_url, user_id)
                return result
                
            # 2.5. Alternative gallery-dl method
            logging.info("Trying gallery-dl fallback...")
            result = await self._download_with_gallery_dl(instagram_url, shortcode, media_type)
            if result:
                # Cache ga saqlash
                await self._save_to_database(result, instagram_url, user_id)
                return result
                
            # 2.7. Try direct API access (experimental)
            logging.info("Trying direct API method...")
            result = await self._download_with_direct_api(instagram_url, shortcode, media_type)
            if result:
                # Cache ga saqlash
                await self._save_to_database(result, instagram_url, user_id)
                return result
                
            # 3. Apify fallback (premium, ishonchli)
            if APIFY_API_TOKENS:
                logging.info("Trying Apify fallback...")
                result = await self._download_with_apify(instagram_url, shortcode, media_type)
                if result:
                    # Cache ga saqlash
                    await self._save_to_database(result, instagram_url, user_id)
                    return result
            else:
                logging.warning("No Apify tokens available for fallback")
                
            logging.error(f"All download methods failed for: {instagram_url}")
            return None
            
        except Exception as e:
            logging.error(f"Instagram download error: {e}")
            return None
            
    async def _check_database_cache(self, instagram_url: str) -> Optional[Tuple[str, str, str]]:
        """
        Database da avval yuklab olingan media ni tekshirish
        """
        try:
            cached_media = await self.db.get_instagram_media(instagram_url)
            if cached_media and cached_media.get("telegram_file_id"):
                return (
                    cached_media["telegram_file_id"],  # Telegram file ID
                    cached_media["title"],
                    cached_media["media_id"]
                )
            return None
        except Exception as e:
            logging.error(f"Database cache check error: {e}")
            return None
            
    async def _download_with_ytdlp(self, url: str, shortcode: str, media_type: str) -> Optional[Tuple[str, str, str]]:
        """
        yt-dlp yordamida yuklab olish (anti-bot measures bilan)
        """
        try:
            # yt-dlp configurations for different scenarios
            configurations = [
                # Configuration 1: No authentication, basic attempt
                {
                    "format": "best[height<=1080][ext=mp4]/best[ext=mp4]/best",
                    "user_agent": USER_AGENTS[0],
                    "headers": {
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate",
                        "Connection": "keep-alive",
                        "Referer": "https://www.instagram.com/",
                    },
                    "sleep_interval": 1,
                },
                # Configuration 2: Alternative format
                {
                    "format": "worst[ext=mp4]/worst",
                    "user_agent": USER_AGENTS[1],
                    "headers": {
                        "Accept": "*/*",
                        "Referer": "https://www.instagram.com/",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                },
                # Configuration 3: Try different user agent
                {
                    "format": "best",
                    "user_agent": USER_AGENTS[2],
                    "headers": {
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Referer": "https://www.instagram.com/",
                    },
                },
                # Configuration 4: Minimal headers
                {
                    "format": "best",
                    "user_agent": USER_AGENTS[3],
                },
            ]
            
            for i, config in enumerate(configurations, 1):
                try:
                    logging.info(f"Trying yt-dlp configuration {i}/{len(configurations)}")
                    
                    # Temporary file path
                    temp_filename = f"instagram_{shortcode}_{i}.%(ext)s"
                    output_path = os.path.join(TEMP_DIR, temp_filename)
                    
                    # Build yt-dlp options
                    ydl_opts = {
                        "outtmpl": output_path,
                        "quiet": True,
                        "no_warnings": True,
                        "extractaudio": False,
                        "format": config.get("format", "best"),
                        "http_headers": config.get("headers", {}),
                        "sleep_interval": config.get("sleep_interval", 0),
                        "max_sleep_interval": config.get("max_sleep_interval", 0),
                    }
                    
                    if config.get("user_agent"):
                        ydl_opts["http_headers"]["User-Agent"] = config["user_agent"]
                        
                    # Use subprocess for better control
                    cmd = ["yt-dlp"]
                    cmd.extend(["--quiet", "--no-warnings"])
                    cmd.extend(["--format", config.get("format", "best")])
                    cmd.extend(["--output", output_path])
                    
                    if config.get("user_agent"):
                        cmd.extend(["--user-agent", config["user_agent"]])
                        
                    if config.get("sleep_interval"):
                        cmd.extend(["--sleep-interval", str(config["sleep_interval"])])
                        
                    # Add cookies file if exists
                    cookies_file = os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt")
                    cookies_added = False
                    
                    if os.path.exists(cookies_file) and os.path.getsize(cookies_file) > 100:
                        cmd.extend(["--cookies", cookies_file])
                        cookies_added = True
                        logging.info(f"Using cookies file: {cookies_file}")
                    
                    # Try browser cookies only if no file cookies and not in container
                    if not cookies_added and not os.path.exists("/.dockerenv"):
                        if i == 1:  # Only try on first attempt to avoid spam
                            cmd.extend(["--cookies-from-browser", "chrome"])
                        elif i == 2:  # Try firefox on second attempt
                            cmd.extend(["--cookies-from-browser", "firefox"])
                    
                    # Skip browser cookies if in container environment
                    if not cookies_added and i <= 2:
                        logging.info(f"Config {i}: No valid cookies available, trying without authentication")
                        
                    cmd.append(url)
                    
                    # Execute with timeout
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(), 
                            timeout=60  # 1 minute timeout
                        )
                        
                        if process.returncode == 0:
                            # Find downloaded file
                            for ext in ['mp4', 'webm', 'mov', 'jpg', 'jpeg', 'png']:
                                file_path = os.path.join(TEMP_DIR, f"instagram_{shortcode}_{i}.{ext}")
                                if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                                    title = f"Instagram {media_type.title()}"
                                    logging.info(f"yt-dlp success with config {i}: {file_path}")
                                    return file_path, title, shortcode
                        else:
                            error_msg = stderr.decode() if stderr else "Unknown error"
                            logging.warning(f"yt-dlp config {i} failed: {error_msg}")
                            
                    except asyncio.TimeoutError:
                        logging.warning(f"yt-dlp config {i} timed out")
                        if process.returncode is None:
                            process.terminate()
                            await process.wait()
                            
                except Exception as e:
                    logging.warning(f"yt-dlp config {i} error: {e}")
                    
                # Small delay between attempts
                await asyncio.sleep(1)
                
            return None
            
        except Exception as e:
            logging.error(f"yt-dlp download failed: {e}")
            return None
            
    async def _download_with_gallery_dl(self, url: str, shortcode: str, media_type: str) -> Optional[Tuple[str, str, str]]:
        """
        gallery-dl yordamida yuklab olish (yt-dlp ga alternative)
        """
        try:
            # gallery-dl configuration
            temp_filename = f"instagram_{shortcode}_gallery"
            output_dir = os.path.join(TEMP_DIR, temp_filename)
            os.makedirs(output_dir, exist_ok=True)
            
            cmd = [
                "gallery-dl",
                "--quiet",
                "--dest", output_dir,
                "--filename", f"{shortcode}.{{extension}}",
                url
            ]
            
            # Add cookies if available
            cookies_file = os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt")
            if os.path.exists(cookies_file):
                cmd.extend(["--cookies", cookies_file])
            
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=45  # 45 second timeout
                )
                
                if process.returncode == 0:
                    # Find downloaded file
                    for file in os.listdir(output_dir):
                        file_path = os.path.join(output_dir, file)
                        if os.path.getsize(file_path) > 1000:
                            # Move to main temp directory
                            final_path = os.path.join(TEMP_DIR, f"instagram_{shortcode}_gallery.{file.split('.')[-1]}")
                            os.rename(file_path, final_path)
                            # Clean up temp directory
                            import shutil
                            shutil.rmtree(output_dir, ignore_errors=True)
                            
                            title = f"Instagram {media_type.title()}"
                            logging.info(f"gallery-dl success: {final_path}")
                            return final_path, title, shortcode
                else:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    logging.warning(f"gallery-dl failed: {error_msg}")
                    
            except asyncio.TimeoutError:
                logging.warning("gallery-dl timed out")
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
            
            # Clean up temp directory
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
            return None
            
        except FileNotFoundError:
            logging.info("gallery-dl not installed, skipping")
            return None
        except Exception as e:
            logging.error(f"gallery-dl download failed: {e}")
            return None
            
    async def _download_with_direct_api(self, url: str, shortcode: str, media_type: str) -> Optional[Tuple[str, str, str]]:
        """
        Direct Instagram API access (experimental)
        """
        try:
            # Instagram's public API endpoints (these change frequently)
            api_urls = [
                f"https://www.instagram.com/api/v1/media/{shortcode}/info/",
                f"https://i.instagram.com/api/v1/media/{shortcode}/info/",
                f"https://graph.instagram.com/{shortcode}",
            ]
            
            headers = {
                "User-Agent": USER_AGENTS[0],
                "Accept": "application/json",
                "Referer": "https://www.instagram.com/",
                "X-Requested-With": "XMLHttpRequest",
            }
            
            for api_url in api_urls:
                try:
                    async with self.session.get(api_url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Try to extract media URL from response
                            if "items" in data and data["items"]:
                                item = data["items"][0]
                                video_url = None
                                
                                # Look for video URL
                                if "video_versions" in item:
                                    video_url = item["video_versions"][0]["url"]
                                elif "image_versions2" in item and "candidates" in item["image_versions2"]:
                                    video_url = item["image_versions2"]["candidates"][0]["url"]
                                
                                if video_url:
                                    # Download the media file
                                    file_path = await self._download_file_from_url(video_url, shortcode)
                                    if file_path:
                                        title = f"Instagram {media_type.title()}"
                                        logging.info(f"Direct API success: {file_path}")
                                        return file_path, title, shortcode
                                        
                except Exception as e:
                    logging.debug(f"Direct API attempt failed for {api_url}: {e}")
                    continue
                    
            return None
            
        except Exception as e:
            logging.error(f"Direct API download failed: {e}")
            return None
            
    async def _download_with_apify(self, url: str, shortcode: str, media_type: str) -> Optional[Tuple[str, str, str]]:
        """
        Apify Instagram Scraper yordamida yuklab olish
        """
        try:
            # Try different actors with different tokens
            for actor_id in INSTAGRAM_SCRAPER_ACTORS:
                token = self._get_next_apify_token()
                if not token:
                    continue
                    
                try:
                    logging.info(f"Trying Apify actor: {actor_id} with token {token[:10]}...")
                    result = await self._try_apify_actor(actor_id, url, token, shortcode, media_type)
                    if result:
                        return result
                        
                except Exception as e:
                    logging.warning(f"Apify actor {actor_id} failed: {e}")
                    continue
                    
            return None
            
        except Exception as e:
            logging.error(f"Apify download failed: {e}")
            return None
            
    async def _try_apify_actor(self, actor_id: str, url: str, token: str, shortcode: str, media_type: str) -> Optional[Tuple[str, str, str]]:
        """
        Aniq Apify actor bilan sinab ko'rish
        """
        try:
            # Different configurations for different actors
            if actor_id == "shu8hvrXbJbY3Eb9W":
                # This actor needs specific configuration
                run_data = {
                    "directUrls": [url],
                    "resultsType": "posts",
                    "resultsLimit": 1,
                    "searchType": "hashtag",  # Changed from "url" to valid option
                    "searchLimit": 1,
                    "addParentData": False,
                }
            elif "post-scraper" in actor_id:
                # Post scraper configuration
                run_data = {
                    "startUrls": [{"url": url}],
                    "resultsLimit": 1,
                }
            else:
                # Default configuration for other actors
                if media_type == "stories":
                    run_data = {
                        "directUrls": [url],
                        "resultsType": "stories", 
                        "resultsLimit": 5,
                        "searchType": "hashtag",
                        "addParentData": False,
                    }
                else:
                    run_data = {
                        "directUrls": [url],
                        "resultsType": "posts",
                        "resultsLimit": 1,
                        "searchType": "hashtag",  # Use valid option
                        "searchLimit": 1,
                        "addParentData": False,
                    }
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            # Start run
            async with self.session.post(
                f"https://api.apify.com/v2/acts/{actor_id}/runs",
                json=run_data,
                headers=headers
            ) as response:
                if response.status != 201:
                    response_text = await response.text()
                    logging.error(f"Failed to start Apify run: {response.status} - {response_text}")
                    return None
                    
                run_info = await response.json()
                run_id = run_info["data"]["id"]
                
            logging.info(f"Apify run started: {run_id}")
            
            # Wait for completion
            dataset_items = await self._wait_for_apify_run(run_id, token)
            if not dataset_items:
                return None
                
            # Process results
            for item in dataset_items:
                result = await self._process_apify_item(item, shortcode, media_type)
                if result:
                    return result
                    
            return None
            
        except Exception as e:
            logging.error(f"Apify actor {actor_id} error: {e}")
            return None
            
    async def _wait_for_apify_run(self, run_id: str, token: str, max_wait: int = 120) -> Optional[List[dict]]:
        """
        Apify run tugashini kutish
        """
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            for _ in range(max_wait // 5):  # Check every 5 seconds
                async with self.session.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        logging.error(f"Failed to check run status: {response.status}")
                        return None
                        
                    run_info = await response.json()
                    status = run_info["data"]["status"]
                    
                    if status == "SUCCEEDED":
                        # Get dataset
                        dataset_id = run_info["data"]["defaultDatasetId"]
                        async with self.session.get(
                            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                            headers=headers
                        ) as dataset_response:
                            if dataset_response.status == 200:
                                items = await dataset_response.json()
                                return items
                            else:
                                logging.error(f"Failed to get dataset: {dataset_response.status}")
                                return None
                                
                    elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                        logging.error(f"Apify run failed with status: {status}")
                        return None
                        
                await asyncio.sleep(5)
                
            logging.error("Apify run timed out")
            return None
            
        except Exception as e:
            logging.error(f"Error waiting for Apify run: {e}")
            return None
            
    async def _process_apify_item(self, item: dict, shortcode: str, media_type: str) -> Optional[Tuple[str, str, str]]:
        """
        Apify natijasini qayta ishlash
        """
        try:
            # Extract media URL based on type
            media_url = None
            title = f"Instagram {media_type.title()}"
            
            # Try different fields for media URL
            if media_type == "stories":
                # For stories, try video first, then image
                video_fields = ["videoUrl", "video_url", "url"]
                image_fields = ["displayUrl", "display_url", "imageUrl", "image_url"]
                
                for field in video_fields:
                    if field in item and item[field]:
                        media_url = item[field]
                        break
                        
                if not media_url:
                    for field in image_fields:
                        if field in item and item[field]:
                            media_url = item[field]
                            break
            else:
                # For posts and reels
                video_fields = ["videoUrl", "video_url", "displayUrl", "display_url", "url", "videoPlayUrl"]
                for field in video_fields:
                    if field in item and item[field]:
                        media_url = item[field]
                        break
                        
            if not media_url:
                logging.warning(f"No media URL found in Apify result for {media_type}")
                logging.debug(f"Available fields: {list(item.keys())}")
                return None
                
            # Extract title/caption
            caption_fields = ["caption", "text", "alt", "title"]
            for field in caption_fields:
                if field in item and item[field]:
                    title = sanitize_filename(str(item[field])[:50])
                    break
                
            # Download file
            file_path = await self._download_file_from_url(media_url, shortcode)
            if not file_path:
                return None
                
            return file_path, title, shortcode
            
        except Exception as e:
            logging.error(f"Error processing Apify item: {e}")
            return None
            
    async def _download_file_from_url(self, url: str, shortcode: str) -> Optional[str]:
        """
        URL dan fayl yuklab olish
        """
        try:
            # Determine file extension
            ext = "mp4"  # default
            if url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                ext = url.split('.')[-1]
                
            file_path = os.path.join(TEMP_DIR, f"instagram_{shortcode}.{ext}")
            
            headers = {
                "User-Agent": USER_AGENTS[0],
                "Referer": "https://www.instagram.com/",
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"Failed to download file: {response.status}")
                    return None
                    
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                        
            if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                return file_path
            else:
                logging.error("Downloaded file is too small or doesn't exist")
                return None
                
        except Exception as e:
            logging.error(f"File download error: {e}")
            return None
            
    async def _save_to_database(self, result: Tuple[str, str, str], instagram_url: str, user_id: int = None):
        """
        Natijani database ga saqlash
        """
        try:
            file_path, title, media_id = result
            
            # TODO: Upload to Telegram and get file_id
            # For now, we'll use the file path
            telegram_file_id = file_path  # This should be replaced with actual Telegram file ID
            
            await self.db.save_instagram_media(
                media_id=media_id,
                title=title,
                video_url=instagram_url,
                telegram_file_id=telegram_file_id,
                user_id=user_id
            )
            
            logging.info(f"Media saved to database: {media_id}")
            
        except Exception as e:
            logging.error(f"Database save error: {e}")


# === Compatibility functions ===
async def download_instagram_media(instagram_url: str, user_id: int = None) -> Optional[Tuple[str, str, str]]:
    """
    Instagram media yuklab olish - asosiy funksiya
    """
    from bot.utils.db_api.db import DB
    
    async with InstagramMediaDownloader(DB) as downloader:
        return await downloader.download_media(instagram_url, user_id)


async def get_instagram_media_info(instagram_url: str) -> Optional[dict]:
    """
    Media haqida ma'lumot olish (yuklab olmasdan)
    """
    from bot.utils.db_api.db import DB
    
    try:
        # Check database first
        db = DB()
        cached_media = await db.get_instagram_media(instagram_url)
        if cached_media:
            return {
                "title": cached_media["title"],
                "id": cached_media["media_id"],
                "description": cached_media["title"],
                "thumbnail": cached_media.get("thumbnail", ""),
                "uploader": "Instagram",
                "duration": cached_media.get("duration", 0),
            }
            
        # If not in cache, try to get basic info without downloading
        async with InstagramMediaDownloader(db) as downloader:
            shortcode, media_type = downloader._extract_shortcode_and_type(instagram_url)
            if shortcode:
                return {
                    "title": f"Instagram {media_type.title()}",
                    "id": shortcode,
                    "description": f"Instagram {media_type}",
                    "thumbnail": "",
                    "uploader": "Instagram",
                    "duration": 0,
                }
                
        return None
        
    except Exception as e:
        logging.error(f"Failed to get Instagram media info: {e}")
        return None


async def convert_instagram_video_to_audio(instagram_url: str) -> Optional[str]:
    """
    Instagram videosini audio ga o'girish
    """
    try:
        # Download video first
        result = await download_instagram_media(instagram_url)
        if not result:
            return None
            
        video_path, title, media_id = result
        
        # Check if file exists
        if not os.path.exists(video_path):
            logging.error(f"Video file not found: {video_path}")
            return None
        
        # Convert to audio using ffmpeg
        audio_path = os.path.join(TEMP_DIR, f"audio_{media_id}.mp3")
        
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",  # No video
            "-acodec", "libmp3lame",
            "-q:a", "2",
            "-y",  # Overwrite existing
            audio_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
            # Clean up video file
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except:
                    pass
            return audio_path
        else:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logging.error(f"FFmpeg conversion failed: {error_msg}")
            return None
            
    except Exception as e:
        logging.error(f"Failed to convert video to audio: {e}")
        return None


# === Shazam integration ===
async def find_music_name(audio_file: str) -> Optional[str]:
    """
    Audio fayldan Shazam yordamida musiqa nomini aniqlaydi
    """
    try:
        # Check if file exists
        if not os.path.exists(audio_file):
            logging.error(f"Audio file not found: {audio_file}")
            return None
            
        # Check file size
        if os.path.getsize(audio_file) < 1000:
            logging.error(f"Audio file too small: {audio_file}")
            return None
            
        shazam = Shazam()
        out = await shazam.recognize_song(audio_file)
        
        if out and 'track' in out:
            track = out['track']
            title = track.get('title', '')
            subtitle = track.get('subtitle', '')
            
            if title and subtitle:
                return f"{title} - {subtitle}"
            elif title:
                return title
                
        return None
        
    except Exception as e:
        logging.error(f"Shazam recognition failed: {e}")
        return None


# === Test function ===
async def test_instagram_download():
    """
    Test funksiyasi
    """
    test_urls = [
        "https://www.instagram.com/p/test123/",
        "https://www.instagram.com/reel/test456/",
    ]
    
    for url in test_urls:
        print(f"\nTesting: {url}")
        result = await download_instagram_media(url)
        if result:
            file_path, title, media_id = result
            print(f"✅ Success: {title} ({media_id})")
            print(f"📁 File: {file_path}")
        else:
            print("❌ Failed")


if __name__ == "__main__":
    asyncio.run(test_instagram_download())
