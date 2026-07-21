"""
Logging framework for the AI Data Migration Accelerator.

Single responsibility: configure Python's standard `logging` module so that
every module in the codebase can do `logging.getLogger(__name__)` and get
consistent, readable output — a Rich-formatted stream to the console, and a
plain-text file handler under `logs/`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from rich.logging import RichHandler

_LOG_FORMAT = "%(message)s"
_FILE_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO", log_dir: str | Path = "logs") -> Path:
    """Configure root logging handlers (console + file).

    Idempotent: safe to call once at CLI startup. Returns the path of the
    log file created for this run, so the orchestrator can reference it
    when writing `execution.log` into the output artifacts directory.
    """
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_file = log_dir_path / f"run_{timestamp}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Clear any pre-existing handlers (relevant if setup_logging is ever
    # called more than once, e.g. in tests).
    root_logger.handlers.clear()

    console_handler = RichHandler(rich_tracebacks=True, show_path=False)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FILE_LOG_FORMAT))
    root_logger.addHandler(file_handler)

    return log_file
