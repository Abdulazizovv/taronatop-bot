from asgiref.sync import sync_to_async
from botapp.models import BotUser, BotChat
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
    
    