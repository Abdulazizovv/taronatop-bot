from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from bot.filters.is_admin import IsAdmin
from bot.loader import dp, db
from bot.data.config import ADMINS
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q
from botapp.models import BotUser, BotChat, YoutubeAudio, InstagramMedia, TikTokMedia, SearchQuery
import asyncio


async def get_bot_statistics():
    """Get comprehensive bot statistics."""
    try:
        # Basic user statistics
        total_users = await db.get_users_count()
        active_users = await db.get_active_users_count()
        blocked_users = await db.get_blocked_users_count()
        
        # Get recent activity (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_users = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: BotUser.objects.filter(created_at__gte=seven_days_ago).count()
        )
        
        # Chat statistics
        total_chats = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: BotChat.objects.count()
        )
        
        active_chats = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: BotChat.objects.filter(is_active=True).count()
        )
        
        # Media statistics
        youtube_downloads = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: YoutubeAudio.objects.count()
        )
        
        instagram_downloads = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: InstagramMedia.objects.count()
        )
        
        tiktok_downloads = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: TikTokMedia.objects.count()
        )
        
        # Search statistics
        total_searches = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: SearchQuery.objects.aggregate(total=Count('count'))['total'] or 0
        )
        
        # Top search queries
        top_searches = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: list(SearchQuery.objects.order_by('-count')[:5].values('query', 'count'))
        )
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'blocked_users': blocked_users,
            'recent_users': recent_users,
            'total_chats': total_chats,
            'active_chats': active_chats,
            'youtube_downloads': youtube_downloads,
            'instagram_downloads': instagram_downloads,
            'tiktok_downloads': tiktok_downloads,
            'total_searches': total_searches,
            'top_searches': top_searches
        }
        
    except Exception as e:
        logging.error(f"Error getting bot statistics: {e}")
        return None


