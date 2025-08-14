"""
Database utility for updating Instagram media audio information.
"""

import logging
from typing import Optional, Dict
from asgiref.sync import sync_to_async
from botapp.models import InstagramMedia, YoutubeAudio

@sync_to_async
def save_youtube_audio_to_db(video_id: str, title: str, telegram_file_id: str, url: str = None, thumbnail_url: str = None, user_id: int = None) -> Optional[int]:
    """
    Save YouTube audio to database and return its ID.
    
    Args:
        video_id: YouTube video ID
        title: Audio title
        telegram_file_id: Telegram file ID for quick access
        url: YouTube video URL
        thumbnail_url: Video thumbnail URL
        user_id: User who requested the audio
        
    Returns:
        YoutubeAudio ID if successful, None otherwise
    """
    try:
        # Get user instance if user_id provided
        user_instance = None
        if user_id:
            from botapp.models import BotUser
            user_instance = BotUser.objects.filter(user_id=str(user_id)).first()
        
        # Check if already exists
        audio, created = YoutubeAudio.objects.get_or_create(
            video_id=video_id,
            defaults={
                'title': title[:255],  # Limit to field length
                'telegram_file_id': telegram_file_id,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'user': user_instance
            }
        )
        
        if not created and telegram_file_id:
            # Update telegram_file_id if new one provided
            audio.telegram_file_id = telegram_file_id
            if user_instance and not audio.user:
                audio.user = user_instance
            audio.save(update_fields=['telegram_file_id', 'user'])
        
        logging.info(f"[DB] YouTube audio saved: {title} (ID: {audio.id})")
        return audio.id
        
    except Exception as e:
        logging.error(f"[DB] Error saving YouTube audio {video_id}: {e}")
        return None

@sync_to_async
def link_instagram_to_youtube_audio(media_id: str, youtube_audio_id: int, song_info: Dict = None) -> bool:
    """
    Link Instagram media to YouTube audio for fast future access.
    
    Args:
        media_id: Instagram media identifier
        youtube_audio_id: ID of YoutubeAudio record
        song_info: Optional song information to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        media = InstagramMedia.objects.filter(media_id=media_id).first()
        if not media:
            logging.warning(f"[DB] Instagram media not found for linking: {media_id}")
            return False
        
        youtube_audio = YoutubeAudio.objects.filter(id=youtube_audio_id).first()
        if not youtube_audio:
            logging.warning(f"[DB] YouTube audio not found for linking: {youtube_audio_id}")
            return False
        
        # Link Instagram media to YouTube audio
        media.audio = youtube_audio
        
        # Save song info if provided
        if song_info:
            media.track = song_info.get('track', '')[:255]
            media.artist = song_info.get('artist', '')[:255]
        
        media.save()
        
        logging.info(f"[DB] Linked Instagram {media_id} to YouTube audio {youtube_audio_id}")
        return True
        
    except Exception as e:
        logging.error(f"[DB] Error linking Instagram {media_id} to YouTube {youtube_audio_id}: {e}")
        return False

@sync_to_async
def get_linked_youtube_audio(media_id: str) -> Optional[Dict]:
    """
    Get linked YouTube audio for Instagram media.
    
    Args:
        media_id: Instagram media identifier
        
    Returns:
        Dict with YouTube audio info or None if not linked
    """
    try:
        media = InstagramMedia.objects.select_related('audio').filter(media_id=media_id).first()
        
        if media and media.audio and media.audio.telegram_file_id:
            return {
                'youtube_audio_id': media.audio.id,
                'video_id': media.audio.video_id,
                'title': media.audio.title,
                'telegram_file_id': media.audio.telegram_file_id,
                'url': media.audio.url,
                'thumbnail_url': media.audio.thumbnail_url,
                'track': media.track,
                'artist': media.artist,
                'has_linked_audio': True
            }
        
        return None
        
    except Exception as e:
        logging.error(f"[DB] Error getting linked YouTube audio for {media_id}: {e}")
        return None

@sync_to_async
def update_instagram_media_audio_info(media_id: str, has_audio: bool, song_info: Optional[Dict] = None) -> bool:
    """
    Update Instagram media with audio information and song details.
    
    Args:
        media_id: Instagram media identifier
        has_audio: Whether the media contains audio streams
        song_info: Optional song information from Shazam
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        media = InstagramMedia.objects.filter(media_id=media_id).first()
        if not media:
            logging.warning(f"[DB] Instagram media not found for audio update: {media_id}")
            return False
        
        # Update audio status
        media.has_audio = has_audio
        
        # If song info provided, save it
        if song_info:
            media.track = song_info.get('title', '')[:255]  # Limit to field length
            media.artist = song_info.get('artist', '')[:255]
            logging.info(f"[DB] Saved song info for {media_id}: {media.artist} - {media.track}")
        
        media.save()
        logging.info(f"[DB] Updated audio info for {media_id}: has_audio={has_audio}")
        return True
        
    except Exception as e:
        logging.error(f"[DB] Error updating audio info for {media_id}: {e}")
        return False


@sync_to_async
def get_instagram_media_song_info(media_id: str) -> Optional[Dict]:
    """
    Get saved song information for Instagram media.
    
    Args:
        media_id: Instagram media identifier
        
    Returns:
        Dict with song info or None if not found
    """
    try:
        media = InstagramMedia.objects.filter(media_id=media_id).first()
        
        if media and media.track and media.artist:
            return {
                'title': media.track,
                'artist': media.artist,
                'has_song_info': True
            }
        
        return None
        
    except Exception as e:
        logging.error(f"[DB] Error getting song info for {media_id}: {e}")
        return None
            
        media.has_audio = has_audio
        media.save(update_fields=['has_audio'])
        
        logging.info(f"[DB] Updated audio info for {media_id}: has_audio={has_audio}")
        return True
        
    except Exception as e:
        logging.error(f"[DB] Error updating audio info for {media_id}: {e}")
        return False


@sync_to_async 
def get_instagram_media_audio_info(media_id: str) -> dict:
    """
    Get Instagram media audio information.
    
    Args:
        media_id: Instagram media identifier
        
    Returns:
        dict: Media info including audio status
    """
    try:
        media = InstagramMedia.objects.filter(media_id=media_id).first()
        if not media:
            return {"found": False}
        
        has_audio = getattr(media, 'has_audio', None)
        
        return {
            "found": True,
            "media_id": media.media_id,
            "title": media.title,
            "telegram_file_id": media.telegram_file_id,
            "has_audio": has_audio,
            "duration": media.duration,
        }
        
    except Exception as e:
        logging.error(f"[DB] Error getting audio info for {media_id}: {e}")
        return {"found": False, "error": str(e)}
