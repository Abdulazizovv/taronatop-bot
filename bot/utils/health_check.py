"""
Health check utility for monitoring bot status
"""
import logging
import asyncio
from typing import Dict, Any
from bot.loader import bot, db
from bot.data import config


async def check_bot_health() -> Dict[str, Any]:
    """Perform comprehensive health check"""
    health_status = {
        "status": "healthy",
        "checks": {},
        "timestamp": None
    }
    
    try:
        # Check bot API connection
        health_status["checks"]["bot_api"] = await check_bot_api()
        
        # Check database connection
        health_status["checks"]["database"] = await check_database()
        
        # Check admin availability
        health_status["checks"]["admins"] = await check_admins()
        
        # Determine overall status
        failed_checks = [name for name, check in health_status["checks"].items() if not check["status"]]
        if failed_checks:
            health_status["status"] = "unhealthy"
            health_status["failed_checks"] = failed_checks
            
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        health_status["status"] = "error"
        health_status["error"] = str(e)
    
    return health_status


async def check_bot_api() -> Dict[str, Any]:
    """Check if bot API is accessible"""
    try:
        bot_info = await bot.get_me()
        return {
            "status": True,
            "message": f"Bot @{bot_info.username} is accessible",
            "bot_id": bot_info.id,
            "bot_username": bot_info.username
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Bot API check failed: {e}"
        }


async def check_database() -> Dict[str, Any]:
    """Check database connectivity"""
    try:
        # Try to fetch user count
        user_count = await db.get_user_count()
        return {
            "status": True,
            "message": f"Database accessible, {user_count} users registered"
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Database check failed: {e}"
        }


async def check_admins() -> Dict[str, Any]:
    """Check if admins are configured"""
    try:
        admin_ids = config.ADMINS
        if not admin_ids:
            return {
                "status": False,
                "message": "No admins configured"
            }
        
        admin_count = len(admin_ids)
        return {
            "status": True,
            "message": f"{admin_count} admin(s) configured",
            "admin_count": admin_count
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Admin check failed: {e}"
        }


if __name__ == "__main__":
    async def main():
        health = await check_bot_health()
        print(f"Health Status: {health}")
    
    asyncio.run(main())
