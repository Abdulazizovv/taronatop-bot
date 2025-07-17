from aiogram import types
from aiogram.dispatcher.filters.builtin import CommandStart
from bot.loader import dp, db
from aiogram.dispatcher import FSMContext


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
    
    await message.answer(
        f"Hello, {user['first_name']}! Welcome to our bot. "
        "Use /help to see available commands."
    )
    


