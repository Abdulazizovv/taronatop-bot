"""
Shazam integration service for music recognition
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any
from shazamio import Shazam, Serialize


class ShazamService:
    """Service for music recognition using Shazam API"""
    
    def __init__(self):
        self.shazam = Shazam()
        
    async def recognize_music(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """
        Recognize music from audio file using Shazam.
        Returns dict with song info or None if not recognized.
        """
        try:
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
                logging.warning(f"[Shazam] Invalid audio file: {audio_path}")
                return None
            
            logging.info(f"[Shazam] Starting music recognition for: {audio_path}")
            
            # Recognize music - using new method instead of deprecated recognize_song
            result = await self.shazam.recognize(audio_path)
            
            if not result or not result.get('track'):
                logging.info(f"[Shazam] No music recognized in: {audio_path}")
                return None
            
            # Extract track information
            track = result['track']
            
            song_info = {
                'title': track.get('title', 'Unknown'),
                'artist': track.get('subtitle', 'Unknown Artist'),
                'key': track.get('key'),
                'genres': self._extract_genres(track),
                'release_date': self._extract_release_date(track),
                'label': self._extract_label(track),
                'duration': self._extract_duration(track),
                'isrc': self._extract_isrc(track),
                'apple_music_url': self._extract_apple_music_url(track),
                'spotify_url': self._extract_spotify_url(track),
                'youtube_url': self._extract_youtube_url(track),
                'shazam_url': track.get('url'),
                'artwork_url': self._extract_artwork_url(track),
                'confidence': result.get('retryms', 0)  # Lower retry time indicates higher confidence
            }
            
            logging.info(f"[Shazam] Music recognized: {song_info['artist']} - {song_info['title']}")
            return song_info
            
        except Exception as e:
            logging.error(f"[Shazam] Music recognition error: {e}")
            return None

    async def recognize_music_from_video(self, video_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract audio from video and recognize music using Shazam.
        Returns dict with song info or None if not recognized.
        """
        try:
            from bot.utils.instagram_service import extract_audio_with_ffmpeg
            
            # Extract audio from video
            audio_path = await extract_audio_with_ffmpeg(video_path)
            if not audio_path:
                logging.warning(f"[Shazam] Audio extraction failed for video: {video_path}")
                return None
            
            # Recognize music from extracted audio
            song_info = await self.recognize_music(audio_path)
            
            # Cleanup temporary audio file
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass
            
            return song_info
            
        except Exception as e:
            logging.error(f"[Shazam] Video music recognition error: {e}")
            return None
            logging.error(f"[Shazam] Music recognition error: {e}")
            return None
    
    def _extract_genres(self, track: Dict) -> str:
        """Extract genres from track data"""
        try:
            genres = track.get('genres', {})
            if isinstance(genres, dict):
                primary = genres.get('primary', '')
                if primary:
                    return primary
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def _extract_release_date(self, track: Dict) -> Optional[str]:
        """Extract release date from track data"""
        try:
            sections = track.get('sections', [])
            for section in sections:
                if section.get('type') == 'SONG':
                    metadata = section.get('metadata', [])
                    for meta in metadata:
                        if meta.get('title') == 'Released':
                            return meta.get('text')
            return None
        except Exception:
            return None
    
    def _extract_label(self, track: Dict) -> Optional[str]:
        """Extract record label from track data"""
        try:
            sections = track.get('sections', [])
            for section in sections:
                if section.get('type') == 'SONG':
                    metadata = section.get('metadata', [])
                    for meta in metadata:
                        if meta.get('title') == 'Label':
                            return meta.get('text')
            return None
        except Exception:
            return None
    
    def _extract_duration(self, track: Dict) -> Optional[int]:
        """Extract song duration in seconds"""
        try:
            # Duration might be in different places
            duration_ms = track.get('duration_ms')
            if duration_ms:
                return int(duration_ms / 1000)
            
            sections = track.get('sections', [])
            for section in sections:
                if section.get('type') == 'SONG':
                    metadata = section.get('metadata', [])
                    for meta in metadata:
                        if meta.get('title') == 'Duration':
                            duration_text = meta.get('text', '')
                            # Parse duration like "3:45"
                            if ':' in duration_text:
                                parts = duration_text.split(':')
                                if len(parts) == 2:
                                    minutes = int(parts[0])
                                    seconds = int(parts[1])
                                    return minutes * 60 + seconds
            return None
        except Exception:
            return None
    
    def _extract_isrc(self, track: Dict) -> Optional[str]:
        """Extract ISRC code"""
        try:
            return track.get('isrc')
        except Exception:
            return None
    
    def _extract_apple_music_url(self, track: Dict) -> Optional[str]:
        """Extract Apple Music URL"""
        try:
            hub = track.get('hub', {})
            providers = hub.get('providers', [])
            for provider in providers:
                if provider.get('type') == 'APPLEMUSIC':
                    actions = provider.get('actions', [])
                    for action in actions:
                        if action.get('type') == 'uri':
                            return action.get('uri')
            return None
        except Exception:
            return None
    
    def _extract_spotify_url(self, track: Dict) -> Optional[str]:
        """Extract Spotify URL"""
        try:
            hub = track.get('hub', {})
            providers = hub.get('providers', [])
            for provider in providers:
                if provider.get('type') == 'SPOTIFY':
                    actions = provider.get('actions', [])
                    for action in actions:
                        if action.get('type') == 'uri':
                            return action.get('uri')
            return None
        except Exception:
            return None
    
    def _extract_youtube_url(self, track: Dict) -> Optional[str]:
        """Extract YouTube URL"""
        try:
            hub = track.get('hub', {})
            providers = hub.get('providers', [])
            for provider in providers:
                if provider.get('type') == 'YOUTUBE':
                    actions = provider.get('actions', [])
                    for action in actions:
                        if action.get('type') == 'uri':
                            return action.get('uri')
            return None
        except Exception:
            return None
    
    def _extract_artwork_url(self, track: Dict) -> Optional[str]:
        """Extract artwork/cover image URL"""
        try:
            images = track.get('images', {})
            # Try to get highest quality image
            for size in ['coverarthq', 'coverart', 'background']:
                if size in images:
                    return images[size]
            return None
        except Exception:
            return None
    
    def format_song_info(self, song_info: Dict[str, Any]) -> str:
        """Format song information for display"""
        try:
            title = song_info.get('title', 'Unknown')
            artist = song_info.get('artist', 'Unknown Artist')
            
            text = f"🎵 **{title}**\n👨‍🎤 {artist}"
            
            # Add additional info if available
            if song_info.get('genres') and song_info['genres'] != 'Unknown':
                text += f"\n🎭 {song_info['genres']}"
            
            if song_info.get('release_date'):
                text += f"\n📅 {song_info['release_date']}"
            
            if song_info.get('label'):
                text += f"\n🏷️ {song_info['label']}"
            
            if song_info.get('duration'):
                duration = song_info['duration']
                minutes = duration // 60
                seconds = duration % 60
                text += f"\n⏱️ {minutes}:{seconds:02d}"
            
            # Add streaming links
            links = []
            if song_info.get('apple_music_url'):
                links.append("[Apple Music](apple_music_url)")
            if song_info.get('spotify_url'):
                links.append("[Spotify](spotify_url)")
            if song_info.get('youtube_url'):
                links.append("[YouTube](youtube_url)")
            
            if links:
                text += f"\n\n🔗 {' • '.join(links)}"
            
            return text
            
        except Exception as e:
            logging.error(f"[Shazam] Format error: {e}")
            return f"🎵 {song_info.get('title', 'Unknown')} - {song_info.get('artist', 'Unknown Artist')}"


# Global instance
shazam_service = ShazamService()
