"""Celery application factory.

Task modules for individual AI agents (data cleaning, forecasting, etc.)
will register themselves against this instance in later milestones, the
same way ``infrastructure.celery.tasks.dataset_sync`` does today for
dataset syncs.
"""

from __future__ import annotations

from celery import Celery

from quantix_api.core.config import get_settings

settings = get_settings()

app = Celery(
    "quantix",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 30,  # hard kill runaway tasks after 30 minutes
    task_soft_time_limit=60 * 25,
    worker_max_tasks_per_child=200,  # mitigate memory growth in long-running workers
    broker_connection_retry_on_startup=True,
)

# Imported at the bottom, after `app` is defined, to avoid a circular
# import — task modules import `app` from this module.
from quantix_api.infrastructure.celery import tasks  # noqa: E402, F401
