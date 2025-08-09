from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.filters.is_private import IsPrivate
from typing import List, Dict
from bot.loader import dp, db
from aiogram.dispatcher.filters import Command
from bot.utils.youtube import get_trending_music
import logging
from bot.keyboards.inline.music import create_music_keyboard

# Constants
ITEMS_PER_PAGE = 10
MAX_TRENDING_RESULTS = 200

def format_trending_page(results: List[Dict], page: int = 1, items_per_page: int = ITEMS_PER_PAGE) -> str:
    """
    Format trending music results into a paginated text message.
    
    Args:
        results: List of video dictionaries
        page: Current page number
        items_per_page: Number of items per page
        
    Returns:
        Formatted message text
    """
    if not results:
        return "🔥 Hozircha trend musiqalar topilmadi."

    total_results = len(results)
    total_pages = max(1, (total_results - 1) // items_per_page + 1)
    page = max(1, min(page, total_pages))

    start = (page - 1) * items_per_page
    end = start + items_per_page
    sliced = results[start:end]

    text = [
        "🔥 <b>Trend musiqalar:</b>",
        ""
    ]

    for i, video in enumerate(sliced, start=start + 1):
        title = video.get("title", "Nomsiz")
        channel = video.get("channel_title", "")
        view_count = video.get("view_count", "")
        
        # Format each entry
        entry = f"{i}. {title}"
        # if channel:
        #     entry += f"\n   👤 {channel}"
        # if view_count:
        #     entry += view_count
            
        text.append(entry)

    text.append("")
    text.append(f"📄 Sahifa {page}/{total_pages} • Jami {total_results} ta musiqa")
    
    return "\n".join(text)


@dp.message_handler(Command("top"), IsPrivate(), state=None)
async def handle_user_trending(message: types.Message, state: FSMContext):
    """Handle /top command in private chats to show trending music."""
    
    try:
        search_msg = await message.reply("🔥 Trend musiqalar yuklanmoqda...")

        # Get trending music - using RU as region (UZ not supported by YouTube API)  
        trending_results = get_trending_music(max_results=MAX_TRENDING_RESULTS, region_code="RU")

        if not trending_results:
            await search_msg.edit_text("😕 Hozircha trend musiqalar topilmadi. Keyinroq urinib ko'ring.")
            return

        # Store results in state for pagination
        await state.update_data(results=trending_results)

        # Format and display first page
        text = format_trending_page(trending_results, page=1)
        keyboard = create_music_keyboard(trending_results, page=1)

        await search_msg.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        logging.info(f"User {message.from_user.id} requested trending music in private chat")

    except Exception as e:
        logging.error(f"[Trending Music Error] {e}")
        await message.reply("⚠️ Trend musiqalarni yuklashda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
