from aiogram import types
from bot.loader import dp
from bot.filters import IsAdmin
from aiogram.dispatcher import FSMContext


@dp.message_handler(IsAdmin(), commands=['start'], state='*')
async def admin_start(message: types.Message, state: FSMContext):

    await state.finish()

    await message.answer("Hello, admin! 👋\n", reply_markup=types.ReplyKeyboardRemove())