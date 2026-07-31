"""Structured logging setup for the backend."""

import logging
import sys

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure the root logger with a single structured stream handler.

    Replaces any handlers configured by imported libraries so log format
    and level stay consistent across the app, regardless of import order.
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())
