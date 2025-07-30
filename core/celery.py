import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Create Celery application
app = Celery('core')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery configuration for asyncio and Docker
app.conf.update(
    task_default_timeout=3600,  # Task timeout (in seconds)
    task_track_started=True,    # Track when tasks start
    worker_concurrency=4,       # Number of concurrent workers (adjust based on resources)
    task_always_eager=False,    # Disable eager mode for production
    task_serializer='json',     # Use JSON for task serialization
    accept_content=['json'],    # Accept JSON content
    result_serializer='json',   # Use JSON for result serialization
    event_loop='asyncio',       # Explicitly use asyncio event loop
    worker_pool='solo',         # Use solo pool for asyncio tasks (or 'gevent' if gevent is added)
    broker_connection_retry_on_startup=True,  # Retry broker connection on startup
)

# Optional: Configure beat for scheduled tasks (if using django-celery-beat)
app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'