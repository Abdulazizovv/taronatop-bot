from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import BotUser, BotChat, YoutubeAudio, InstagramMedia, TikTokMedia, SearchQuery
import json


def is_staff_user(user):
    """Check if user is staff."""
    return user.is_authenticated and user.is_staff


@user_passes_test(is_staff_user)
def statistics_dashboard(request):
    """Main statistics dashboard view."""
    
    # Basic statistics
    total_users = BotUser.objects.count()
    active_users = BotUser.objects.filter(is_active=True).count()
    blocked_users = BotUser.objects.filter(is_active=False).count()
    
    total_chats = BotChat.objects.count()
    active_chats = BotChat.objects.filter(is_active=True).count()
    
    # Media statistics
    youtube_downloads = YoutubeAudio.objects.count()
    instagram_downloads = InstagramMedia.objects.count()
    tiktok_downloads = TikTokMedia.objects.count()
    total_downloads = youtube_downloads + instagram_downloads + tiktok_downloads
    
    # Search statistics
    total_searches = SearchQuery.objects.aggregate(
        total=Count('count')
    )['total'] or 0
    
    top_searches = SearchQuery.objects.order_by('-count')[:10]
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_users = BotUser.objects.filter(created_at__gte=thirty_days_ago).count()
    recent_downloads = (
        YoutubeAudio.objects.filter(created_at__gte=thirty_days_ago).count() +
        InstagramMedia.objects.filter(created_at__gte=thirty_days_ago).count() +
        TikTokMedia.objects.filter(created_at__gte=thirty_days_ago).count()
    )
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'total_chats': total_chats,
        'active_chats': active_chats,
        'youtube_downloads': youtube_downloads,
        'instagram_downloads': instagram_downloads,
        'tiktok_downloads': tiktok_downloads,
        'total_downloads': total_downloads,
        'total_searches': total_searches,
        'top_searches': top_searches,
        'recent_users': recent_users,
        'recent_downloads': recent_downloads,
    }
    
    return render(request, 'botapp/statistics.html', context)


@user_passes_test(is_staff_user)
def statistics_api(request):
    """API endpoint for statistics data."""
    
    # Get date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # User registration data by day
    user_data = []
    download_data = []
    search_data = []
    
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Users registered on this day
        day_users = BotUser.objects.filter(
            created_at__gte=day_start,
            created_at__lte=day_end
        ).count()
        
        # Downloads on this day
        day_downloads = (
            YoutubeAudio.objects.filter(
                created_at__gte=day_start,
                created_at__lte=day_end
            ).count() +
            InstagramMedia.objects.filter(
                created_at__gte=day_start,
                created_at__lte=day_end
            ).count() +
            TikTokMedia.objects.filter(
                created_at__gte=day_start,
                created_at__lte=day_end
            ).count()
        )
        
        # Searches on this day
        day_searches = SearchQuery.objects.filter(
            created_at__gte=day_start,
            created_at__lte=day_end
        ).aggregate(total=Count('count'))['total'] or 0
        
        user_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'users': day_users
        })
        
        download_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'downloads': day_downloads
        })
        
        search_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'searches': day_searches
        })
    
    return JsonResponse({
        'user_data': user_data,
        'download_data': download_data,
        'search_data': search_data
    })


@user_passes_test(is_staff_user)
def user_analytics(request):
    """Detailed user analytics view."""
    
    # User activity by language
    language_stats = BotUser.objects.values('language_code').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # User activity by status
    status_stats = {
        'active': BotUser.objects.filter(is_active=True).count(),
        'blocked': BotUser.objects.filter(is_active=False).count(),
        'admin': BotUser.objects.filter(is_admin=True).count(),
    }
    
    # Recent user registrations (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_users = BotUser.objects.filter(
        created_at__gte=seven_days_ago
    ).order_by('-created_at')[:50]
    
    context = {
        'language_stats': language_stats,
        'status_stats': status_stats,
        'recent_users': recent_users,
    }
    
    return render(request, 'botapp/user_analytics.html', context)


@user_passes_test(is_staff_user)
def download_analytics(request):
    """Detailed download analytics view."""
    
    # Download counts by platform
    platform_stats = {
        'youtube': YoutubeAudio.objects.count(),
        'instagram': InstagramMedia.objects.count(),
        'tiktok': TikTokMedia.objects.count(),
    }
    
    # Recent downloads
    recent_downloads = {
        'youtube': YoutubeAudio.objects.order_by('-created_at')[:20],
        'instagram': InstagramMedia.objects.order_by('-created_at')[:20],
        'tiktok': TikTokMedia.objects.order_by('-created_at')[:20],
    }
    
    # Download trends (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    download_trends = []
    
    for i in range(30):
        day = thirty_days_ago + timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        youtube_count = YoutubeAudio.objects.filter(
            created_at__gte=day_start,
            created_at__lte=day_end
        ).count()
        
        instagram_count = InstagramMedia.objects.filter(
            created_at__gte=day_start,
            created_at__lte=day_end
        ).count()
        
        tiktok_count = TikTokMedia.objects.filter(
            created_at__gte=day_start,
            created_at__lte=day_end
        ).count()
        
        download_trends.append({
            'date': day.strftime('%Y-%m-%d'),
            'youtube': youtube_count,
            'instagram': instagram_count,
            'tiktok': tiktok_count,
            'total': youtube_count + instagram_count + tiktok_count
        })
    
    context = {
        'platform_stats': platform_stats,
        'recent_downloads': recent_downloads,
        'download_trends': download_trends,
    }
    
    return render(request, 'botapp/download_analytics.html', context)
