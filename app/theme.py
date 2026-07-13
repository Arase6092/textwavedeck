"""黑匣子剧场的视觉令牌和系统动效偏好。"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

STAGE_BACKGROUND = "#07080B"
CONTROL_SURFACE = "#111318"
HOVER_SURFACE = "#191D24"
STRUCTURE_LINE = "#303641"
PRIMARY_TEXT = "#F4F6FA"
SECONDARY_TEXT = "#A8AFBC"
DISABLED_TEXT = "#626A78"
FOCUS_BLUE = "#3B6FFF"
ERROR_RED = "#FF5C68"

TOP_CHROME_HEIGHT = 52
BOTTOM_CHROME_HEIGHT = 64
TOP_REVEAL_HEIGHT = 56
BOTTOM_REVEAL_HEIGHT = 72
CHROME_HIDE_DELAY_MS = 2000
CHROME_FADE_DURATION_MS = 160
MODE_REVEAL_DURATION_MS = 1500
STAGE_SAFE_MARGIN = 32


def reduced_motion_enabled() -> bool:
    """读取测试覆盖值或 Windows 客户区动画偏好。"""
    forced = os.environ.get("GESTURE_PPT_REDUCED_MOTION")
    if forced in {"0", "1"}:
        return forced == "1"
    if sys.platform != "win32":
        return False

    animation_enabled = wintypes.BOOL(1)
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
            0x1042,
            0,
            ctypes.byref(animation_enabled),
            0,
        )
    except (AttributeError, OSError):
        return False
    return bool(ok and not animation_enabled.value)


def application_stylesheet() -> str:
    """返回主窗口共享的完整暗场样式。"""
    return f"""
        QMainWindow, QWidget {{
            background: {STAGE_BACKGROUND};
            color: {PRIMARY_TEXT};
            font-family: 'Segoe UI Variable', 'Segoe UI';
            letter-spacing: 0px;
        }}
        QFrame#topChrome, QFrame#bottomChrome {{
            background: {CONTROL_SURFACE};
            border: 0;
        }}
        QFrame#topChrome {{ border-bottom: 1px solid {STRUCTURE_LINE}; }}
        QFrame#bottomChrome {{ border-top: 1px solid {STRUCTURE_LINE}; }}
        QToolButton, QPushButton {{
            min-width: 40px;
            min-height: 40px;
            padding: 0 8px;
            background: transparent;
            color: {PRIMARY_TEXT};
            border: 1px solid transparent;
            border-radius: 4px;
        }}
        QToolButton:hover, QPushButton:hover {{
            background: {HOVER_SURFACE};
            border-color: {STRUCTURE_LINE};
        }}
        QToolButton:focus, QPushButton:focus {{
            border-color: {FOCUS_BLUE};
        }}
        QToolButton:pressed, QPushButton:pressed {{
            background: {STRUCTURE_LINE};
        }}
        QToolButton:disabled, QPushButton:disabled {{
            color: {DISABLED_TEXT};
        }}
        QLabel#folio {{
            color: {PRIMARY_TEXT};
            font-size: 16px;
            font-weight: 600;
            padding: 0 12px;
        }}
        QLabel#fileName {{ color: {SECONDARY_TEXT}; font-size: 12px; }}
        QLabel#emptyFolio {{ color: {FOCUS_BLUE}; font-size: 92px; font-weight: 700; }}
        QLabel#emptyTitle {{ color: {PRIMARY_TEXT}; font-size: 21px; font-weight: 600; }}
        QLabel#statusLabel {{ color: {SECONDARY_TEXT}; font-size: 12px; }}
        QProgressBar {{
            min-height: 2px;
            max-height: 2px;
            border: 0;
            background: {STRUCTURE_LINE};
            text-align: center;
        }}
        QProgressBar::chunk {{ background: {FOCUS_BLUE}; }}
        QGraphicsView#cylinderCarousel, QGraphicsView#slideViewer {{
            background: {STAGE_BACKGROUND};
            border: 0;
        }}
        QMessageBox {{ background: {CONTROL_SURFACE}; }}
        QMessageBox QLabel {{ color: {PRIMARY_TEXT}; background: transparent; }}
    """
