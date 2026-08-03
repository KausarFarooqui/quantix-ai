"""Structured logging configuration.

Uses ``structlog`` to emit JSON logs in production/staging (machine
parseable, ready for log aggregation) and human-readable console output in
development. All application code should obtain loggers via
``get_logger(__name__)`` rather than the stdlib ``logging`` module directly.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from quantix_api.core.config import Environment, Settings


def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging + structlog processors for the process."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level.upper(),
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.environment in (Environment.PRODUCTION, Environment.STAGING):
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a namespaced structlog logger bound to ``name``."""
    return structlog.get_logger(name)
