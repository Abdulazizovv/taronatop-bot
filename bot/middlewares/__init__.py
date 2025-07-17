from aiogram import Dispatcher

from bot.loader import dp
from .throttling import ThrottlingMiddleware
from .channel_check import ChannelCheckMiddleware



def setup(dp: Dispatcher):
    dp.middleware.setup(ThrottlingMiddleware())
    dp.middleware.setup(ChannelCheckMiddleware())

if __name__ == "middlewares":
    dp.middleware.setup(ThrottlingMiddleware())
    dp.middleware.setup(ChannelCheckMiddleware())
