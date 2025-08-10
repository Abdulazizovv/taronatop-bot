#!/usr/bin/env python3
"""
Test script for YouTube API fallback mechanism
Run this to test if yt-dlp fallback works when API quota exceeded
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.utils.youtube import search_youtube_with_ytdlp, YouTubeSearch
import logging

logging.basicConfig(level=logging.INFO)

def test_ytdlp_fallback():
    """Test yt-dlp fallback search functionality"""
    print("Testing yt-dlp fallback search...")
    
    try:
        results = search_youtube_with_ytdlp("Uzbek music", max_results=5)
        print(f"✅ yt-dlp search found {len(results)} results")
        
        for i, result in enumerate(results[:3], 1):
            print(f"{i}. {result['title']} - {result['channel']}")
            
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ yt-dlp fallback failed: {e}")
        return False

def test_api_search():
    """Test API search with fallback"""
    print("\nTesting YouTube API search with fallback...")
    
    try:
        searcher = YouTubeSearch("Uzbek music", max_results=5)
        results = searcher.to_dict()
        print(f"✅ Search found {len(results)} results")
        
        for i, result in enumerate(results[:3], 1):
            print(f"{i}. {result['title']} - {result['channel']}")
            
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ API search failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing YouTube Search Fallback Mechanism\n")
    
    # Test 1: yt-dlp fallback
    fallback_works = test_ytdlp_fallback()
    
    # Test 2: Full search with fallback
    search_works = test_api_search()
    
    print(f"\n📊 Test Results:")
    print(f"  yt-dlp fallback: {'✅ Working' if fallback_works else '❌ Failed'}")
    print(f"  API + fallback:  {'✅ Working' if search_works else '❌ Failed'}")
    
    if fallback_works:
        print("\n🎉 Fallback mechanism is working! Your bot will continue functioning even when API quota is exceeded.")
    else:
        print("\n⚠️  Fallback mechanism failed. Check yt-dlp installation.")
