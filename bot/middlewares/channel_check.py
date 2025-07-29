from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.handler import CancelHandler
from aiogram.utils.exceptions import ChatNotFound

from bot.loader import db
from bot.utils import users_not_joined_channels
from bot.keyboards.inline.required_chats import chats_kb


class ChannelCheckMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: Message, data: dict):

        # Check if user is blocked
        if await db.is_user_blocked(message.from_user.id):
            await message.answer("❗ Siz bloklangansiz!\nIltimos, admin bilan bog'laning.")
            raise CancelHandler()

        # only working on private chats
        if not message.chat.type == "private":
            return
        
        # only working with messages from users
        if not message.from_user:
            return
        
        # ignore bot messages
        if message.from_user.is_bot:
            return
        
        # ignore messages from admins
        if message.from_user.id in await db.get_admins():
            return

        # user's not joined channels
        not_joined_channels = await users_not_joined_channels(
            user_id=message.from_user.id,
            required_chats=await db.get_required_chats()
        )
        if not_joined_channels:
            keyboard = chats_kb(not_joined_channels)


            await message.answer(
                "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
                reply_markup=keyboard
            )
            raise CancelHandler()
