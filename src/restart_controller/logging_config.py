"""Logging configuration for the restart controller.

Console (stderr): INFO and above.
File: DEBUG and above, with rotation.
Format: ISO 8601 timestamp, logger name, message.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "%(asctime)s [%(levelname)s] (%(name)s) - %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"
LOG_FILE = "restart_controller.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3


def setup_logging(log_file: str | None = LOG_FILE) -> None:
    """Configure logging with stderr and optional file handlers.

    Args:
        log_file: Path to the log file. Pass None to disable file logging.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT)
    formatter.default_msec_format = "%s.%03d"

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    if log_file is not None:
        file_handler = RotatingFileHandler(log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