def format_statistics_message(stats):
    """Format statistics into a readable message."""
    if not stats:
        return "❌ Statistikalarni olishda xatolik yuz berdi."
    
    message = [
        "📊 <b>Bot Statistikalari</b>",
        "=" * 30,
        "",
        "👥 <b>Foydalanuvchilar:</b>",
        f"• Jami: {stats['total_users']:,}",
        f"• Faol: {stats['active_users']:,}",
        f"• Bloklangan: {stats['blocked_users']:,}",
        f"• Oxirgi 7 kunlik: {stats['recent_users']:,}",
        "",
        "💬 <b>Chatlar:</b>",
        f"• Jami: {stats['total_chats']:,}",
        f"• Faol: {stats['active_chats']:,}",
        "",
        "📥 <b>Yuklamalar:</b>",
        f"• YouTube: {stats['youtube_downloads']:,}",
        f"• Instagram: {stats['instagram_downloads']:,}",
        f"• TikTok: {stats['tiktok_downloads']:,}",
        f"• Jami: {stats['youtube_downloads'] + stats['instagram_downloads'] + stats['tiktok_downloads']:,}",
        "",
        "🔍 <b>Qidiruvlar:</b>",
        f"• Jami: {stats['total_searches']:,}",
        ""
    ]
    
    if stats['top_searches']:
        message.append("🔥 <b>Top qidiruvlar:</b>")
        for i, search in enumerate(stats['top_searches'], 1):
            message.append(f"{i}. {search['query']} ({search['count']} marta)")
    else:
        message.append("🔍 Hali qidiruvlar yo'q")
    
    message.extend([
        "",
        f"🕐 Yangilangan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ])
    
    return "\n".join(message)


@dp.message_handler(Command("stats"), IsAdmin(), state="*")
async def admin_statistics(message: types.Message, state: FSMContext):
    """Handle /stats command for admins."""
    
    try:
        # Clear any active state
        await state.finish()
        
        # Send loading message
        loading_msg = await message.reply("📊 Statistikalar yuklanmoqda...")
        
        # Get statistics
        stats = await get_bot_statistics()
        
        if stats:
            text = format_statistics_message(stats)
            await loading_msg.edit_text(text, parse_mode="HTML")
        else:
            await loading_msg.edit_text("❌ Statistikalarni olishda xatolik yuz berdi.")
            
        logging.info(f"Admin {message.from_user.id} requested bot statistics")
        
    except Exception as e:
        logging.error(f"Error in admin_statistics: {e}")
        await message.reply("❌ Statistikalarni ko'rsatishda xatolik yuz berdi.")


@dp.message_handler(Command("users"), IsAdmin(), state="*")
async def admin_users_stats(message: types.Message, state: FSMContext):
    """Handle /users command for detailed user statistics."""
    
    try:
        await state.finish()
        
        loading_msg = await message.reply("👥 Foydalanuvchi statistikalari yuklanmoqda...")
        
        # Get detailed user statistics
        total_users = await db.get_users_count()
        active_users = await db.get_active_users_count()
        blocked_users = await db.get_blocked_users_count()
        
        # Get user registration statistics by days
        now = timezone.now()
        today = now.date()
        
        stats_by_days = []
        for i in range(7):
            day = today - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))
            
            day_users = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda start=day_start, end=day_end: BotUser.objects.filter(
                    created_at__gte=start,
                    created_at__lte=end
                ).count()
            )
            
            stats_by_days.append({
                'date': day.strftime('%Y-%m-%d'),
                'users': day_users
            })
        
        # Format message
        message_text = [
            "👥 <b>Foydalanuvchi Statistikalari</b>",
            "=" * 35,
            "",
            f"📊 <b>Umumiy ma'lumotlar:</b>",
            f"• Jami foydalanuvchilar: {total_users:,}",
            f"• Faol foydalanuvchilar: {active_users:,}",
            f"• Bloklangan: {blocked_users:,}",
            f"• Faol foiz: {(active_users/total_users*100) if total_users > 0 else 0:.1f}%",
            "",
            "📅 <b>Oxirgi 7 kunlik ro'yxatdan o'tish:</b>"
        ]
        
        for day_stat in stats_by_days:
            message_text.append(f"• {day_stat['date']}: {day_stat['users']} ta")
        
        total_week = sum(day['users'] for day in stats_by_days)
        message_text.extend([
            "",
            f"📈 Haftalik jami: {total_week} ta yangi foydalanuvchi",
            f"🕐 Yangilangan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ])
        
        await loading_msg.edit_text("\n".join(message_text), parse_mode="HTML")
        
        logging.info(f"Admin {message.from_user.id} requested user statistics")
        
    except Exception as e:
        logging.error(f"Error in admin_users_stats: {e}")
        await message.reply("❌ Foydalanuvchi statistikalarini ko'rsatishda xatolik yuz berdi.")


@dp.message_handler(Command("downloads"), IsAdmin(), state="*") 
async def admin_downloads_stats(message: types.Message, state: FSMContext):
    """Handle /downloads command for media download statistics."""
    
    try:
        await state.finish()
        
        loading_msg = await message.reply("📥 Yuklamalar statistikasi yuklanmoqda...")
        
        # Get download statistics by platform
        youtube_count = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: YoutubeAudio.objects.count()
        )
        
        instagram_count = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: InstagramMedia.objects.count()
        )
        
        tiktok_count = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: TikTokMedia.objects.count()
        )
        
        # Get recent downloads (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        recent_youtube = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: YoutubeAudio.objects.filter(created_at__gte=seven_days_ago).count()
        )
        
        recent_instagram = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: InstagramMedia.objects.filter(created_at__gte=seven_days_ago).count()
        )
        
        recent_tiktok = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: TikTokMedia.objects.filter(created_at__gte=seven_days_ago).count()
        )
        
        total_downloads = youtube_count + instagram_count + tiktok_count
        total_recent = recent_youtube + recent_instagram + recent_tiktok
        
        # Format message
        message_text = [
            "📥 <b>Yuklamalar Statistikasi</b>",
            "=" * 30,
            "",
            "📊 <b>Platformalar bo'yicha:</b>",
            f"🎵 YouTube: {youtube_count:,}",
            f"📸 Instagram: {instagram_count:,}",
            f"🎥 TikTok: {tiktok_count:,}",
            f"📦 Jami: {total_downloads:,}",
            "",
            "📅 <b>Oxirgi 7 kun:</b>",
            f"🎵 YouTube: {recent_youtube:,}",
            f"📸 Instagram: {recent_instagram:,}",
            f"🎥 TikTok: {recent_tiktok:,}",
            f"📦 Jami: {total_recent:,}",
            ""
        ]
        
        if total_downloads > 0:
            message_text.extend([
                "📈 <b>Foizlar:</b>",
                f"🎵 YouTube: {(youtube_count/total_downloads*100):.1f}%",
                f"📸 Instagram: {(instagram_count/total_downloads*100):.1f}%",
                f"🎥 TikTok: {(tiktok_count/total_downloads*100):.1f}%",
                ""
            ])
        
        message_text.append(f"🕐 Yangilangan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await loading_msg.edit_text("\n".join(message_text), parse_mode="HTML")
        
        logging.info(f"Admin {message.from_user.id} requested download statistics")
        
    except Exception as e:
        logging.error(f"Error in admin_downloads_stats: {e}")
        await message.reply("❌ Yuklamalar statistikasini ko'rsatishda xatolik yuz berdi.")
