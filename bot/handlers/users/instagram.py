from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.loader import dp, db, bot

from bot.utils.instagram_service import ensure_instagram_media, download_video_from_telegram, extract_audio_with_ffmpeg
from bot.utils.audio_db_utils import (
    update_instagram_media_audio_info, 
    get_instagram_media_audio_info,
    save_youtube_audio_to_db,
    link_instagram_to_youtube_audio,
    get_linked_youtube_audio
)
from bot.utils.fast_youtube_service import FastYouTubeMusicService

from bot.keyboards.inline.instagram import instagram_keyboard, instagram_callback
from bot.data.config import PRIVATE_CHANNEL_ID
from bot.utils.instagram_simple import (
    find_music_name,
)
from bot.utils.youtube_enhanced import (
    search_youtube,
    download_youtube_music,
)
from bot.utils.db_api.db import DBUtils
import logging
import re
import os
import asyncio
from typing import Optional

# Robust Instagram URL regex (supports http/https, www, m.)
INSTAGRAM_URL_REGEX = re.compile(r"(https?://)?(www\.)?(m\.)?instagram\.com/[^\s]+", re.IGNORECASE)


def extract_instagram_url(text: str) -> str:
    """Extract and normalize the first Instagram URL from text.
    Ensures https scheme and strips trailing punctuation.
    """
    if not text:
        return ""
    m = INSTAGRAM_URL_REGEX.search(text)
    if not m:
        return ""
    url = m.group(0).rstrip(").,]>\'\"”’")
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.strip()


def fallback_media_id_from_url(url: str) -> str:
    try:
        cleaned = url.split("?")[0].rstrip("/")
        return cleaned.rsplit("/", 1)[-1]
    except Exception:
        return "unknown"


@dp.message_handler(lambda m: bool(m.text) and INSTAGRAM_URL_REGEX.search(m.text), state="*")
async def handle_instagram_link(message: types.Message, state: FSMContext):
    text = message.text or ""
    link = extract_instagram_url(text)
    if not link:
        await message.answer("❌ Iltimos, Instagram linkini yuboring.")
        return

    try:
        await state.finish()
    except Exception:
        pass

    status_msg = None
    try:
        status_msg = await message.answer("⏳ Video yuklanmoqda...", disable_web_page_preview=True)
    except Exception:
        pass

    # Always process Instagram media to get correct media_id
    result = await ensure_instagram_media(link, bot, user_id=message.from_user.id)
    if not result.success or not result.telegram_file_id:
        err = result.message or "❌ Xatolik yuz berdi"
        if status_msg:
            try:
                await status_msg.edit_text(err, disable_web_page_preview=True)
            except Exception:
                await message.answer(err, disable_web_page_preview=True)
        else:
            await message.answer(err, disable_web_page_preview=True)
        return

    # Now check for linked audio using the correct media_id
    linked_audio = await get_linked_youtube_audio(result.media_id)

    # Send video to the user using cached file_id
    caption = (
        f"🎥 <b>Video</b>\n\n"
        f"📌  {result.title or '—'}\n\n"
    )
    
    # Check if we have linked audio to show appropriate message
    if linked_audio and linked_audio.get('telegram_file_id'):
        caption += f"⚡ <b>Saqlangan musiqa mavjud!</b>\n"
        caption += f"🎵 {linked_audio.get('artist', 'Unknown')} - {linked_audio.get('track', 'Unknown')}\n"
        caption += f"📺 {linked_audio.get('title', 'Unknown')}\n\n"
    
    # Music recognition info
    elif result.song_info:
        from bot.utils.shazam_service import shazam_service
        song_text = shazam_service.format_song_info(result.song_info)
        caption += f"🎵 <b>Aniqlangan musiqa:</b>\n{song_text}\n\n"
    elif result.has_audio is True:
        caption += "🎵 <i>Musiqa mavjud</i>\n\n"
    elif result.has_audio is False:
        caption += "🔇 <i>Musiqa yo'q</i>\n\n"
    else:
        caption += "🔍 <i>Musiqa tekshirilmagan</i>\n\n"
    
    caption += f"@Taronatop_robot orqali yuklab olindi!\n"

    try:
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                # If cannot delete, at least edit to a short note
                try:
                    await status_msg.edit_text("✅ Media yuborilmoqda...", disable_web_page_preview=True)
                except Exception:
                    pass
        # Check if we have song info and linked audio to show appropriate keyboard
        has_song_info = bool(result.song_info and result.song_info.get('title') and result.song_info.get('artist'))
        has_linked_audio = bool(linked_audio and linked_audio.get('telegram_file_id'))
        
        await message.answer_video(
            video=result.telegram_file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=instagram_keyboard(result.media_id, result.has_audio, has_song_info, has_linked_audio),
        )
    except Exception as e:
        logging.warning(f"Send video failed, falling back to text: {e}")
        txt = (
            "✅ Media tayyor!\n\n"
            f"📌 {result.title or '—'}\n\n"
        )
        
        # Audio haqida ma'lumot qo'shamiz
        if result.has_audio is True:
            txt += "🎵 <i>Musiqa mavjud</i>\n\n"
        elif result.has_audio is False:
            txt += "🔇 <i>Musiqa yo'q</i>\n\n"
        else:
            txt += "🔍 <i>Musiqa tekshirilmagan</i>\n\n"
            
        txt += f"@Taronatop_robot orqali yuklab olindi!\n"
        
        # Check if we have song info and linked audio to show appropriate keyboard
        has_song_info = bool(result.song_info and result.song_info.get('title') and result.song_info.get('artist'))
        has_linked_audio = bool(linked_audio and linked_audio.get('telegram_file_id'))
        
        await message.answer(
            txt,
            reply_markup=instagram_keyboard(result.media_id, result.has_audio, has_song_info, has_linked_audio),
            disable_web_page_preview=True,
        )


