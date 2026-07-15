"""运行时路径辅助，兼容源码和 PyInstaller 冻结包。"""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """返回当前运行环境下的项目根目录。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def bundle_path(*parts: str) -> Path:
    """返回随源码或冻结包分发的资源路径。"""
    return project_root().joinpath(*parts)
