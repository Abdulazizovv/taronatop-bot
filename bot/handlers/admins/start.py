from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from bot.filters.is_admin import IsAdmin
from bot.loader import dp
from bot.data.config import ADMINS, ADMIN_PANEL_URL
import logging


@dp.message_handler(Command("start"), IsAdmin(), state="*")
async def admin_start(message: types.Message, state: FSMContext):
    """Handle /start command for admins with manual and commands list."""
    
    try:
        # Clear any active state
        await state.finish()
        
        user_first_name = message.from_user.first_name or "Admin"
        
        admin_manual = [
            f"👋 Salom, {user_first_name}!",
            "🤖 <b>Bot Admin Paneli</b>",
            "",
            "📋 <b>Mavjud buyruqlar:</b>",
            "",
            "📊 <b>Statistika:</b>",
            "• /stats - Asosiy bot statistikalari",
            "• /users - Foydalanuvchilar tahlili", 
            "• /downloads - Yuklamalar statistikasi",
            "",
            "🎵 <b>Musiqa:</b>",
            "• /top - Trend musiqalar ro'yxati",
            "• /find - Media fayllardan musiqa topish",
            "",
            "⚙️ <b>Boshqaruv:</b>",
            "• /admin - Admin panel havolasi",
            "• /help - Yordam ma'lumotlari",
            "",
            "🌐 <b>Veb Dashboard:</b>",
            "• Asosiy panel: /statistics/",
            "• Foydalanuvchilar: /analytics/users/",
            "• Yuklamalar: /analytics/downloads/",
            "",
            "📖 <b>Qo'llanma:</b>",
            "",
            "🔍 <b>Statistikalarni ko'rish:</b>",
            "1. /stats - Tezkor umumiy ma'lumotlar",
            "2. /users - Batafsil foydalanuvchilar tahlili",
            "3. /downloads - Platform bo'yicha yuklamalar",
            "",
            "📊 <b>Veb dashboarddan foydalanish:</b>",
            "1. Admin panelga kiring",
            "2. Statistika bo'limini tanlang",
            "3. Real vaqt grafiklari va jadvallarni ko'ring",
            "",
            "🎯 <b>Bot monitoring:</b>",
            "• Faol foydalanuvchilar soni",
            "• Kunlik ro'yxatdan o'tishlar",
            "• Platform bo'yicha yuklamalar",
            "• Mashhur qidiruv so'zlari",
            "",
            "⚡ <b>Tezkor amallar:</b>",
            "• /stats - Asosiy ko'rsatkichlar",
            "• /top - Trend musiqa ko'rsatish",
            "• Web panel orqali batafsil tahlil",
            "",
            "❓ <b>Yordam kerakmi?</b>",
            "Har qanday savol bo'lsa, /help buyrug'ini ishlatishingiz mumkin.",
            "",
            f"🔗 <b>Admin Panel:</b> {ADMIN_PANEL_URL}",
            "",
            "✅ Muvaffaqiyatli bot boshqaruvi!"
        ]
        
        # Send admin manual
        await message.reply(
            "\n".join(admin_manual),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        logging.info(f"Admin {message.from_user.id} ({user_first_name}) accessed admin start menu")
        
    except Exception as e:
        logging.error(f"Error in admin_start: {e}")
        await message.reply("❌ Admin menyusini ko'rsatishda xatolik yuz berdi.")


@dp.message_handler(Command("admin"), IsAdmin(), state="*")
async def admin_panel_link(message: types.Message, state: FSMContext):
    """Send admin panel link to admins."""
    
    try:
        await state.finish()
        
        panel_message = [
            "🌐 <b>Admin Panel</b>",
            "",
            f"🔗 <b>Havola:</b> {ADMIN_PANEL_URL}",
            "",
            "📊 <b>Mavjud bo'limlar:</b>",
            "• Foydalanuvchilar boshqaruvi",
            "• Chatlar ro'yxati", 
            "• Yuklamalar tarixchi",
            "• Qidiruv statistikalari",
            "• Reklama boshqaruvi",
            "",
            "⚙️ <b>Veb dashboard:</b>",
            "• /statistics/ - Asosiy statistikalar",
            "• /analytics/users/ - Foydalanuvchilar tahlili",
            "• /analytics/downloads/ - Yuklamalar tahlili",
            "",
            "🔒 <b>Xavfsizlik:</b>",
            "Admin panel faqat staff foydalanuvchilar uchun ochiq."
        ]
        
        await message.reply(
            "\n".join(panel_message),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        logging.info(f"Admin {message.from_user.id} requested admin panel link")
        
    except Exception as e:
        logging.error(f"Error in admin_panel_link: {e}")
        await message.reply("❌ Admin panel havolasini yuborishda xatolik yuz berdi.")


@dp.message_handler(Command("help"), IsAdmin(), state="*")
async def admin_help(message: types.Message, state: FSMContext):
    """Detailed help for admins."""
    
    try:
        await state.finish()
        
        help_text = [
            "📚 <b>Admin Yordam</b>",
            "",
            "🤖 <b>Bot haqida:</b>",
            "Bu bot YouTube, Instagram va TikTok'dan media yuklab olish,",
            "Shazam orqali musiqa topish va trend musiqalarni ko'rsatish uchun mo'ljallangan.",
            "",
            "👥 <b>Foydalanuvchilar:</b>",
            "• Bot orqali har qanday video/audio yuklab olish mumkin",
            "• Musiqa fayllari Shazam bilan tanib olinadi",
            "• Trend musiqalar /top buyrug'i orqali ko'riladi",
            "",
            "📊 <b>Monitoring:</b>",
            "/stats - Asosiy statistikalar:",
            "• Umumiy va faol foydalanuvchilar",
            "• Platform bo'yicha yuklamalar",
            "• Mashhur qidiruvlar",
            "",
            "/users - Foydalanuvchilar tahlili:",
            "• Kunlik ro'yxatdan o'tishlar", 
            "• Til bo'yicha taqsimot",
            "• Faollik darajasi",
            "",
            "/downloads - Yuklamalar tahlili:",
            "• Platform statistikalari",
            "• Trend grafiklari",
            "• So'nggi yuklamalar",
            "",
            "🌐 <b>Veb Dashboard:</b>",
            "• Real vaqt statistikalari",
            "• Interaktiv grafiklar",
            "• Batafsil jadvallar",
            "• Mobil moslashuvchan",
            "",
            "� <b>Texnik ma'lumotlar:</b>",
            "• aiogram 2.14.3 framework",
            "• Django admin panel",
            "• SQLite/PostgreSQL database", 
            "• YouTube API v3",
            "• Shazam API",
            "",
            "🆘 <b>Muammolar:</b>",
            "• Bot ishlamayotgan bo'lsa - loglarni tekshiring",
            "• API xatoliklari - kalitlarni yangilang",
            "• Database muammolari - backup yarating",
            "",
            "💡 <b>Maslahatlar:</b>",
            "• Kunlik statistikalarni kuzating",
            "• Mashhur qidiruvlarni tahlil qiling",
            "• Platform foydaliligini baholang",
            "• Foydalanuvchilar faolligini monitoring qiling",
            "",
            "📞 <b>Qo'shimcha yordam:</b>",
            "Texnik muammolar yoki takliflar bo'lsa,",
            "dasturchi bilan bog'laning."
        ]
        
        await message.reply(
            "\n".join(help_text),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        logging.info(f"Admin {message.from_user.id} requested help")
        
    except Exception as e:
        logging.error(f"Error in admin_help: {e}")
        await message.reply("❌ Yordam ma'lumotlarini ko'rsatishda xatolik yuz berdi.")