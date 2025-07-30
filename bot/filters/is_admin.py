from aiogram import types
from aiogram.dispatcher.filters import BoundFilter
from bot.data import config
from bot.loader import db


class IsAdmin(BoundFilter):
    async def check(self, message: types.Message):
        return await db.is_user_admin(user_id=message.from_user.id) or message.from_user.id in config.ADMINS