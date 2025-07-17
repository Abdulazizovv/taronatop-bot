from aiogram.dispatcher import FSMContext
from aiogram.types import CallbackQuery
from aiogram.dispatcher.filters import Text
from bot.loader import dp, db
from bot.keyboards.inline.required_chats import chats_kb
from bot.utils import users_not_joined_channels
from aiogram.utils.exceptions import MessageNotModified

@dp.callback_query_handler(Text(equals="submit_required_chats"))
async def check_required_channels(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    required_chats = await db.get_required_chats()

    not_joined = await users_not_joined_channels(
        user_id=user_id,
        required_chats=required_chats
    )

    

    if not_joined:
        # User is NOT a member of all channels — remind to join again
        kb = chats_kb(not_joined)
        await call.answer("Iltimos, avval barcha ko'rsatilgan kanal(guruh)larga a'zo bo'ling!")
        try:
            await call.message.edit_reply_markup(kb)
        except MessageNotModified:
            pass
    else:
        # User is member of all channels — continue
        await call.message.edit_text("Rahmat! Siz barcha kerakli kanallarga a'zo bo‘ldingiz ✅.\n"
                                  "Endi botdan to'liq foydalanishingiz mumkin.")

    await call.answer()
