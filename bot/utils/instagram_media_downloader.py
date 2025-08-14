"""
Instagram Media Downloader - To'liq yangi implementatsiya
Bu modul Instagram media (reels, post, stories) yuklab olish uchun ishlatiladi.

Xususiyatlari:
1. Database cache - avval yuklab olingan medialar qayta yuklanmaydi
2. Multi-fallback system: yt-dlp -> Apify Instagram Scraper
3. Multiple Apify API keys support
4. User-friendly messages va detailed logging
5. Telegram file ID orqali qayta ishlatish audio uchun
"""

import os
import logging
import asyncio
import aiohttp
import aiofiles
import json
import re
import time
import hashlib
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlparse, parse_qs
from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename
from dotenv import load_dotenv
import random
from uuid import uuid4
from shazamio import Shazam

# Load environment variables
load_dotenv()

# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)

# Private Telegram channel for file storage
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID")

# Multiple Apify API tokens for load balancing
APIFY_API_TOKENS = [
    os.getenv("APIFY_API_TOKEN"),
    os.getenv("APIFY_API_TOKEN_2"),
    os.getenv("APIFY_API_TOKEN_3"),
    os.getenv("APIFY_API_TOKEN_4"),
    os.getenv("APIFY_API_TOKEN_5")
]

# Filter out None values
APIFY_API_TOKENS = [token for token in APIFY_API_TOKENS if token]

# Instagram scraper actors for Apify
INSTAGRAM_SCRAPER_ACTORS = [
    "shu8hvrXbJbY3Eb9W",  # Instagram Scraper
    "heLL6fUofdAS7gRqf",  # Instagram Posts Scraper  
    "hMTVqz8ZTL5KPe7vJ",  # Social Media Scraper
    "apify/instagram-scraper"  # Public Instagram Scraper
]

# User agents for different methods
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 12; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
]


