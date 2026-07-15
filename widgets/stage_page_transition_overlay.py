"""单页舞台左右 Push 翻页动效。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from app.theme import STAGE_SAFE_MARGIN, stage_background_gradient


class StagePageTransitionOverlay(QWidget):
    """在手势单页放映中绘制旧页和新页的左右推入效果。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._progress = 0.0
        self._direction = "next"
        self._old_pixmap = QPixmap()
        self._new_pixmap = QPixmap()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    @Property(float)
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    @property
    def direction(self) -> str:
        return self._direction

    def configure(self, old_path: str, new_path: str, *, direction: str) -> None:
        """载入转场两页；direction 为 next 或 previous。"""
        self._old_pixmap = QPixmap(str(Path(old_path)))
        self._new_pixmap = QPixmap(str(Path(new_path)))
        self._direction = "previous" if direction == "previous" else "next"
        self.progress = 0.0

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), stage_background_gradient(QRectF(self.rect())))
        if self._old_pixmap.isNull() or self._new_pixmap.isNull():
            return

        base_rect = self._stage_rect(self._old_pixmap)
        width = float(self.width())
        offset = width * self._progress
        if self._direction == "next":
            old_rect = base_rect.translated(-offset, 0)
            new_rect = base_rect.translated(width - offset, 0)
        else:
            old_rect = base_rect.translated(offset, 0)
            new_rect = base_rect.translated(-width + offset, 0)

        painter.drawPixmap(old_rect, self._old_pixmap, QRectF(self._old_pixmap.rect()))
        painter.drawPixmap(new_rect, self._new_pixmap, QRectF(self._new_pixmap.rect()))

    def _stage_rect(self, pixmap: QPixmap) -> QRectF:
        available_width = max(1.0, self.width() - STAGE_SAFE_MARGIN * 2)
        available_height = max(1.0, self.height() - STAGE_SAFE_MARGIN * 2)
        scale = min(available_width / max(1, pixmap.width()), available_height / max(1, pixmap.height()))
        width = pixmap.width() * scale
        height = pixmap.height() * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
