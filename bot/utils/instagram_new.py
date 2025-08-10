import os
import logging
import asyncio
import aiohttp
import aiofiles
import json
import re
import time
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlparse, parse_qs
from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename
from dotenv import load_dotenv
import random
import hashlib

# Load environment variables
load_dotenv()

# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# === Enhanced Instagram Downloader ===
class InstagramDownloader:
    """Modern, fast Instagram downloader with multiple fallback methods"""
    
    def __init__(self):
        self.session = None
        self.cookies_loaded = False
        self.rate_limit_delay = 1
        
        # User agents for different methods
        self.user_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Android 11; Mobile; rv:68.0) Gecko/68.0 Firefox/88.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
        ]
    
    async def __aenter__(self):
        await self._setup_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _setup_session(self):
        """Setup aiohttp session with proper headers"""
        timeout = aiohttp.ClientTimeout(total=30)
        
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Load cookies if available
        cookies = await self._load_cookies()
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            cookies=cookies
        )
    
    async def _load_cookies(self) -> Optional[dict]:
        """Load Instagram cookies from file"""
        cookies_files = [
            "cookies.txt",
            os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt"),
            "/usr/src/app/cookies.txt"
        ]
        
        for cookies_file in cookies_files:
            if os.path.exists(cookies_file):
                try:
                    cookies = {}
                    with open(cookies_file, 'r') as f:
                        for line in f:
                            if line.startswith('#') or not line.strip():
                                continue
                            parts = line.strip().split('\t')
                            if len(parts) >= 7 and 'instagram.com' in parts[0]:
                                cookies[parts[5]] = parts[6]
                    
                    if cookies:
                        logging.info(f"Loaded Instagram cookies from {cookies_file}")
                        self.cookies_loaded = True
                        return cookies
                        
                except Exception as e:
                    logging.warning(f"Failed to load cookies from {cookies_file}: {e}")
        
        logging.warning("No Instagram cookies found - some content may be restricted")
        return None
    
    async def download_media(self, url: str) -> Optional[Tuple[str, str, str]]:
        """
        Download Instagram media using multiple methods
        Returns: (file_path, title, media_id)
        """
        methods = [
            self._download_with_rapid_api,
            self._download_with_enhanced_ytdlp,
            self._download_with_direct_scraping,
            self._download_with_basic_ytdlp,
        ]
        
        for i, method in enumerate(methods, 1):
            try:
                logging.info(f"Trying Instagram download method {i}/4: {method.__name__}")
                result = await method(url)
                
                if result and result[0] and os.path.exists(result[0]):
                    logging.info(f"Instagram download successful using method {i}")
                    return result
                    
            except Exception as e:
                logging.warning(f"Instagram method {i} failed: {e}")
                
                # Add delay for rate limiting
                if "rate" in str(e).lower() or "limit" in str(e).lower():
                    self.rate_limit_delay = min(self.rate_limit_delay * 2, 30)
                    logging.info(f"Rate limit detected, waiting {self.rate_limit_delay}s")
                    await asyncio.sleep(self.rate_limit_delay)
        
        logging.error("All Instagram download methods failed")
        return None
    
    async def _download_with_rapid_api(self, url: str) -> Optional[Tuple[str, str, str]]:
        """Method 1: Use Instagram rapid API (fastest)"""
        try:
            # Extract shortcode from URL
            shortcode = self._extract_shortcode(url)
            if not shortcode:
                return None
            
            # Use Instagram's own API endpoints (public)
            api_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
            
            headers = {
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': url,
            }
            
            async with self.session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'items' in data and data['items']:
                        media = data['items'][0]
                        return await self._process_media_data(media, shortcode)
            
            return None
            
        except Exception as e:
            logging.error(f"Rapid API method failed: {e}")
            return None
    
    async def _download_with_enhanced_ytdlp(self, url: str) -> Optional[Tuple[str, str, str]]:
        """Method 2: Enhanced yt-dlp with optimized settings"""
        try:
            ydl_opts = {
                "format": "best[height<=1080]/best",
                "outtmpl": os.path.join(TEMP_DIR, "%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "no_check_certificate": True,
                
                # Anti-detection measures
                "extractor_retries": 3,
                "fragment_retries": 3,
                "retries": 2,
                "sleep_interval": 2,
                "sleep_interval_requests": 1,
                
                # Instagram-specific headers
                "http_headers": {
                    'User-Agent': random.choice(self.user_agents),
                    'X-IG-App-ID': '936619743392459',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.instagram.com/',
                },
                
                # Instagram extractor args
                "extractor_args": {
                    "instagram": {
                        "skip_auth_warning": True,
                        "api_version": "v1",
                    }
                }
            }
            
            # Add cookies if available
            cookies_files = ["cookies.txt", "/usr/src/app/cookies.txt"]
            for cookies_file in cookies_files:
                if os.path.exists(cookies_file):
                    ydl_opts["cookiefile"] = cookies_file
                    break
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if info:
                    file_id = info.get('id', 'unknown')
                    title = sanitize_filename(info.get('title') or info.get('description') or f'instagram_{file_id}')
                    ext = info.get('ext', 'mp4')
                    
                    file_path = os.path.join(TEMP_DIR, f"{file_id}.{ext}")
                    
                    if os.path.exists(file_path):
                        return file_path, title, file_id
            
            return None
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Enhanced yt-dlp failed: {error_msg}")
            
            # Check for specific Instagram errors
            if "rate-limit" in error_msg or "login required" in error_msg:
                raise Exception("Instagram rate limit or login required")
            
            return None
    
    async def _download_with_direct_scraping(self, url: str) -> Optional[Tuple[str, str, str]]:
        """Method 3: Direct HTML scraping (backup method)"""
        try:
            shortcode = self._extract_shortcode(url)
            if not shortcode:
                return None
            
            # Get page HTML
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
            
            # Extract JSON data from HTML
            json_match = re.search(r'window\._sharedData = ({.*?});', html)
            if not json_match:
                return None
            
            data = json.loads(json_match.group(1))
            
            # Navigate to media data
            entry_data = data.get('entry_data', {})
            post_page = entry_data.get('PostPage', [])
            
            if post_page and post_page[0]:
                media = post_page[0]['graphql']['shortcode_media']
                return await self._process_scraped_media(media, shortcode)
            
            return None
            
        except Exception as e:
            logging.error(f"Direct scraping failed: {e}")
            return None
    
    async def _download_with_basic_ytdlp(self, url: str) -> Optional[Tuple[str, str, str]]:
        """Method 4: Basic yt-dlp as last resort"""
        try:
            ydl_opts = {
                "format": "best",
                "outtmpl": os.path.join(TEMP_DIR, "%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if info:
                    file_id = info.get('id', 'unknown')
                    title = sanitize_filename(info.get('title', f'instagram_{file_id}'))
                    ext = info.get('ext', 'mp4')
                    
                    file_path = os.path.join(TEMP_DIR, f"{file_id}.{ext}")
                    
                    if os.path.exists(file_path):
                        return file_path, title, file_id
            
            return None
            
        except Exception as e:
            logging.error(f"Basic yt-dlp failed: {e}")
            return None
    
    def _extract_shortcode(self, url: str) -> Optional[str]:
        """Extract Instagram shortcode from URL"""
        patterns = [
            r'instagram\.com/p/([A-Za-z0-9_-]+)',
            r'instagram\.com/reel/([A-Za-z0-9_-]+)',
            r'instagram\.com/tv/([A-Za-z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def _process_media_data(self, media: dict, shortcode: str) -> Optional[Tuple[str, str, str]]:
        """Process media data from API response"""
        try:
            # Get video URL
            video_url = None
            if 'video_versions' in media:
                video_url = media['video_versions'][0]['url']
            elif 'image_versions2' in media:
                video_url = media['image_versions2']['candidates'][0]['url']
            
            if not video_url:
                return None
            
            # Download the file
            file_path = await self._download_file(video_url, shortcode)
            if not file_path:
                return None
            
            # Get title
            caption = media.get('caption')
            title = "Instagram Media"
            if caption and 'text' in caption:
                title = sanitize_filename(caption['text'][:50])
            
            return file_path, title, shortcode
            
        except Exception as e:
            logging.error(f"Failed to process media data: {e}")
            return None
    
    async def _process_scraped_media(self, media: dict, shortcode: str) -> Optional[Tuple[str, str, str]]:
        """Process media data from HTML scraping"""
        try:
            # Get video URL
            video_url = media.get('video_url')
            if not video_url:
                # Try image URL as fallback
                video_url = media.get('display_url')
            
            if not video_url:
                return None
            
            # Download the file
            file_path = await self._download_file(video_url, shortcode)
            if not file_path:
                return None
            
            # Get title
            edges = media.get('edge_media_to_caption', {}).get('edges', [])
            title = "Instagram Media"
            if edges and edges[0]['node']['text']:
                title = sanitize_filename(edges[0]['node']['text'][:50])
            
            return file_path, title, shortcode
            
        except Exception as e:
            logging.error(f"Failed to process scraped media: {e}")
            return None
    
    async def _download_file(self, url: str, filename: str) -> Optional[str]:
        """Download file from URL"""
        try:
            # Determine file extension
            ext = "mp4"
            if "jpg" in url or "jpeg" in url:
                ext = "jpg"
            elif "png" in url:
                ext = "png"
            
            file_path = os.path.join(TEMP_DIR, f"{filename}.{ext}")
            
            headers = {
                'Referer': 'https://www.instagram.com/',
                'User-Agent': random.choice(self.user_agents),
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    
                    logging.info(f"Downloaded Instagram media: {file_path}")
                    return file_path
            
            return None
            
        except Exception as e:
            logging.error(f"Failed to download file: {e}")
            return None
    
    async def get_media_info(self, url: str) -> Optional[dict]:
        """Get media information without downloading"""
        try:
            shortcode = self._extract_shortcode(url)
            if not shortcode:
                return None
            
            # Try API method first
            api_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
            
            headers = {
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': url,
            }
            
            async with self.session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'items' in data and data['items']:
                        media = data['items'][0]
                        
                        caption = media.get('caption')
                        caption_text = ""
                        if caption and 'text' in caption:
                            caption_text = caption['text']
                        
                        return {
                            "title": caption_text[:100] if caption_text else "Instagram Media",
                            "description": caption_text,
                            "thumbnail": media.get('image_versions2', {}).get('candidates', [{}])[0].get('url'),
                            "uploader": media.get('user', {}).get('username'),
                            "duration": media.get('video_duration'),
                            "id": shortcode,
                            "view_count": media.get('view_count'),
                            "like_count": media.get('like_count'),
                        }
            
            # Fallback to yt-dlp info extraction
            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "no_warnings": True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info:
                    return {
                        "title": info.get("title", "Instagram Media"),
                        "description": info.get("description"),
                        "thumbnail": info.get("thumbnail"),
                        "uploader": info.get("uploader"),
                        "duration": info.get("duration"),
                        "id": info.get("id"),
                        "view_count": info.get("view_count"),
                        "like_count": info.get("like_count"),
                    }
            
            return None
            
        except Exception as e:
            logging.error(f"Failed to get media info: {e}")
            return None

# === Global downloader instance ===
_downloader = None

async def get_downloader():
    """Get global downloader instance"""
    global _downloader
    if _downloader is None:
        _downloader = InstagramDownloader()
        await _downloader._setup_session()
    return _downloader

# === Public API functions ===
async def download_instagram_media(insta_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Download Instagram media using optimized methods
    Returns: (file_path, title, media_id)
    """
    async with InstagramDownloader() as downloader:
        return await downloader.download_media(insta_url)

async def get_instagram_media_info(insta_url: str) -> Optional[dict]:
    """Get Instagram media info without downloading"""
    async with InstagramDownloader() as downloader:
        return await downloader.get_media_info(insta_url)

# === Legacy compatibility functions ===
async def convert_instagram_video_to_audio(insta_url: str) -> Optional[str]:
    """Convert Instagram video to audio (legacy compatibility)"""
    result = await download_instagram_media(insta_url)
    if result and result[0]:
        # Convert video to audio if needed
        video_path = result[0]
        if video_path.endswith('.mp4'):
            audio_path = video_path.replace('.mp4', '.mp3')
            
            # Use FFmpeg to convert
            import subprocess
            try:
                subprocess.run([
                    "ffmpeg", "-i", video_path,
                    "-q:a", "2", "-y", audio_path
                ], check=True, capture_output=True)
                
                if os.path.exists(audio_path):
                    return audio_path
            except Exception as e:
                logging.error(f"Audio conversion failed: {e}")
        
        return video_path
    
    return None

# === Testing function ===
async def test_instagram_download():
    """Test Instagram download functionality"""
    test_urls = [
        "https://www.instagram.com/p/test/",  # Replace with actual Instagram URL
    ]
    
    for url in test_urls:
        print(f"Testing: {url}")
        
        async with InstagramDownloader() as downloader:
            # Test info extraction
            info = await downloader.get_media_info(url)
            if info:
                print(f"✅ Info: {info['title'][:50]}")
            else:
                print("❌ Failed to get info")
            
            # Test download
            result = await downloader.download_media(url)
            if result:
                print(f"✅ Download: {result[1]}")
                
                # Cleanup
                if os.path.exists(result[0]):
                    os.remove(result[0])
            else:
                print("❌ Download failed")
        
        print()

if __name__ == "__main__":
    asyncio.run(test_instagram_download())
