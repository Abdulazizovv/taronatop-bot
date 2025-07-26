from aiogram import types
from aiogram.dispatcher.filters import CommandHelp
from bot.loader import dp
from bot.filters.is_group import IsGroup

@dp.message_handler(IsGroup(), CommandHelp(), state="*")
async def help_group(message: types.Message):
    await message.reply(
        "🎧 <b>TaronaTop</b> bot guruhda faollashtirildi!\n\n"
        "U orqali siz quyidagilarni qilishingiz mumkin:\n"
        "🔗 YouTube, TikTok va Instagram havolalari orqali musiqa va videolarni yuklash\n"
        "🎼 Video ostidagi musiqa nomini aniqlash va to‘liq versiyasini olish\n"
        "🗣 Ovozli xabar orqali musiqa topish(Shazam funksiyasi)\n"
        "🔍 Qo‘shiq nomini yozib qidirish\n\n"
        "📌 Barcha foydalanuvchilar uchun qulay va tezkor!\n\n"
        "Foydalanish bo'yicha yo'riqnoma: \n"
        "- Qidirish funksiyasi:\n"
        "/search <i>matn</i>\n"
        "masalan <code> /search ummon dengiz</code>\n"
        "- Shazam funksiyasi:\n"
        "shunchaki ovozli xabarga javob qilib /find buyru'gini yuboring\n",
        parse_mode='HTML'
    )