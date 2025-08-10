# YouTube API Key Setup Guide

## Problem
Your bot hit the YouTube Data API quota limit (10,000 units per day). This happens when your bot processes many search requests.

## Solution: Multiple API Keys

### Step 1: Create Additional YouTube API Keys

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create 4-5 new projects (or use existing ones)
3. Enable YouTube Data API v3 for each project
4. Create API keys for each project
5. Add these keys to your environment variables

### Step 2: Environment Variables Setup

Add these to your `.env` file or environment:

```bash
# Primary API key (existing)
YOUTUBE_API_KEY=AIzaSyAwPkzuxxxxxxxxxxxxxxxxxxxxxxxx

# Additional API keys for quota management
YOUTUBE_API_KEY_2=AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
YOUTUBE_API_KEY_3=AIzaSyCxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
YOUTUBE_API_KEY_4=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
YOUTUBE_API_KEY_5=AIzaSyExxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 3: Quota Management Features Implemented

✅ **API Key Rotation**: Automatically switches to next key when quota exceeded
✅ **Fallback to yt-dlp**: Uses yt-dlp search when all API keys exhausted
✅ **Error Handling**: Graceful degradation without bot crashes
✅ **Logging**: Tracks which API key is used and when rotation occurs

### Step 4: Alternative Solutions

If you don't want multiple API keys:

#### Option A: Increase Quota (Paid)
- Go to Google Cloud Console → APIs & Services → Quotas
- Request quota increase (costs $0.1 per 100 requests beyond free tier)

#### Option B: Use Only yt-dlp (Free but slower)
- Comment out API search in `YouTubeSearch._search_youtube()`
- Rely entirely on yt-dlp fallback

#### Option C: Implement Caching
- Cache search results for popular queries
- Reduce API calls for repeated searches

### Step 5: Monitor Usage

Check your API usage:
1. Go to Google Cloud Console
2. Navigate to APIs & Services → Dashboard
3. Click on YouTube Data API v3
4. View quotas and usage

### Current Implementation Benefits

1. **Zero Downtime**: Bot continues working even when quotas exceeded
2. **Smart Rotation**: Only rotates keys when needed
3. **Fallback Search**: yt-dlp provides search when APIs exhausted
4. **Backward Compatible**: Works with single API key setup
5. **Automatic Recovery**: Retries with fresh keys

### Testing the Fix

After adding multiple API keys, your bot will:
1. Use primary key until quota exceeded
2. Rotate to secondary keys automatically
3. Fall back to yt-dlp if all keys exhausted
4. Continue functioning without interruption

The error you saw should not occur anymore with this implementation.
