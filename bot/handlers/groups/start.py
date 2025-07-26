from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.loader import dp, db, bot
from bot.filters.is_group import IsGroup
from aiogram.dispatcher.filters.builtin import CommandStart


@dp.message_handler(IsGroup(), CommandStart())
async def group_start(message: types.Message, state: FSMContext):
    # Foydalanuvchi ismi va chatni olish
    user_full_name = message.from_user.full_name
    group_title = message.chat.title

    # Guruhdagi start komandasi uchun xush kelibsiz xabari
    await message.reply(
        f"👋 Salom, {user_full_name}!\n"
        f"Siz *{group_title}* guruhida `TaronaTop` botni ishga tushirdingiz.\n\n"
        f"🎶 Endi siz guruh ichida quyidagi imkoniyatlardan foydalanishingiz mumkin:\n"
        f"— YouTube, Instagram va TikTok musiqalarini yuklab olish\n"
        f"— Qo‘shiq nomi yoki ovozli xabar orqali qidiruv\n"
        f"— Musiqalarni guruhga yuborish va ulashish\n\n"
        f"Botdan foydalanish yo'riqnomasi - /help\n"
        f"Botdan foydalanishni boshlash uchun shunchaki qo‘shiq nomini yozing yoki link yuboring!",
        parse_mode="Markdown"
    )
