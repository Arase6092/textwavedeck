"""幻灯片预览控件：缩放、拖动和适应窗口。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


class SlideViewer(QGraphicsView):
    """使用 Graphics View 实现大图平移和缩放。"""

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._zoom = 1.0
        self._drag_start: QPoint | None = None
        self.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def show_image(self, path: str, fit: bool = True) -> None:
        """加载当前页图片，默认适应窗口。"""
        pixmap = QPixmap(str(Path(path)))
        self.scene().clear()
        self._pixmap_item = self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(self._pixmap_item.boundingRect())
        self._zoom = 1.0
        if fit:
            self.fit_in_view()

    def fit_in_view(self) -> None:
        """将图片完整放入预览区域。"""
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 1.0

    def reset_zoom(self) -> None:
        """恢复 100% 原始比例。"""
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self._zoom = 1.0
        self.centerOn(self._pixmap_item)

    def change_zoom(self, delta: float) -> float:
        """以鼠标位置为中心调整缩放。"""
        next_zoom = max(0.25, min(4.0, self._zoom + delta))
        factor = next_zoom / self._zoom
        self.scale(factor, factor)
        self._zoom = next_zoom
        return self._zoom

    def wheelEvent(self, event) -> None:  # noqa: N802
        """滚轮缩放；按住 Ctrl 时也支持缩放。"""
        delta = 0.1 if event.angleDelta().y() > 0 else -0.1
        self.change_zoom(delta)
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """按住左键进入拖动模式。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """拖动已放大的图片。"""
        if self._drag_start is not None:
            current = event.position().toPoint()
            delta = current - self._drag_start
            self._drag_start = current
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """结束拖动。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)
