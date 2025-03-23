from aiogram import types
from bot.loader import dp
from bot.filters import IsAdmin
from aiogram.dispatcher import FSMContext
from bot.keyboards.inline import admin_main_menu_kb


@dp.message_handler(IsAdmin(), commands=['start'], state='*')
async def admin_start(message: types.Message, state: FSMContext):

    await state.finish()

    await message.answer("Assalomu alaykum, admin!", reply_markup=admin_main_menu_kb())