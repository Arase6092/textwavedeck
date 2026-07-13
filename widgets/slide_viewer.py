"""幻灯片预览控件：缩放、拖动和适应窗口。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from app.theme import STAGE_BACKGROUND, STAGE_SAFE_MARGIN


def classify_release(
    delta_x: float,
    delta_y: float,
    *,
    fit_mode: bool,
    threshold: float = 80.0,
) -> str | None:
    """判断适应窗口状态下的水平滑动方向。"""
    if not fit_mode or abs(delta_x) < threshold or abs(delta_x) <= abs(delta_y) * 1.25:
        return None
    return "next" if delta_x < 0 else "previous"


class SlideViewer(QGraphicsView):
    """使用 Graphics View 实现大图平移和缩放。"""

    previous_requested = Signal()
    next_requested = Signal()
    fit_mode_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._zoom = 1.0
        self._fit_mode = True
        self._drag_start: QPoint | None = None
        self._press_point: QPoint | None = None
        self.setBackgroundBrush(QColor(STAGE_BACKGROUND))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def show_image(self, path: str, fit: bool = True) -> None:
        """加载当前页图片，默认适应窗口。"""
        pixmap = QPixmap(str(Path(path)))
        self.scene().clear()
        self._pixmap_item = self.scene().addPixmap(pixmap)
        self._pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene().setSceneRect(self._pixmap_item.boundingRect())
        self._zoom = 1.0
        if fit:
            self.fit_in_view()

    def fit_in_view(self) -> None:
        """将图片完整放入预览区域。"""
        if self._pixmap_item is None:
            return
        self.resetTransform()
        bounds = self._pixmap_item.boundingRect()
        available_width = max(1.0, self.viewport().width() - STAGE_SAFE_MARGIN * 2)
        available_height = max(1.0, self.viewport().height() - STAGE_SAFE_MARGIN * 2)
        factor = min(available_width / max(1.0, bounds.width()), available_height / max(1.0, bounds.height()))
        self.scale(factor, factor)
        self._pixmap_item.setPos(0, 0)
        self.centerOn(self._pixmap_item)
        self._zoom = 1.0
        self._set_fit_mode(True)

    def reset_zoom(self) -> None:
        """恢复 100% 原始比例。"""
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self._zoom = 1.0
        self.centerOn(self._pixmap_item)
        self._set_fit_mode(False)

    def change_zoom(self, delta: float) -> float:
        """以鼠标位置为中心调整缩放。"""
        next_zoom = max(0.25, min(4.0, self._zoom + delta))
        factor = next_zoom / self._zoom
        self.scale(factor, factor)
        self._zoom = next_zoom
        self._set_fit_mode(False)
        return self._zoom

    @property
    def is_fit_mode(self) -> bool:
        """返回当前是否处于适应窗口状态。"""
        return self._fit_mode

    @property
    def zoom_factor(self) -> float:
        """返回逻辑缩放倍数。"""
        return self._zoom

    def _set_fit_mode(self, value: bool) -> None:
        if self._fit_mode != value:
            self._fit_mode = value
            self.fit_mode_changed.emit(value)

    def wheelEvent(self, event) -> None:  # noqa: N802
        """滚轮缩放；按住 Ctrl 时也支持缩放。"""
        delta = 0.1 if event.angleDelta().y() > 0 else -0.1
        self.change_zoom(delta)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """按住左键进入拖动模式。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self._press_point = self._drag_start
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """拖动已放大的图片。"""
        if self._drag_start is not None:
            current = event.position().toPoint()
            if self._fit_mode and self._press_point is not None:
                if self._pixmap_item is not None:
                    total = current - self._press_point
                    self._pixmap_item.setPos(total.x() * 0.22, 0)
                event.accept()
                return
            delta = current - self._drag_start
            self._drag_start = current
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """结束拖动。"""
        if event.button() == Qt.MouseButton.LeftButton:
            release_point = event.position().toPoint()
            press_point = self._press_point
            self._drag_start = None
            self._press_point = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if self._pixmap_item is not None:
                self._pixmap_item.setPos(0, 0)
            if press_point is not None:
                delta = release_point - press_point
                action = classify_release(delta.x(), delta.y(), fit_mode=self._fit_mode)
                if action == "next":
                    self.next_requested.emit()
                elif action == "previous":
                    self.previous_requested.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """双击在适应窗口和 100% 原始比例间切换。"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._fit_mode:
                self.reset_zoom()
            else:
                self.fit_in_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """适应窗口模式下随舞台大小重新计算显示比例。"""
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit_in_view()
