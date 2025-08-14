"""
Instagram media audio detection utility.
Efficiently checks if downloaded media contains audio streams.
"""

import os
import logging
import asyncio
from typing import Optional

async def check_media_has_audio(file_path: str) -> Optional[bool]:
    """
    Enhanced audio detection using ffprobe with multiple strategies.
    Returns True if audio found, False if no audio, None if check failed.
    """
    try:
        import shutil
        if not shutil.which("ffprobe"):
            logging.warning("[Audio Check] ffprobe not found, cannot check audio")
            return None
        
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 1000:
            logging.warning(f"[Audio Check] Invalid file: {file_path}")
            return False
        
        # Strategy 1: Quick audio stream detection
        cmd1 = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            file_path
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd1, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                output = stdout.decode().strip()
                if output and "audio" in output.lower():
                    logging.info(f"[Audio Check] Quick check: Audio found in {file_path}")
                    return True
        except Exception as e:
            logging.warning(f"[Audio Check] Quick check failed: {e}")
        
        # Strategy 2: Detailed stream analysis
        cmd2 = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,channels,sample_rate",
            "-of", "json",
            file_path
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd2,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                import json
                data = json.loads(stdout.decode())
                streams = data.get("streams", [])
                
                # Check for audio streams
                audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
                
                if audio_streams:
                    # Verify audio stream has actual content
                    audio_stream = audio_streams[0]
                    channels = audio_stream.get("channels", 0)
                    sample_rate = audio_stream.get("sample_rate")
                    codec_name = audio_stream.get("codec_name", "")
                    
                    if channels > 0 and sample_rate and codec_name:
                        logging.info(f"[Audio Check] Detailed check: Valid audio stream found - {codec_name}, {channels}ch, {sample_rate}Hz")
                        return True
                    else:
                        logging.info(f"[Audio Check] Audio stream present but incomplete: channels={channels}, sample_rate={sample_rate}")
                        return False
                else:
                    logging.info(f"[Audio Check] No audio streams found in {file_path}")
                    return False
                    
        except Exception as e:
            logging.warning(f"[Audio Check] Detailed check failed: {e}")
        
        # Strategy 3: Fallback - try to detect audio track duration
        cmd3 = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "csv=p=0",
            file_path
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd3,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                duration_str = stdout.decode().strip()
                if duration_str and duration_str != "N/A":
                    try:
                        duration = float(duration_str)
                        if duration > 0:
                            logging.info(f"[Audio Check] Fallback check: Audio duration {duration}s found")
                            return True
                    except ValueError:
                        pass
        except Exception as e:
            logging.warning(f"[Audio Check] Fallback check failed: {e}")
        
        # If all strategies fail to find audio
        logging.info(f"[Audio Check] All strategies confirm: No audio in {file_path}")
        return False
            
    except Exception as e:
        logging.error(f"[Audio Check] Critical error checking audio: {e}")
        return None


async def get_media_info_with_audio(file_path: str) -> dict:
    """
    Get comprehensive media information including audio presence.
    """
    try:
        import shutil
        if not shutil.which("ffprobe"):
            return {"has_audio": None, "error": "ffprobe not available"}
        
        # Get detailed media info
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=codec_type,codec_name",
            "-of", "json",
            file_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            
            # Analyze streams
            streams = data.get("streams", [])
            has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
            has_video = any(stream.get("codec_type") == "video" for stream in streams)
            
            # Get duration
            duration = None
            format_info = data.get("format", {})
            if "duration" in format_info:
                try:
                    duration = float(format_info["duration"])
                except (ValueError, TypeError):
                    pass
            
            return {
                "has_audio": has_audio,
                "has_video": has_video,
                "duration": duration,
                "streams": streams,
                "error": None
            }
        else:
            error_msg = stderr.decode() if stderr else "Unknown ffprobe error"
            logging.error(f"[Media Info] ffprobe failed: {error_msg}")
            return {"has_audio": None, "error": error_msg}
            
    except Exception as e:
        logging.error(f"[Media Info] Error: {e}")
        return {"has_audio": None, "error": str(e)}
