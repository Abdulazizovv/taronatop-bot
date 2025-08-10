from aiogram import types
from bot.loader import dp
from bot.filters.is_group import IsGroup
from bot.utils.youtube_enhanced import get_youtube_video_info
from bot.keyboards.inline.select_format import create_format_selection_keyboard as create_format_keyboard
import logging

@dp.message_handler(IsGroup(), state="*")
async def handle_youtube_in_group(message: types.Message):
    text = message.text or ""

    # YouTube link bormi?
    is_youtube_url = any(x in text for x in ["youtube.com/watch?v=", "youtu.be/", "youtube.com/shorts/"])

    if not is_youtube_url:
        return  # boshqa xabarlar e'tibordan chetda qoladi

    try:
        search_msg = await message.reply("🔍 Video tekshirilmoqda...")

        video_info = await get_youtube_video_info(text)

        if not video_info:
            await search_msg.edit_text("❌ Video topilmadi yoki noto'g'ri havola.")
            return

        await message.reply_photo(
            photo=video_info["thumbnail_url"],
            caption=f"🎥 <b>Video topildi:</b>\n\n{video_info['title']}\n\nYuklab olish formatini tanlang👇",
            parse_mode="HTML",
            reply_markup=create_format_keyboard(video_id=video_info["video_id"])
        )

        await search_msg.delete()

    except Exception as e:
        logging.error(f"[Group YouTube Link Error] {e}")
        await message.reply("❌ Video bilan ishlashda xatolik yuz berdi.")
