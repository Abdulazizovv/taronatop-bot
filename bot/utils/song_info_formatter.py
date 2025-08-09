#!/usr/bin/env python3
"""
Enhanced song information display utility.
This module provides functions to format and display song information from Shazam results.
"""

def format_song_info(track_data, include_extra_info=True):
    """
    Format song information from Shazam track data for display.
    
    Args:
        track_data: The track data from Shazam result
        include_extra_info: Whether to include additional info like genre, year, etc.
        
    Returns:
        Formatted string with song information
    """
    title = track_data.get('title', 'Unknown Title')
    subtitle = track_data.get('subtitle', 'Unknown Artist')
    
    # Basic song info
    song_info = f"🎵 <b>Topildi!</b>\n📀 <b>{title}</b>\n🎤 <i>{subtitle}</i>"
    
    if include_extra_info:
        # Add genre if available
        if 'genres' in track_data and track_data['genres']:
            primary_genre = track_data['genres']['primary']
            song_info += f"\n🎭 <i>{primary_genre}</i>"
        
        # Add year if available
        if 'sections' in track_data:
            for section in track_data['sections']:
                if section['type'] == 'SONG' and 'metadata' in section:
                    for metadata in section['metadata']:
                        if metadata['title'] == 'Released' and metadata['text']:
                            year = metadata['text']
                            song_info += f"\n📅 {year}"
                            break
        
        # Add label if available
        if 'sections' in track_data:
            for section in track_data['sections']:
                if section['type'] == 'SONG' and 'metadata' in section:
                    for metadata in section['metadata']:
                        if metadata['title'] == 'Label' and metadata['text']:
                            label = metadata['text']
                            song_info += f"\n🏷️ {label}"
                            break
    
    return song_info


def get_shazam_link(track_data):
    """
    Extract Shazam link from track data if available.
    
    Args:
        track_data: The track data from Shazam result
        
    Returns:
        Shazam URL string or None
    """
    if 'share' in track_data and 'href' in track_data['share']:
        return track_data['share']['href']
    return None


def format_detailed_song_info(track_data):
    """
    Format detailed song information including streaming links.
    
    Args:
        track_data: The track data from Shazam result
        
    Returns:
        Formatted string with detailed song information
    """
    basic_info = format_song_info(track_data, include_extra_info=True)
    
    # Add Shazam link if available
    shazam_link = get_shazam_link(track_data)
    if shazam_link:
        basic_info += f"\n🔗 <a href='{shazam_link}'>Shazam'da ko'rish</a>"
    
    return basic_info
