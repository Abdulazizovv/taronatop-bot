import os


BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMINS = os.getenv("ADMINS").split(",") if os.getenv("ADMINS") else []
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID", "-1002616385121")
ADMIN_PANEL_URL = os.getenv("ADMIN_PANEL_URL", "http://localhost:8000/admin/")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY is not set in environment variables")