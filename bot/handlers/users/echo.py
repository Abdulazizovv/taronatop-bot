from aiogram import types
import logging
from bot.loader import dp, db ,bot
from bot.utils.youtube import YouTubeSearch, download_music
from bot.keyboards.inline.music import create_music_keyboard, music_callback, pagination_callback
from aiogram.dispatcher import FSMContext
from typing import List, Dict
import os
from bot.data.config import PRIVATE_CHANNEL_ID

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



# getting search term or link
@dp.message_handler(state=None)
async def handle_search(message: types.Message, state: FSMContext):
    """
    Handle user search queries.
    """
    search_query = message.text.strip()
    
    if not search_query:
        await message.answer("Iltimos, qidirish uchun so'rov yuboring.")
        return
        
    if search_query.startswith(("http://", "https://")):
        await message.answer("ℹ️ Siz YouTube havolasini yubordingiz. Bu funksiya keyinchalik qo'shiladi.")
        return

    logging.info(f"User {message.from_user.id} searching for: {search_query}")

    try:
        # Show searching status
        search_msg = await message.answer("🔍 Qidirilmoqda...")
        
        # Perform search
        youtube = YouTubeSearch(search_query, max_results=MAX_SEARCH_RESULTS)
        results = youtube.to_dict()
        
        if not results:
            await search_msg.edit_text("😕 Hech qanday natija topilmadi.")
            return

        # Save results to state
        await state.update_data(results=results)
        
        # Show first page of results
        text = format_results_page(results, page=1)
        keyboard = create_music_keyboard(results, page=1)
        
        await search_msg.edit_text(
            text, 
            reply_markup=keyboard, 
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        await message.answer("⚠️ Qidiruvda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

@dp.callback_query_handler(lambda c: c.data == "noop")
async def handle_noop(call: types.CallbackQuery):
    """
    Handle no-operation callback (for disabled buttons).
    """
    await call.answer(cache_time=60)

@dp.callback_query_handler(lambda c: c.data == "delete")
async def handle_delete(call: types.CallbackQuery):
    """
    Handle message deletion request.
    """
    try:
        await call.answer("Yopilmoqda...")
        await call.message.delete()
    except Exception as e:
        logging.error(f"Failed to delete message: {e}")
        await call.answer("❌ Xabarni o'chirib bo'lmadi.")

@dp.callback_query_handler(music_callback.filter(action="select"))
async def handle_music_selection(call: types.CallbackQuery, callback_data: Dict[str, str], state: FSMContext):
    await call.answer(cache_time=1)

    video_id = callback_data.get("video_id")
    if not video_id:
        await call.message.answer("⚠️ Siz tanlagan audio topilmadi.")
        return

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        # 1. Holatdagi natijalarni olish
        data = await state.get_data()
        results = data.get("results", [])
        selected_video = next((v for v in results if v.get("video_id") == video_id), None)

        if not selected_video:
            await call.message.answer("⚠️ Tanlangan video topilmadi.")
            return

        title = selected_video.get("title", "No Title")

        # 2. Keshdan tekshirish
        audio_info = await db.get_youtube_audio(video_id)
        if audio_info and audio_info.get("telegram_file_id"):
            
            await call.message.answer_audio(
                audio=audio_info["telegram_file_id"],
                title=title,
                caption=f"🎵 <b>TaronaTop</b> — tingla, yuklab ol, zavqlan!\n@taronatop_robot",
                parse_mode="HTML"
            )
            return

        # 3. Yuklab olishni boshlash
        await bot.send_chat_action(call.message.chat.id, types.ChatActions.UPLOAD_AUDIO)
        downloading_msg = await call.message.answer("⏳ Yuklab olinmoqda, kuting...")

        audio_data, filepath, clean_title = await download_music(url)
        if not audio_data:
            await downloading_msg.edit_text("❌ Audio yuklab olishda xatolik yuz berdi.")
            return

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if file_size_mb > 49:
            await downloading_msg.edit_text("❌ Fayl hajmi juda katta. Uni yuborib bo‘lmadi.")
            return

        # 4. Telegram kanalga yuborish
        msg = await call.bot.send_audio(
            chat_id=PRIVATE_CHANNEL_ID,
            audio=audio_data,
            title=clean_title,
            caption=clean_title
        )
        telegram_file_id = msg.audio.file_id

        # 5. Bazaga saqlash
        await db.save_youtube_audio(
            video_id=video_id,
            title=clean_title,
            telegram_file_id=telegram_file_id,
            url=url,
            user_id=call.from_user.id
        )

        # 6. Foydalanuvchiga yuborish
        await downloading_msg.edit_text("✅ Yuklab olindi! Endi sizga yuborilmoqda...")
        await call.message.answer_audio(
            audio=telegram_file_id,
            title=clean_title,
            caption=f"🎵 <b>TaronaTop</b> — tingla, yuklab ol, zavqlan!\n@taronatop_robot",
            parse_mode="HTML"
        )

    except Exception as e:
        logging.exception("❌ Music selection error")
        await call.message.answer("⚠️ Video tanlashda xatolik yuz berdi.")


@dp.callback_query_handler(pagination_callback.filter(action=["next", "previous"]))
async def handle_pagination(
    call: types.CallbackQuery, 
    callback_data: Dict[str, str], 
    state: FSMContext
):
    """
    Handle pagination for search results.
    """
    action = callback_data.get("action")
    requested_page = int(callback_data.get("page", 1))

    try:
        data = await state.get_data()
        results = data.get("results", [])
        
        if not results:
            await call.answer("Natijalar topilmadi.")
            return

        total_pages = max(1, (len(results) - 1) // ITEMS_PER_PAGE + 1)
        new_page = max(1, min(requested_page, total_pages))

        text = format_results_page(results, page=new_page)
        keyboard = create_music_keyboard(results, page=new_page)
        
        await call.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await call.answer()
        
    except Exception as e:
        logging.error(f"Pagination error: {str(e)}")
        await call.answer("⚠️ Sahifalashda xatolik yuz berdi.")