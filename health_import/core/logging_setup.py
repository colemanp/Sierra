"""Logging configuration for health data import"""
import logging
import sys
from typing import Optional

LOGGER_NAME = "health_import"

# Custom log level for conflicts
CONFLICT = 25  # Between INFO (20) and WARNING (30)
logging.addLevelName(CONFLICT, "CONFLICT")


class ConflictLogger(logging.Logger):
    """Logger with custom conflict level"""

    def conflict(self, msg, *args, **kwargs):
        if self.isEnabledFor(CONFLICT):
            self._log(CONFLICT, msg, args, **kwargs)


logging.setLoggerClass(ConflictLogger)


def setup_logging(verbosity: int = 0, quiet: bool = False) -> logging.Logger:
    """
    Configure logging based on verbosity level.

    verbosity=0: INFO + warnings (default)
    verbosity=1: show inserts/skips
    verbosity=2: show all field values
    quiet=True: errors only
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()

    if quiet:
        level = logging.ERROR
    elif verbosity >= 2:
        level = logging.DEBUG
    elif verbosity >= 1:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Format based on verbosity
    if verbosity >= 2:
        fmt = "[%(levelname)s] %(message)s"
    else:
        fmt = "[%(levelname)s] %(message)s"

    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger() -> ConflictLogger:
    """Get the health_import logger"""
    return logging.getLogger(LOGGER_NAME)
