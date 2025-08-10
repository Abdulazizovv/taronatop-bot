"""
HTML formatting utilities for safe message parsing in aiogram.
This module provides functions to safely format HTML messages and prevent parse errors.
"""

import html
import re
from typing import Optional


def escape_html(text: str) -> str:
    """
    Escape special HTML characters to prevent parsing errors.
    
    Args:
        text: Input text that may contain HTML special characters
        
    Returns:
        Escaped text safe for HTML parsing
    """
    if not text:
        return ""
    
    # Escape basic HTML characters
    text = html.escape(str(text))
    return text


def format_html_message(text: str, escape_content: bool = True) -> str:
    """
    Format message text for safe HTML parsing in aiogram.
    
    Args:
        text: Message text with potential HTML tags
        escape_content: Whether to escape content between HTML tags
        
    Returns:
        Safely formatted HTML text
    """
    if not text:
        return ""
    
    # If escape_content is True, escape everything except allowed HTML tags
    if escape_content:
        # Temporarily replace allowed HTML tags
        allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']
        tag_replacements = {}
        
        for tag in allowed_tags:
            # Opening tags
            pattern = f'<{tag}>'
            replacement = f'__SAFE_TAG_OPEN_{tag.upper()}__'
            text = text.replace(pattern, replacement)
            tag_replacements[replacement] = pattern
            
            # Closing tags
            pattern = f'</{tag}>'
            replacement = f'__SAFE_TAG_CLOSE_{tag.upper()}__'
            text = text.replace(pattern, replacement)
            tag_replacements[replacement] = pattern
            
            # Tags with attributes (like <a href="...">)
            pattern = re.compile(f'<{tag}[^>]*>', re.IGNORECASE)
            matches = pattern.findall(text)
            for match in matches:
                replacement = f'__SAFE_TAG_ATTR_{tag.upper()}_{len(tag_replacements)}__'
                text = text.replace(match, replacement)
                tag_replacements[replacement] = match
        
        # Escape all remaining HTML
        text = html.escape(text)
        
        # Restore allowed tags
        for replacement, original in tag_replacements.items():
            text = text.replace(replacement, original)
    
    return text


def safe_html_format(template: str, **kwargs) -> str:
    """
    Safely format HTML template with variables, escaping user input.
    
    Args:
        template: HTML template string with format placeholders
        **kwargs: Variables to substitute in template
        
    Returns:
        Safely formatted HTML string
    """
    # Escape all user input variables
    escaped_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            escaped_kwargs[key] = escape_html(value)
        else:
            escaped_kwargs[key] = value
    
    try:
        return template.format(**escaped_kwargs)
    except (KeyError, ValueError) as e:
        # Fallback: escape the entire template
        return escape_html(str(template))


def validate_html_tags(text: str) -> tuple[bool, Optional[str]]:
    """
    Validate that HTML tags are properly closed in the text.
    
    Args:
        text: Text to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text:
        return True, None
    
    # Stack to track opening tags
    tag_stack = []
    
    # Find all tags
    tag_pattern = re.compile(r'<(/?)([a-zA-Z]+)(?:\s[^>]*)?>|<(/?)([a-zA-Z]+)>')
    
    for match in tag_pattern.finditer(text):
        is_closing = bool(match.group(1) or match.group(3))
        tag_name = (match.group(2) or match.group(4)).lower()
        
        if is_closing:
            if not tag_stack:
                return False, f"Closing tag </{tag_name}> without opening tag"
            
            last_tag = tag_stack.pop()
            if last_tag != tag_name:
                return False, f"Mismatched tags: opened <{last_tag}> but closed </{tag_name}>"
        else:
            # Self-closing tags (not applicable for Telegram HTML)
            if tag_name not in ['br', 'hr', 'img']:
                tag_stack.append(tag_name)
    
    if tag_stack:
        return False, f"Unclosed tags: {', '.join(tag_stack)}"
    
    return True, None


def clean_html_message(text: str) -> str:
    """
    Clean and fix common HTML issues in message text.
    
    Args:
        text: Input text with potential HTML issues
        
    Returns:
        Cleaned text safe for aiogram HTML parsing
    """
    if not text:
        return ""
    
    # Remove or fix common problematic patterns
    text = str(text)
    
    # Fix common issues
    text = text.replace('&', '&amp;')  # Escape ampersands first
    text = text.replace('<', '&lt;').replace('>', '&gt;')  # Escape < and >
    
    # Restore allowed HTML tags (basic approach)
    allowed_patterns = [
        (r'&lt;b&gt;', '<b>'),
        (r'&lt;/b&gt;', '</b>'),
        (r'&lt;i&gt;', '<i>'),
        (r'&lt;/i&gt;', '</i>'),
        (r'&lt;u&gt;', '<u>'),
        (r'&lt;/u&gt;', '</u>'),
        (r'&lt;s&gt;', '<s>'),
        (r'&lt;/s&gt;', '</s>'),
        (r'&lt;code&gt;', '<code>'),
        (r'&lt;/code&gt;', '</code>'),
        (r'&lt;pre&gt;', '<pre>'),
        (r'&lt;/pre&gt;', '</pre>'),
    ]
    
    for pattern, replacement in allowed_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text


def safe_send_message(message_func, text: str, **kwargs):
    """
    Safely send message with HTML parsing, falling back to plain text if needed.
    
    Args:
        message_func: Function to send message (like message.reply or bot.send_message)
        text: Message text
        **kwargs: Additional arguments for message_func
        
    Returns:
        Result of message sending
    """
    # First try with HTML parsing
    try:
        return message_func(text, parse_mode="HTML", **kwargs)
    except Exception as e:
        if "CantParseEntities" in str(e):
            # Fall back to escaped HTML
            try:
                escaped_text = clean_html_message(text)
                return message_func(escaped_text, parse_mode="HTML", **kwargs)
            except Exception:
                # Final fallback: plain text
                plain_text = re.sub(r'<[^>]+>', '', text)  # Remove all HTML tags
                return message_func(plain_text, **kwargs)
        else:
            raise e
