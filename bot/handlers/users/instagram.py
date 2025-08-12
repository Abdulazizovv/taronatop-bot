from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.loader import dp, db, bot
# Primary method - working fallback
from bot.utils.instagram_fallback import (
    download_instagram_media,
    convert_instagram_video_to_audio,
    find_music_name,
    get_instagram_media_info
)
# Secondary fallback methods
from bot.utils.instagram_apify_simple import (
    download_instagram_media as download_instagram_media_apify,
    convert_instagram_video_to_audio as convert_instagram_video_to_audio_apify,
)
from bot.utils.instagram_new import (
    download_instagram_media as download_instagram_media_fallback1,
    convert_instagram_video_to_audio as convert_instagram_video_to_audio_fallback1,
)
from bot.utils.youtube_enhanced import (
    search_youtube,
    download_youtube_music
)

from bot.keyboards.inline.instagram import instagram_keyboard, instagram_callback
from bot.data.config import PRIVATE_CHANNEL_ID
import logging
import os


@dp.message_handler(lambda message: message.text.startswith("https://www.instagram.com/"), state="*")
async def handle_instagram_link(message: types.Message, state: FSMContext):
    search_query = message.text.strip()
    try:
        search_msg = await message.reply("⏳ Apify Instagram Scraper ishlatilmoqda...")

        # Check if media info already exists in DB
        media_info = await db.get_instagram_media(search_query)
        if media_info and media_info.get("telegram_file_id"):
            await message.answer_video(
                video=media_info["telegram_file_id"],
                caption=f"🎥 <b>Instagram Media:</b>\n\n{media_info['title']}\n",
                parse_mode="HTML",
                reply_markup=instagram_keyboard(media_id=media_info["media_id"])
            )
            await search_msg.delete()
            return

        # Try primary method first (working fallback)
        await bot.send_chat_action(message.chat.id, types.ChatActions.UPLOAD_VIDEO)
        result = await download_instagram_media(search_query)

        # Try Apify as secondary
        if not result:
            await search_msg.edit_text("⏳ Apify orqali urinilmoqda...")
            result = await download_instagram_media_apify(search_query)

        # Final fallback to old method
        if not result:
            await search_msg.edit_text("⏳ Oxirgi fallback usuli...")
            result = await download_instagram_media_fallback1(search_query)

        if not result:
            await search_msg.edit_text("❌ Media topilmadi yoki noto'g'ri havola.")
            return

        media_path, title, media_id = result
        media_file = types.InputFile(media_path)

        sent_message = await bot.send_video(
            chat_id=PRIVATE_CHANNEL_ID,
            video=media_file,
            caption=f"🎥 <b>Instagram Media:</b>\n\n{title}\n",
            parse_mode="HTML"
        )

        telegram_file_id = sent_message.video.file_id
        await db.save_instagram_media(
            media_id=media_id,
            title=title,
            telegram_file_id=telegram_file_id,
            video_url=search_query,
            user_id=message.from_user.id
        )

        await message.answer_video(
            video=telegram_file_id,
            caption=f"🎥 <b>Instagram Media:</b>\n\n{title}\n✅ Muvaffaqiyatli yuklab olindi",
            parse_mode="HTML",
            reply_markup=instagram_keyboard(media_id=media_id)
        )

        await search_msg.delete()

    except Exception as e:
        logging.error(f"[Instagram Link Error] {e}")
        await message.answer("❌ Media bilan ishlashda xatolik yuz berdi.")


@dp.callback_query_handler(instagram_callback.filter(action="download"))
async def download_instagram_media_music(call: types.CallbackQuery, callback_data: dict):
    media_id = callback_data.get("media_id")

    await call.answer("Yuklanmoqda ...")
    await call.message.edit_reply_markup()

    if not media_id:
        await call.message.answer("❌ Media identifikatori topilmadi.")
        return

    try:
        media_info = await db.get_instagram_media_by_id(media_id)
        if not media_info:
            await call.message.answer("❌ Media topilmadi.")
            return

        if media_info.get("audio"):
            audio_file_id = media_info["audio"]["telegram_file_id"]
            await call.message.answer_audio(
                audio=audio_file_id,
                title=media_info["title"],
                caption=f"🎵 <b>Instagram Media Audio:</b> {media_info['title']}\n",
                parse_mode="HTML"
            )
            return

        result = await convert_instagram_video_to_audio(media_info["video_url"])
        
        # Try Apify as secondary
        if not result:
            result = await convert_instagram_video_to_audio_apify(media_info["video_url"])
        
        # Final fallback
        if not result:
            result = await convert_instagram_video_to_audio_fallback1(media_info["video_url"])
            
        if not result:
            await call.message.answer("❌ Video audiosini olishda xatolik yuz berdi.")
            return

        audio_path = result
        track_name = await find_music_name(audio_path)
        print(f"Track name found: {track_name}")
        if not track_name:
            await call.message.answer("❌ Videoda musiqa topilmadi.")
            return

        # Search for the track on YouTube
        search_results = await search_youtube(track_name, max_results=1)
        if not search_results:
            await call.message.answer("❌ Musiqa YouTube da topilmadi.")
            return

        # Get the first result
        video_info = search_results[0]
        youtube_url = video_info["url"]
        
        # Download audio from YouTube
        audio_download = await download_youtube_music(youtube_url)
        if not audio_download:
            await call.message.answer("❌ Musiqa yuklab olishda xatolik yuz berdi.")
            return

        audio_data, audio_file_path, filename = audio_download
        audio_file = types.InputFile(audio_data)

        sent_message = await bot.send_audio(
            chat_id=PRIVATE_CHANNEL_ID,
            audio=audio_file,
            title=video_info["title"],
            caption=f"🎵 <b>Instagram Media Audio:</b> {video_info['title']}\n",
            parse_mode="HTML"
        )

        telegram_file_id = sent_message.audio.file_id

        youtube_audio = await db.save_youtube_audio(
            video_id=video_info["video_id"],
            title=video_info["title"],
            telegram_file_id=telegram_file_id,
            user_id=call.from_user.id
        )

        await db.add_audio_to_instagram_media(
            media_id=media_id,
            audio_id=youtube_audio["video_id"]
        )

        await call.message.answer_audio(
            audio=telegram_file_id,
            title=video_info["title"],
            caption=f"🎵 <b>Instagram Media Audio:</b> {video_info['title']}\n",
            parse_mode="HTML"
        )
        
        # Clean up temporary files
        try:
            if audio_file_path and os.path.exists(audio_file_path):
                os.remove(audio_file_path)
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as cleanup_error:
            logging.warning(f"Cleanup error: {cleanup_error}")

    except Exception as e:
        logging.error(f"[Download Instagram Media Audio Error] {e}")
        await call.message.answer("❌ Yuklab olishda xatolik yuz berdi.")
