from aiogram import types
from aiogram.dispatcher.filters import CommandHelp
from bot.loader import dp

@dp.message_handler(CommandHelp(), chat_type=types.ChatType.PRIVATE)
async def help_private(message: types.Message):
    await message.answer(
        "🎵 *TaronaTop* botiga xush kelibsiz!\n\n"
        "Ushbu bot yordamida siz quyidagi imkoniyatlardan foydalanishingiz mumkin:\n\n"
        "📥 YouTube'dan musiqa va videolarni yuklab olish\n"
        "🎶 Video ichida ishlatilgan musiqa (soundtrack) ni aniqlab, to‘liq variantini yuklab olish\n"
        "📹 TikTok va Instagram’dan videolarni yuklab olish (suv belgisiz)\n"
        "🔍 Qo‘shiq nomi orqali yoki ovozli xabar orqali qidiruv\n"
        "💬 Guruhlarda ham samarali ishlaydi!\n\n"
        "Boshlash uchun shunchaki havola (link), qo‘shiq nomi yoki ovozli xabar yuboring!",
        parse_mode='Markdown'
    )
