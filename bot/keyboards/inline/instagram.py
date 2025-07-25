from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData

instagram_callback = CallbackData("instagram", "action", "media_id")

def instagram_keyboard(media_id: str) -> InlineKeyboardMarkup:
    """
    Instagram media uchun inline klaviatura yaratadi.

    Args:
        media_id (str): Instagram media identifikatori

    Returns:
        InlineKeyboardMarkup: Inline klaviatura
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton("📥 Musiqani yuklab olish", callback_data=instagram_callback.new(action="download", media_id=media_id))
    )
    
    return keyboard