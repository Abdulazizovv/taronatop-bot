from aiogram import types
from aiogram.dispatcher.filters.builtin import CommandStart
from bot.loader import dp, db, bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.handler import CancelHandler
from bot.utils import users_not_joined_channels
from bot.keyboards.inline.required_chats import chats_kb
from bot.filters.is_private import IsPrivate


@dp.message_handler(IsPrivate(), CommandStart())
async def bot_start(message: types.Message, state: FSMContext):
    """
    Handles the /start command.
    Creates or retrieves the user from the database.
    """
    # Clear any previous state
    await state.finish()

    bot_info = await bot.get_me()

    # Retrieve or create the user in the database
    user = await db.get_or_create_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        username=message.from_user.username
    )

    # user's not joined channels
    not_joined_channels = await users_not_joined_channels(
        user_id=message.from_user.id,
        required_chats=await db.get_required_chats()
    )
    if not_joined_channels:
        keyboard = chats_kb(not_joined_channels)


        await message.answer(
            "Assalomu alaykum, botimizga xush kelibsiz!!\n"
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=keyboard
        )
        raise CancelHandler()
    
    await message.answer(
        f"🎵 Assalomu alaykum, {message.from_user.full_name}!\n\n"
        f"🤖 Sizni *TaronaTop* botida ko‘rib turganimizdan xursandmiz!\n\n"
        f"Bu bot yordamida siz quyidagi imkoniyatlarga ega bo‘lasiz:\n"
        f"🎶 YouTube va Instagram'dan istalgan qo‘shiqni topish va yuklab olish\n"
        f"🔍 Qo‘shiq nomi orqali tezkor qidiruv\n"
        f"🎙 Ovozli xabar orqali musiqa qidirish\n"
        f"🎼 Qo‘shiq parchasi orqali qo'shiqni aniqlash va yuklash\n"
        f"📥 Yuklab olingan musiqalarni saqlab qo‘yish va qayta eshitish\n\n"
        f"Boshlash uchun shunchaki qo‘shiq nomini yuboring yoki ovozli xabar jo‘nating!\n"
        f"Bot guruhlarda ham ishlaydi!\n",
        parse_mode='Markdown',
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="Guruhga qo'shish",
                        url=f"https://t.me/{bot_info.username}?startgroup=true"
                    )
                ],
            ]
        )
    )
    

    


