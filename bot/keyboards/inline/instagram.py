from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData
from typing import Optional

instagram_callback = CallbackData("instagram", "action", "media_id")

def instagram_keyboard(media_id: str, has_audio: Optional[bool] = None, has_song_info: bool = False, has_linked_audio: bool = False) -> InlineKeyboardMarkup:
    """
    Instagram media uchun inline klaviatura yaratadi.
    
    Args:
        media_id (str): Instagram media identifikatori
        has_audio (bool, optional): Media audio bor-yo'qligini bildiradi
        has_song_info (bool): Shazam orqali musiqa ma'lumotlari topilganmi
        has_linked_audio (bool): Database'da saqlangan YouTube audio bormi
    
    Returns:
        InlineKeyboardMarkup: Inline klaviatura
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Agar linked audio mavjud bo'lsa, instant yuklab olish tugmasi
    if has_linked_audio:
        keyboard.add(
            InlineKeyboardButton(
                "⚡ Saqlangan musiqani yuborish", 
                callback_data=instagram_callback.new(action="send_linked_audio", media_id=media_id)
            )
        )
    # Agar song info mavjud bo'lsa, YouTube'dan to'liq musiqani yuklab olish tugmasi
    elif has_song_info:
        keyboard.add(
            InlineKeyboardButton(
                "🎵 YouTube'dan musiqani yuklab olish", 
                callback_data=instagram_callback.new(action="download_from_youtube", media_id=media_id)
            )
        )
    elif has_audio is True:
        # Audio bor lekin song info yo'q - Shazam orqali aniqlash
        keyboard.add(
            InlineKeyboardButton(
                "🎵 Musiqani aniqlash va yuklab olish", 
                callback_data=instagram_callback.new(action="identify_and_download", media_id=media_id)
            )
        )
    elif has_audio is False:
        # Audio yo'q bo'lsa ma'lumotlar tugmasi qo'shamiz
        keyboard.add(
            InlineKeyboardButton(
                "🔇 Videoda audio yo'q", 
                callback_data=instagram_callback.new(action="no_audio", media_id=media_id)
            )
        )
    else:
        # Audio tekshirilmagan bo'lsa standart tugma
        keyboard.add(
            InlineKeyboardButton(
                "🔍 Audioni tekshirish", 
                callback_data=instagram_callback.new(action="check_audio", media_id=media_id)
            )
        )
    
    return keyboard