@dp.callback_query_handler(instagram_callback.filter(action="download"))
async def download_instagram_media_music(call: types.CallbackQuery, callback_data: dict):
    """
    Instagram music extraction - faqat audio mavjud videolar uchun.
    """
    media_id = callback_data.get("media_id")
    user_id = call.from_user.id
    
    # Initial response
    await call.answer("🎵 Musiqa tayyorlanmoqda...")
    
    # Remove keyboard to prevent multiple clicks
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass

    if not media_id:
        await call.message.answer("❌ Media identifikatori topilmadi.")
        return

    status_msg = None
    temp_files = []  # Track all temp files for cleanup
    
    try:
        # Show initial status
        status_msg = await call.message.answer(
            "⏳ Musiqa yuklanmoqda...", 
            disable_web_page_preview=True
        )
        
        # Get media info from database
        media_info = await db.get_instagram_media_by_id(media_id)
        if not media_info or not media_info.get("telegram_file_id"):
            await _update_status(status_msg, "❌ Media ma'lumotlari topilmadi.")
            return

        # Check if this media is known to have no audio
        from bot.utils.audio_db_utils import get_instagram_media_audio_info
        audio_info = await get_instagram_media_audio_info(media_id)
        if audio_info.get("has_audio") is False:
            await _update_status(status_msg, "🔇 Bu videoda audio yo'q.")
            return

        # STEP 1: Check if audio already exists and linked
        if media_info.get("audio") and media_info["audio"].get("telegram_file_id"):
            await _send_cached_audio(call, status_msg, media_info)
            return
        
        # STEP 2: Try to get track name from stored data
        track_name = None
        track = media_info.get("track")
        artist = media_info.get("artist")
        
        if track and artist:
            track_name = f"{artist} - {track}"
            logging.info(f"[IG Music] Using stored track: {track_name}")
        else:
            # STEP 3: Extract audio from video and recognize music
            track_name = await _extract_and_recognize_music(
                status_msg, media_info, media_id, temp_files
            )
        
        if not track_name:
            # STEP 4: Fallback - use video title for search
            video_title = media_info.get("title", "").strip()
            if video_title and len(video_title) > 5:
                track_name = video_title
                logging.info(f"[IG Music] Using video title as fallback: {track_name}")
            else:
                await _update_status(status_msg, "❌ Musiqa aniqlanmadi va video sarlavhasi ham yo'q.")
                return
        
        # STEP 5: Search on YouTube
        await _update_status(status_msg, "🔍 Musiqa qidirilmoqda...")
        
        search_results = await search_youtube(track_name, max_results=3)
        if not search_results:
            await _update_status(status_msg, "❌ Videodagi musiqa topilmadi.")
            return
        
        # Try each search result until we find one that works
        for i, video_info in enumerate(search_results):
            try:
                success = await _process_youtube_result(
                    call, status_msg, media_id, video_info, user_id, temp_files
                )
                if success:
                    return
            except Exception as e:
                logging.warning(f"[IG Music] YouTube result {i+1} failed: {e}")
                continue
        
        # If all results failed
        await _update_status(status_msg, "❌ Barcha natijalarda xatolik yuz berdi.")
        
    except Exception as e:
        logging.error(f"[IG Music] Unexpected error: {e}")
        await _update_status(status_msg, "❌ Kutilmagan xatolik yuz berdi.")
        
    finally:
        # Cleanup all temporary files
        await _cleanup_files(temp_files)


