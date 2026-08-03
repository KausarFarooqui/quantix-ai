"""Celery task modules. Import each module here so
``app.autodiscover_tasks`` (see ``infrastructure.celery.app``) picks them up.
"""

from quantix_api.infrastructure.celery.tasks import dataset_sync  # noqa: F401
