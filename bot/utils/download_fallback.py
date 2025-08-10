#!/usr/bin/env python3
"""
YouTube Download Fallback Manager
Manages multiple download methods to avoid bot detection
"""

import asyncio
import logging
from typing import Optional, Tuple, Any
from io import BytesIO

class YouTubeDownloadManager:
    """Manages multiple download strategies to avoid bot detection"""
    
    def __init__(self):
        self.strategies = [
            self._download_with_api_search,
            self._download_with_enhanced_ytdlp,
            self._download_with_basic_ytdlp,
        ]
    
    async def download_audio_with_fallback(self, video_url: str) -> Tuple[Optional[BytesIO], Optional[str], Optional[str]]:
        """Try multiple download strategies until one succeeds"""
        
        for i, strategy in enumerate(self.strategies, 1):
            try:
                logging.info(f"Trying download strategy {i}/3: {strategy.__name__}")
                result = await strategy(video_url)
                
                if result[0] is not None:  # Success
                    logging.info(f"Download successful using strategy {i}")
                    return result
                    
            except Exception as e:
                error_msg = str(e)
                logging.warning(f"Strategy {i} failed: {error_msg}")
                
                # If bot detection, skip to next strategy immediately
                if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
                    logging.warning(f"Bot detection in strategy {i}, trying next method")
                    continue
        
        # All strategies failed
        logging.error("All download strategies failed")
        return None, None, None
    
    async def _download_with_api_search(self, video_url: str) -> Tuple[Optional[BytesIO], Optional[str], Optional[str]]:
        """Strategy 1: Use YouTube API to get info, then download with yt-dlp"""
        from bot.utils.youtube import get_video_info, download_music
        
        try:
            # Get video info via API first (more reliable)
            video_info = await get_video_info(video_url)
            if not video_info:
                return None, None, None
            
            # Then download using the info
            return await download_music(video_url)
            
        except Exception as e:
            raise e
    
    async def _download_with_enhanced_ytdlp(self, video_url: str) -> Tuple[Optional[BytesIO], Optional[str], Optional[str]]:
        """Strategy 2: Enhanced yt-dlp with cookies and headers"""
        from bot.utils.youtube import download_music
        
        return await download_music(video_url)
    
    async def _download_with_basic_ytdlp(self, video_url: str) -> Tuple[Optional[BytesIO], Optional[str], Optional[str]]:
        """Strategy 3: Basic yt-dlp as last resort"""
        import os
        from yt_dlp import YoutubeDL
        from bot.utils.youtube import extract_video_id, clean_filename, TEMP_DIR
        
        video_id = extract_video_id(video_url)
        if not video_id:
            return None, None, None
        
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # Very basic options - no cookies, minimal headers
        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": os.path.join(TEMP_DIR, f"{video_id}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128"  # Lower quality for last resort
            }],
            "quiet": True,
            "no_warnings": True,
        }
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = os.path.join(TEMP_DIR, f"{video_id}.mp3")
                
            with open(filename, 'rb') as f:
                return BytesIO(f.read()), filename, clean_filename(info.get("title", "Unknown")) + ".mp3"
                
        except Exception as e:
            logging.error(f"Basic yt-dlp failed: {e}")
            return None, None, None

# Global instance
download_manager = YouTubeDownloadManager()

async def download_with_fallback(video_url: str) -> Tuple[Optional[BytesIO], Optional[str], Optional[str]]:
    """Public interface for fallback download"""
    return await download_manager.download_audio_with_fallback(video_url)

if __name__ == "__main__":
    # Test the fallback system
    async def test():
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = await download_with_fallback(url)
        
        if result[0]:
            print("✅ Download successful!")
            print(f"File size: {len(result[0].getvalue())} bytes")
        else:
            print("❌ All download methods failed")
    
    asyncio.run(test())
