"""Structured logging setup, configured from `config/logging.yaml`."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

import yaml

from restaurant_ops.config import CONFIG_DIR

_CONFIGURED = False


def configure_logging(path: Path | None = None) -> None:
    """Apply the logging configuration once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    config_path = path or CONFIG_DIR / "logging.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        logging.config.dictConfig(yaml.safe_load(handle))
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
