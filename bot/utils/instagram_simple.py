import os
import logging
import asyncio
import subprocess
import re
from typing import Optional, Tuple
from uuid import uuid4
from yt_dlp.utils import sanitize_filename

# === Constants ===
TEMP_DIR = "/var/tmp/taronatop_bot"
os.makedirs(TEMP_DIR, exist_ok=True)

# === Simple Instagram Downloader (yt-dlp only) ===
async def download_instagram_media_simple(instagram_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Oddiy Instagram media downloader - faqat yt-dlp
    """
    try:
        shortcode = extract_shortcode(instagram_url)
        title = f"instagram_{shortcode or uuid4().hex[:8]}"
        
        # Try different yt-dlp approaches
        approaches = [
            # Approach 1: Modern mobile UA
            {
                "format": "best[height<=1080]",
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "extractor_args": ["instagram:api_version=v1"]
            },
            # Approach 2: Android UA
            {
                "format": "best",
                "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36",
                "extractor_args": []
            },
            # Approach 3: Desktop UA
            {
                "format": "best",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
                "extractor_args": []
            },
            # Approach 4: Simple
            {
                "format": "best",
                "user_agent": "",
                "extractor_args": []
            }
        ]
        
        for i, approach in enumerate(approaches):
            try:
                logging.info(f"Trying download approach {i+1}/4")
                
                output_path = os.path.join(TEMP_DIR, f"{title}_v{i+1}.%(ext)s")
                
                # Build yt-dlp command
                cmd = [
                    "yt-dlp",
                    "--no-warnings",
                    "--quiet",
                    "--format", approach["format"],
                    "--output", output_path
                ]
                
                if approach["user_agent"]:
                    cmd.extend(["--user-agent", approach["user_agent"]])
                
                for arg in approach["extractor_args"]:
                    cmd.extend(["--extractor-args", arg])
                
                cmd.append(instagram_url)
                
                # Execute
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=25)
                
                if process.returncode == 0:
                    # Find downloaded file
                    for ext in ['mp4', 'webm', 'mov', 'avi', 'mkv']:
                        file_path = os.path.join(TEMP_DIR, f"{title}_v{i+1}.{ext}")
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:  # At least 1KB
                            logging.info(f"Success with approach {i+1}: {file_path}")
                            return file_path, title, shortcode or "unknown"
                else:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    logging.warning(f"Approach {i+1} failed: {error_msg}")
                    
            except asyncio.TimeoutError:
                logging.warning(f"Approach {i+1} timed out")
                continue
            except Exception as e:
                logging.warning(f"Approach {i+1} error: {str(e)}")
                continue
        
        logging.error("All download approaches failed")
        return None
        
    except Exception as e:
        logging.error(f"Simple Instagram download failed: {str(e)}")
        return None

def extract_shortcode(url: str) -> Optional[str]:
    """
    URL dan shortcode ajratib oladi
    """
    try:
        patterns = [
            r'/p/([A-Za-z0-9_-]+)',
            r'/reel/([A-Za-z0-9_-]+)',
            r'/tv/([A-Za-z0-9_-]+)',
            r'/stories/[^/]+/([A-Za-z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
        
    except Exception:
        return None

async def convert_instagram_video_to_audio_simple(insta_url: str) -> Optional[str]:
    """
    Instagram videosini audio ga o'giradi (simple)
    """
    try:
        # Download video
        result = await download_instagram_media_simple(insta_url)
        if not result:
            return None
        
        video_path, title, media_id = result
        
        # Convert to audio
        audio_path = os.path.splitext(video_path)[0] + ".mp3"
        
        try:
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",  # No video
                "-acodec", "mp3",
                "-ab", "192k",
                "-ar", "44100",
                "-y",  # Overwrite
                audio_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode == 0 and os.path.exists(audio_path):
                # Remove video file
                if os.path.exists(video_path):
                    os.remove(video_path)
                    
                logging.info(f"Audio conversion successful: {audio_path}")
                return audio_path
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logging.error(f"FFmpeg conversion failed: {error_msg}")
                return None
                
        except asyncio.TimeoutError:
            logging.error("FFmpeg conversion timed out")
            return None
        except Exception as e:
            logging.error(f"FFmpeg error: {str(e)}")
            return None
            
    except Exception as e:
        logging.error(f"Failed to convert Instagram video to audio: {str(e)}")
        return None

async def get_instagram_media_info_simple(insta_url: str) -> Optional[dict]:
    """
    Media haqida ma'lumot oladi (simple)
    """
    try:
        shortcode = extract_shortcode(insta_url)
        return {
            "title": f"Instagram Media {shortcode or 'Unknown'}",
            "id": shortcode or "unknown",
            "description": "Instagram Media",
            "thumbnail": "",
            "uploader": "Unknown",
            "duration": 0,
        }
    except Exception as e:
        logging.error(f"Failed to get Instagram media info: {str(e)}")
        return None

# === Shazam integration ===
async def find_music_name(audio_file: str) -> Optional[str]:
    """
    Audio fayldan Shazam yordamida musiqa nomini aniqlaydi
    """
    try:
        from shazamio import Shazam
        shazam = Shazam()
        result = await shazam.recognize(audio_file)

        if result and "track" in result:
            track = result["track"]
            title = track.get("title", "Unknown")
            artist = track.get("subtitle", "Unknown")
            return f"{title} – {artist}"

    except Exception as e:
        logging.error(f"[Shazam Error] {e}")
    
    return None
