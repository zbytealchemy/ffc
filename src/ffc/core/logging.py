"""Logging configuration for the FFC framework."""
import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Any, Optional, Union


class JSONFormatter(logging.Formatter):
    """Format logs as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        timestamp = datetime.fromtimestamp(record.created).isoformat()

        json_record: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include any extra attributes from the record
        for key, value in record.__dict__.items():
            if key not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                json_record[key] = value

        if record.exc_info:
            json_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(json_record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """Set up logging configuration.

    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file (default: None, logs to stdout)
        max_bytes: Maximum size of each log file
        backup_count: Number of backup files to keep
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level.upper())

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter
    formatter = JSONFormatter()

    # Create handlers
    handlers: list[
        Union[logging.StreamHandler, logging.handlers.RotatingFileHandler]
    ] = []

    # Always add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # Add file handler if log file is specified
    if log_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Add handlers to logger
    for handler in handlers:
        logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Name of the logger

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
