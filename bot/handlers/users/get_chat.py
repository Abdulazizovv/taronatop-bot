from bot.loader import bot, dp, db
from aiogram import types
from aiogram.utils.exceptions import ChatNotFound, Unauthorized, BadRequest


@dp.my_chat_member_handler()
async def on_bot_added_to_channel(update: types.ChatMemberUpdated):
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    channel = update.chat

    await bot.send_message(
        chat_id=1376269802,
        text=str(channel) + f"\n{old_status} || {new_status}"
    )

    invite_link = None

    if new_status in ["member", "administrator", "owner"]:

        if new_status in ["administrator", "owner"]:
            try:
                invite_link = await bot.export_chat_invite_link(channel.id)
            except (ChatNotFound, Unauthorized, BadRequest) as e:
                invite_link = None

        # Bot kanalga qo‘shildi yoki administrator bo‘ldi
        await db.add_chat(
            chat_id=channel.id,
            chat_type=channel.type,
            title=channel.title,
            username=channel.username,
            invite_link=invite_link,
            is_admin=new_status in ["administrator", "owner"],
        )

        # Bot yangi qo‘shilgan
        # await bot.send_message(
        #     chat_id=1376269802,  # o‘zingizga xabar yuborish uchun admin ID
        #     text=f"🤖 Bot kanalga qo‘shildi: {channel.title} ({channel.id})"
        # )
    elif new_status in ["kicked", "left"]:
        
        # Bot kanalidan chiqarildi
        await db.deactivate_chat(chat_id=channel.id)

        # await bot.send_message(
        #     chat_id=1376269802,
        #     text=f"❌ Bot '{channel.title}' kanalidan chiqarildi."
        # )