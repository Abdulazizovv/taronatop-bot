"""
Instagram Media Handler - Yangi implementatsiya
Yangi instagram_downloader_new.py bilan ishlaydi
"""

import logging
import os
import tempfile
import asyncio
from typing import Optional

from aiogram import types
from aiogram.dispatcher import FSMContext

from bot.loader import dp, db, bot
from bot.utils.instagram_downloader_new import (
    download_instagram_media,
    get_instagram_media_from_cache,
    update_instagram_telegram_file_id,
    get_instagram_media_for_audio
)
from bot.utils.youtube_enhanced import search_youtube, download_youtube_music
from bot.utils.audio_extractor import extract_audio_from_video
from bot.keyboards.inline.instagram import instagram_keyboard, instagram_callback
from bot.data.config import PRIVATE_CHANNEL_ID
from shazamio import Shazam

# Logging setup
logger = logging.getLogger(__name__)


@dp.message_handler(lambda message: message.text and ("instagram.com/" in message.text), state="*")
async def handle_instagram_link_new(message: types.Message, state: FSMContext):
    """
    Instagram link'larini qayta ishlash - yangi implementatsiya
    """
    url = message.text.strip()
    user_id = message.from_user.id
    
    try:
        # User experience: darhol javob berish
        status_msg = await message.reply("⏳ <b>Instagram media tekshirilmoqda...</b>", parse_mode="HTML")
        
        logger.info(f"Processing Instagram URL from user {user_id}: {url}")
        
        # Chat action for better UX
        await bot.send_chat_action(message.chat.id, types.ChatActions.UPLOAD_VIDEO)
        
        # Download media using new system
        result = await download_instagram_media(url, user_id=user_id)
        
        if not result['success']:
            await status_msg.edit_text(f"❌ <b>Xatolik:</b> {result['message']}", parse_mode="HTML")
            return
            
        data = result['data']
        
        # Agar cache'dan kelgan bo'lsa
        if data['from_cache']:
            logger.info(f"Serving cached Instagram media: {data['media_id']}")
            
            await message.answer_video(
                video=data['telegram_file_id'],
                caption=f"🎥 <b>Instagram Media</b>\n\n📝 {data['title']}\n\n✅ <i>Avval yuklab olingan</i>",
                parse_mode="HTML",
                reply_markup=instagram_keyboard(media_id=data['media_id'])
            )
            await status_msg.delete()
            return
        
        # Yangi media yuklangan
        await status_msg.edit_text("⬆️ <b>Telegram kanalga yuklanmoqda...</b>", parse_mode="HTML")
        
        # File path mavjudligini tekshirish
        if 'file_path' in data and data['file_path'] and os.path.exists(data['file_path']):
            # Local file from yt-dlp
            video_file = types.InputFile(data['file_path'])
            media_source = "yt-dlp"
        elif data['video_url']:
            # URL from Apify
            video_file = data['video_url']
            media_source = "Apify"
        else:
            await status_msg.edit_text("❌ <b>Video faylini topishda xatolik</b>", parse_mode="HTML")
            return
        
        # Send to private channel first
        try:
            sent_message = await bot.send_video(
                chat_id=PRIVATE_CHANNEL_ID,
                video=video_file,
                caption=f"🎥 <b>Instagram Media</b>\n\n📝 {data['title']}\n\n🔗 {url}\n👤 User: {user_id}\n⚙️ Method: {media_source}",
                parse_mode="HTML"
            )
            
            telegram_file_id = sent_message.video.file_id
            
            # Update database with telegram file ID
            await update_instagram_telegram_file_id(data['media_id'], telegram_file_id)
            
        except Exception as e:
            logger.error(f"Error sending to private channel: {e}")
            await status_msg.edit_text("❌ <b>Kanalga yuklashda xatolik</b>", parse_mode="HTML")
            return
        
        # Send to user
        await message.answer_video(
            video=telegram_file_id,
            caption=f"🎥 <b>Instagram Media</b>\n\n📝 {data['title']}\n\n✅ <i>Muvaffaqiyatli yuklab olindi</i>\n⚙️ <i>{media_source} orqali</i>",
            parse_mode="HTML",
            reply_markup=instagram_keyboard(media_id=data['media_id'])
        )
        
        await status_msg.delete()
        
        # Cleanup local file if exists
        if 'file_path' in data and data['file_path'] and os.path.exists(data['file_path']):
            try:
                os.remove(data['file_path'])
                # Also remove info file if exists
                info_file = data['file_path'].replace('.mp4', '.info.json').replace('.mkv', '.info.json')
                if os.path.exists(info_file):
                    os.remove(info_file)
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
        
        logger.info(f"Successfully processed Instagram media: {data['media_id']}")
        
    except Exception as e:
        logger.error(f"Instagram handler error for {url}: {e}")
        try:
            await status_msg.edit_text("❌ <b>Kutilmagan xatolik yuz berdi</b>", parse_mode="HTML")
        except:
            await message.reply("❌ <b>Kutilmagan xatolik yuz berdi</b>", parse_mode="HTML")


