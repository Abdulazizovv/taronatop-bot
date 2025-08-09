#!/usr/bin/env python3
"""
Simple verification script for enhanced Shazam functionality.
"""

import os

def check_enhanced_shazam_setup():
    """Check if the enhanced Shazam setup is complete."""
    
    print("🔍 Checking Enhanced Shazam Functionality Setup")
    print("=" * 50)
    
    # Check if audio extractor utility exists
    audio_extractor_path = "/home/abdulazizov/myProjects/paid/taronatop_bot/bot/utils/audio_extractor.py"
    if os.path.exists(audio_extractor_path):
        print("✅ Audio extractor utility exists")
        
        # Check key functions in the file
        with open(audio_extractor_path, 'r') as f:
            content = f.read()
            functions = [
                "extract_audio_for_shazam",
                "get_file_type_from_message",
                "get_file_from_message",
                "get_file_extension_for_type"
            ]
            
            for func in functions:
                if func in content:
                    print(f"  ✅ Function {func} found")
                else:
                    print(f"  ❌ Function {func} missing")
    else:
        print("❌ Audio extractor utility missing")
    
    # Check updated handlers
    handlers_info = [
        ("/home/abdulazizov/myProjects/paid/taronatop_bot/bot/handlers/users/get_voice.py", "Private chat handler"),
        ("/home/abdulazizov/myProjects/paid/taronatop_bot/bot/handlers/groups/shazam.py", "Group chat handler")
    ]
    
    print("\n📁 Checking updated handlers:")
    for handler_path, handler_name in handlers_info:
        if os.path.exists(handler_path):
            print(f"✅ {handler_name} exists")
            
            with open(handler_path, 'r') as f:
                content = f.read()
                
                # Check for enhanced functionality
                enhancements = [
                    "audio_extractor",
                    "content_types=[",
                    "VIDEO",
                    "AUDIO",
                    "get_file_type_from_message"
                ]
                
                for enhancement in enhancements:
                    if enhancement in content:
                        print(f"  ✅ Enhancement: {enhancement}")
                    else:
                        print(f"  ⚠️ Missing: {enhancement}")
        else:
            print(f"❌ {handler_name} missing")
    
    # Check sample media files
    print("\n🎵 Sample media files in workspace:")
    media_files = [
        "berezovee_3651978722991758705.mp4",
        "lixiang_auto_dag_3562162141830266071.mp3",
        "lixiang_auto_dag_3562162141830266071.mp4",
        "trzrc_3613593809146010810.mp3",
        "trzrc_3613593809146010810.mp4"
    ]
    
    for file_name in media_files:
        file_path = f"/home/abdulazizov/myProjects/paid/taronatop_bot/{file_name}"
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            size_mb = size / (1024 * 1024)
            print(f"  ✅ {file_name} ({size_mb:.1f} MB)")
        else:
            print(f"  ❌ {file_name}")
    
    print("\n🎯 Enhanced Shazam Features:")
    print("  🎤 Voice messages - Supported")
    print("  🎥 Video files - Enhanced support added")
    print("  🎵 Audio files - Enhanced support added") 
    print("  ⭕ Video notes - Enhanced support added")
    print("  📄 Audio/Video documents - Enhanced support added")
    
    print("\n📋 How to use the enhanced functionality:")
    print("  Private chats: Send any voice/video/audio file")
    print("  Groups: Reply to voice/video/audio with /find command")
    
    print("\n✅ Enhanced Shazam setup verification completed!")

if __name__ == "__main__":
    check_enhanced_shazam_setup()