class InstagramMediaDownloader:
    """
    Instagram media yuklab olish uchun asosiy klass
    """
    
    def __init__(self, db, bot):
        """
        Initializatsiya
        
        Args:
            db: Database API instance
            bot: Telegram bot instance
        """
        self.db = db
        self.bot = bot
        self.session = None
        self.apify_token_index = 0
        
        logging.info("Instagram Media Downloader initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._setup_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _setup_session(self):
        """Setup aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=60)
        
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout
        )
        
        logging.info("HTTP session configured")
    
    def _normalize_instagram_url(self, url: str) -> str:
        """
        Instagram URL ni standardlashtiradi
        
        Args:
            url: Instagram URL
            
        Returns:
            Normalized URL
        """
        # Remove query parameters and normalize
        url = url.split('?')[0].rstrip('/')
        
        # Ensure https
        if not url.startswith('https://'):
            url = url.replace('http://', 'https://')
        
        return url
    
    def _extract_media_id(self, url: str) -> Optional[str]:
        """
        Instagram URL dan media ID ajratib oladi
        
        Args:
            url: Instagram URL
            
        Returns:
            Media ID yoki None
        """
        patterns = [
            r'/p/([A-Za-z0-9_-]+)',
            r'/reel/([A-Za-z0-9_-]+)',
            r'/tv/([A-Za-z0-9_-]+)',
            r'/stories/[^/]+/([A-Za-z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Fallback: URL dan hash yaratish
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    async def download_instagram_media(self, instagram_url: str, user_id: int, 
                                     user_message=None) -> Optional[Dict]:
        """
        Instagram mediasini yuklab oladi
        
        Args:
            instagram_url: Instagram media URL
            user_id: Foydalanuvchi ID si
            user_message: Foydalanuvchiga xabar yuborish uchun message object
            
        Returns:
            Media ma'lumotlari yoki None
        """
        try:
            # URL ni normalize qilish
            normalized_url = self._normalize_instagram_url(instagram_url)
            media_id = self._extract_media_id(normalized_url)
            
            logging.info(f"Starting Instagram download for URL: {normalized_url}")
            logging.info(f"Media ID: {media_id}")
            
            # 1. Avval database dan tekshirish
            if user_message:
                await user_message.edit_text("🔍 Ma'lumotlar bazasidan tekshirilmoqda...")
            
            cached_media = await self.db.get_instagram_media(normalized_url)
            if cached_media and cached_media.get("telegram_file_id"):
                logging.info(f"Found cached media for {media_id}")
                
                if user_message:
                    await user_message.edit_text("✅ Keshdan topildi!")
                
                return {
                    "success": True,
                    "cached": True,
                    "media_data": cached_media,
                    "file_path": None,
                    "source": "cache"
                }
            
            # 2. Yangi yuklab olish
            logging.info(f"No cache found, starting fresh download for {media_id}")
            
            if user_message:
                await user_message.edit_text("📥 Yuklab olish boshlandi...")
            
            # Try yt-dlp first (free method)
            result = await self._download_with_ytdlp(normalized_url, media_id)
            
            if not result:
                if user_message:
                    await user_message.edit_text("⚡ Bepul usul ishlamadi, premium usuldan foydalanilmoqda...")
                
                # Try Apify as fallback
                result = await self._download_with_apify(normalized_url, media_id)
            
            if not result:
                logging.error(f"All download methods failed for {normalized_url}")
                if user_message:
                    await user_message.edit_text("❌ Yuklab olishda xatolik yuz berdi")
                return None
            
            file_path, title, media_id = result
            
            logging.info(f"Download successful: {file_path}")
            
            if user_message:
                await user_message.edit_text("📤 Telegram ga yuklanmoqda...")
            
            # 3. Telegram kanalga yuklash
            telegram_file_id = await self._upload_to_telegram_channel(file_path, title)
            
            if not telegram_file_id:
                logging.error("Failed to upload to Telegram channel")
                if user_message:
                    await user_message.edit_text("❌ Telegram ga yuklashda xatolik")
                return None
            
            # 4. Database ga saqlash
            media_data = await self.db.save_instagram_media(
                media_id=media_id,
                title=title,
                video_url=normalized_url,
                telegram_file_id=telegram_file_id,
                user_id=user_id
            )
            
            logging.info(f"Media saved to database: {media_id}")
            
            # 5. Temp faylni o'chirish
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Temp file cleaned: {file_path}")
            except Exception as e:
                logging.warning(f"Failed to clean temp file: {e}")
            
            if user_message:
                await user_message.edit_text("✅ Tayyor!")
            
            return {
                "success": True,
                "cached": False,
                "media_data": media_data,
                "file_path": file_path,
                "source": "fresh_download"
            }
            
        except Exception as e:
            logging.error(f"Instagram download error: {e}")
            if user_message:
                await user_message.edit_text("❌ Xatolik yuz berdi")
            return None
    
    async def _download_with_ytdlp(self, url: str, media_id: str) -> Optional[Tuple[str, str, str]]:
        """
        yt-dlp orqali yuklab olish (bepul usul)
        
        Args:
            url: Instagram URL
            media_id: Media ID
            
        Returns:
            (file_path, title, media_id) yoki None
        """
        try:
            logging.info(f"Trying yt-dlp download for {media_id}")
            
            # Multiple yt-dlp configurations for better success rate
            configurations = [
                {
                    "format": "best[height<=1080]/best",
                    "user_agent": USER_AGENTS[0],
                    "extractor_args": {"instagram": {"api_version": "v1"}}
                },
                {
                    "format": "best",
                    "user_agent": USER_AGENTS[1],
                    "extractor_args": {"instagram": {"skip_auth_warning": True}}
                },
                {
                    "format": "worst",  # Sometimes only low quality works
                    "user_agent": USER_AGENTS[2],
                    "extractor_args": {}
                }
            ]
            
            for i, config in enumerate(configurations):
                try:
                    logging.info(f"Trying yt-dlp configuration {i+1}/3")
                    
                    ydl_opts = {
                        "format": config["format"],
                        "outtmpl": os.path.join(TEMP_DIR, f"{media_id}_%(id)s.%(ext)s"),
                        "quiet": True,
                        "no_warnings": True,
                        "no_check_certificate": True,
                        "prefer_insecure": True,
                        "extractor_retries": 3,
                        "fragment_retries": 3,
                        "retries": 2,
                        "socket_timeout": 30,
                        "http_headers": {
                            "User-Agent": config["user_agent"],
                            "Referer": "https://www.instagram.com/",
                            "X-IG-App-ID": "936619743392459",
                        },
                        "extractor_args": {"instagram": config["extractor_args"]}
                    }
                    
                    # Try to find cookies file
                    cookies_files = [
                        "cookies.txt",
                        "/app/cookies.txt",
                        "/usr/src/app/cookies.txt",
                        os.path.join(os.getcwd(), "cookies.txt")
                    ]
                    
                    for cookies_file in cookies_files:
                        if os.path.exists(cookies_file):
                            ydl_opts["cookiefile"] = cookies_file
                            logging.info(f"Using cookies: {cookies_file}")
                            break
                    
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        
                        if info:
                            file_id = info.get('id', media_id)
                            title = sanitize_filename(
                                info.get('title') or 
                                info.get('description', '')[:50] or 
                                f'instagram_{file_id}'
                            )
                            ext = info.get('ext', 'mp4')
                            
                            # Find downloaded file
                            for filename in os.listdir(TEMP_DIR):
                                if file_id in filename and filename.endswith(f'.{ext}'):
                                    file_path = os.path.join(TEMP_DIR, filename)
                                    if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                                        logging.info(f"yt-dlp success: {file_path}")
                                        return file_path, title, media_id
                    
                except Exception as e:
                    logging.warning(f"yt-dlp config {i+1} failed: {e}")
                    continue
            
            logging.warning("All yt-dlp configurations failed")
            return None
            
        except Exception as e:
            logging.error(f"yt-dlp download failed: {e}")
            return None
    
    async def _download_with_apify(self, url: str, media_id: str) -> Optional[Tuple[str, str, str]]:
        """
        Apify Instagram Scraper orqali yuklab olish
        
        Args:
            url: Instagram URL
            media_id: Media ID
            
        Returns:
            (file_path, title, media_id) yoki None
        """
        try:
            if not APIFY_API_TOKENS:
                logging.error("No Apify API tokens configured")
                return None
            
            logging.info(f"Trying Apify download for {media_id}")
            
            # Try different actor/token combinations
            for actor_id in INSTAGRAM_SCRAPER_ACTORS:
                for token in APIFY_API_TOKENS:
                    try:
                        logging.info(f"Trying actor {actor_id} with token {token[:8]}...")
                        
                        result = await self._try_apify_actor(actor_id, url, token, media_id)
                        if result:
                            logging.info(f"Apify success with actor {actor_id}")
                            return result
                        
                    except Exception as e:
                        logging.warning(f"Actor {actor_id} with token {token[:8]}... failed: {e}")
                        continue
            
            logging.error("All Apify actors/tokens failed")
            return None
            
        except Exception as e:
            logging.error(f"Apify download failed: {e}")
            return None
    
    async def _try_apify_actor(self, actor_id: str, url: str, token: str, media_id: str) -> Optional[Tuple[str, str, str]]:
        """
        Bitta Apify actor bilan sinab ko'rish
        
        Args:
            actor_id: Apify actor ID
            url: Instagram URL
            token: Apify API token
            media_id: Media ID
            
        Returns:
            (file_path, title, media_id) yoki None
        """
        try:
            base_url = "https://api.apify.com/v2"
            
            # Input data for the actor
            input_data = {
                "directUrls": [url],
                "resultsType": "posts",
                "resultsLimit": 1,
                "searchType": "posts",
                "searchLimit": 1
            }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Start actor run
            run_url = f"{base_url}/acts/{actor_id}/runs"
            
            async with self.session.post(run_url, headers=headers, json=input_data) as response:
                if response.status != 201:
                    logging.warning(f"Failed to start actor run: HTTP {response.status}")
                    return None
                
                run_info = await response.json()
                run_id = run_info["data"]["id"]
                
                logging.info(f"Actor run started: {run_id}")
                
                # Wait for completion (max 2 minutes)
                result_data = await self._wait_for_apify_run(run_id, token, max_wait=120)
                
                if not result_data or len(result_data) == 0:
                    logging.warning("No data returned from Apify")
                    return None
                
                # Extract media information
                item = result_data[0]
                video_url = self._extract_video_url_from_apify_data(item)
                
                if not video_url:
                    logging.warning("No video URL found in Apify data")
                    return None
                
                # Download video file
                title = self._extract_title_from_apify_data(item, media_id)
                file_path = await self._download_file_from_url(video_url, f"{media_id}.mp4")
                
                if file_path:
                    return file_path, title, media_id
                
                return None
            
        except Exception as e:
            logging.error(f"Apify actor try failed: {e}")
            return None
    
    async def _wait_for_apify_run(self, run_id: str, token: str, max_wait: int = 120) -> Optional[List[dict]]:
        """
        Apify run tugashini kutadi
        
        Args:
            run_id: Run ID
            token: API token
            max_wait: Maksimal kutish vaqti (soniya)
            
        Returns:
            Run natijasi yoki None
        """
        try:
            base_url = "https://api.apify.com/v2"
            headers = {'Authorization': f'Bearer {token}'}
            
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # Check run status
                status_url = f"{base_url}/actor-runs/{run_id}"
                
                async with self.session.get(status_url, headers=headers) as response:
                    if response.status == 200:
                        run_info = await response.json()
                        status = run_info["data"]["status"]
                        
                        if status == "SUCCEEDED":
                            # Get dataset items
                            dataset_id = run_info["data"]["defaultDatasetId"]
                            items_url = f"{base_url}/datasets/{dataset_id}/items"
                            
                            async with self.session.get(items_url, headers=headers) as items_response:
                                if items_response.status == 200:
                                    items_data = await items_response.json()
                                    logging.info(f"Apify run completed successfully, got {len(items_data)} items")
                                    return items_data
                        
                        elif status in ["FAILED", "TIMED-OUT", "ABORTED"]:
                            logging.error(f"Apify run failed with status: {status}")
                            return None
                        
                        # Still running, wait
                        await asyncio.sleep(3)
                    else:
                        logging.warning(f"Failed to check run status: HTTP {response.status}")
                        await asyncio.sleep(3)
            
            logging.error("Apify run timed out")
            return None
            
        except Exception as e:
            logging.error(f"Error waiting for Apify run: {e}")
            return None
    
    def _extract_video_url_from_apify_data(self, data: dict) -> Optional[str]:
        """
        Apify data dan video URL ajratib oladi
        
        Args:
            data: Apify scraped data
            
        Returns:
            Video URL yoki None
        """
        try:
            # Different possible paths for video URL
            video_paths = [
                "videoUrl",
                "video_url", 
                "displayUrl",
                "display_url",
                "url"
            ]
            
            for path in video_paths:
                if path in data and data[path]:
                    url = data[path]
                    if isinstance(url, str) and url.startswith("http"):
                        return url
            
            # Check nested structures
            if "node" in data:
                return self._extract_video_url_from_apify_data(data["node"])
            
            return None
            
        except Exception as e:
            logging.error(f"Error extracting video URL: {e}")
            return None
    
    def _extract_title_from_apify_data(self, data: dict, fallback_id: str) -> str:
        """
        Apify data dan title ajratib oladi
        
        Args:
            data: Apify scraped data
            fallback_id: Fallback ID agar title topilmasa
            
        Returns:
            Title
        """
        try:
            # Different possible paths for title/caption
            title_paths = [
                "caption",
                "title",
                "text",
                "description"
            ]
            
            for path in title_paths:
                if path in data and data[path]:
                    title = str(data[path]).strip()
                    if title:
                        # Clean and truncate title
                        title = sanitize_filename(title)
                        if len(title) > 100:
                            title = title[:100] + "..."
                        return title
            
            # Fallback
            return f"instagram_{fallback_id}"
            
        except Exception as e:
            logging.error(f"Error extracting title: {e}")
            return f"instagram_{fallback_id}"
    
    async def _download_file_from_url(self, url: str, filename: str) -> Optional[str]:
        """
        URL dan fayl yuklab oladi
        
        Args:
            url: Fayl URL
            filename: Saqlash uchun fayl nomi
            
        Returns:
            Fayl yo'li yoki None
        """
        try:
            file_path = os.path.join(TEMP_DIR, filename)
            
            headers = {
                'Referer': 'https://www.instagram.com/',
                'User-Agent': random.choice(USER_AGENTS)
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    
                    # Verify file was downloaded
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                        logging.info(f"File downloaded: {file_path} ({os.path.getsize(file_path)} bytes)")
                        return file_path
                    else:
                        logging.error("Downloaded file is too small or empty")
                        return None
                else:
                    logging.error(f"Failed to download file: HTTP {response.status}")
                    return None
            
        except Exception as e:
            logging.error(f"File download error: {e}")
            return None
    
    async def _upload_to_telegram_channel(self, file_path: str, title: str) -> Optional[str]:
        """
        Faylni Telegram private kanalga yuklaydi
        
        Args:
            file_path: Fayl yo'li
            title: Fayl sarlavhasi
            
        Returns:
            Telegram file ID yoki None
        """
        try:
            if not PRIVATE_CHANNEL_ID:
                logging.error("PRIVATE_CHANNEL_ID not configured")
                return None
            
            from aiogram import types
            
            # Determine file type and create appropriate input
            file_ext = os.path.splitext(file_path)[1].lower()
            video_file = types.InputFile(file_path)
            
            if file_ext in ['.mp4', '.mov', '.avi', '.webm']:
                # Send as video
                sent_message = await self.bot.send_video(
                    chat_id=PRIVATE_CHANNEL_ID,
                    video=video_file,
                    caption=f"📱 Instagram: {title}",
                    supports_streaming=True
                )
                return sent_message.video.file_id
            else:
                # Send as document
                sent_message = await self.bot.send_document(
                    chat_id=PRIVATE_CHANNEL_ID,
                    document=video_file,
                    caption=f"📱 Instagram: {title}"
                )
                return sent_message.document.file_id
            
        except Exception as e:
            logging.error(f"Telegram upload error: {e}")
            return None
    
    async def get_audio_from_instagram_media(self, media_id: str, user_id: int,
                                           user_message=None) -> Optional[Dict]:
        """
        Instagram mediadan audio ajratib oladi va Shazam orqali musiqani topadi
        
        Args:
            media_id: Instagram media ID
            user_id: Foydalanuvchi ID si
            user_message: User message object
            
        Returns:
            Audio ma'lumotlari yoki None
        """
        try:
            # 1. Media ma'lumotlarini olish
            media_info = await self.db.get_instagram_media_by_id(media_id)
            if not media_info:
                logging.error(f"Media not found: {media_id}")
                return None
            
            # 2. Agar audio avval saqlangan bo'lsa, uni qaytarish
            if media_info.get("audio") and media_info["audio"].get("telegram_file_id"):
                logging.info(f"Found cached audio for media {media_id}")
                return {
                    "success": True,
                    "cached": True,
                    "audio_data": media_info["audio"],
                    "source": "cache"
                }
            
            if user_message:
                await user_message.edit_text("🎵 Audio ajratilmoqda...")
            
            # 3. Telegram dan video yuklab olish
            telegram_file_id = media_info.get("telegram_file_id")
            if not telegram_file_id:
                logging.error("No telegram file ID found")
                return None
            
            # Download video from Telegram using file ID
            file_info = await self.bot.get_file(telegram_file_id)
            video_path = os.path.join(TEMP_DIR, f"{media_id}_video.mp4")
            
            await self.bot.download_file(file_info.file_path, video_path)
            
            # 4. Video dan audio ajratish (FFmpeg)
            audio_path = await self._extract_audio_from_video(video_path, media_id)
            
            if not audio_path:
                logging.error("Failed to extract audio from video")
                if user_message:
                    await user_message.edit_text("❌ Audio ajratishda xatolik")
                return None
            
            if user_message:
                await user_message.edit_text("🔍 Musiqa nomi aniqlanmoqda...")
            
            # 5. Shazam orqali musiqa nomini topish
            track_name = await self._recognize_music_with_shazam(audio_path)
            
            if not track_name:
                logging.warning("No music recognized by Shazam")
                if user_message:
                    await user_message.edit_text("❌ Videoda musiqa topilmadi")
                return None
            
            logging.info(f"Music recognized: {track_name}")
            
            if user_message:
                await user_message.edit_text(f"🎵 '{track_name}' topildi, YouTube dan yuklanmoqda...")
            
            # 6. YouTube dan musiqa yuklab olish
            from bot.utils.youtube_enhanced import search_youtube, download_youtube_music
            
            search_results = await search_youtube(track_name, max_results=1)
            if not search_results:
                logging.warning("Track not found on YouTube")
                if user_message:
                    await user_message.edit_text("❌ Musiqa YouTube da topilmadi")
                return None
            
            video_info = search_results[0]
            youtube_url = video_info["url"]
            
            # Download audio from YouTube
            audio_download = await download_youtube_music(youtube_url)
            if not audio_download:
                logging.error("Failed to download music from YouTube")
                if user_message:
                    await user_message.edit_text("❌ YouTube dan yuklab olishda xatolik")
                return None
            
            audio_data, audio_file_path, filename = audio_download
            
            # 7. Telegram private kanalga yuklash
            from aiogram import types
            audio_file = types.InputFile(audio_file_path)
            
            sent_message = await self.bot.send_audio(
                chat_id=PRIVATE_CHANNEL_ID,
                audio=audio_file,
                title=video_info["title"],
                caption=f"🎵 Instagram Audio: {track_name}",
                parse_mode="HTML"
            )
            
            telegram_audio_file_id = sent_message.audio.file_id
            
            # 8. YouTube audio database ga saqlash
            youtube_audio = await self.db.save_youtube_audio(
                video_id=video_info["video_id"],
                title=video_info["title"],
                telegram_file_id=telegram_audio_file_id,
                url=youtube_url,
                thumbnail_url=video_info.get("thumbnail"),
                user_id=user_id
            )
            
            # 9. Instagram media ga audio bog'lash
            await self.db.add_audio_to_instagram_media(
                media_id=media_id,
                audio_id=video_info["video_id"]
            )
            
            # 10. Temp fayllarni tozalash
            try:
                for temp_file in [video_path, audio_path, audio_file_path]:
                    if temp_file and os.path.exists(temp_file):
                        os.remove(temp_file)
                        
                logging.info("Temp files cleaned up")
            except Exception as e:
                logging.warning(f"Cleanup error: {e}")
            
            if user_message:
                await user_message.edit_text("✅ Audio tayyor!")
            
            return {
                "success": True,
                "cached": False,
                "audio_data": {
                    "title": video_info["title"],
                    "telegram_file_id": telegram_audio_file_id,
                    "youtube_url": youtube_url,
                    "recognized_track": track_name
                },
                "source": "fresh_extraction"
            }
            
        except Exception as e:
            logging.error(f"Audio extraction error: {e}")
            if user_message:
                await user_message.edit_text("❌ Audio olishda xatolik yuz berdi")
            return None
    
    async def _extract_audio_from_video(self, video_path: str, media_id: str) -> Optional[str]:
        """
        Video fayldan audio ajratadi FFmpeg yordamida
        
        Args:
            video_path: Video fayl yo'li
            media_id: Media ID
            
        Returns:
            Audio fayl yo'li yoki None
        """
        try:
            audio_path = os.path.join(TEMP_DIR, f"{media_id}_audio.mp3")
            
            import subprocess
            
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-q:a", "2",
                "-map", "a",
                "-y",  # Overwrite if exists
                audio_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(audio_path):
                logging.info(f"Audio extracted: {audio_path}")
                return audio_path
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logging.error(f"FFmpeg failed: {error_msg}")
                return None
            
        except Exception as e:
            logging.error(f"Audio extraction error: {e}")
            return None
    
    async def _recognize_music_with_shazam(self, audio_path: str) -> Optional[str]:
        """
        Shazam orqali musiqani taniydi
        
        Args:
            audio_path: Audio fayl yo'li
            
        Returns:
            Musiqa nomi yoki None
        """
        try:
            logging.info(f"Starting Shazam recognition for {audio_path}")
            
            shazam = Shazam()
            
            # Recognize music
            out = await shazam.recognize_song(audio_path)
            
            if 'track' in out:
                track = out['track']
                title = track.get('title', '')
                subtitle = track.get('subtitle', '')  # Usually artist name
                
                if title:
                    track_name = f"{title}"
                    if subtitle:
                        track_name += f" - {subtitle}"
                    
                    logging.info(f"Music recognized: {track_name}")
                    return track_name
            
            logging.warning("No music recognized by Shazam")
            return None
            
        except Exception as e:
            logging.error(f"Shazam recognition error: {e}")
            return None


# === Convenience functions ===

async def download_instagram_media(instagram_url: str, user_id: int, db, bot, 
                                 user_message=None) -> Optional[Dict]:
    """
    Instagram media yuklab olish uchun convenience function
    
    Args:
        instagram_url: Instagram URL
        user_id: User ID
        db: Database instance
        bot: Bot instance
        user_message: User message for status updates
        
    Returns:
        Download result
    """
    async with InstagramMediaDownloader(db, bot) as downloader:
        return await downloader.download_instagram_media(instagram_url, user_id, user_message)


async def get_instagram_media_audio(media_id: str, user_id: int, db, bot,
                                   user_message=None) -> Optional[Dict]:
    """
    Instagram mediadan audio olish uchun convenience function
    
    Args:
        media_id: Instagram media ID
        user_id: User ID
        db: Database instance
        bot: Bot instance
        user_message: User message for status updates
        
    Returns:
        Audio extraction result
    """
    async with InstagramMediaDownloader(db, bot) as downloader:
        return await downloader.get_audio_from_instagram_media(media_id, user_id, user_message)
