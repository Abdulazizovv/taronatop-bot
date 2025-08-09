# Enhanced Shazam Functionality Documentation

## Overview
Your Telegram bot's Shazam functionality has been enhanced to support multiple media types beyond just voice messages.

## Supported Media Types

### 🎤 Voice Messages
- **Format**: .ogg (Telegram voice messages)
- **Usage**: Same as before - automatically processed
- **Supported in**: Private chats and groups (with /find command)

### 🎥 Video Files
- **Formats**: .mp4, .avi, .mov, .mkv, .webm, etc.
- **Processing**: Audio is extracted from video for recognition
- **Max size**: 50MB
- **Usage**: 
  - Private: Send video directly
  - Groups: Reply to video with `/find`

### 🎵 Audio Files
- **Formats**: .mp3, .wav, .flac, .aac, .ogg, etc.
- **Processing**: Direct audio processing (may include format conversion)
- **Max size**: 50MB
- **Usage**:
  - Private: Send audio file directly
  - Groups: Reply to audio with `/find`

### ⭕ Video Notes (Round Videos)
- **Format**: Telegram's circular video messages
- **Processing**: Audio extracted from video note
- **Usage**:
  - Private: Send video note directly
  - Groups: Reply to video note with `/find`

### 📄 Document Files
- **Supported**: Documents with audio/* or video/* MIME types
- **Examples**: Audio files sent as documents, video files sent as documents
- **Processing**: Same as regular audio/video files
- **Usage**:
  - Private: Send document directly
  - Groups: Reply to document with `/find`

## How It Works

### Audio Extraction Process
1. **File Detection**: Bot identifies the media type from the message
2. **Download**: File is downloaded from Telegram servers
3. **Audio Extraction**: For videos, audio is extracted using FFmpeg
4. **Format Conversion**: Audio is converted to optimal format for Shazam (WAV, 44.1kHz, stereo)
5. **Duration Limiting**: Only first 30 seconds are processed for better recognition
6. **Shazam Recognition**: Processed audio is sent to Shazam API
7. **Cleanup**: Temporary files are automatically deleted

### File Size Limits
- Maximum file size: **50MB**
- Audio duration for recognition: **30 seconds** (from the beginning)
- Supported by Telegram's file size limits

## Usage Examples

### Private Chats
```
User sends:
- Voice message → Bot recognizes music
- Video file → Bot extracts audio and recognizes music
- Audio file → Bot recognizes music
- Video note → Bot extracts audio and recognizes music
- Audio document → Bot recognizes music
```

### Group Chats
```
User1: [sends video with music]
User2: /find (reply to the video)
Bot: [recognizes music and downloads it]
```

## Technical Implementation

### Files Modified
- `bot/handlers/users/get_voice.py` - Enhanced private chat handler
- `bot/handlers/groups/shazam.py` - Enhanced group chat handler
- `bot/utils/audio_extractor.py` - New utility for audio extraction

### Dependencies Used
- **ffmpeg-python**: Video to audio extraction
- **pydub**: Audio format conversion and processing
- **shazamio**: Music recognition
- **yt-dlp**: YouTube audio downloading

### Key Functions
- `extract_audio_for_shazam()` - Main audio extraction function
- `get_file_type_from_message()` - Determines media type from message
- `get_file_from_message()` - Extracts file object from message
- `get_file_extension_for_type()` - Maps file types to extensions

## Error Handling

### Common Error Messages
- `❌ Fayl topilmadi.` - File not found in message
- `❌ Fayl hajmi juda katta.` - File size exceeds 50MB limit
- `❌ Audio ajratishda xatolik yuz berdi.` - Audio extraction failed
- `❌ Musiqa aniqlanmadi.` - Shazam couldn't recognize the music

### Troubleshooting
1. **File too large**: Ask user to send smaller file or trim video/audio
2. **Audio extraction fails**: Usually due to corrupted file or unsupported codec
3. **No music recognized**: Music might be too quiet, distorted, or not in Shazam's database
4. **Processing timeout**: Large files may take longer to process

## Performance Considerations

### Optimization Features
- **Duration limiting**: Only first 30 seconds processed
- **Automatic cleanup**: Temporary files deleted after processing
- **File size checks**: Large files rejected early
- **Format optimization**: Audio converted to best format for recognition

### Processing Time
- Voice messages: ~2-5 seconds
- Audio files: ~3-8 seconds
- Video files: ~5-15 seconds (depending on size and length)

## Future Enhancements
- Support for live audio streams
- Multiple audio track selection for videos
- Batch processing for multiple files
- Audio preprocessing filters for better recognition
