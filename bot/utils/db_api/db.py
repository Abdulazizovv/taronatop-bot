from asgiref.sync import sync_to_async
from botapp.models import BotUser, BotChat



# Database API for Bot User Management
class DB:
    
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
    def add_chat(chat_id: int, chat_type: str, title: str | None = None, username: str | None = None, is_admin: bool = False):
        
        # first getting chat if exists else create
        chat = BotChat.objects.filter(chat_id=chat_id).first()
        if not chat:
            chat = BotChat.objects.create(
                chat_id=chat_id,
                chat_type=chat_type,
                title=title,
                username=username,
                is_admin=is_admin
            )
        else:
            # Update existing chat details
            chat.chat_type = chat_type
            chat.title = title
            chat.username = username
            chat.is_admin = is_admin
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
            return True
        except BotChat.DoesNotExist:
            print("error")
            return False
        
    