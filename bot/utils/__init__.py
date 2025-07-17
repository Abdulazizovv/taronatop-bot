from . import db_api
from . import misc
from .notify_admins import on_startup_notify

import logging




async def users_not_joined_channels(user_id: int, required_chats: list):
    """
    Check if the user is subscribed to all required channels.
    
    :param user_id: ID of the user to check.
    :param required_chats: List of required chat IDs.
    :return: True if the user is subscribed to all channels, False otherwise.
    """
    from bot.loader import bot
    
    if not required_chats:
        logging.info("No required chats provided.")
        return []


    not_joined_channels = []
    for chat in required_chats:
        try:
            chat_id = chat['chat_id']
            if not chat_id:
                logging.info("Chat ID is empty, skipping.")
                continue
            member = await bot.get_chat_member(chat_id, user_id)
            logging.info(f"Chat ID: {chat_id}, Member Status: {member.status}")
            if member.status not in ['member', 'administrator', 'owner', 'creator']:
                not_joined_channels.append(chat)
        except Exception as err:
            logging.error(f"Error checking chat_id {chat_id} for user {user_id}: {err}")
    if not not_joined_channels:
        return []
    
    return not_joined_channels
    