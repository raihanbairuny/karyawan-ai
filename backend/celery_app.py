"""
Karyawan AI — Celery Configuration
Background task processor menggunakan Redis sebagai message broker.
"""

from celery import Celery
from config import settings

celery_app = Celery(
    "karyawan_ai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.worker"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="Asia/Jakarta",
    enable_utc=True,

    # Reliability
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result expiry (24 jam)
    result_expires=86400,

    # Task routing — setiap karyawan punya queue sendiri
    task_routes={
        "tasks.worker.execute_agent_task": {"queue": "default"},
    },
)
