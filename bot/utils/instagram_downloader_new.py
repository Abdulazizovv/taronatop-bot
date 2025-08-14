"""
Instagram Media Downloader - Yangi implementatsiya
Xususiyatlari:
1. Database tekshiruvi (avval yuklab olingan mediani qayta yuklamaslik)
2. yt-dlp bilan bepul yuklab olish (anti-bot himoya bilan)
3. Apify fallback (bir nechta API key'lar bilan)
4. User experience optimizatsiyasi
5. To'liq logging va xato boshqaruvi
6. Telegram file ID orqali media qayta ishlatish
"""

import os
import re
import logging
import asyncio
import aiohttp
import aiofiles
import json
import time
import subprocess
import tempfile
from typing import Dict, Optional, Tuple, List, Union
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from pathlib import Path

# Third-party imports
import yt_dlp
from shazamio import Shazam

# Django imports
from asgiref.sync import sync_to_async

# Bot imports
from botapp.models import InstagramMedia, BotUser

# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)

# Multiple Apify API tokens for load balancing
APIFY_API_TOKENS = [
    os.getenv("APIFY_API_TOKEN_1"),
    os.getenv("APIFY_API_TOKEN_2"),
    os.getenv("APIFY_API_TOKEN_3"),
    os.getenv("APIFY_API_TOKEN_4"),
    os.getenv("APIFY_API_TOKEN_5"),
]

# Filter out None values and add fallback
APIFY_API_TOKENS = [token for token in APIFY_API_TOKENS if token]
if not APIFY_API_TOKENS:
    fallback_token = os.getenv("APIFY_API_TOKEN")
    if fallback_token:
        APIFY_API_TOKENS = [fallback_token]

# Apify Actor IDs for Instagram scraping
APIFY_ACTORS = [
    "shu8hvrXbJbY3Eb9W",  # Main actor
    "apify/instagram-post-scraper",
    "apify/instagram-scraper",
]

# User agents for anti-detection
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

# Logging configuration
logger = logging.getLogger(__name__)


class InstagramDownloaderError(Exception):
    """Instagram downloader xatolari uchun maxsus exception"""

    pass