@dp.callback_query_handler(instagram_callback.filter(action="download"))
async def download_instagram_audio_new(call: types.CallbackQuery, callback_data: dict):
    """
    Instagram mediadan audio ajratish va musiqa topish - yangi implementatsiya
    """
    media_id = callback_data.get("media_id")
    user_id = call.from_user.id
    
    await call.answer("🎵 Audio tayyorlanmoqda...")
    
    try:
        logger.info(f"Processing audio request for Instagram media: {media_id}")
        
        # Remove keyboard to show processing
        await call.message.edit_reply_markup()
        
        # Status message
        status_msg = await call.message.reply("⏳ <b>Audio ajratilmoqda...</b>", parse_mode="HTML")
        
        # Check if audio already extracted
        existing_audio = await db.get_instagram_media_audio(media_id)
        if existing_audio and existing_audio.get('telegram_file_id'):
            logger.info(f"Found existing audio for Instagram media: {media_id}")
            
            await call.message.answer_audio(
                audio=existing_audio['telegram_file_id'],
                title=existing_audio.get('title', 'Instagram Audio'),
                caption=f"🎵 <b>Instagram Audio</b>\n\n📝 {existing_audio.get('title', '')}\n\n✅ <i>Avval ajratilgan</i>",
                parse_mode="HTML"
            )
            await status_msg.delete()
            return
        
        # Get telegram file ID for the video
        telegram_file_id = await get_instagram_media_for_audio(media_id)
        if not telegram_file_id:
            await status_msg.edit_text("❌ <b>Video fayl topilmadi</b>", parse_mode="HTML")
            return
        
        # Download video file from Telegram
        await status_msg.edit_text("⬇️ <b>Video yuklab olinmoqda...</b>", parse_mode="HTML")
        
        try:
            file_info = await bot.get_file(telegram_file_id)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video_path = temp_video.name
                
            # Download file
            await bot.download_file(file_info.file_path, temp_video_path)
            
        except Exception as e:
            logger.error(f"Error downloading video file: {e}")
            await status_msg.edit_text("❌ <b>Video yuklab olishda xatolik</b>", parse_mode="HTML")
            return
        
        # Extract audio from video
        await status_msg.edit_text("🎵 <b>Audio ajratilmoqda...</b>", parse_mode="HTML")
        
        try:
            # Extract audio using ffmpeg
            temp_audio_path = await extract_audio_from_video(temp_video_path)
            
            if not temp_audio_path or not os.path.exists(temp_audio_path):
                await status_msg.edit_text("❌ <b>Audio ajratishda xatolik</b>", parse_mode="HTML")
                return
                
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            await status_msg.edit_text("❌ <b>Audio ajratishda xatolik</b>", parse_mode="HTML")
            return
        finally:
            # Cleanup video file
            try:
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)
            except:
                pass
        
        # Identify music using Shazam
        await status_msg.edit_text("🔍 <b>Musiqa aniqlanmoqda...</b>", parse_mode="HTML")
        
        try:
            shazam = Shazam()
            shazam_result = await shazam.recognize_song(temp_audio_path)
            
            track_info = None
            if shazam_result and 'track' in shazam_result:
                track_data = shazam_result['track']
                track_title = track_data.get('title', '')
                track_artist = track_data.get('subtitle', '')
                
                if track_title and track_artist:
                    track_info = {
                        'title': track_title,
                        'artist': track_artist,
                        'query': f"{track_artist} - {track_title}"
                    }
                    logger.info(f"Shazam identified: {track_info['query']}")
            
        except Exception as e:
            logger.warning(f"Shazam recognition failed: {e}")
            track_info = None
        
        # If Shazam found music, search on YouTube
        if track_info:
            await status_msg.edit_text(f"🔍 <b>YouTube'da qidirilmoqda:</b> {track_info['query']}", parse_mode="HTML")
            
            try:
                search_results = await search_youtube(track_info['query'], max_results=1)
                
                if search_results:
                    video_info = search_results[0]
                    youtube_url = video_info["url"]
                    
                    # Download from YouTube
                    await status_msg.edit_text("⬇️ <b>YouTube'dan yuklab olinmoqda...</b>", parse_mode="HTML")
                    
                    audio_download = await download_youtube_music(youtube_url)
                    
                    if audio_download:
                        audio_data, audio_file_path, filename = audio_download
                        
                        # Send to private channel
                        sent_message = await bot.send_audio(
                            chat_id=PRIVATE_CHANNEL_ID,
                            audio=types.InputFile(audio_data),
                            title=video_info["title"],
                            performer=track_info['artist'],
                            caption=f"🎵 <b>Instagram Audio</b>\n\n📝 {video_info['title']}\n👤 {track_info['artist']}\n🆔 Media: {media_id}",
                            parse_mode="HTML"
                        )
                        
                        audio_file_id = sent_message.audio.file_id
                        
                        # Save to database
                        await db.save_youtube_audio(
                            video_id=video_info["video_id"],
                            title=video_info["title"],
                            telegram_file_id=audio_file_id,
                            user_id=user_id
                        )
                        
                        await db.add_audio_to_instagram_media(
                            media_id=media_id,
                            audio_id=video_info["video_id"]
                        )
                        
                        # Send to user
                        await call.message.answer_audio(
                            audio=audio_file_id,
                            title=video_info["title"],
                            caption=f"🎵 <b>Instagram Audio</b>\n\n📝 {video_info['title']}\n👤 {track_info['artist']}\n\n✅ <i>Muvaffaqiyatli topildi</i>",
                            parse_mode="HTML"
                        )
                        
                        await status_msg.delete()
                        
                        # Cleanup
                        try:
                            if os.path.exists(temp_audio_path):
                                os.remove(temp_audio_path)
                            if audio_file_path and os.path.exists(audio_file_path):
                                os.remove(audio_file_path)
                        except:
                            pass
                        
                        logger.info(f"Successfully processed Instagram audio: {media_id}")
                        return
                        
            except Exception as e:
                logger.error(f"YouTube download error: {e}")
        
        # If no music found or YouTube failed, send extracted audio
        await status_msg.edit_text("📤 <b>Audio yuborilmoqda...</b>", parse_mode="HTML")
        
        try:
            # Send extracted audio
            with open(temp_audio_path, 'rb') as audio_file:
                await call.message.answer_audio(
                    audio=types.InputFile(audio_file),
                    title="Instagram Audio",
                    caption=f"🎵 <b>Instagram Audio</b>\n\n🆔 Media: {media_id}\n\n⚠️ <i>Musiqa aniqlanmadi</i>",
                    parse_mode="HTML"
                )
            
            await status_msg.delete()
            
        except Exception as e:
            logger.error(f"Error sending extracted audio: {e}")
            await status_msg.edit_text("❌ <b>Audio yuborishda xatolik</b>", parse_mode="HTML")
        
        # Cleanup
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except:
            pass
            
    except Exception as e:
        logger.error(f"Instagram audio handler error for {media_id}: {e}")
        try:
            await call.message.reply("❌ <b>Audio tayyorlashda xatolik</b>", parse_mode="HTML")
        except:
            pass


# Example usage and testing
if __name__ == "__main__":
    # This is just for testing, not meant to run in production
    pass
