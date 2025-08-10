#!/usr/bin/env python3
"""
Cookie Setup Helper for YouTube Bot Detection Fix
This script helps you set up cookies.txt for yt-dlp
"""

import os
import sys

def check_cookies_file():
    """Check if cookies.txt exists and is valid"""
    cookies_paths = [
        "cookies.txt",
        os.path.join(os.path.dirname(__file__), "cookies.txt")
    ]
    
    for path in cookies_paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                content = f.read()
                if 'youtube.com' in content and len(content) > 100:
                    print(f"✅ Valid cookies.txt found: {path}")
                    return True
                else:
                    print(f"⚠️  Invalid cookies.txt found: {path}")
    
    print("❌ No valid cookies.txt found")
    return False

def create_sample_cookies():
    """Create a sample cookies.txt with instructions"""
    sample_content = """# Netscape HTTP Cookie File
# This is a generated file! Do not edit.

# Instructions:
# 1. Go to youtube.com in your browser and login
# 2. Install "Get cookies.txt" browser extension
# 3. Export cookies and replace this file
# 4. Or use browser developer tools to manually export

# Sample format (replace with real cookies):
# .youtube.com	TRUE	/	TRUE	1234567890	cookie_name	cookie_value

# Real cookies should look like this:
# .youtube.com	TRUE	/	FALSE	1735689600	VISITOR_INFO1_LIVE	sample_value_here
# .youtube.com	TRUE	/	TRUE	1735689600	YSC	sample_ysc_value
"""
    
    with open('cookies.txt', 'w') as f:
        f.write(sample_content)
    
    print("📝 Created sample cookies.txt file")
    print("Please replace it with real cookies from your browser")

def test_youtube_access():
    """Test if yt-dlp can access YouTube with current setup"""
    try:
        from yt_dlp import YoutubeDL
        
        opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        
        if os.path.exists('cookies.txt'):
            opts['cookiefile'] = 'cookies.txt'
        
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False)
            
        print("✅ YouTube access test passed!")
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
            print("❌ Bot detection triggered - cookies needed")
        else:
            print(f"❌ YouTube access failed: {error_msg}")
        return False

def main():
    print("🔧 YouTube Cookies Setup Helper\n")
    
    # Check current status
    print("1. Checking for cookies.txt...")
    cookies_exist = check_cookies_file()
    
    # Test YouTube access
    print("\n2. Testing YouTube access...")
    access_works = test_youtube_access()
    
    # Provide recommendations
    print(f"\n📊 Status Report:")
    print(f"  Cookies file: {'✅ Found' if cookies_exist else '❌ Missing'}")
    print(f"  YouTube access: {'✅ Working' if access_works else '❌ Blocked'}")
    
    if not cookies_exist:
        print(f"\n💡 Recommendations:")
        print(f"  1. Install 'Get cookies.txt' browser extension")
        print(f"  2. Login to youtube.com in your browser")
        print(f"  3. Export cookies and save as cookies.txt")
        print(f"  4. Run this script again to test")
        
        create_sample = input("\nCreate sample cookies.txt file? (y/n): ")
        if create_sample.lower() == 'y':
            create_sample_cookies()
    
    elif not access_works:
        print(f"\n💡 Recommendations:")
        print(f"  1. Export fresh cookies from browser")
        print(f"  2. Ensure you're logged into YouTube")
        print(f"  3. Try using different YouTube account")
        print(f"  4. Check cookies.txt format (Netscape format required)")
    
    else:
        print(f"\n🎉 Everything is working correctly!")
        print(f"Your bot should no longer get bot detection errors.")

if __name__ == "__main__":
    main()
