"""Logging configuration for health data import"""
import logging
import sys
from pathlib import Path
from datetime import datetime

LOGGER_NAME = "health_import"
LOG_DIR = Path(__file__).parent.parent.parent / "logs"

# Custom log level for conflicts
CONFLICT = 25  # Between INFO (20) and WARNING (30)
logging.addLevelName(CONFLICT, "CONFLICT")


class ConflictLogger(logging.Logger):
    """Logger with custom conflict level"""

    def conflict(self, msg, *args, **kwargs):
        if self.isEnabledFor(CONFLICT):
            self._log(CONFLICT, msg, args, **kwargs)


logging.setLoggerClass(ConflictLogger)


def setup_logging(verbosity: int = 0, quiet: bool = False, log_to_file: bool = True) -> logging.Logger:
    """
    Configure logging based on verbosity level.

    verbosity=0: INFO + warnings (default)
    verbosity=1: show inserts/skips
    verbosity=2: show all field values
    quiet=True: errors only
    log_to_file: also write to logs/import.log
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

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_fmt = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # File handler
    if log_to_file:
        LOG_DIR.mkdir(exist_ok=True)
        log_file = LOG_DIR / "import.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    return logger


def get_logger() -> ConflictLogger:
    """Get the health_import logger"""
    return logging.getLogger(LOGGER_NAME)
