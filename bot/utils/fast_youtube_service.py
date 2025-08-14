"""
Fast YouTube Music Download Service
Optimized for speed and efficiency
"""

import asyncio
import logging
import os
import tempfile
import yt_dlp
from typing import Optional, Dict, Tuple
from io import BytesIO
import aiofiles

from bot.utils.youtube_enhanced import YouTubeAPIManager

class FastYouTubeMusicService:
    """Fast YouTube music download service with optimized settings"""
    
    def __init__(self):
        self.youtube_api = YouTubeAPIManager()
        self.temp_dir = "/var/tmp/taronatop_bot"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Optimized yt-dlp options for speed and compatibility
        self.yt_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.temp_dir, '%(id)s.%(ext)s'),
            'noplaylist': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192K',  # Good quality but not too large
            'quiet': True,
            'no_warnings': True,
            'prefer_ffmpeg': True,
            'writeinfojson': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            # Speed optimizations
            'concurrent_fragment_downloads': 3,
            'retries': 1,  # Reduced retries for speed
            'socket_timeout': 15,  # Reduced timeout
            'fragment_retries': 1,
            # Additional compatibility options
            'cookiefile': 'cookies.txt',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
    
    async def fast_search_song(self, song_info: Dict) -> Optional[Dict]:
        """
        Fast YouTube search for song with single query strategy.
        
        Args:
            song_info: Dict with track, artist, title
            
        Returns:
            Dict with video info or None
        """
        try:
            # Use the most likely to succeed query first
            artist = song_info.get('artist', '').strip()
            track = song_info.get('track', '').strip()
            
            if artist and track:
                # Most effective query format
                query = f"{artist} {track} official audio"
            else:
                query = song_info.get('title', '').strip()
            
            if not query:
                return None
            
            logging.info(f"[Fast YouTube] Searching: {query}")
            
            # Single API call for speed
            search_results = await self.youtube_api.search_videos(query, max_results=5)
            
            if not search_results:
                return None
            
            # Quick scoring - take first result if it looks good
            for result in search_results:
                title = result.get('title', '').lower()
                
                # Check if we have video ID (from youtube_enhanced API)
                video_id = result.get('id') or result.get('video_id')
                if not video_id:
                    continue
                
                # Simple but effective matching
                if artist and track:
                    if artist.lower() in title and track.lower() in title:
                        logging.info(f"[Fast YouTube] Quick match: {result['title']}")
                        # Ensure we have 'id' field for compatibility
                        if 'id' not in result and 'video_id' in result:
                            result['id'] = result['video_id']
                        return result
            
            # If no exact match, return first result with valid ID
            for result in search_results:
                video_id = result.get('id') or result.get('video_id')
                if video_id:
                    logging.info(f"[Fast YouTube] Using first result: {result['title']}")
                    # Ensure we have 'id' field for compatibility
                    if 'id' not in result and 'video_id' in result:
                        result['id'] = result['video_id']
                    return result
            
            return None
            
        except Exception as e:
            logging.error(f"[Fast YouTube] Search error: {e}")
            return None
    
    async def fast_download_audio(self, video_id: str, video_info: Dict = None) -> Optional[Tuple[BytesIO, str, str]]:
        """
        Fast audio download with optimized settings.
        
        Args:
            video_id: YouTube video ID
            video_info: Optional video information
            
        Returns:
            Tuple of (BytesIO audio data, filename, title) or None
        """
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            title = video_info.get('title', video_id) if video_info else video_id
            
            logging.info(f"[Fast YouTube] Downloading: {title}")
            
            # Use asyncio to run yt-dlp in thread pool
            loop = asyncio.get_event_loop()
            download_result = await loop.run_in_executor(
                None, 
                self._download_sync, 
                url, 
                video_id
            )
            
            if not download_result:
                return None
            
            audio_path, actual_title = download_result
            
            # Read file to BytesIO
            async with aiofiles.open(audio_path, 'rb') as f:
                audio_data = BytesIO(await f.read())
            
            # Clean up temp file
            try:
                os.unlink(audio_path)
            except:
                pass
            
            filename = f"{video_id}.mp3"
            final_title = actual_title or title
            
            logging.info(f"[Fast YouTube] Download completed: {final_title}")
            return (audio_data, filename, final_title)
            
        except Exception as e:
            logging.error(f"[Fast YouTube] Download error for {video_id}: {e}")
            return None
    
    def _download_sync(self, url: str, video_id: str) -> Optional[Tuple[str, str]]:
        """
        Synchronous download using yt-dlp.
        
        Returns:
            Tuple of (file_path, title) or None
        """
        try:
            with yt_dlp.YoutubeDL(self.yt_opts) as ydl:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                title = info.get('title', video_id)
                
                # Download
                ydl.download([url])
                
                # Find the downloaded file
                possible_files = [
                    os.path.join(self.temp_dir, f"{video_id}.mp3"),
                    os.path.join(self.temp_dir, f"{video_id}.m4a"),
                ]
                
                for file_path in possible_files:
                    if os.path.exists(file_path):
                        return (file_path, title)
                
                # If not found, search for any file with video_id
                for filename in os.listdir(self.temp_dir):
                    if video_id in filename and filename.endswith(('.mp3', '.m4a')):
                        return (os.path.join(self.temp_dir, filename), title)
                
                return None
                
        except Exception as e:
            logging.error(f"[Fast YouTube] Sync download error: {e}")
            return None
    
    async def search_and_download_fast(self, song_info: Dict) -> Optional[Dict]:
        """
        Complete fast workflow: search + download.
        
        Args:
            song_info: Dict with track, artist, title
            
        Returns:
            Dict with download result or None
        """
        try:
            # Fast search
            youtube_video = await self.fast_search_song(song_info)
            if not youtube_video:
                logging.warning(f"[Fast YouTube] No video found for: {song_info}")
                return None
            
            # Fast download
            video_id = youtube_video.get('id')
            download_result = await self.fast_download_audio(video_id, youtube_video)
            
            if not download_result:
                logging.warning(f"[Fast YouTube] Download failed for: {video_id}")
                return None
            
            audio_data, filename, title = download_result
            
            return {
                'audio_data': audio_data,
                'filename': filename,
                'title': title,
                'video_id': video_id,
                'youtube_video': youtube_video,
                'song_info': song_info,
                'url': youtube_video.get('url', f"https://www.youtube.com/watch?v={video_id}")
            }
            
        except Exception as e:
            logging.error(f"[Fast YouTube] Complete workflow error: {e}")
            return None