@dp.callback_query_handler(instagram_callback.filter(action="no_audio"))
async def handle_no_audio_callback(call: types.CallbackQuery, callback_data: dict):
    """Handle callback when video has no audio"""
    await call.answer("🔇 Bu videoda audio yo'q", show_alert=True)


@dp.callback_query_handler(instagram_callback.filter(action="check_audio"))
async def handle_check_audio_callback(call: types.CallbackQuery, callback_data: dict):
    """Check audio in video that wasn't analyzed before"""
    media_id = callback_data.get("media_id")
    
    await call.answer("🔍 Audio tekshirilmoqda...")
    
    if not media_id:
        await call.message.answer("❌ Media identifikatori topilmadi.")
        return
    
    try:
        # Get media info from database
        media_info = await db.get_instagram_media_by_id(media_id)
        if not media_info or not media_info.get("telegram_file_id"):
            await call.message.answer("❌ Media ma'lumotlari topilmadi.")
            return
        
        # Download video from Telegram to check audio
        status_msg = await call.message.answer("⏳ Video tekshirilmoqda...")
        
        from bot.utils.instagram_service import download_video_from_telegram
        from bot.utils.media_analyzer import check_media_has_audio
        from bot.utils.audio_db_utils import update_instagram_media_audio_info
        
        tg_video_path = await download_video_from_telegram(bot, media_info["telegram_file_id"])
        if not tg_video_path:
            await status_msg.edit_text("❌ Video faylini olishda xatolik yuz berdi.")
            return
        
        # Check audio
        has_audio = await check_media_has_audio(tg_video_path)
        
        # Clean up temp file
        try:
            if tg_video_path and os.path.exists(tg_video_path):
                os.remove(tg_video_path)
        except Exception:
            pass
        
        if has_audio is None:
            await status_msg.edit_text("❌ Audio tekshirishda xatolik yuz berdi.")
            return
        
        # Save audio info to database
        await update_instagram_media_audio_info(media_id, has_audio)
        
        # Update message with new keyboard
        if has_audio:
            await status_msg.edit_text("✅ Audio topildi! Endi musiqani yuklab olishingiz mumkin.")
            # Update original message keyboard
            try:
                new_keyboard = instagram_keyboard(media_id, has_audio=True)
                await call.message.edit_reply_markup(reply_markup=new_keyboard)
            except Exception:
                pass
        else:
            await status_msg.edit_text("🔇 Bu videoda audio yo'q.")
            # Update original message keyboard
            try:
                new_keyboard = instagram_keyboard(media_id, has_audio=False)
                await call.message.edit_reply_markup(reply_markup=new_keyboard)
            except Exception:
                pass
                
    except Exception as e:
        logging.error(f"[Check Audio] Error: {e}")
        await call.message.answer("❌ Audio tekshirishda xatolik yuz berdi.")


async def _update_status(status_msg, text: str):
    """Update status message safely"""
    if status_msg:
        try:
            await status_msg.edit_text(text, disable_web_page_preview=True)
        except Exception:
            pass


async def _send_cached_audio(call, status_msg, media_info):
    """Send already cached audio"""
    audio_file_id = media_info["audio"]["telegram_file_id"]
    title = media_info["audio"].get("title") or media_info.get("title") or "Instagram Audio"
    
    try:
        if status_msg:
            await status_msg.delete()
    except Exception:
        pass
    
    await call.message.answer_audio(
        audio=audio_file_id,
        title=title,
        caption=f"🎵 <b>{title}</b>\n\n@Taronatop_robot orqali yuklab olindi",
        parse_mode="HTML"
    )
    logging.info(f"[IG Music] Sent cached audio for media {media_info.get('media_id')}")


