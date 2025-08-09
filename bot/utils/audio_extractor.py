"""
Audio extraction utility for Shazam functionality.
Handles extraction of audio from various file types (voice, video, audio).
"""
import os
import logging
from typing import Union, Optional
import ffmpeg
from pydub import AudioSegment


def extract_audio_for_shazam(
    file_path: str, 
    output_path: str, 
    file_type: str = "voice",
    duration_limit: int = 30
) -> str:
    """
    Extract audio from various file types and prepare it for Shazam recognition.
    
    Args:
        file_path: Path to the input file
        output_path: Path for the output audio file
        file_type: Type of input file ("voice", "video", "audio")
        duration_limit: Maximum duration in seconds for Shazam processing
        
    Returns:
        Path to the extracted audio file ready for Shazam
        
    Raises:
        Exception: If audio extraction fails
    """
    try:
        if file_type == "voice":
            # Voice messages are already in audio format, just copy/rename
            if file_path != output_path:
                import shutil
                shutil.copy2(file_path, output_path)
            return output_path
            
        elif file_type == "video":
            # Extract audio from video using ffmpeg
            logging.info(f"Extracting audio from video: {file_path}")
            
            # Extract audio and convert to format suitable for Shazam
            stream = ffmpeg.input(file_path)
            audio_stream = stream.audio
            
            # Limit duration for better processing
            if duration_limit:
                audio_stream = audio_stream.filter('atrim', duration=duration_limit)
            
            # Convert to a format that Shazam can process well
            out = ffmpeg.output(
                audio_stream,
                output_path,
                acodec='pcm_s16le',  # Uncompressed audio for better recognition
                ar=44100,  # 44.1 kHz sample rate
                ac=2,  # Stereo
                f='wav'  # WAV format
            )
            
            ffmpeg.run(out, overwrite_output=True, quiet=True)
            return output_path
            
        elif file_type == "audio":
            # Process audio files (might need format conversion)
            logging.info(f"Processing audio file: {file_path}")
            
            # Load audio with pydub for format flexibility
            audio = AudioSegment.from_file(file_path)
            
            # Limit duration if specified
            if duration_limit and len(audio) > duration_limit * 1000:
                audio = audio[:duration_limit * 1000]  # pydub works with milliseconds
            
            # Convert to format suitable for Shazam
            audio = audio.set_frame_rate(44100).set_channels(2)
            
            # Export as WAV for better Shazam compatibility
            audio.export(output_path, format="wav")
            return output_path
            
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
            
    except Exception as e:
        logging.error(f"Audio extraction failed for {file_path}: {str(e)}")
        raise Exception(f"Failed to extract audio: {str(e)}")


def get_file_type_from_message(message) -> Optional[str]:
    """
    Determine the file type from a Telegram message.
    
    Args:
        message: Telegram message object
        
    Returns:
        String indicating file type: "voice", "video", "audio", or None
    """
    if message.voice:
        return "voice"
    elif message.video:
        return "video"
    elif message.audio:
        return "audio"
    elif message.video_note:  # Circular video messages
        return "video"
    elif message.document:
        # Check if document is an audio/video file by MIME type
        if message.document.mime_type:
            mime = message.document.mime_type.lower()
            if mime.startswith('audio/'):
                return "audio"
            elif mime.startswith('video/'):
                return "video"
    
    return None


def get_file_from_message(message):
    """
    Get the file object from a Telegram message based on content type.
    
    Args:
        message: Telegram message object
        
    Returns:
        File object that can be downloaded
    """
    if message.voice:
        return message.voice
    elif message.video:
        return message.video
    elif message.audio:
        return message.audio
    elif message.video_note:
        return message.video_note
    elif message.document:
        return message.document
    
    return None


def get_file_extension_for_type(file_type: str) -> str:
    """
    Get appropriate file extension for the given file type.
    
    Args:
        file_type: Type of file ("voice", "video", "audio")
        
    Returns:
        File extension string
    """
    if file_type == "voice":
        return "ogg"
    elif file_type == "video":
        return "mp4"
    elif file_type == "audio":
        return "mp3"
    else:
        return "tmp"
