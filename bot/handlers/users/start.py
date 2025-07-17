from aiogram import types
from aiogram.dispatcher.filters.builtin import CommandStart
from bot.loader import dp, db
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.handler import CancelHandler
from bot.utils import users_not_joined_channels
from bot.keyboards.inline.required_chats import chats_kb


@dp.message_handler(CommandStart())
async def bot_start(message: types.Message, state: FSMContext):
    """
    Handles the /start command.
    Creates or retrieves the user from the database.
    """
    # Clear any previous state
    await state.finish()

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
        "Assalomu alaykum, botimizga xush kelibsiz!\n"
    )
    

    


