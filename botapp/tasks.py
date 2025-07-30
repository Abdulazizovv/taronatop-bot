from celery import shared_task
from reklama.models import Advertisement
from botapp.models import BotUser
from django.utils import timezone
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.data.config import PRIVATE_CHANNEL_ID, BOT_TOKEN
import logging
import time

# Telebot ob'ektini yaratish
bot = telebot.TeleBot(BOT_TOKEN)

@shared_task(bind=True, max_retries=3)
def send_advertisement_task(self, ad_id):
    """
    Sinxron Celery taski reklama yuborish uchun.
    telebot kutubxonasidan foydalanadi.
    """
    try:
        # Reklama ma'lumotlarini olish
        ad = Advertisement.objects.select_related('post').prefetch_related('target_users', 'buttons').get(id=ad_id)

        # Maqsadli foydalanuvchilar yoki barcha faol foydalanuvchilarni olish
        users = ad.target_users.all() if ad.target_users.exists() else BotUser.objects.filter(is_active=True)

        # Inline keyboard tayyorlash
        reply_markup = None
        if ad.buttons.exists():
            keyboard = InlineKeyboardMarkup()
            for btn in ad.buttons.all():
                keyboard.add(InlineKeyboardButton(text=btn.title, url=btn.url))
            reply_markup = keyboard

        # Har bir foydalanuvchiga reklama yuborish
        for user in users:
            try:
                bot.copy_message(
                    chat_id=user.user_id,
                    from_chat_id=PRIVATE_CHANNEL_ID,
                    message_id=int(ad.post.message_id),
                    reply_markup=reply_markup
                )
                ad.count += 1
                time.sleep(0.05)  # Telegram API limitlarini hurmat qilish uchun
            except Exception as e:
                logging.warning(f"Foydalanuvchiga yuborishda xato {user.user_id}: {str(e)}")
                continue

        # Reklama holatini yangilash
        ad.status = Advertisement.AdvertisementStatus.PUBLISHED
        ad.sent_time = timezone.now()
        ad.save()

        logging.info(f"Reklama {ad_id} {ad.count} foydalanuvchiga muvaffaqiyatli yuborildi.")

    except Exception as e:
        logging.error(f"Reklama taskida xato {ad_id}: {str(e)}")
        # Xato bo'lsa, qayta urinish
        raise self.retry(exc=e, countdown=2 ** self.request.retries)