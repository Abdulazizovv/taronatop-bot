from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData


# Callback data for format selection
format_callback = CallbackData("select_format", "video_id", "format_type")

def create_format_selection_keyboard(video_id: str) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard for selecting video/audio format.
    
    :param video_id: The ID of the YouTube video.
    :return: InlineKeyboardMarkup object with format selection buttons.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Add buttons for different formats
    keyboard.add(
        InlineKeyboardButton("Audio (MP3)", callback_data=format_callback.new(video_id=video_id, format_type="audio")),
        InlineKeyboardButton("Video (MP4)", callback_data=format_callback.new(video_id=video_id, format_type="video"))
    )
    
    # Add a cancel button
    keyboard.add(InlineKeyboardButton("Bekor qilish", callback_data="cancel"))
    
    return keyboard