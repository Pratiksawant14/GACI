"""
Application Logging Configuration.
Provides standard structured logging for services, database operations, and agent traces.
"""

import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    logger = logging.getLogger(settings.APP_NAME)
    logger.setLevel(level)
    return logger


logger = setup_logging()
