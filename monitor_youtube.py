#!/usr/bin/env python3
"""
YouTube Bot Detection Monitor
Tracks and analyzes bot detection patterns
"""

import re
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter

def analyze_bot_detection_logs(log_file="logs/bot.log", hours=24):
    """Analyze bot detection patterns from logs"""
    
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    bot_detections = []
    download_attempts = []
    errors = []
    
    print(f"🔍 Analyzing last {hours} hours of logs...\n")
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                # Parse timestamp
                timestamp_match = re.search(r'\[([\d\-\s:,]+)\]', line)
                if not timestamp_match:
                    continue
                
                try:
                    timestamp_str = timestamp_match.group(1).split(',')[0]  # Remove milliseconds
                    log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    if log_time < cutoff_time:
                        continue
                        
                except ValueError:
                    continue
                
                # Categorize log entries
                if "Sign in to confirm" in line or "bot" in line.lower():
                    bot_detections.append((log_time, line.strip()))
                elif "download" in line.lower() and ("music" in line.lower() or "video" in line.lower()):
                    download_attempts.append((log_time, line.strip()))
                elif "ERROR" in line or "Failed" in line:
                    errors.append((log_time, line.strip()))
    
    except Exception as e:
        print(f"Error reading log file: {e}")
        return
    
    # Analysis
    print(f"📊 Analysis Results (Last {hours} hours):")
    print(f"{'='*50}")
    print(f"🤖 Bot detections: {len(bot_detections)}")
    print(f"📥 Download attempts: {len(download_attempts)}")
    print(f"❌ Errors: {len(errors)}")
    
    if bot_detections:
        print(f"\n🚨 Bot Detection Events:")
        for time, event in bot_detections[-5:]:  # Last 5 events
            print(f"  {time.strftime('%H:%M:%S')} - {event[:100]}...")
    
    # Success rate
    if download_attempts:
        success_rate = max(0, (len(download_attempts) - len(bot_detections)) / len(download_attempts) * 100)
        print(f"\n📈 Estimated Success Rate: {success_rate:.1f}%")
    
    # Hourly pattern
    if bot_detections:
        hourly_detections = defaultdict(int)
        for time, _ in bot_detections:
            hourly_detections[time.hour] += 1
        
        print(f"\n🕐 Bot Detection by Hour:")
        for hour in sorted(hourly_detections.keys()):
            count = hourly_detections[hour]
            bar = "█" * min(count, 20)
            print(f"  {hour:02d}:00 - {count:2d} {bar}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    
    if len(bot_detections) > 10:
        print("  🚨 HIGH bot detection rate detected!")
        print("  ✅ Export fresh cookies.txt from browser")
        print("  ✅ Consider using VPN or proxy")
        print("  ✅ Reduce download frequency")
    elif len(bot_detections) > 5:
        print("  ⚠️  Moderate bot detection rate")
        print("  ✅ Update cookies.txt if older than 30 days")
        print("  ✅ Monitor rate limiting")
    else:
        print("  ✅ Bot detection rate is acceptable")
        print("  ✅ Current setup appears to be working well")

def check_current_status():
    """Check current YouTube access status"""
    print("\n🔧 Testing Current YouTube Access:")
    print("=" * 40)
    
    try:
        from bot.utils.youtube import get_enhanced_ydl_opts
        from yt_dlp import YoutubeDL
        
        # Test enhanced options
        opts = get_enhanced_ydl_opts()
        cookies_enabled = 'cookiefile' in opts
        headers_enabled = 'http_headers' in opts
        
        print(f"🍪 Cookies: {'✅ Enabled' if cookies_enabled else '❌ Disabled'}")
        print(f"🌐 Enhanced headers: {'✅ Enabled' if headers_enabled else '❌ Disabled'}")
        
        # Test actual access
        test_opts = opts.copy()
        test_opts.update({
            'quiet': True,
            'no_warnings': True,
            'skip_download': True
        })
        
        with YoutubeDL(test_opts) as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False)
        
        print(f"🎯 YouTube access: ✅ Working")
        print(f"📺 Test video: {info.get('title', 'Unknown')}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"🎯 YouTube access: ❌ Failed")
        
        if "Sign in to confirm" in error_msg:
            print(f"🚨 Bot detection triggered!")
            print(f"💡 Solution: Export cookies.txt from browser")
        else:
            print(f"❌ Error: {error_msg}")

if __name__ == "__main__":
    print("🔍 YouTube Bot Detection Monitor")
    print("=" * 50)
    
    # Analyze logs
    analyze_bot_detection_logs()
    
    # Check current status
    check_current_status()
    
    print(f"\n📚 For help with cookies setup, run:")
    print(f"   python setup_cookies.py")
    print(f"\n📚 For comprehensive guide, see:")
    print(f"   setup_youtube_cookies.md")
