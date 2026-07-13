"""中文日志配置。"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_path() -> Path:
    """返回日志文件路径。"""
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "GesturePPT" / "logs" / "gesture-ppt.log"


def configure_logging() -> None:
    """配置控制台和滚动文件日志。"""
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler], force=True)
