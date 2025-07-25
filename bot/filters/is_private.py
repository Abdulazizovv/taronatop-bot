from aiogram import types
from aiogram.dispatcher.filters import BoundFilter
from bot.data import config


class IsPrivate(BoundFilter):
    async def check(self, message: types.Message):
        if message.chat.type == 'private':
            return True
        return False