async def _extract_and_recognize_music(status_msg, media_info, media_id, temp_files):
    """Extract audio from video and recognize music"""
    try:
        # Download video from Telegram
        await _update_status(status_msg, "📥 Video yuklab olinmoqda...")
        
        tg_video_path = await download_video_from_telegram(bot, media_info["telegram_file_id"])
        if not tg_video_path:
            logging.error("[IG Music] Failed to download video from Telegram")
            return None
        
        temp_files.append(tg_video_path)
        
        # Check if video has audio stream using ffprobe
        await _update_status(status_msg, "🔊 Audio tekshirilmoqda...")
        
        has_audio = await _check_audio_stream(tg_video_path)
        if not has_audio:
            logging.info("[IG Music] Video has no audio stream")
            return None
        
        # Extract audio using ffmpeg
        await _update_status(status_msg, "🎵 Audio ajratilmoqda...")
        
        audio_path = await _extract_audio_robust(tg_video_path)
        if not audio_path:
            logging.error("[IG Music] Failed to extract audio")
            return None
        
        temp_files.append(audio_path)
        
        # Recognize music
        await _update_status(status_msg, "🔍 Musiqa aniqlanmoqda...")
        
        track_name = await find_music_name(audio_path)
        
        # Save recognized track to database for future use
        if track_name and " - " in track_name:
            parts = [p.strip() for p in track_name.split(" - ", 1)]
            if len(parts) == 2:
                await DBUtils.update_instagram_track(media_id, parts[1], parts[0])
                logging.info(f"[IG Music] Saved track to DB: {track_name}")
        
        return track_name
        
    except Exception as e:
        logging.error(f"[IG Music] Extract and recognize failed: {e}")
        return None


async def _check_audio_stream(video_path: str) -> bool:
    """Check if video has audio stream using ffprobe"""
    try:
        import shutil
        if not shutil.which("ffprobe"):
            logging.warning("[IG Music] ffprobe not found, assuming audio exists")
            return True
        
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            video_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        
        has_audio = proc.returncode == 0 and stdout.decode().strip()
        logging.info(f"[IG Music] Audio stream check: {has_audio}")
        return bool(has_audio)
        
    except Exception as e:
        logging.warning(f"[IG Music] Audio stream check failed: {e}")
        return True  # Assume audio exists if check fails


async def _extract_audio_robust(video_path: str) -> Optional[str]:
    """Extract audio using ffmpeg with multiple fallback strategies"""
    try:
        import shutil
        if not shutil.which("ffmpeg"):
            logging.error("[IG Music] ffmpeg not found")
            return None
        
        audio_path = os.path.splitext(video_path)[0] + ".mp3"
        
        # Try different ffmpeg strategies
        strategies = [
            # Strategy 1: High quality with explicit mapping
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-map", "0:a:0",
                "-acodec", "libmp3lame", "-b:a", "192k", "-ar", "44100",
                audio_path
            ],
            # Strategy 2: Lower quality, more compatible
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-acodec", "mp3", "-ab", "128k",
                audio_path
            ],
            # Strategy 3: Auto codec selection
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-q:a", "2",
                audio_path
            ]
        ]
        
        for i, cmd in enumerate(strategies, 1):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await proc.communicate()
                
                if proc.returncode == 0 and os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
                    logging.info(f"[IG Music] Audio extracted with strategy {i}")
                    return audio_path
                else:
                    logging.warning(f"[IG Music] Strategy {i} failed: {stderr.decode() if stderr else 'Unknown error'}")
                    # Clean up failed attempt
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                        
            except Exception as e:
                logging.warning(f"[IG Music] Strategy {i} exception: {e}")
                continue
        
        logging.error("[IG Music] All extraction strategies failed")
        return None
        
    except Exception as e:
        logging.error(f"[IG Music] Audio extraction error: {e}")
        return None


