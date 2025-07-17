from aiogram import types

from bot.loader import dp


# Unknown commands
@dp.message_handler(state=None)
async def bot_echo(message: types.Message):
    await message.reply(
        "Siz mavjud bo'lmagan buyruq yubordingiz. \n"
        "Botni qayta ishga tushurish uchun /start buyrug'ini yuboring.\n"
        "/help - Yordam olish uchun buyrug'ini yuboring.\n"
    )
    