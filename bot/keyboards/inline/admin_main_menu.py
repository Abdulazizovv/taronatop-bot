from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData


main_menu_callback = CallbackData("main_menu", "action")


def admin_main_menu_kb():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="So'rovnoma yaratish", callback_data=main_menu_callback.new(action="create_poll")),
                InlineKeyboardButton(text="So'rovnomalar", callback_data=main_menu_callback.new(action="polls")),
            ],
            [
                InlineKeyboardButton(text="Mening kanalim", callback_data=main_menu_callback.new(action="my_channel")),
            ],
            [
                InlineKeyboardButton(text="Reklama yuborish", callback_data=main_menu_callback.new(action="send_ad")),
                InlineKeyboardButton(text="Statistika", callback_data=main_menu_callback.new(action="stats")),
            ]
        ]
    )
    return kb