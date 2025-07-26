from asgiref.sync import sync_to_async
from botapp.models import BotUser, BotChat, YoutubeAudio, YoutubeVideo, InstagramMedia, TikTokMedia
import logging



# Database API for Bot User Management
class DB:

    # Get admins id list
    @staticmethod
    @sync_to_async
    def get_admins():
        admins = BotUser.objects.filter(is_admin=True).values_list('user_id', flat=True)
        return list(admins)
    
    # Get or create a bot user by user_id
    @staticmethod
    @sync_to_async
    def get_or_create_user(user_id: int, first_name: str| None = None, last_name: str | None = None, username: str | None = None):
        user, created = BotUser.objects.get_or_create(
            user_id=user_id,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'username': username
            }
        )

        if created:
            logging.info(f"New user registered: {first_name} {last_name} | @{username} |")

        return {
            "user_id": user.user_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "created": created
        }
    
    # Get user by user_id
    @staticmethod
    @sync_to_async
    def get_user(user_id: int):
        try:
            user = BotUser.objects.get(user_id=user_id)
            return {
                "user_id": user.user_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "is_admin": user.is_admin,
                "is_active": user.is_active,
                "is_blocked": user.is_blocked,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            }
        except BotUser.DoesNotExist:
            return None
    
    # Adding new chat
    @staticmethod
    @sync_to_async
    def add_chat(chat_id: int, chat_type: str, title: str | None = None, username: str | None = None, invite_link: str | None = None, is_admin: bool = False):
        
        # first getting chat if exists else create
        chat = BotChat.objects.filter(chat_id=chat_id).first()
        if not chat:
            chat = BotChat.objects.create(
                chat_id=chat_id,
                chat_type=chat_type,
                title=title,
                username=username,
                is_admin=is_admin,
                invite_link=invite_link,
            )
            logging.info(f"Bot added to new chat: | title : {title} | type: {chat_type} | username: {username} | is_admin: {is_admin}")
        else:
            # Update existing chat details
            chat.chat_type = chat_type
            chat.title = title
            chat.username = username
            chat.is_admin = is_admin
            if invite_link is not None:
                chat.invite_link = invite_link
            chat.is_active = True
            chat.is_blocked = False
            chat.save()
        
        return {
            "chat_id": chat.chat_id,
            "chat_type": chat.chat_type,
            "title": chat.title,
            "username": chat.username,
            "is_admin": chat.is_admin,
            "is_active": chat.is_active,
            "is_blocked": chat.is_blocked,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at
        }
    
    # Deactivate a chat
    @staticmethod
    @sync_to_async
    def deactivate_chat(chat_id: int):
        try:
            chat = BotChat.objects.get(chat_id=chat_id)
            chat.is_active = False
            chat.is_admin = False
            chat.is_blocked = True
            chat.is_required = False
            chat.save()
            logging.info(f"Deactivated chat: {chat.title}")
            return True
        except BotChat.DoesNotExist:
            return False
        
    # Get all required chats
    @staticmethod
    @sync_to_async
    def get_required_chats():
        chats = BotChat.objects.filter(is_admin=True, is_required=True).values(
            'chat_id', 'chat_type', 'title', 'username', 'invite_link', 'is_admin', 
            'is_active', 'is_blocked', 'created_at', 'updated_at'
        )
        return list(chats)

    # Get all YouTube audio records for a user
    @staticmethod
    @sync_to_async
    def get_youtube_audios(user_id: int):
        audios = YoutubeAudio.objects.filter(user_id=user_id).values(
            'video_id', 'title', 'telegram_file_id', 'url', 'thumbnail_url', 'created_at', 'updated_at'
        )
        return list(audios)
    
    # Save YouTube audio record
    @staticmethod
    @sync_to_async
    def save_youtube_audio(video_id: str, title: str,
                           telegram_file_id: str | None = None, url: str | None = None,
                           thumbnail_url: str | None = None, user_id: int | None = None):
        
        user = BotUser.objects.filter(user_id=user_id).first() if user_id else None

        audio, created = YoutubeAudio.objects.update_or_create(
            video_id=video_id,
            defaults={
                'title': title,
                # 'duration': duration,
                'telegram_file_id': telegram_file_id,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'user': user
            }
        )
        if created:
            logging.info(f"New YouTube audio saved: {title} ({video_id})")
        return {
            "id": audio.id,
            "video_id": audio.video_id,
            "title": audio.title,
            # "duration": audio.duration,
            "telegram_file_id": audio.telegram_file_id,
            "url": audio.url,
            "thumbnail_url": audio.thumbnail_url,
            "user_id": audio.user_id,
            "created_at": audio.created_at,
            "updated_at": audio.updated_at
        }
    
    # Get YouTube audio by video ID
    @staticmethod
    @sync_to_async
    def get_youtube_audio(video_id: str):
        try:
            audio = YoutubeAudio.objects.get(video_id=video_id)
            return {
                "video_id": audio.video_id,
                "title": audio.title,
                # "duration": audio.duration,
                "telegram_file_id": audio.telegram_file_id,
                "url": audio.url,
                "thumbnail_url": audio.thumbnail_url,
                "user": {
                    "user_id": audio.user.user_id if audio.user else None,
                    "first_name": audio.user.first_name if audio.user else None,
                    "last_name": audio.user.last_name if audio.user else None,
                    "username": audio.user.username if audio.user else None
                } if audio.user else None,
                "created_at": audio.created_at,
                "updated_at": audio.updated_at
            }
        except YoutubeAudio.DoesNotExist:
            return None
        
    # Get YouTube video by video ID
    @staticmethod
    @sync_to_async
    def get_youtube_video(video_id: str):
        try:
            video = YoutubeVideo.objects.get(video_id=video_id)
            return {
                "video_id": video.video_id,
                "title": video.title,
                "duration": video.duration,
                "telegram_file_id": video.telegram_file_id,
                "thumbnail_url": video.thumbnail_url,
                "url": video.url,
                "user": {
                    "user_id": video.user.user_id if video.user else None,
                    "first_name": video.user.first_name if video.user else None,
                    "last_name": video.user.last_name if video.user else None,
                    "username": video.user.username if video.user else None
                } if video.user else None,
                "created_at": video.created_at,
                "updated_at": video.updated_at
            }
        except YoutubeVideo.DoesNotExist:
            return None
    # Save YouTube video record
    @staticmethod
    @sync_to_async
    def save_youtube_video(video_id: str, title: str, duration: int | None = None,
                           telegram_file_id: str | None = None,
                           thumbnail_url: str | None = None, url: str | None = None,
                           user_id: int | None = None):
        
        user = BotUser.objects.filter(user_id=user_id).first() if user_id else None

        video, created = YoutubeVideo.objects.update_or_create(
            video_id=video_id,
            defaults={
                'title': title,
                'telegram_file_id': telegram_file_id,
                'duration': duration,
                'thumbnail_url': thumbnail_url,
                'url': url,
                'user': user
            }
        )
        if created:
            logging.info(f"New YouTube video saved: {title} ({video_id})")
        return {
            "video_id": video.video_id,
            "title": video.title,
            "duration": video.duration,
            "telegram_file_id": video.telegram_file_id,
            "thumbnail_url": video.thumbnail_url,
            "url": video.url,
            "user_id": video.user.user_id if video.user else None,
            "created_at": video.created_at,
            "updated_at": video.updated_at
        }
    
    # Get all YouTube videos for a user
    @staticmethod
    @sync_to_async
    def get_youtube_videos(user_id: int):
        videos = YoutubeVideo.objects.filter(user_id=user_id).values(
            'video_id', 'title', 'duration', 'telegram_file_id', 'thumbnail_url', 'url', 'created_at', 'updated_at'
        )
        return list(videos)
    

    # Save Instagram media record
    @staticmethod
    @sync_to_async
    def save_instagram_media(media_id: str,title: str, video_url: str | None = None,
                             telegram_file_id: str | None = None, thumbnail: str | None = None,
                             duration: int | None = None, track: str | None = None,
                             artist: str | None = None, user_id: int | None = None):
        
        user = BotUser.objects.filter(user_id=user_id).first() if user_id else None

        media, created = InstagramMedia.objects.update_or_create(
            media_id=media_id,
            defaults={
                'title': title,
                'video_url': video_url,
                'telegram_file_id': telegram_file_id,
                'thumbnail': thumbnail,
                'duration': duration,
                'track': track,
                'artist': artist,
                'user': user
            }
        )
        if created:
            logging.info(f"New Instagram media saved: {title}")
        return {
            "title": media.title,
            "video_url": media.video_url,
            "telegram_file_id": media.telegram_file_id,
            "thumbnail": media.thumbnail,
            "duration": media.duration,
            "track": media.track,
            "artist": media.artist,
            "user_id": media.user.user_id if media.user else None,
            "created_at": media.created_at,
            "updated_at": media.updated_at
        }
    
    # Get Instagram media by url
    @staticmethod
    @sync_to_async
    def get_instagram_media(video_url: str):
        try:
            media = InstagramMedia.objects.get(video_url=video_url)
            return {
                "media_id": media.media_id,
                "title": media.title,
                "video_url": media.video_url,
                "telegram_file_id": media.telegram_file_id,
                "thumbnail": media.thumbnail,
                "duration": media.duration,
                "track": media.track,
                "artist": media.artist,
                "user": {
                    "user_id": media.user.user_id if media.user else None,
                    "first_name": media.user.first_name if media.user else None,
                    "last_name": media.user.last_name if media.user else None,
                    "username": media.user.username if media.user else None
                } if media.user else None,
                "created_at": media.created_at,
                "updated_at": media.updated_at
            }
        except InstagramMedia.DoesNotExist:
            return None
        
    # Get all Instagram media for a user
    @staticmethod
    @sync_to_async
    def get_instagram_media_by_user(user_id: int):
        media = InstagramMedia.objects.filter(user_id=user_id).values(
            'title', 'video_url', 'telegram_file_id', 'thumbnail', 'duration', 'track', 'artist', 'created_at', 'updated_at'
        )
        return list(media)
    
    # Get Instagram media by media_id
    @staticmethod
    @sync_to_async
    def get_instagram_media_by_id(media_id: str):
        try:
            media = InstagramMedia.objects.get(media_id=media_id)
            return {
                "media_id": media.media_id,
                "title": media.title,
                "video_url": media.video_url,
                "telegram_file_id": media.telegram_file_id,
                "thumbnail": media.thumbnail,
                "duration": media.duration,
                "track": media.track,
                "artist": media.artist,
                "user": {
                    "user_id": media.user.user_id if media.user else None,
                    "first_name": media.user.first_name if media.user else None,
                    "last_name": media.user.last_name if media.user else None,
                    "username": media.user.username if media.user else None
                } if media.user else None,
                "audio": {
                    "title": media.audio.title if media.audio else None,
                    "telegram_file_id": media.audio.telegram_file_id if media.audio else None,
                } if media.audio else None,
                "created_at": media.created_at,
                "updated_at": media.updated_at
            }
        except InstagramMedia.DoesNotExist:
            return None
        
    # Add audio to Instagram media
    @staticmethod
    @sync_to_async
    def add_audio_to_instagram_media(media_id: str, audio_id: str):
        try:
            media = InstagramMedia.objects.get(media_id=media_id)
            audio = YoutubeAudio.objects.get(video_id=audio_id)
            media.audio = audio
            media.save()
            logging.info(f"Added audio {audio.title} to Instagram media {media.title}")
            return {
                "media_id": media.media_id,
                "audio_id": audio.video_id,
                "media_title": media.title,
                "audio_title": audio.title
            }
        except (InstagramMedia.DoesNotExist, YoutubeAudio.DoesNotExist) as e:
            logging.error(f"[Add Audio Error] {e}")
            return None

    # Save TikTok media record
    @staticmethod
    @sync_to_async
    def save_tiktok_media(media_id: str, title: str, video_url: str | None = None,
                          telegram_file_id: str | None = None, thumbnail: str | None = None,
                          duration: int | None = None, track: str | None = None,
                          artist: str | None = None, user_id: int | None = None):
        
        user = BotUser.objects.filter(user_id=user_id).first() if user_id else None

        media, created = TikTokMedia.objects.update_or_create(
            media_id=media_id,
            defaults={
                'title': title,
                'video_url': video_url,
                'telegram_file_id': telegram_file_id,
                'thumbnail': thumbnail,
                'duration': duration,
                'track': track,
                'artist': artist,
                'user': user
            }
        )
        if created:
            logging.info(f"New TikTok media saved: {title}")
        return {
            "media_id": media.media_id,
            "title": media.title,
            "video_url": media.video_url,
            "telegram_file_id": media.telegram_file_id,
            "thumbnail": media.thumbnail,
            "duration": media.duration,
            "track": media.track,
            "artist": media.artist,
            "user": {
                "user_id": media.user.user_id if media.user else None,
                "first_name": media.user.first_name if media.user else None,
                "last_name": media.user.last_name if media.user else None,
                "username": media.user.username if media.user else None
            } if media.user else None,
            "audio": {
                "title": media.audio.title if media.audio else None,
                "telegram_file_id": media.audio.telegram_file_id if media.audio else None,
            } if media.audio else None,
            "created_at": media.created_at,
            "updated_at": media.updated_at
        }

    # Get TikTok media by url
    @staticmethod
    @sync_to_async
    def get_tiktok_media(video_url: str):
        try:
            media = TikTokMedia.objects.get(video_url=video_url)
            return {
                "media_id": media.media_id,
                "title": media.title,
                "video_url": media.video_url,
                "telegram_file_id": media.telegram_file_id,
                "thumbnail": media.thumbnail,
                "duration": media.duration,
                "track": media.track,
                "artist": media.artist,
                "user": {
                    "user_id": media.user.user_id if media.user else None,
                    "first_name": media.user.first_name if media.user else None,
                    "last_name": media.user.last_name if media.user else None,
                    "username": media.user.username if media.user else None
                } if media.user else None,
                "audio": {
                    "title": media.audio.title if media.audio else None,
                    "telegram_file_id": media.audio.telegram_file_id if media.audio else None,
                } if media.audio else None,
                "created_at": media.created_at,
                "updated_at": media.updated_at
            }
        except TikTokMedia.DoesNotExist:
            return None
        
    # Get TikTok media by media_id
    @staticmethod
    @sync_to_async
    def get_tiktok_media_by_id(media_id: str):
        try:
            media = TikTokMedia.objects.get(media_id=media_id)
            return {
                "media_id": media.media_id,
                "title": media.title,
                "video_url": media.video_url,
                "telegram_file_id": media.telegram_file_id,
                "thumbnail": media.thumbnail,
                "duration": media.duration,
                "track": media.track,
                "artist": media.artist,
                "user": {
                    "user_id": media.user.user_id if media.user else None,
                    "first_name": media.user.first_name if media.user else None,
                    "last_name": media.user.last_name if media.user else None,
                    "username": media.user.username if media.user else None
                } if media.user else None,
                "audio": {
                    "title": media.audio.title if media.audio else None,
                    "telegram_file_id": media.audio.telegram_file_id if media.audio else None,
                } if media.audio else None,
                "created_at": media.created_at,
                "updated_at": media.updated_at
            }
        except TikTokMedia.DoesNotExist:
            return None
        
    # Add audio to TikTok media
    @staticmethod
    @sync_to_async
    def add_audio_to_tiktok_media(media_id: str, audio_id: str):
        try:
            media = TikTokMedia.objects.get(media_id=media_id)
            media.audio = YoutubeAudio.objects.get(video_id=audio_id)
            media.save()
            return True
        except (TikTokMedia.DoesNotExist, YoutubeAudio.DoesNotExist):
            return False