async def _process_youtube_result(call, status_msg, media_id, video_info, user_id, temp_files):
    """Process a YouTube search result"""
    try:
        video_id = video_info["video_id"]
        title = video_info["title"]
        youtube_url = video_info["url"]
        
        # Check if we already have this audio cached
        cached_audio = await db.get_youtube_audio(video_id)
        if cached_audio and cached_audio.get("telegram_file_id"):
            await _link_and_send_audio(call, status_msg, media_id, cached_audio, from_cache=True)
            return True
        
        # Download audio from YouTube
        await _update_status(status_msg, f"⬇️ '{title}' yuklab olinmoqda...")
        
        audio_download = await download_youtube_music(youtube_url)
        if not audio_download:
            logging.warning(f"[IG Music] Failed to download: {title}")
            return False
        
        audio_data, audio_file_path, filename = audio_download
        if audio_file_path:
            temp_files.append(audio_file_path)
        
        # Upload to private channel
        await _update_status(status_msg, "📤 Audio jo'natilmoqda...")
        
        audio_file = types.InputFile(audio_data, filename=filename)
        sent_message = await bot.send_audio(
            chat_id=PRIVATE_CHANNEL_ID,
            audio=audio_file,
            title=title,
            caption=f"🎵 <b>{title}</b>\n\n📱 Instagram: {media_id}\n@TaronatopBot",
            parse_mode="HTML"
        )
        
        telegram_file_id = sent_message.audio.file_id
        
        # Save to database
        youtube_audio = await db.save_youtube_audio(
            video_id=video_id,
            title=title,
            telegram_file_id=telegram_file_id,
            user_id=user_id
        )
        
        # Link to Instagram media
        await db.add_audio_to_instagram_media(media_id=media_id, audio_id=video_id)
        
        # Send to user
        await _link_and_send_audio(call, status_msg, media_id, youtube_audio, from_cache=False)
        
        logging.info(f"[IG Music] Successfully processed: {title}")
        return True
        
    except Exception as e:
        logging.error(f"[IG Music] YouTube processing failed: {e}")
        return False


async def _link_and_send_audio(call, status_msg, media_id, audio_data, from_cache=False):
    """Link audio to Instagram media and send to user"""
    try:
        if status_msg:
            await status_msg.delete()
    except Exception:
        pass
    
    title = audio_data.get("title", "Audio")
    telegram_file_id = audio_data["telegram_file_id"]
    
    
    await call.message.answer_audio(
        audio=telegram_file_id,
        title=title,
        caption=f"🎵 <b>{title}</b>\n\n@Taronatop_robot orqali yuklab olindi",
        parse_mode="HTML"
    )


async def _cleanup_files(temp_files):
    """Clean up all temporary files"""
    for file_path in temp_files:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logging.debug(f"[IG Music] Cleaned up: {file_path}")
        except Exception as e:
            logging.warning(f"[IG Music] Cleanup failed for {file_path}: {e}")


@dp.callback_query_handler(instagram_callback.filter(action="send_linked_audio"))
async def send_linked_audio(call: types.CallbackQuery, callback_data: dict):
    """
    Send already saved YouTube audio instantly.
    """
    try:
        media_id = callback_data.get("media_id")
        
        await call.answer("⚡ Saqlangan musiqa yuborilmoqda...")
        
        # Remove keyboard to prevent multiple clicks
        try:
            await call.message.edit_reply_markup()
        except Exception:
            pass

        # Get linked audio
        linked_audio = await get_linked_youtube_audio(media_id)
        
        if linked_audio and linked_audio.get('telegram_file_id'):
            await call.message.answer_audio(
                audio=linked_audio['telegram_file_id'],
                title=linked_audio.get('track', 'Unknown'),
                performer=linked_audio.get('artist', 'Unknown'),
                caption=f"🎵 <b>{linked_audio.get('title', 'Unknown')}</b>\n\n"
                       f"⚡ Tezkor yuklash (saqlangan fayl)\n"
                       f"🔍 Aniqlangan: {linked_audio.get('artist', 'Unknown')} - {linked_audio.get('track', 'Unknown')}\n"
                       f"📺 To'liq musiqa yuklab olindi\n\n"
                       f"@Taronatop_robot",
                parse_mode="HTML"
            )
            logging.info(f"[Instagram] Sent linked audio for {media_id}")
        else:
            await call.message.answer("❌ Saqlangan musiqa topilmadi.")
            
    except Exception as e:
        logging.error(f"[Instagram] Send linked audio error: {e}")
        await call.message.answer("❌ Xatolik yuz berdi.")


