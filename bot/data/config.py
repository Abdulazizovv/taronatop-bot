import os


BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMINS = os.getenv("ADMINS").split(",") if os.getenv("ADMINS") else []
