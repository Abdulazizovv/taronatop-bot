from aiogram import types
from bot.loader import dp, db, bot
from shazamio import Shazam
from bot.data.config import PRIVATE_CHANNEL_ID
from bot.filters.is_group import IsGroup
from bot.utils.audio_extractor import (
    extract_audio_for_shazam, 
    get_file_type_from_message, 
    get_file_from_message,
    get_file_extension_for_type
)
from yt_dlp import YoutubeDL
import os
import logging
import re

CHANNEL_ID = PRIVATE_CHANNEL_ID


def extract_video_id_from_url(url: str) -> str | None:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


@dp.message_handler(IsGroup(), commands=["find"])
async def find_music_from_media_reply(message: types.Message):
    # Check if replying to a message with supported media
    if not message.reply_to_message:
        await message.reply("❗ Iltimos, ovozli xabar, video yoki audio faylga javoban /find buyrug'ini yozing.")
        return
    
    reply_msg = message.reply_to_message
    file_type = get_file_type_from_message(reply_msg)
    
    if not file_type:
        await message.reply("❗ Iltimos, ovozli xabar, video yoki audio faylga javoban /find buyrug'ini yozing.")
        return
    
    file_obj = get_file_from_message(reply_msg)
    if not file_obj:
        await message.reply("❌ Fayl topilmadi.")
        return
    
    # Check file size (Telegram limit and reasonable processing limit)
    max_size = 50 * 1024 * 1024  # 50MB
    if hasattr(file_obj, 'file_size') and file_obj.file_size and file_obj.file_size > max_size:
        await message.reply("❌ Fayl hajmi juda katta. Maksimal 50MB fayllar qabul qilinadi.")
        return

    await message.reply("🔍 Musiqa aniqlanmoqda...")
    
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
            await message.reply("❌ Audio ajratishda xatolik yuz berdi.")
            return

        shazam = Shazam()
        result = await shazam.recognize(extracted_audio_path)

        if not result or 'track' not in result:
            await message.reply("❌ Musiqa aniqlanmadi. Iltimos, boshqa fayl yuboring.")
            return

        track = result['track']
        title = track['title']
        subtitle = track['subtitle']
        query = f"{title} {subtitle}"

        # YouTube'dan qidirish
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

        # Avvaldan mavjudmi tekshirish
        audio = await db.get_youtube_audio(video_id)
        if audio and audio['telegram_file_id']:
            await message.reply_audio(
                audio=audio['telegram_file_id'],
                title=title,
                performer=subtitle,
                caption="🎵 Musiqa @taronatop_robot tomonidan topildi."
            )
            return

        await message.reply("🔄 Musiqa yuklanmoqda...")

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

        # Kanaldan joylash
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

        # Saqlash
        await db.save_youtube_audio(
            video_id=video_id,
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            telegram_file_id=telegram_file_id,
            user_id=message.from_user.id,
        )

        await message.reply_audio(
            audio=telegram_file_id,
            title=title,
            performer=subtitle,
            caption="🎵 Musiqa @taronatop_robot tomonidan topildi."
        )

    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Musiqa aniqlanmadi yoki yuklab olishda xatolik yuz berdi.")
    finally:
        # Clean up temporary files
        for temp_file in [temp_input_file, temp_audio_file]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        # Clean up any downloaded audio files
        for ext in ["mp3", "m4a", "webm"]:
            path = f"{message.from_user.id}_audio.{ext}"
            if os.path.exists(path):
                os.remove(path)
