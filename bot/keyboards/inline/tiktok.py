from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData

tiktok_callback = CallbackData("tiktok", "action", "media_id")

def tiktok_keyboard(media_id: str) -> InlineKeyboardMarkup:
    """
    TikTok media uchun inline klaviatura yaratadi.

    Args:
        media_id (str): TikTok media identifikatori

    Returns:
        InlineKeyboardMarkup: Inline klaviatura
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton("📥 Musiqani yuklab olish", callback_data=tiktok_callback.new(action="download", media_id=media_id))
    )
    
    return keyboard