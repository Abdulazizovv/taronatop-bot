#!/usr/bin/env python3
"""
Standalone YouTube Bot Detection Test
Tests YouTube access without Django dependencies
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_youtube_access():
    """Test YouTube access with current setup"""
    print("🔧 Testing YouTube Access (Standalone)")
    print("=" * 50)
    
    try:
        # Test basic yt-dlp access
        from yt_dlp import YoutubeDL
        
        # Enhanced options (same as in youtube.py)
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            
            # Anti-bot measures
            "extractor_retries": 3,
            "fragment_retries": 3,
            "retries": 3,
            "sleep_interval_requests": 1,
            
            # Browser-like headers
            "http_headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        }
        
        # Check for cookies
        cookies_file = "cookies.txt"
        if os.path.exists(cookies_file):
            with open(cookies_file, 'r') as f:
                content = f.read()
                if 'youtube.com' in content and len(content) > 200:
                    ydl_opts["cookiefile"] = cookies_file
                    print("🍪 Cookies: ✅ Found and loaded")
                else:
                    print("🍪 Cookies: ⚠️  Found but invalid")
        else:
            print("🍪 Cookies: ❌ Not found")
        
        print("🌐 Enhanced headers: ✅ Enabled")
        print("🔄 Retries & delays: ✅ Enabled")
        
        # Test actual YouTube access
        print("\n🎯 Testing YouTube access...")
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
        
        print("✅ YouTube access: WORKING")
        print(f"📺 Test video: {info.get('title', 'Unknown')}")
        print(f"🎵 Duration: {info.get('duration', 0)} seconds")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ YouTube access: FAILED")
        print(f"Error: {error_msg}")
        
        if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
            print("\n🚨 BOT DETECTION TRIGGERED!")
            print("💡 Solutions:")
            print("  1. Export cookies.txt from your browser")
            print("  2. Use VPN or proxy")
            print("  3. Wait and try again later")
            print("  4. Try from different IP address")
        
        return False

def test_download():
    """Test actual download functionality"""
    print("\n🎵 Testing Download Functionality")
    print("=" * 40)
    
    try:
        from yt_dlp import YoutubeDL
        import tempfile
        
        # Download test (very short video)
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        ydl_opts = {
            "format": "bestaudio/best",  # More flexible format selection
            "outtmpl": os.path.join(tempfile.gettempdir(), "%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128"
            }],
            "quiet": True,
            "no_warnings": True,
            "no_check_certificate": True,
            
            # Anti-bot measures
            "extractor_retries": 2,
            "retries": 2,
            "sleep_interval": 1,
            
            # Headers
            "http_headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        # Add cookies if available
        if os.path.exists("cookies.txt"):
            ydl_opts["cookiefile"] = "cookies.txt"
        
        print("🎵 Attempting download...")
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=True)
        
        print("✅ Download: SUCCESSFUL")
        print(f"📁 File: {info.get('id', 'unknown')}.mp3")
        
        # Cleanup
        try:
            mp3_file = os.path.join(tempfile.gettempdir(), f"{info['id']}.mp3")
            if os.path.exists(mp3_file):
                os.remove(mp3_file)
                print("🗑️  Cleanup: Done")
        except:
            pass
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Download: FAILED")
        print(f"Error: {error_msg}")
        
        if "Sign in to confirm" in error_msg:
            print("🚨 Bot detection during download!")
        
        return False

def check_api_keys():
    """Check YouTube API keys"""
    print("\n🔑 Checking API Keys")
    print("=" * 30)
    
    api_keys = [
        os.getenv("YOUTUBE_API_KEY"),
        os.getenv("YOUTUBE_API_KEY_2"),
        os.getenv("YOUTUBE_API_KEY_3"),
    ]
    
    valid_keys = [key for key in api_keys if key]
    
    print(f"📊 Found {len(valid_keys)} API keys")
    
    for i, key in enumerate(valid_keys, 1):
        masked_key = key[:10] + "..." + key[-4:] if len(key) > 14 else key
        print(f"  Key {i}: {masked_key}")
    
    return len(valid_keys) > 0

if __name__ == "__main__":
    print("🔧 YouTube Bot Detection Standalone Test")
    print("=" * 60)
    
    # Check API keys
    has_api_keys = check_api_keys()
    
    # Test YouTube access
    access_works = test_youtube_access()
    
    # Test download if access works
    download_works = False
    if access_works:
        download_works = test_download()
    
    # Summary
    print(f"\n📊 Test Summary")
    print("=" * 20)
    print(f"🔑 API Keys: {'✅' if has_api_keys else '❌'}")
    print(f"🌐 YouTube Access: {'✅' if access_works else '❌'}")
    print(f"🎵 Download: {'✅' if download_works else '❌'}")
    
    if access_works and download_works:
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"Your bot should work without bot detection errors.")
    elif access_works:
        print(f"\n⚠️  Access works but download failed")
        print(f"Check FFmpeg installation and file permissions")
    else:
        print(f"\n❌ Bot detection is blocking access")
        print(f"Run: python setup_cookies.py")
        print(f"Read: setup_youtube_cookies.md")
