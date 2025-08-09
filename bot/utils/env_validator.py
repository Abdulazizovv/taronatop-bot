"""
Environment validation utility to ensure all required environment variables are set
"""
import os
import logging


def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = [
        'BOT_TOKEN',
        'DJANGO_SECRET_KEY',
        'YOUTUBE_API_KEY',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate ADMINS format if provided
    if os.getenv("ADMINS"):
        try:
            admin_ids = [int(admin_id.strip()) for admin_id in os.getenv("ADMINS").split(",") if admin_id.strip()]
            if not admin_ids:
                logging.warning("ADMINS environment variable is empty")
        except ValueError:
            raise ValueError("ADMINS must be comma-separated integers")
    
    # Validate boolean environment variables
    bool_vars = {
        'DJANGO_DEBUG': ['true', 'false'],
    }
    
    for var, valid_values in bool_vars.items():
        value = os.getenv(var, '').lower()
        if value and value not in valid_values:
            raise ValueError(f"{var} must be one of: {', '.join(valid_values)}")
    
    logging.info("Environment validation passed")


if __name__ == "__main__":
    validate_environment()
