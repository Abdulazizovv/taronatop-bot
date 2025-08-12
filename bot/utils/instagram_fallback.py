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

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# === Fallback Instagram Downloader (No API required) ===
class FallbackInstagramDownloader:
    """
    Fallback Instagram downloader without API dependencies
    """
    
    def __init__(self):
        self.session = None
        logging.info("Fallback Instagram downloader initialized")
    
    async def __aenter__(self):
        await self._setup_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _setup_session(self):
        """Setup aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=60)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
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
    
    async def download_instagram_media(self, instagram_url: str) -> Optional[Tuple[str, str, str]]:
        """
        Instagram mediasini yuklab oladi (fallback methods)
        """
        try:
            # Method 1: Try Instagram Web API
            result = await self._try_web_api(instagram_url)
            if result:
                return result
            
            # Method 2: Try yt-dlp with basic options
            result = await self._try_ytdlp_basic(instagram_url)
            if result:
                return result
            
            # Method 3: Try gallery-dl
            result = await self._try_gallery_dl(instagram_url)
            if result:
                return result
            
            logging.error("All fallback methods failed")
            return None
            
        except Exception as e:
            logging.error(f"Fallback Instagram download failed: {str(e)}")
            return None
    
    async def _try_web_api(self, instagram_url: str) -> Optional[Tuple[str, str, str]]:
        """
        Instagram web API orqali sinab ko'radi
        """
        try:
            # Extract shortcode from URL
            shortcode = self._extract_shortcode(instagram_url)
            if not shortcode:
                return None
            
            # Try to get media info from Instagram web
            api_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
            
            async with self.session.get(api_url) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                # Extract video URL
                video_url = self._extract_video_from_api_data(data)
                if not video_url:
                    return None
                
                # Download video
                title = f"instagram_{shortcode}"
                file_path = await self._download_video_direct(video_url, title)
                
                return file_path, title, shortcode
                
        except Exception as e:
            logging.warning(f"Web API method failed: {str(e)}")
            return None
    
    async def _try_ytdlp_basic(self, instagram_url: str) -> Optional[Tuple[str, str, str]]:
        """
        yt-dlp basic options bilan sinab ko'radi
        """
        try:
            shortcode = self._extract_shortcode(instagram_url)
            title = f"instagram_{shortcode or uuid4().hex[:8]}"
            output_path = os.path.join(TEMP_DIR, f"{title}.%(ext)s")
            
            # Basic yt-dlp command
            cmd = [
                "yt-dlp",
                "--no-warnings",
                "--quiet",
                "--format", "best",
                "--output", output_path,
                "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
                instagram_url
            ]
            
            # Run yt-dlp
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode == 0:
                # Find downloaded file
                for ext in ['mp4', 'webm', 'mov']:
                    file_path = os.path.join(TEMP_DIR, f"{title}.{ext}")
                    if os.path.exists(file_path):
                        return file_path, title, shortcode or "unknown"
            
            return None
            
        except Exception as e:
            logging.warning(f"yt-dlp basic method failed: {str(e)}")
            return None
    
    async def _try_gallery_dl(self, instagram_url: str) -> Optional[Tuple[str, str, str]]:
        """
        gallery-dl bilan sinab ko'radi
        """
        try:
            shortcode = self._extract_shortcode(instagram_url)
            title = f"instagram_{shortcode or uuid4().hex[:8]}"
            
            # gallery-dl command
            cmd = [
                "gallery-dl",
                "--quiet",
                "--directory", TEMP_DIR,
                "--filename", f"{title}.{{extension}}",
                instagram_url
            ]
            
            # Run gallery-dl
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode == 0:
                # Find downloaded file
                for ext in ['mp4', 'jpg', 'png', 'webm']:
                    file_path = os.path.join(TEMP_DIR, f"{title}.{ext}")
                    if os.path.exists(file_path):
                        return file_path, title, shortcode or "unknown"
            
            return None
            
        except Exception as e:
            logging.warning(f"gallery-dl method failed: {str(e)}")
            return None
    
    def _extract_shortcode(self, url: str) -> Optional[str]:
        """
        URL dan shortcode ajratib oladi
        """
        try:
            patterns = [
                r'/p/([A-Za-z0-9_-]+)',
                r'/reel/([A-Za-z0-9_-]+)',
                r'/tv/([A-Za-z0-9_-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception:
            return None
    
    def _extract_video_from_api_data(self, data: dict) -> Optional[str]:
        """
        API data dan video URL ajratib oladi
        """
        try:
            # Instagram API response structure varies
            if "graphql" in data:
                media = data["graphql"]["shortcode_media"]
                if media.get("is_video") and "video_url" in media:
                    return media["video_url"]
            
            return None
            
        except Exception:
            return None
    
    async def _download_video_direct(self, video_url: str, title: str) -> Optional[str]:
        """
        Video faylni to'g'ridan-to'g'ri yuklab oladi
        """
        try:
            file_path = os.path.join(TEMP_DIR, f"{title}.mp4")
            
            async with self.session.get(video_url) as response:
                if response.status != 200:
                    return None
                
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path
            
            return None
            
        except Exception as e:
            logging.error(f"Direct download failed: {str(e)}")
            return None


# === Compatibility functions ===
async def download_instagram_media(insta_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Fallback Instagram media yuklab oladi
    """
    try:
        async with FallbackInstagramDownloader() as downloader:
            return await downloader.download_instagram_media(insta_url)
    except Exception as e:
        logging.error(f"Failed to download Instagram media: {str(e)}")
        return None

async def get_instagram_media_info(insta_url: str) -> Optional[dict]:
    """
    Media haqida ma'lumot oladi
    """
    try:
        result = await download_instagram_media(insta_url)
        if result:
            file_path, title, media_id = result
            
            # Delete downloaded file
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
