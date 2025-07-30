from bot.loader import dp, db
from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.filters import IsAdmin
from bot.data.config import PRIVATE_CHANNEL_ID, ADMIN_PANEL_URL

# Send ad post to private channel for saving
async def send_ad_post_to_private_channel(post: types.Message):
    channel_post = await post.copy_to(chat_id=PRIVATE_CHANNEL_ID, disable_notification=True)
    return channel_post


@dp.message_handler(IsAdmin(), commands=["reklama"], state='*')
async def reklama(message: types.Message, state: FSMContext):
    await state.finish()

    await message.answer(
        "Marhamat, admin! Reklama postini yuboring.\n",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="Bekor qilish ❌")
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    await state.set_state("ad_post")

@dp.message_handler(IsAdmin(), content_types=types.ContentTypes.ANY, state="ad_post")
async def ad_post(message: types.Message, state: FSMContext):

    if message.text == "Bekor qilish ❌":
        await message.answer("Reklama postini yuborish bekor qilindi. /reklama orqali qayta urinib ko'ring.")
        await state.finish()
        return

    channel_post = await send_ad_post_to_private_channel(message)
    if channel_post:
        saved_post = await db.save_ad_post(
            message_id=channel_post.message_id,
            user_id=message.from_user.id,
        )
        if saved_post:
            await message.answer(
                f"Reklama postingiz muvaffaqiyatli saqlandi! ✅\n"
                f"Post ID: #<code>{saved_post['id']}</code>\n"
                f"Admin panelga kirib reklama postini yuborishingiz mumkin.\n"
                f"Admin panel 👉 <a href='{ADMIN_PANEL_URL}'>Kirish</a>\n",
                parse_mode=types.ParseMode.HTML
            )
        else:
            await message.answer("Reklama postini saqlashda xatolik yuz berdi. Iltimos, qayta urinib ko'ring. /reklama")

    else:
        await message.answer("Reklama postini yuborishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring. /reklama")
    await state.finish()
    return