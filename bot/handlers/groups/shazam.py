from aiogram import types
from bot.loader import dp, db, bot
from shazamio import Shazam
from bot.data.config import PRIVATE_CHANNEL_ID
from bot.filters.is_group import IsGroup
from yt_dlp import YoutubeDL
import os
import logging
import re

CHANNEL_ID = PRIVATE_CHANNEL_ID


def extract_video_id_from_url(url: str) -> str | None:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


@dp.message_handler(IsGroup(), commands=["find"])
async def find_music_from_voice_reply(message: types.Message):
    # Faqat ovozli xabarga javoban ishlasin
    if not message.reply_to_message or not message.reply_to_message.voice:
        await message.reply("❗ Iltimos, ovozli xabarga javoban /find buyrug'ini yozing.")
        return

    voice = message.reply_to_message.voice
    file = await bot.get_file(voice.file_id)
    downloaded = await bot.download_file(file.file_path)

    temp_file = f"temp_{message.from_user.id}.ogg"
    with open(temp_file, "wb") as f:
        f.write(downloaded.read())

    await message.reply("🔍 Musiqa aniqlanmoqda...")

    try:
        shazam = Shazam()
        result = await shazam.recognize(temp_file)

        if not result or 'track' not in result:
            await message.reply("❌ Musiqa aniqlanmadi. Iltimos, boshqa ovozli xabar yuboring.")
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
        if os.path.exists(temp_file):
            os.remove(temp_file)
        for ext in ["mp3", "m4a", "webm"]:
            path = f"{message.from_user.id}_audio.{ext}"
            if os.path.exists(path):
                os.remove(path)
