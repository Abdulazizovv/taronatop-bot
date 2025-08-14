"""
YouTube music search and download service for Instagram-detected songs
"""

import logging
import asyncio
from typing import Optional, Dict, List
from bot.utils.youtube_enhanced import YouTubeAPIManager


class YouTubeMusicService:
    """Service for searching and downloading music from YouTube based on Shazam results"""
    
    def __init__(self):
        self.youtube_api = YouTubeAPIManager()
    
    async def search_song_on_youtube(self, song_info: Dict) -> Optional[Dict]:
        """
        Search for a song on YouTube using Shazam information.
        
        Args:
            song_info: Dictionary with song info from Shazam (title, artist, etc.)
            
        Returns:
            Dict with YouTube video info or None if not found
        """
        try:
            title = song_info.get('title', '')
            artist = song_info.get('artist', '')
            
            if not title or not artist:
                logging.warning("[YouTube Music] Insufficient song info for search")
                return None
            
            # Create search queries with different combinations
            search_queries = [
                f"{artist} {title} official",
                f"{artist} {title} audio",
                f"{artist} {title}",
                f"{title} {artist}",
                f"{title} by {artist}"
            ]
            
            logging.info(f"[YouTube Music] Searching for: {artist} - {title}")
            
            for query in search_queries:
                try:
                    # Search on YouTube
                    search_results = await self.youtube_api.search_videos(
                        query=query,
                        max_results=5
                    )
                    
                    if search_results:
                        # Filter results to find the best match
                        best_match = self._find_best_match(search_results, title, artist)
                        
                        if best_match:
                            logging.info(f"[YouTube Music] Found match: {best_match['title']}")
                            return best_match
                    
                except Exception as e:
                    logging.warning(f"[YouTube Music] Search failed for query '{query}': {e}")
                    continue
            
            logging.warning(f"[YouTube Music] No YouTube results found for {artist} - {title}")
            return None
            
        except Exception as e:
            logging.error(f"[YouTube Music] Search error: {e}")
            return None
    
    def _find_best_match(self, search_results: List[Dict], target_title: str, target_artist: str) -> Optional[Dict]:
        """
        Find the best matching video from search results.
        
        Args:
            search_results: List of YouTube search results
            target_title: Target song title
            target_artist: Target artist name
            
        Returns:
            Best matching video info or None
        """
        try:
            target_title_lower = target_title.lower()
            target_artist_lower = target_artist.lower()
            
            # Score each result
            scored_results = []
            
            for video in search_results:
                title = video.get('title', '').lower()
                description = video.get('description', '').lower()
                channel_title = video.get('channel_title', '').lower()
                duration = video.get('duration_seconds', 0)
                
                score = 0
                
                # Title matching
                if target_title_lower in title:
                    score += 10
                if target_artist_lower in title:
                    score += 10
                
                # Channel/artist matching
                if target_artist_lower in channel_title:
                    score += 8
                
                # Description matching
                if target_title_lower in description:
                    score += 3
                if target_artist_lower in description:
                    score += 3
                
                # Duration scoring (prefer songs 1-8 minutes)
                if 60 <= duration <= 480:  # 1-8 minutes
                    score += 5
                elif duration > 600:  # Too long, likely not a song
                    score -= 5
                
                # Prefer official content
                if any(keyword in title for keyword in ['official', 'audio', 'music video']):
                    score += 5
                
                # Avoid live versions, covers, remixes if possible
                if any(keyword in title for keyword in ['live', 'cover', 'remix', 'karaoke']):
                    score -= 3
                
                if score > 0:
                    scored_results.append((score, video))
            
            # Return the highest scoring result
            if scored_results:
                scored_results.sort(key=lambda x: x[0], reverse=True)
                best_score, best_video = scored_results[0]
                
                logging.info(f"[YouTube Music] Best match score: {best_score} for '{best_video['title']}'")
                return best_video
            
            # If no good matches, return the first result as fallback
            if search_results:
                logging.info("[YouTube Music] Using first result as fallback")
                return search_results[0]
            
            return None
            
        except Exception as e:
            logging.error(f"[YouTube Music] Match scoring error: {e}")
            return search_results[0] if search_results else None
    
    async def download_youtube_music_audio(self, video_info: Dict) -> Optional[str]:
        """
        Download audio from YouTube video.
        
        Args:
            video_info: YouTube video information
            
        Returns:
            Path to downloaded audio file or None
        """
        try:
            video_id = video_info.get('video_id')
            if not video_id:
                logging.error("[YouTube Music] No video ID provided")
                return None
            
            # Use existing YouTube download functionality
            from bot.utils.youtube_enhanced import download_youtube_music
            
            audio_data = await download_youtube_music(
                video_url=video_info.get('url', f"https://www.youtube.com/watch?v={video_id}")
            )
            
            if audio_data:
                # download_youtube_music returns (BytesIO, filename, title)
                audio_content, filename, title = audio_data
                
                # Save to temporary file
                import tempfile
                import os
                temp_dir = "/var/tmp/taronatop_bot"
                os.makedirs(temp_dir, exist_ok=True)
                
                audio_path = os.path.join(temp_dir, f"yt_music_{video_id}.mp3")
                with open(audio_path, 'wb') as f:
                    f.write(audio_content.getvalue())
                
                logging.info(f"[YouTube Music] Downloaded audio: {audio_path}")
                return audio_path
            
        except Exception as e:
            logging.error(f"[YouTube Music] Download error: {e}")
            return None
    
    async def search_and_download_song(self, song_info: Dict) -> Optional[Dict]:
        """
        Complete workflow: search song on YouTube and download audio.
        
        Args:
            song_info: Song information from Shazam
            
        Returns:
            Dict with download info or None
        """
        try:
            # Search for song on YouTube
            youtube_video = await self.search_song_on_youtube(song_info)
            if not youtube_video:
                return None
            
            # Download audio
            audio_path = await self.download_youtube_music_audio(youtube_video)
            if not audio_path:
                return None
            
            return {
                'audio_path': audio_path,
                'youtube_video': youtube_video,
                'song_info': song_info,
                'title': f"{song_info.get('artist', 'Unknown')} - {song_info.get('title', 'Unknown')}",
                'artist': song_info.get('artist', 'Unknown'),
                'track': song_info.get('title', 'Unknown')
            }
            
        except Exception as e:
            logging.error(f"[YouTube Music] Search and download error: {e}")
            return None


# Global instance
youtube_music_service = YouTubeMusicService()
