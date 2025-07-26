from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.filters.is_group import IsGroup
from typing import List, Dict
from bot.keyboards.inline.select_format import create_format_selection_keyboard as create_format_keyboard
from bot.loader import dp, db
from aiogram.dispatcher.filters import Command
from bot.utils.youtube import get_video_info, YouTubeSearch
import logging
from bot.keyboards.inline.music import create_music_keyboard

# Constants
ITEMS_PER_PAGE = 10
MAX_SEARCH_RESULTS = 50

def format_results_page(results: List[Dict], page: int = 1, items_per_page: int = ITEMS_PER_PAGE) -> str:
    """
    Format search results into a paginated text message.
    
    Args:
        results: List of video dictionaries
        page: Current page number
        items_per_page: Number of items per page
        
    Returns:
        Formatted message text
    """
    if not results:
        return "🔍 Hech qanday natija topilmadi."

    total_results = len(results)
    total_pages = max(1, (total_results - 1) // items_per_page + 1)
    page = max(1, min(page, total_pages))

    start = (page - 1) * items_per_page
    end = start + items_per_page
    sliced = results[start:end]

    text = [
        "🔎 <b>Qidiruv natijalari:</b>",
        ""
    ]

    for i, video in enumerate(sliced, start=start + 1):
        # duration = video.get("duration_formatted", "Noma'lum")
        title = video.get("title", "Nomsiz")
        text.append(f"{i}. {title}")

    return "\n".join(text)

@dp.message_handler(Command("search"), IsGroup(), state=None)  # <-- bound filter
async def handle_group_search(message: types.Message, state: FSMContext):
    args = message.get_args()
    search_query = args.strip()

    if not search_query:
        await message.reply("❗ Iltimos, /search buyrug‘i bilan birga qidiruv so‘zini ham yuboring.\nMasalan: <code>/search ummon dengiz</code>", parse_mode="HTML")
        return

    if len(search_query) < 4:
        await message.reply("❗ Qidirish uchun so'rov kamida 4 ta belgidan iborat bo'lishi kerak.")
        return

    is_youtube_url = any(x in search_query for x in ["youtube.com/watch?v=", "youtu.be/", "youtube.com/shorts/"])

    if is_youtube_url:
        try:
            search_msg = await message.reply("🔍 Video tekshirilmoqda...")

            video_info = get_video_info(search_query)
            if not video_info:
                await search_msg.edit_text("❌ Video topilmadi yoki noto'g'ri havola.")
                return

            await message.answer_photo(
                photo=video_info["thumbnail_url"],
                caption=f"🎥 <b>Video topildi:</b>\n\n{video_info['title']}\n\nYuklab olish formatini tanlang👇",
                parse_mode="HTML",
                reply_markup=create_format_keyboard(video_id=video_info["video_id"])
            )
        except Exception as e:
            logging.error(f"[YouTube Link Error] {e}")
            await message.reply("❌ Video bilan ishlashda xatolik yuz berdi.")
        return

    try:
        search_msg = await message.reply("🔍 Qidirilmoqda...")

        youtube = YouTubeSearch(search_query, max_results=MAX_SEARCH_RESULTS)
        results = youtube.to_dict()

        if not results:
            await search_msg.edit_text("😕 Hech qanday natija topilmadi.")
            return

        await state.update_data(results=results)

        text = format_results_page(results, page=1)
        keyboard = create_music_keyboard(results, page=1)

        await search_msg.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"[Search Error] {e}")
        await message.reply("⚠️ Qidiruvda xatolik yuz berdi. Iltimos, keyinroq urinib ko‘ring.")