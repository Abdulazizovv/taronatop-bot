from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def chats_kb(chats):
    """Create an inline keyboard for required chats."""
    keyboard = InlineKeyboardMarkup(row_width=1)

    if not chats:
        return None

    for chat in chats:
        title = chat.get('title', 'Unknown Chat')
        username = chat.get('username', '')
        invite_link = chat.get('invite_link', '')

        keyboard.add(InlineKeyboardButton(text=title, url=invite_link or f"https://t.me/{username}"))

    submit_btn = InlineKeyboardButton(text="Tekshirish✅", callback_data="submit_required_chats")
    keyboard.add(submit_btn)

    return keyboard