@dp.callback_query_handler(instagram_callback.filter(action="download_from_youtube"))
async def download_music_from_youtube(call: types.CallbackQuery, callback_data: dict):
    """
    Download full music from YouTube based on saved song info.
    Fast implementation with linking for future use.
    """
    try:
        media_id = callback_data.get("media_id")
        user_id = call.from_user.id
        
        await call.answer("🎵 YouTube'dan musiqa yuklanmoqda...")
        
        # Remove keyboard to prevent multiple clicks
        try:
            await call.message.edit_reply_markup()
        except Exception:
            pass

        # First check if already linked
        linked_audio = await get_linked_youtube_audio(media_id)
        if linked_audio and linked_audio.get('telegram_file_id'):
            # Already linked - send immediately
            await call.message.answer_audio(
                audio=linked_audio['telegram_file_id'],
                title=linked_audio.get('track', 'Unknown'),
                performer=linked_audio.get('artist', 'Unknown'),
                caption=f"🎵 <b>{linked_audio.get('title', 'Unknown')}</b>\n\n"
                       f"⚡ Tez yuklash (saqlangan fayl)\n"
                       f"🔍 Aniqlangan: {linked_audio.get('artist', 'Unknown')} - {linked_audio.get('track', 'Unknown')}\n"
                       f"📺 To'liq musiqa yuklab olindi\n\n"
                       f"@Taronatop_robot",
                parse_mode="HTML"
            )
            return
        
        # Get saved song info
        from bot.utils.audio_db_utils import get_instagram_media_song_info
        song_info = await get_instagram_media_song_info(media_id)
        
        if not song_info:
            await call.message.answer("❌ Saqlangan musiqa ma'lumotlari topilmadi.")
            return
        
        status_msg = await call.message.answer("⏳ YouTube'da qidirilmoqda va yuklanmoqda...")
        
        try:
            # Use fast YouTube service
            fast_service = FastYouTubeMusicService()
            
            download_result = await fast_service.search_and_download_fast(song_info)
            
            if not download_result:
                await status_msg.edit_text("❌ YouTube'da musiqa topilmadi yoki yuklab olishda xatolik.")
                return
            
            # Upload to private channel to get file_id
            from aiogram.types import InputFile
            
            audio_data = download_result['audio_data']
            audio_data.seek(0)  # Reset BytesIO position
            
            audio_msg = await bot.send_audio(
                chat_id=PRIVATE_CHANNEL_ID,
                audio=InputFile(audio_data, filename=download_result['filename']),
                title=song_info.get('title', 'Unknown'),
                performer=song_info.get('artist', 'Unknown'),
                caption=f"🎵 Fast YouTube: {download_result['title']}"
            )
            
            if not audio_msg or not audio_msg.audio:
                await status_msg.edit_text("❌ Audio yuklashda xatolik.")
                return
            
            # Save to database for future fast access
            youtube_audio_id = await save_youtube_audio_to_db(
                video_id=download_result['video_id'],
                title=download_result['title'],
                telegram_file_id=audio_msg.audio.file_id,
                url=download_result['url'],
                thumbnail_url=download_result['youtube_video'].get('thumbnail')
            )
            
            if youtube_audio_id:
                # Link Instagram media to YouTube audio
                await link_instagram_to_youtube_audio(media_id, youtube_audio_id, song_info)
                logging.info(f"[Instagram] Linked {media_id} to YouTube audio {youtube_audio_id}")
            
            # Send to user
            await status_msg.delete()
            await call.message.answer_audio(
                audio=audio_msg.audio.file_id,
                title=song_info.get('title', 'Unknown'),
                performer=song_info.get('artist', 'Unknown'),
                caption=f"🎵 <b>{download_result['title']}</b>\n\n"
                       f"🔍 Shazam orqali aniqlandi\n"
                       f"📺 YouTube'dan yuklab olindi\n"
                       f"⚡ Keyingi safar tezroq yuboriladi\n\n"
                       f"@Taronatop_robot",
                parse_mode="HTML"
            )
            
            # Cleanup
            try:
                if os.path.exists(download_result['audio_path']):
                    os.remove(download_result['audio_path'])
            except Exception:
                pass
            
        except Exception as e:
            logging.error(f"[IG YouTube] Download error: {e}")
            await status_msg.edit_text("❌ YouTube'dan yuklab olishda xatolik yuz berdi.")
            
    except Exception as e:
        logging.error(f"[IG YouTube] Callback error: {e}")
        await call.message.answer("❌ Xatolik yuz berdi.")