class InstagramMediaDownloader:
    """
    Instagram media yuklab olish uchun to'liq implementatsiya
    """

    def __init__(self, user_id: Optional[int] = None):
        self.user_id = user_id
        self.session = None
        self.apify_token_index = 0
        self.user_agent_index = 0

    async def __aenter__(self):
        await self._setup_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _setup_session(self):
        """HTTP session sozlash"""
        timeout = aiohttp.ClientTimeout(total=180)
        connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": self._get_user_agent()},
        )

    def _get_user_agent(self) -> str:
        """Random user agent olish"""
        ua = USER_AGENTS[self.user_agent_index]
        self.user_agent_index = (self.user_agent_index + 1) % len(USER_AGENTS)
        return ua

    def _get_next_apify_token(self) -> Optional[str]:
        """Keyingi Apify token ni olish (round-robin)"""
        if not APIFY_API_TOKENS:
            return None

        token = APIFY_API_TOKENS[self.apify_token_index]
        self.apify_token_index = (self.apify_token_index + 1) % len(APIFY_API_TOKENS)
        return token

    def _extract_media_info(
        self, url: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Instagram URL dan media ma'lumotlarini ajratib olish
        Returns: (media_id, media_type, shortcode)
        """
        try:
            # Remove query parameters and fragments
            clean_url = url.split("?")[0].split("#")[0]

            # Pattern matching for different URL formats
            patterns = [
                r"instagram\.com/p/([A-Za-z0-9_-]+)",  # Posts
                r"instagram\.com/reel/([A-Za-z0-9_-]+)",  # Reels
                r"instagram\.com/stories/[^/]+/([0-9]+)",  # Stories
                r"instagram\.com/tv/([A-Za-z0-9_-]+)",  # IGTV
            ]

            media_type = None
            shortcode = None

            for pattern in patterns:
                match = re.search(pattern, clean_url)
                if match:
                    shortcode = match.group(1)
                    if "/p/" in clean_url:
                        media_type = "post"
                    elif "/reel/" in clean_url:
                        media_type = "reel"
                    elif "/stories/" in clean_url:
                        media_type = "story"
                    elif "/tv/" in clean_url:
                        media_type = "igtv"
                    break

            if shortcode:
                # Use shortcode as media_id for consistency
                media_id = shortcode
                logger.info(
                    f"Instagram URL parsed: media_id={media_id}, type={media_type}"
                )
                return media_id, media_type, shortcode

            logger.warning(f"Could not parse Instagram URL: {url}")
            return None, None, None

        except Exception as e:
            logger.error(f"Error parsing Instagram URL {url}: {e}")
            return None, None, None

    @sync_to_async
    def _check_database(self, media_id: str) -> Optional[InstagramMedia]:
        """
        Bazadan media mavjudligini tekshirish
        """
        try:
            return InstagramMedia.objects.filter(media_id=media_id).first()
        except Exception as e:
            logger.error(f"Database check error for {media_id}: {e}")
            return None

    @sync_to_async
    def _save_to_database(self, media_data: Dict) -> Optional[InstagramMedia]:
        """
        Mediani bazaga saqlash
        """
        try:
            def _truncate(val: Optional[str], max_len: int) -> Optional[str]:
                if val is None:
                    return None
                s = str(val)
                return s[:max_len]

            user = None
            if self.user_id:
                user, _ = BotUser.objects.get_or_create(user_id=str(self.user_id))

            media_id = _truncate(media_data.get("media_id"), 255)
            title = _truncate(media_data.get("title", ""), 255) or ""
            # URLField default max_length = 200 in Django
            video_url = _truncate(media_data.get("video_url"), 200)
            thumbnail = _truncate(media_data.get("thumbnail"), 200)
            telegram_file_id = _truncate(media_data.get("telegram_file_id"), 255)
            duration = media_data.get("duration")

            media, created = InstagramMedia.objects.update_or_create(
                media_id=media_id,
                defaults={
                    "title": title,
                    "video_url": video_url,
                    "telegram_file_id": telegram_file_id,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "user": user,
                },
            )

            action = "Created" if created else "Updated"
            logger.info(f"{action} Instagram media in database: {media.media_id}")
            return media

        except Exception as e:
            logger.error(f"Database save error: {e}")
            return None

    async def download_media(self, url: str) -> Dict:
        """
        Instagram mediasini yuklab olishning asosiy funksiyasi

        Returns:
        {
            'success': bool,
            'message': str,
            'data': {
                'media_id': str,
                'title': str,
                'video_url': str,
                'thumbnail': str,
                'duration': int,
                'telegram_file_id': str,
                'from_cache': bool
            }
        }
        """
        try:
            logger.info(f"Starting Instagram download for URL: {url}")

            # 1. URL dan media ma'lumotlarini ajratib olish
            media_id, media_type, shortcode = self._extract_media_info(url)
            if not media_id:
                return {
                    "success": False,
                    "message": "❌ Instagram URL noto'g'ri formatda",
                    "data": None,
                }

            # 2. Bazadan tekshirish
            logger.info(f"Checking database for media_id: {media_id}")
            existing_media = await self._check_database(media_id)

            if existing_media and existing_media.telegram_file_id:
                logger.info(f"Found existing media in database: {media_id}")
                return {
                    "success": True,
                    "message": "✅ Media avval yuklab olingan",
                    "data": {
                        "media_id": existing_media.media_id,
                        "title": existing_media.title,
                        "video_url": existing_media.video_url,
                        "thumbnail": existing_media.thumbnail,
                        "duration": existing_media.duration,
                        "telegram_file_id": existing_media.telegram_file_id,
                        "from_cache": True,
                    },
                }

            # 3. Yangi media yuklab olish
            logger.info(f"Downloading new media: {media_id}")

            # Birinchi yt-dlp bilan urinish
            result = await self._download_with_ytdlp(url, media_id)

            # Agar yt-dlp ishlamasa, Apify bilan urinish
            if not result["success"]:
                logger.info("yt-dlp failed, trying Apify...")
                result = await self._download_with_apify(url, media_id)

            return result

        except Exception as e:
            logger.error(f"Download error for {url}: {e}")
            return {
                "success": False,
                "message": f"❌ Yuklab olishda xatolik: {str(e)}",
                "data": None,
            }

    async def _download_with_ytdlp(self, url: str, media_id: str) -> Dict:
        """
        yt-dlp yordamida yuklab olish (bepul usul)
        """
        try:
            logger.info(f"Attempting yt-dlp download for {media_id}")

            # Temporary file paths
            temp_dir = Path(TEMP_DIR) / f"ytdlp_{uuid4().hex[:8]}"
            temp_dir.mkdir(exist_ok=True)

            # yt-dlp configuration
            ydl_opts = {
                "outtmpl": str(temp_dir / "%(title)s.%(ext)s"),
                "format": "best[height<=720]/best",  # Limit quality for faster download
                "extractaudio": False,
                "writeinfojson": True,
                "writedescription": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
                "ignoreerrors": True,
                "no_warnings": False,
                "quiet": False,
                "verbose": False,
                # Anti-detection headers
                "http_headers": {
                    "User-Agent": self._get_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
                # Additional options for Instagram
                "sleep_interval_requests": 2,
                "sleep_interval": 1,
                "max_sleep_interval": 5,
            }

            # Run yt-dlp in subprocess
            result = await self._run_ytdlp_subprocess(url, ydl_opts, temp_dir, media_id)

            if result["success"]:
                # Save to database
                media_data = result["data"]
                await self._save_to_database(media_data)

                logger.info(f"yt-dlp download successful for {media_id}")
                return result
            else:
                logger.warning(
                    f"yt-dlp download failed for {media_id}: {result['message']}"
                )
                return result

        except Exception as e:
            logger.error(f"yt-dlp download error for {media_id}: {e}")
            return {
                "success": False,
                "message": f"yt-dlp yuklab olishda xatolik: {str(e)}",
                "data": None,
            }
        finally:
            # Cleanup temp directory
            try:
                if "temp_dir" in locals():
                    import shutil

                    shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

    async def _run_ytdlp_subprocess(self, url: str, ydl_opts: Dict, temp_dir: Path, media_id: Optional[str] = None) -> Dict:
        """
        yt-dlp ni subprocess sifatida ishga tushirish
        """
        try:
            # Create yt-dlp command
            cmd = [
                'yt-dlp',
                '--format', 'best[height<=720]/best',
                '--output', str(temp_dir / '%(title)s.%(ext)s'),
                '--write-info-json',
                '--user-agent', ydl_opts['http_headers']['User-Agent'],
                '--sleep-interval', '2',
                url
            ]

            # Run subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

            if process.returncode == 0:
                # Find downloaded files
                video_files = list(temp_dir.glob('*.mp4')) + list(temp_dir.glob('*.mkv'))
                info_files = list(temp_dir.glob('*.info.json'))

                if video_files and info_files:
                    video_file = video_files[0]
                    info_file = info_files[0]

                    # Read info file
                    async with aiofiles.open(info_file, 'r', encoding='utf-8') as f:
                        info_data = json.loads(await f.read())

                    # Ensure media_id present
                    mid = media_id or info_data.get('id') or url.split('/')[-1].split('?')[0]

                    return {
                        'success': True,
                        'message': "✅ yt-dlp bilan yuklab olindi",
                        'data': {
                            'media_id': mid,
                            'title': info_data.get('title', 'Instagram Video'),
                            'video_url': url,  # store source URL in DB
                            'thumbnail': info_data.get('thumbnail'),
                            'duration': info_data.get('duration'),
                            'telegram_file_id': None,
                            'from_cache': False,
                            'file_path': str(video_file),  # local path for sending if needed
                            'info': info_data
                        }
                    }

            error_msg = stderr.decode("utf-8") if stderr else "Unknown error"
            return {
                "success": False,
                "message": f"yt-dlp failed: {error_msg}",
                "data": None,
            }

        except asyncio.TimeoutError:
            return {"success": False, "message": "yt-dlp timeout (>120s)", "data": None}
        except Exception as e:
            return {
                "success": False,
                "message": f"yt-dlp subprocess error: {str(e)}",
                "data": None,
            }

    async def _download_with_apify(self, url: str, media_id: str) -> Dict:
        """
        Apify yordamida yuklab olish (premium fallback)
        """
        try:
            logger.info(f"Attempting Apify download for {media_id}")

            if not APIFY_API_TOKENS:
                return {
                    "success": False,
                    "message": "❌ Apify API token sozlanmagan",
                    "data": None,
                }

            # Try multiple tokens and actors
            for attempt in range(len(APIFY_API_TOKENS)):
                token = self._get_next_apify_token()

                for actor_id in APIFY_ACTORS:
                    logger.info(
                        f"Trying Apify actor {actor_id} with token ending in ...{token[-6:]}"
                    )

                    result = await self._run_apify_actor(actor_id, token, url, media_id)

                    if result["success"]:
                        # Save to database
                        media_data = result["data"]
                        await self._save_to_database(media_data)

                        logger.info(f"Apify download successful for {media_id}")
                        return result

                    # Small delay between attempts
                    await asyncio.sleep(1)

            return {
                "success": False,
                "message": "❌ Barcha Apify urinishlar muvaffaqiyatsiz",
                "data": None,
            }

        except Exception as e:
            logger.error(f"Apify download error for {media_id}: {e}")
            return {
                "success": False,
                "message": f"Apify yuklab olishda xatolik: {str(e)}",
                "data": None,
            }

    async def _run_apify_actor(
        self, actor_id: str, token: str, url: str, media_id: str
    ) -> Dict:
        """
        Apify actor ni ishga tushirish
        """
        try:
            # Prepare input data based on actor
            if "post-scraper" in actor_id:
                input_data = {
                    "directUrls": [url],
                    "resultsType": "posts",
                    "resultsLimit": 1,
                    "searchType": "hashtag",
                    "searchLimit": 1,
                }
            else:
                input_data = {"directUrls": [url], "resultsLimit": 1}

            # Start actor run
            run_url = f"https://api.apify.com/v2/acts/{actor_id}/runs"

            async with self.session.post(
                run_url,
                params={"token": token},
                json=input_data,
                headers={"Content-Type": "application/json"},
            ) as response:

                if response.status != 201:
                    error_text = await response.text()
                    logger.warning(
                        f"Apify actor start failed: {response.status} - {error_text}"
                    )
                    return {
                        "success": False,
                        "message": f"Apify actor start failed: {response.status}",
                        "data": None,
                    }

                run_data = await response.json()
                run_id = run_data["data"]["id"]
                logger.info(f"Apify run started: {run_id}")

            # Wait for completion
            result = await self._wait_for_apify_completion(run_id, token)
            return result

        except Exception as e:
            logger.error(f"Apify actor run error: {e}")
            return {
                "success": False,
                "message": f"Apify actor error: {str(e)}",
                "data": None,
            }

    async def _wait_for_apify_completion(
        self, run_id: str, token: str, max_wait: int = 180
    ) -> Dict:
        """
        Apify run yakunlanishini kutish
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                # Check run status
                status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"

                async with self.session.get(
                    status_url, params={"token": token}
                ) as response:

                    if response.status != 200:
                        await asyncio.sleep(5)
                        continue

                    run_data = await response.json()
                    status = run_data["data"]["status"]

                    if status == "SUCCEEDED":
                        # Get results
                        return await self._get_apify_results(run_id, token)

                    elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                        logger.warning(f"Apify run failed with status: {status}")
                        return {
                            "success": False,
                            "message": f"Apify run failed: {status}",
                            "data": None,
                        }

                    # Still running, wait more
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error checking Apify status: {e}")
                await asyncio.sleep(5)

        # Timeout
        logger.warning(f"Apify run timeout after {max_wait}s")
        return {"success": False, "message": "Apify run timeout", "data": None}

    async def _get_apify_results(self, run_id: str, token: str) -> Dict:
        """
        Apify natijalarini olish
        """
        try:
            dataset_url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items"

            async with self.session.get(
                dataset_url, params={"token": token, "format": "json"}
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "message": f"Failed to get Apify results: {response.status}",
                        "data": None,
                    }

                results = await response.json()

                if not results:
                    return {
                        "success": False,
                        "message": "Apify returned empty results",
                        "data": None,
                    }

                # Process first result
                item = results[0]

                # Extract video URL
                video_url = None
                if "videoUrl" in item:
                    video_url = item["videoUrl"]
                elif "displayUrl" in item:
                    video_url = item["displayUrl"]
                elif "url" in item:
                    video_url = item["url"]

                if not video_url:
                    return {
                        "success": False,
                        "message": "No video URL found in Apify results",
                        "data": None,
                    }

                return {
                    "success": True,
                    "message": "✅ Apify bilan yuklab olindi",
                    "data": {
                        "media_id": item.get("id", item.get("shortCode", str(uuid4()))),
                        "title": item.get(
                            "caption", item.get("title", "Instagram Media")
                        ),
                        "video_url": video_url,
                        "thumbnail": item.get("displayUrl"),
                        "duration": item.get(
                            "videoPlayCount"
                        ),  # This might not be duration
                        "telegram_file_id": None,
                        "from_cache": False,
                        "apify_data": item,
                    },
                }

        except Exception as e:
            logger.error(f"Error getting Apify results: {e}")
            return {
                "success": False,
                "message": f"Error processing Apify results: {str(e)}",
                "data": None,
            }

    async def update_telegram_file_id(self, media_id: str, file_id: str) -> bool:
        """
        Telegram file ID ni bazaga saqlash
        """
        try:

            @sync_to_async
            def update_db():
                media = InstagramMedia.objects.filter(media_id=media_id).first()
                if media:
                    media.telegram_file_id = file_id
                    media.save()
                    return True
                return False

            result = await update_db()
            if result:
                logger.info(f"Updated telegram file ID for {media_id}")
            return result

        except Exception as e:
            logger.error(f"Error updating telegram file ID for {media_id}: {e}")
            return False

    async def get_media_for_audio_extraction(self, media_id: str) -> Optional[str]:
        """
        Audio ajratish uchun media faylini olish
        Telegram file ID mavjud bo'lsa, uni qaytaradi
        """
        try:

            @sync_to_async
            def get_media():
                media = InstagramMedia.objects.filter(media_id=media_id).first()
                if media and media.telegram_file_id:
                    return media.telegram_file_id
                return None

            file_id = await get_media()
            if file_id:
                logger.info(f"Found telegram file ID for audio extraction: {media_id}")
                return file_id

            logger.warning(f"No telegram file ID found for {media_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting media for audio extraction {media_id}: {e}")
            return None


# === Convenience functions ===


async def download_instagram_media(url: str, user_id: Optional[int] = None) -> Dict:
    """
    Instagram media yuklab olish uchun asosiy funksiya
    """
    async with InstagramMediaDownloader(user_id=user_id) as downloader:
        return await downloader.download_media(url)


async def get_instagram_media_from_cache(url: str) -> Optional[Dict]:
    """
    Faqat cache dan Instagram media olish
    """
    try:
        downloader = InstagramMediaDownloader()
        media_id, _, _ = downloader._extract_media_info(url)

        if media_id:
            existing_media = await downloader._check_database(media_id)
            if existing_media and existing_media.telegram_file_id:
                return {
                    "media_id": existing_media.media_id,
                    "title": existing_media.title,
                    "video_url": existing_media.video_url,
                    "thumbnail": existing_media.thumbnail,
                    "duration": existing_media.duration,
                    "telegram_file_id": existing_media.telegram_file_id,
                    "from_cache": True,
                }

        return None

    except Exception as e:
        logger.error(f"Error getting Instagram media from cache: {e}")
        return None


async def update_instagram_telegram_file_id(media_id: str, file_id: str) -> bool:
    """
    Instagram media uchun Telegram file ID yangilash
    """
    downloader = InstagramMediaDownloader()
    return await downloader.update_telegram_file_id(media_id, file_id)


async def get_instagram_media_for_audio(media_id: str) -> Optional[str]:
    """
    Audio ajratish uchun Instagram media file ID olish
    """
    downloader = InstagramMediaDownloader()
    return await downloader.get_media_for_audio_extraction(media_id)
