from celery import Celery
import os
from dotenv import load_dotenv
import redis

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Check if Redis is running, otherwise fallback to Celery's eager execution mode
use_eager = False
try:
    r = redis.from_url(REDIS_URL, socket_timeout=2)
    r.ping()
    print("Connected to Redis successfully.")
except Exception as e:
    print(f"Redis connection failed: {e}. Celery falling back to eager execution mode.")
    use_eager = True

celery_app = Celery(
    "storyvoice_worker",
    broker=REDIS_URL if not use_eager else "memory://",
    backend=REDIS_URL if not use_eager else "cache+memory://"
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_always_eager=use_eager,
    task_eager_propagates=use_eager
)

@celery_app.task(name="dummy_task")
def dummy_task():
    return True

