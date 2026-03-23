"""Logging configuration for GutAgent."""

import logging
import os
import sys

# Log level from environment, default to WARNING
LOG_LEVEL = os.getenv("GUTAGENT_LOG_LEVEL", "WARNING").upper()

# Create logger
logger = logging.getLogger("gutagent")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.WARNING))

# Console handler with simple format
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, LOG_LEVEL, logging.WARNING))
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger, optionally with a submodule name."""
    if name:
        return logging.getLogger(f"gutagent.{name}")
    return logger