@dp.callback_query_handler(instagram_callback.filter(action="identify_and_download"))
async def identify_and_download_music(call: types.CallbackQuery, callback_data: dict):
    """
    Identify music and download full song.
    """
    try:
        media_id = callback_data.get("media_id")
        user_id = call.from_user.id
        
        await call.answer("🔍 Musiqa aniqlanmoqda...")
        
        # Remove keyboard to prevent multiple clicks
        try:
            await call.message.edit_reply_markup()
        except Exception:
            pass
        
        status_msg = await call.message.answer("⏳ Musiqa aniqlanmoqda...")
        
        try:
            # Get media from database
            from bot.utils.audio_db_utils import get_instagram_media_audio_info
            media_info = await get_instagram_media_audio_info(media_id)
            
            if not media_info.get("found") or not media_info.get("telegram_file_id"):
                await status_msg.edit_text("❌ Media ma'lumotlari topilmadi.")
                return
            
            # Download video from Telegram
            from bot.utils.instagram_service import download_video_from_telegram, extract_audio_with_ffmpeg
            
            video_path = await download_video_from_telegram(bot, media_info["telegram_file_id"])
            if not video_path:
                await status_msg.edit_text("❌ Video yuklab olishda xatolik.")
                return
            
            # Extract audio for music recognition
            audio_path = await extract_audio_with_ffmpeg(video_path)
            if not audio_path:
                await status_msg.edit_text("❌ Audio chiqarishda xatolik.")
                return
            
            # Recognize music
            from bot.utils.shazam_service import shazam_service
            song_info = await shazam_service.recognize_music(audio_path)
            
            if not song_info:
                await status_msg.edit_text("❌ Musiqa aniqlanmadi.")
                return
            
            # Save song info to database
            from bot.utils.audio_db_utils import update_instagram_media_audio_info
            await update_instagram_media_audio_info(media_id, True, song_info)
            
            await status_msg.edit_text("✅ Musiqa aniqlandi! YouTube'dan yuklanmoqda...")
            
            # Search and download from YouTube using fast service
            fast_service = FastYouTubeMusicService()
            
            download_result = await fast_service.search_and_download_fast(song_info)
            
            if not download_result:
                await status_msg.edit_text(f"❌ YouTube'da '{song_info.get('artist')} - {song_info.get('title')}' topilmadi.")
                return
            
            # Upload to private channel
            from aiogram.types import InputFile
            
            audio_data = download_result['audio_data']
            audio_data.seek(0)  # Reset BytesIO position
            
            audio_msg = await bot.send_audio(
                chat_id=PRIVATE_CHANNEL_ID,
                audio=InputFile(audio_data, filename=download_result['filename']),
                title=song_info.get('title', 'Unknown'),
                performer=song_info.get('artist', 'Unknown'),
                caption=f"🎵 Fast YouTube: {download_result['title']}"
            )
            
            if not audio_msg or not audio_msg.audio:
                await status_msg.edit_text("❌ Audio yuklashda xatolik.")
                return
            
            # Save to database for future fast access
            youtube_audio_id = await save_youtube_audio_to_db(
                video_id=download_result['video_id'],
                title=download_result['title'],
                telegram_file_id=audio_msg.audio.file_id,
                url=download_result['url'],
                thumbnail_url=download_result['youtube_video'].get('thumbnail')
            )
            
            if youtube_audio_id:
                # Link Instagram media to YouTube audio
                await link_instagram_to_youtube_audio(media_id, youtube_audio_id, song_info)
                logging.info(f"[Instagram] Linked {media_id} to YouTube audio {youtube_audio_id}")
            
            # Send to user
            await status_msg.delete()
            await call.message.answer_audio(
                audio=audio_msg.audio.file_id,
                title=song_info.get('title', 'Unknown'),
                performer=song_info.get('artist', 'Unknown'),
                caption=f"🎵 <b>{download_result['title']}</b>\n\n"
                       f"🔍 Shazam orqali aniqlandi\n"
                       f"📺 YouTube'dan yuklab olindi\n"
                       f"⚡ Keyingi safar tezroq yuboriladi\n\n"
                       f"@Taronatop_robot",
                parse_mode="HTML"
            )
            
            # Cleanup
            try:
                for path in [video_path, audio_path]:
                    if path and os.path.exists(path):
                        os.remove(path)
            except Exception:
                pass
            
        except Exception as e:
            logging.error(f"[IG Identify] Process error: {e}")
            await status_msg.edit_text("❌ Musiqa aniqlash va yuklab olishda xatolik.")
            
    except Exception as e:
        logging.error(f"[IG Identify] Callback error: {e}")
        await call.message.answer("❌ Xatolik yuz berdi.")