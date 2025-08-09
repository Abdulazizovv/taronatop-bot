from bot.loader import bot, dp, db
from aiogram import types
from aiogram.utils.exceptions import ChatNotFound, Unauthorized, BadRequest
import logging


@dp.my_chat_member_handler()
async def on_bot_member_status_changed(update: types.ChatMemberUpdated):
    """Handle bot member status changes - both channels/groups and private chats"""
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    chat = update.chat
    user = update.from_user

    # Handle private chats (user blocking/unblocking bot)
    if chat.type == "private":
        logging.info(f"Bot status changed for user {user.id} ({user.username}): {old_status} -> {new_status}")
        
        # When user blocks the bot
        if new_status in ["kicked", "left"] and old_status == "member":
            try:
                await db.update_user_active_status(user_id=user.id, is_active=False)
                logging.info(f"User {user.id} blocked the bot - set is_active=False")
                
                # Optional: notify admin about user blocking
                await bot.send_message(
                    chat_id=1376269802,
                    text=f"🚫 User blocked bot: {user.first_name} (@{user.username}) - ID: {user.id}"
                )
            except Exception as e:
                logging.error(f"Error updating user active status: {e}")
        
        # When user unblocks the bot
        elif new_status == "member" and old_status in ["kicked", "left"]:
            try:
                await db.update_user_active_status(user_id=user.id, is_active=True)
                logging.info(f"User {user.id} unblocked the bot - set is_active=True")
                
                # Optional: notify admin about user unblocking
                # await bot.send_message(
                #     chat_id=1376269802,
                #     text=f"✅ User unblocked bot: {user.first_name} (@{user.username}) - ID: {user.id}"
                # )
            except Exception as e:
                logging.error(f"Error updating user active status: {e}")
        
        return  # Exit early for private chats
    
    # Handle channels and groups (bot being added/removed)
    if chat.type not in ["channel", "group", "supergroup"]:
        return

    await bot.send_message(
        chat_id=1376269802,
        text=str(chat) + f"\n{old_status} || {new_status}"
    )

    invite_link = None

    if new_status in ["member", "administrator", "owner"]:

        if new_status in ["administrator", "owner"]:
            try:
                invite_link = await bot.export_chat_invite_link(chat.id)
            except (ChatNotFound, Unauthorized, BadRequest) as e:
                logging.error(f"Error exporting invite link for channel {chat.id}: {e}")
                invite_link = None

        # Bot kanalga qo'shildi yoki administrator bo'ldi
        
        if not invite_link:
            await db.add_chat(
                chat_id=chat.id,
                chat_type=chat.type,
                title=chat.title,
                username=chat.username,
                is_admin=new_status in ["administrator", "owner"],
            )
        else:
            await db.add_chat(
                chat_id=chat.id,
                chat_type=chat.type,
                title=chat.title,
                username=chat.username,
                invite_link=invite_link,
                is_admin=new_status in ["administrator", "owner"],
            )

        # Bot yangi qo'shilgan
        # await bot.send_message(
        #     chat_id=1376269802,  # o'zingizga xabar yuborish uchun admin ID
        #     text=f"🤖 Bot kanalga qo'shildi: {chat.title} ({chat.id})"
        # )
    elif new_status in ["kicked", "left"]:
        
        # Bot kanalidan chiqarildi
        await db.deactivate_chat(chat_id=chat.id)

        # await bot.send_message(
        #     chat_id=1376269802,
        #     text=f"❌ Bot '{chat.title}' kanalidan chiqarildi."
        # )
