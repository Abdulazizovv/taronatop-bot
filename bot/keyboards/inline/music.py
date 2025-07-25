from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.callback_data import CallbackData
from typing import List, Dict, Optional


# Constants
ITEMS_PER_PAGE = 10
MAX_SEARCH_RESULTS = 50

# Callback data for selecting a music

music_callback = CallbackData("music", "action", "page", "video_id")
pagination_callback = CallbackData("pagination", "action", "page")

def create_music_keyboard(
    results: List[Dict], 
    page: int = 1, 
    items_per_page: int = ITEMS_PER_PAGE
) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard for music selection with pagination.
    
    Args:
        results: List of video dictionaries
        page: Current page number
        items_per_page: Number of items per page
        
    Returns:
        InlineKeyboardMarkup object
    """
    keyboard = InlineKeyboardMarkup(row_width=5)
    total_results = len(results)
    total_pages = max(1, (total_results - 1) // items_per_page + 1)
    page = max(1, min(page, total_pages))

    # Add video selection buttons
    start = (page - 1) * items_per_page
    end = start + items_per_page
    for i, video in enumerate(results[start:end], start=start + 1):
        video_id = video.get("video_id", "")
        if not video_id:
            continue
            
        keyboard.insert(
            InlineKeyboardButton(
                text=str(i),
                callback_data=music_callback.new(
                    action="select",
                    page=page,
                    video_id=video_id
                )
            )
        )

    # Add pagination controls
    pagination_row = []
    
    # Previous button
    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=pagination_callback.new(
                    action="previous",
                    page=page - 1
                )
            )
        )
    else:
        pagination_row.append(
            InlineKeyboardButton(text="◀️", callback_data="noop")
        )
    
    # Delete button
    pagination_row.append(
        InlineKeyboardButton(text="❌", callback_data="delete")
    )
    
    # Next button
    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=pagination_callback.new(
                    action="next",
                    page=page + 1
                )
            )
        )
    else:
        pagination_row.append(
            InlineKeyboardButton(text="▶️", callback_data="noop")
        )

    keyboard.row(*pagination_row)
    
    return keyboard