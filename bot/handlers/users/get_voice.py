from aiogram import types
from bot.loader import dp, db, bot
from shazamio import Shazam
from bot.data.config import PRIVATE_CHANNEL_ID
from bot.filters.is_private import IsPrivate
from bot.utils.audio_extractor import (
    extract_audio_for_shazam, 
    get_file_type_from_message, 
    get_file_from_message,
    get_file_extension_for_type
)
from bot.utils.song_info_formatter import format_song_info
from yt_dlp import YoutubeDL
import os
import logging

CHANNEL_ID = PRIVATE_CHANNEL_ID


def extract_video_id_from_url(url: str) -> str | None:
    """
    Get YouTube video ID from full URL
    """
    import re
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


@dp.message_handler(IsPrivate(), content_types=[types.ContentType.VOICE, types.ContentType.VIDEO, types.ContentType.AUDIO, types.ContentType.VIDEO_NOTE, types.ContentType.DOCUMENT])
async def recognize_media_message(message: types.Message):
    # Check if the message contains supported media
    file_type = get_file_type_from_message(message)
    
    await message.reply("🔍 Musiqa aniqlanmoqda, biroz kuting...")
    
    if not file_type:
        # If it's a document, check if it's audio/video
        if message.document and message.document.mime_type:
            mime = message.document.mime_type.lower()
            if not (mime.startswith('audio/') or mime.startswith('video/')):
                return  # Ignore non-media documents
        else:
            return  # Ignore if no supported media type
    
    file_obj = get_file_from_message(message)
    if not file_obj:
        await message.reply("❌ Fayl topilmadi.")
        return
    
    # Check file size (Telegram limit and reasonable processing limit)
    max_size = 50 * 1024 * 1024  # 50MB
    if hasattr(file_obj, 'file_size') and file_obj.file_size and file_obj.file_size > max_size:
        await message.reply("❌ Fayl hajmi juda katta. Maksimal 50MB fayllar qabul qilinadi.")
        return
    
    file = await bot.get_file(file_obj.file_id)
    downloaded = await bot.download_file(file.file_path)

    # Create temporary files
    file_extension = get_file_extension_for_type(file_type)
    temp_input_file = f"temp_input_{message.from_user.id}.{file_extension}"
    temp_audio_file = f"temp_audio_{message.from_user.id}.wav"
    
    try:
        # Save the downloaded file
        with open(temp_input_file, "wb") as f:
            f.write(downloaded.read())


        # Extract audio for Shazam processing
        try:
            extracted_audio_path = extract_audio_for_shazam(
                temp_input_file, 
                temp_audio_file, 
                file_type=file_type,
                duration_limit=30  # Limit to 30 seconds for better processing
            )
        except Exception as e:
            logging.error(f"Audio extraction failed: {e}")
            await message.answer("❌ Audio ajratishda xatolik yuz berdi.")
            return

        # Step 1: Recognize using Shazam
        shazam = Shazam()
        result = await shazam.recognize(extracted_audio_path)

        if not result or 'track' not in result:
            await message.answer("❌ Musiqa aniqlanmadi. Iltimos, boshqa fayl yuboring.")
            return
        

        track = result['track']
        title = track['title']
        subtitle = track['subtitle']
        query = f"{title} {subtitle}"

        # Display found song information with enhanced formatting
        song_info = format_song_info(track)
        await message.answer(song_info, parse_mode="HTML")

        # Step 2: YouTube search & video_id
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": "in_playlist",
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            entry = info['entries'][0]
            video_url = entry['url'] if 'url' in entry else entry['webpage_url']
            video_id = extract_video_id_from_url(video_url)
            if not video_id:
                raise Exception("Video ID aniqlanmadi")

        # Step 3: Check if already in DB
        audio = await db.get_youtube_audio(video_id)
        if audio and audio['telegram_file_id']:
            await message.answer_audio(audio['telegram_file_id'], title=title, performer=subtitle, caption="🎵 Musiqa @taronatop_robot shazam funksiyasi orqali topildi.")
            return

        # Step 4: Download audio
        logging.info(f"Downloading audio for video ID: {video_id}")

        await message.answer("🔄 Musiqa yuklanmoqda, biroz kuting...")

        audio_file_path = f"{message.from_user.id}_audio.%(ext)s"
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_file_path,
            "noplaylist": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            real_path = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")

        # Step 5: Upload to channel
        with open(real_path, "rb") as audio_file:
            sent = await bot.send_audio(
                chat_id=CHANNEL_ID,
                audio=audio_file,
                title=title,
                performer=subtitle,
                caption=f"🎵 <b>{title}</b> - <i>{subtitle}</i>\n@taronatop_robot",
                parse_mode="HTML"
            )
            telegram_file_id = sent.audio.file_id

        # Step 6: Save to DB
        await db.save_youtube_audio(
            video_id=video_id,
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            # thumbnail_url=info.get("thumbnail"),
            telegram_file_id=telegram_file_id,
            user_id=message.from_user.id,
        )

        # Step 7: Send to user
        await message.answer_audio(telegram_file_id, title=title, performer=subtitle, caption="🎵 Musiqa @taronatop_robot shazam funksiyasi orqali topildi.")

    except Exception as e:
        logging.exception(e)
        await message.answer("❌ Afsuski, musiqa aniqlanmadi yoki yuklab bo'lmadi.")

    finally:
        # Clean up temporary files
        for temp_file in [temp_input_file, temp_audio_file]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        # Clean up any downloaded audio files
        for ext in ["mp3", "m4a", "webm"]:
            temp_audio = f"{message.from_user.id}_audio.{ext}"
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
