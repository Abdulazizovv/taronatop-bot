from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.loader import dp, db, bot
from bot.utils.instagram import (
    download_instagram_media,
    convert_instagram_video_to_audio,
    find_music_name,
    download_youtube_audio_by_title
)
from bot.keyboards.inline.instagram import instagram_keyboard, instagram_callback
from bot.data.config import PRIVATE_CHANNEL_ID
import logging
import os


@dp.message_handler(lambda message: message.text.startswith("https://www.instagram.com/"), state="*")
async def handle_instagram_link(message: types.Message, state: FSMContext):
    search_query = message.text.strip()
    try:
        search_msg = await message.reply("⏳")

        # Check if media info already exists in DB
        media_info = await db.get_instagram_media(search_query)
        if media_info and media_info.get("telegram_file_id"):
            await message.answer_video(
                video=media_info["telegram_file_id"],
                caption=f"🎥 <b>Instagram Media:</b>\n\n{media_info['title']}\n",
                parse_mode="HTML",
                reply_markup=instagram_keyboard(media_id=media_info["media_id"])
            )
            return

        # Otherwise, download it
        await bot.send_chat_action(message.chat.id, types.ChatActions.UPLOAD_VIDEO)
        result = await download_instagram_media(search_query)

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
            caption=f"🎥 <b>Instagram Media:</b>\n\n{title}\n",
            parse_mode="HTML",
            reply_markup=instagram_keyboard(media_id=media_id)
        )

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
        if not result:
            await call.message.answer("❌ Video audiosini olishda xatolik yuz berdi.")
            return

        audio_path = result
        track_name = await find_music_name(audio_path)
        print(f"Track name found: {track_name}")
        if not track_name:
            await call.message.answer("❌ Videoda musiqa topilmadi.")
            return

        audio_download = await download_youtube_audio_by_title(track_name)
        if not audio_download:
            await call.message.answer("❌ Musiqa topilmadi yoki yuklab olishda xatolik yuz berdi.")
            return

        audio_path, file_name, audio_data = audio_download
        audio_file = types.InputFile(audio_path)

        sent_message = await bot.send_audio(
            chat_id=PRIVATE_CHANNEL_ID,
            audio=audio_file,
            title=audio_data["title"],
            caption=f"🎵 <b>Instagram Media Audio:</b> {audio_data['title']}\n",
            parse_mode="HTML"
        )

        telegram_file_id = sent_message.audio.file_id

        youtube_audio = await db.save_youtube_audio(
            video_id=audio_data["id"],
            title=audio_data["title"],
            telegram_file_id=telegram_file_id,
            user_id=call.from_user.id
        )

        await db.add_audio_to_instagram_media(
            media_id=media_id,
            audio_id=youtube_audio["video_id"]
        )

        await call.message.answer_audio(
            audio=telegram_file_id,
            title=audio_data["title"],
            caption=f"🎵 <b>Instagram Media Audio:</b> {audio_data['title']}\n",
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"[Download Instagram Media Audio Error] {e}")
        await call.message.answer("❌ Yuklab olishda xatolik yuz berdi.")
