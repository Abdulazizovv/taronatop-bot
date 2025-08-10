# YouTube Bot Detection Fix Guide

## Problem
YouTube is blocking yt-dlp with "Sign in to confirm you're not a bot" error. This happens when YouTube detects automated requests.

## Solutions Implemented

### ✅ Solution 1: Enhanced Anti-Bot Measures (Already Applied)
- Added browser-like headers
- Implemented request delays and retries
- Enhanced error handling with specific bot detection

### ✅ Solution 2: Cookies Authentication (Recommended)

#### Step 1: Export YouTube Cookies

**Method A: Using Browser Extension (Easiest)**
1. Install "Get cookies.txt" extension for Chrome/Firefox
2. Go to youtube.com and login to your account
3. Click the extension icon and export cookies
4. Save as `cookies.txt` in your bot directory

**Method B: Manual Export (Advanced)**
1. Open YouTube in browser and login
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies → youtube.com
4. Copy all cookies and save in Netscape format

#### Step 2: Place Cookies File
```bash
# Copy cookies.txt to your bot directory
cp cookies.txt /home/abdulazizov/myProjects/paid/taronatop_bot/
```

#### Step 3: Verify Cookies
```bash
# Test if cookies work
cd /home/abdulazizov/myProjects/paid/taronatop_bot
yt-dlp --cookies cookies.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --skip-download
```

### ✅ Solution 3: Alternative Approaches

#### Option A: Use Proxy/VPN
```bash
# Add to your environment
PROXY_URL=http://your-proxy:port
```

#### Option B: YouTube Premium Account
- Use YouTube Premium account cookies
- Premium accounts have higher rate limits

#### Option C: Multiple IP Rotation
- Use different IP addresses for requests
- Implement IP rotation system

## Files Updated

### 1. `/bot/utils/youtube.py`
- ✅ Added `get_enhanced_ydl_opts()` function
- ✅ Enhanced `download_music()` with anti-bot measures
- ✅ Enhanced `download_video()` with error handling
- ✅ Added specific bot detection error messages

### 2. `/.env`
- ✅ Fixed `YOUTUBE_API_KEY_2` naming (was `YOUTUBE_API_KEY2`)
- ✅ Added third API key

## Testing the Fix

### Test 1: Check if cookies are detected
```bash
cd /home/abdulazizov/myProjects/paid/taronatop_bot
python -c "
import os
from bot.utils.youtube import get_enhanced_ydl_opts
opts = get_enhanced_ydl_opts()
print('Cookies found!' if 'cookiefile' in opts else 'No cookies found')
print('Enhanced headers:', 'User-Agent' in opts.get('http_headers', {}))
"
```

### Test 2: Download test
```bash
cd /home/abdulazizov/myProjects/paid/taronatop_bot
python -c "
import asyncio
from bot.utils.youtube import download_music
asyncio.run(download_music('https://www.youtube.com/watch?v=dQw4w9WgXcQ'))
"
```

## Expected Results

### Before Fix:
```
RuntimeError: Music download failed: ERROR: [youtube] EqF94URnTeM: Sign in to confirm you're not a bot.
```

### After Fix:
```
# With cookies:
INFO:root:Using cookies.txt for YouTube authentication
# Download successful

# Without cookies but with enhanced headers:
# Should work for most videos, may occasionally fail for protected content
```

## Troubleshooting

### Issue 1: Still getting bot detection
**Solution**: 
1. Export fresh cookies from a real browser session
2. Ensure cookies.txt is in correct Netscape format
3. Try using different YouTube account

### Issue 2: Cookies expire
**Solution**: 
1. Cookies expire after ~30 days
2. Set up automated cookie refresh
3. Use multiple accounts for rotation

### Issue 3: Rate limiting
**Solution**: 
1. Add delays between requests
2. Use multiple API keys (already implemented)
3. Implement request queuing

## Monitoring

### Check logs for bot detection:
```bash
tail -f logs/bot.log | grep -i "bot detection"
```

### Monitor success rate:
```bash
grep -c "Download successful" logs/bot.log
grep -c "bot detection" logs/bot.log
```

## Advanced Solutions (If Basic Fixes Don't Work)

### 1. Docker with VPN
```dockerfile
# Add VPN to your docker-compose.yml
version: '3.8'
services:
  vpn:
    image: dperson/openvpn-client
    # ... VPN configuration
  
  bot:
    depends_on:
      - vpn
    network_mode: "service:vpn"
```

### 2. Proxy Rotation
```python
# Add to config.py
PROXY_LIST = [
    "http://proxy1:port",
    "http://proxy2:port",
    # ... more proxies
]
```

### 3. Account Pool
```python
# Multiple YouTube accounts with cookies
YOUTUBE_ACCOUNTS = [
    "cookies_account1.txt",
    "cookies_account2.txt",
    # ... more accounts
]
```

The implemented solution should resolve most bot detection issues. If problems persist, follow the advanced solutions or export fresh cookies from your browser.
