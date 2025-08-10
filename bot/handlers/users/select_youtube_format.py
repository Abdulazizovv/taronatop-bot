from aiogram import types
import logging
from aiogram.dispatcher import FSMContext
from typing import Dict

from bot.loader import dp, db, bot
from bot.utils.youtube_enhanced import (
    get_youtube_video_info,
    download_youtube_music,
    download_youtube_video,
    safely_remove_file
)
from bot.keyboards.inline.select_format import format_callback
from bot.data.config import PRIVATE_CHANNEL_ID


@dp.callback_query_handler(format_callback.filter())
async def handle_format_selection(callback_query: types.CallbackQuery, callback_data: Dict[str, str], state: FSMContext):
    video_id = callback_data.get("video_id")
    format_type = callback_data.get("format_type")

    if not video_id or not format_type:
        await callback_query.answer("❌ Noto'g'ri format tanlandi.", show_alert=True)
        return

    try:
        await callback_query.answer("⏳ Yuklanmoqda, iltimos kuting...")
        await callback_query.message.delete()
        await callback_query.message.answer(
            "⏳",
            reply_markup=None
        )
        # Fetch video info
        video_url = f"https://youtube.com/watch?v={video_id}"
        video_info = await get_youtube_video_info(video_url)

        if not video_info:
            await callback_query.answer("❌ Video topilmadi yoki noto'g'ri URL.", show_alert=True)
            return

        title = video_info.get("title", "Nomsiz video")
        clean_title = title.strip()



        if format_type == "audio":
            # 1. Check DB cache
            existing = await db.get_youtube_audio(video_id)
            if existing:
                await callback_query.message.answer_audio(
                    audio=existing['telegram_file_id'],
                    caption=existing['title']
                )

                return

            # 2. Download
            result = await download_youtube_music(video_url)
            if not result:
                await callback_query.message.answer("❌ Audio yuklab olishda xatolik yuz berdi.")
                return
            
            audio_data, filepath, filename = result

            # 3. Upload to Telegram
            msg = await bot.send_audio(
                chat_id=PRIVATE_CHANNEL_ID,
                audio=audio_data,
                caption=clean_title,
                title=clean_title
            )

            # 4. Save to DB
            await db.save_youtube_audio(
                video_id=video_id,
                title=clean_title,
                telegram_file_id=msg.audio.file_id,
                url=video_url,
                thumbnail_url=video_info.get('thumbnail_url'),
                user_id=callback_query.from_user.id
            )

            # 5. Respond to user
            await callback_query.message.answer_audio(
                audio=msg.audio.file_id,
                caption=clean_title
            )

        elif format_type == "video":
            # 1. Check DB cache
            existing = await db.get_youtube_video(video_id)
            
            if existing:
                await callback_query.message.answer_video(
                    video=existing['telegram_file_id'],
                    caption=existing['title']
                )
                return

            # 2. Download
            result = await download_youtube_video(video_url)
            if not result:
                await callback_query.message.answer("Videoni yuklab olib bo'lmadi!")
                return
            
            video_data, filepath, filename = result

            # 3. Upload to Telegram
            msg = await bot.send_video(
                chat_id=PRIVATE_CHANNEL_ID,
                video=video_data,
                caption=clean_title,
                supports_streaming=True
            )

            # 4. Save to DB
            await db.save_youtube_video(
                video_id=video_id,
                title=clean_title,
                telegram_file_id=msg.video.file_id,
                url=video_url,
                user_id=callback_query.from_user.id
            )

            # 5. Respond to user
            await callback_query.message.answer_video(
                video=msg.video.file_id,
                caption=clean_title
            )

        else:
            await callback_query.answer("❌ Noto'g'ri format tanlandi.", show_alert=True)
            return

    except Exception as e:
        logging.exception(f"Error in format selection: {e}")
        await callback_query.answer("❌ Yuklashda xatolik yuz berdi.", show_alert=True)

    finally:
        # Always try to delete temp file if exists
        try:
            if 'filepath' in locals():
                await safely_remove_file(filepath)
        except Exception as e:
            logging.warning(f"Temp faylni o‘chirishda xatolik: {e}")


@dp.callback_query_handler(text="cancel")
async def cancel_format_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    try:
        await callback_query.message.delete()
    except Exception as err:
        logging.error(f"Error deleting message: {err}")

    await callback_query.message.answer(
        "Tanlov bekor qilindi.",
        reply_markup=None
    )
