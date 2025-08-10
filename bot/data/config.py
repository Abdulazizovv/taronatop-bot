import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMINS = os.getenv("ADMINS").split(",") if os.getenv("ADMINS") else []
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID", "-1002616385121")
ADMIN_PANEL_URL = os.getenv("ADMIN_PANEL_URL", "http://localhost:8000/admin/")

# YouTube API Keys - support multiple keys for quota management
YOUTUBE_API_KEYS = [
    os.getenv("YOUTUBE_API_KEY"),
    os.getenv("YOUTUBE_API_KEY_2"),
    os.getenv("YOUTUBE_API_KEY_3"),
    os.getenv("YOUTUBE_API_KEY_4"),
    os.getenv("YOUTUBE_API_KEY_5"),
]

# Filter out None values
YOUTUBE_API_KEYS = [key for key in YOUTUBE_API_KEYS if key]

if not YOUTUBE_API_KEYS:
    raise ValueError("At least one YOUTUBE_API_KEY must be set in environment variables")

# For backward compatibility
YOUTUBE_API_KEY = YOUTUBE_API_KEYS[0]