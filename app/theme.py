"""黑匣子剧场的视觉令牌和系统动效偏好。"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

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
STAGE_SAFE_MARGIN = 72


def line_icon(name: str, color: str = PRIMARY_TEXT) -> QIcon:
    """绘制少量一致的暗场线性图标，不引入额外图标依赖。"""
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "open":
        path = QPainterPath(QPointF(2.5, 5.5))
        path.lineTo(6.5, 5.5)
        path.lineTo(8.0, 7.0)
        path.lineTo(15.5, 7.0)
        path.lineTo(14.0, 14.5)
        path.lineTo(3.5, 14.5)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "grid":
        for x in (3.0, 10.0):
            for y in (3.0, 10.0):
                painter.drawRect(QRectF(x, y, 5.0, 5.0))
    elif name == "stage":
        painter.drawRect(QRectF(2.5, 4.0, 13.0, 10.0))
    elif name == "fullscreen":
        painter.drawLine(QPointF(3.0, 7.0), QPointF(3.0, 3.0))
        painter.drawLine(QPointF(3.0, 3.0), QPointF(7.0, 3.0))
        painter.drawLine(QPointF(11.0, 3.0), QPointF(15.0, 3.0))
        painter.drawLine(QPointF(15.0, 3.0), QPointF(15.0, 7.0))
        painter.drawLine(QPointF(15.0, 11.0), QPointF(15.0, 15.0))
        painter.drawLine(QPointF(15.0, 15.0), QPointF(11.0, 15.0))
        painter.drawLine(QPointF(7.0, 15.0), QPointF(3.0, 15.0))
        painter.drawLine(QPointF(3.0, 15.0), QPointF(3.0, 11.0))
    else:
        painter.end()
        raise ValueError(f"未知图标：{name}")
    painter.end()
    return QIcon(pixmap)


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
        QWidget#chromeGroup {{ background: transparent; }}
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
            background: transparent;
            color: {PRIMARY_TEXT};
            font-size: 16px;
            font-weight: 600;
            padding: 0 12px;
        }}
        QLabel#fileName {{ background: transparent; color: {SECONDARY_TEXT}; font-size: 12px; }}
        QLabel#emptyFolio {{ color: {FOCUS_BLUE}; font-size: 92px; font-weight: 700; }}
        QLabel#emptyTitle {{ color: {PRIMARY_TEXT}; font-size: 21px; font-weight: 600; }}
        QLabel#statusLabel {{ background: transparent; color: {SECONDARY_TEXT}; font-size: 12px; }}
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
