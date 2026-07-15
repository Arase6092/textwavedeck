"""幻灯片预览控件：缩放、拖动和适应窗口。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from app.theme import STAGE_BACKGROUND, STAGE_SAFE_MARGIN, stage_background_gradient


def classify_release(
    delta_x: float,
    delta_y: float,
    *,
    fit_mode: bool,
    threshold: float = 80.0,
) -> str | None:
    """判断长距离水平拖动方向，放大状态仍允许切页。"""
    if abs(delta_x) < threshold or abs(delta_x) <= abs(delta_y) * 1.25:
        return None
    return "next" if delta_x < 0 else "previous"


class SlideViewer(QGraphicsView):
    """使用 Graphics View 实现大图平移和缩放。"""

    previous_requested = Signal()
    next_requested = Signal()
    slideshow_click_started = Signal()
    double_clicked = Signal()
    fit_mode_changed = Signal(bool)
    VALID_INTERACTION_MODES = {"gesture", "preview", "slideshow"}

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._zoom = 1.0
        self._fit_mode = True
        self._fit_margin = STAGE_SAFE_MARGIN
        self._interaction_mode = "gesture"
        self._drag_start: QPoint | None = None
        self._press_point: QPoint | None = None
        self._laser_pointer_item: QGraphicsEllipseItem | None = None
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
        self._laser_pointer_item = None
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
        available_width = max(1.0, self.viewport().width() - self._fit_margin * 2)
        available_height = max(1.0, self.viewport().height() - self._fit_margin * 2)
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

    def set_zoom_factor(self, value: float) -> float:
        """按绝对比例缩放，供双手距离手势避免逐帧累计误差。"""
        next_zoom = max(0.25, min(4.0, round(float(value), 2)))
        if next_zoom == self._zoom:
            return self._zoom
        factor = next_zoom / max(0.01, self._zoom)
        self.scale(factor, factor)
        self._zoom = next_zoom
        self._set_fit_mode(False)
        return self._zoom

    def pan_by_fraction(self, delta_x: float, delta_y: float) -> None:
        """按视口比例平移页面，供掌心平移手势调用。"""
        if self._pixmap_item is None:
            return
        pixel_x = int(delta_x * self.viewport().width())
        pixel_y = int(delta_y * self.viewport().height())
        if pixel_x == 0 and pixel_y == 0:
            return
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - pixel_x)
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - pixel_y)
        self._set_fit_mode(False)

    def set_laser_pointer(self, x: float, y: float) -> None:
        """在当前页上显示激光点。"""
        if self._pixmap_item is None:
            return
        scene_rect = self.scene().sceneRect()
        if scene_rect.isNull():
            return
        normalized_x = max(0.0, min(1.0, float(x)))
        normalized_y = max(0.0, min(1.0, float(y)))
        scene_x = scene_rect.left() + scene_rect.width() * normalized_x
        scene_y = scene_rect.top() + scene_rect.height() * normalized_y
        self._show_laser_pointer_at_scene_position(scene_x, scene_y)

    def show_laser_pointer_at_viewport_center(self) -> tuple[float, float] | None:
        """在当前可见视口的中心显示激光点，并返回对应页面坐标。"""
        if self._pixmap_item is None:
            return None
        scene_rect = self.scene().sceneRect()
        if scene_rect.isNull():
            return None
        center = self.mapToScene(self.viewport().rect().center())
        self._show_laser_pointer_at_scene_position(center.x(), center.y())
        return (
            (center.x() - scene_rect.left()) / scene_rect.width(),
            (center.y() - scene_rect.top()) / scene_rect.height(),
        )

    def _show_laser_pointer_at_scene_position(self, scene_x: float, scene_y: float) -> None:
        """在指定场景坐标显示激光点。"""
        item = self._laser_pointer_item
        if item is None:
            item = QGraphicsEllipseItem()
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            item.setZValue(10_000)
            item.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
            item.setBrush(QBrush(QColor(255, 52, 52, 220)))
            self.scene().addItem(item)
            self._laser_pointer_item = item
        radius = 9.0
        item.setRect(-radius, -radius, radius * 2, radius * 2)
        item.setPos(scene_x, scene_y)
        item.show()

    def clear_laser_pointer(self) -> None:
        """隐藏激光点。"""
        if self._laser_pointer_item is not None:
            self._laser_pointer_item.hide()

    @property
    def is_fit_mode(self) -> bool:
        """返回当前是否处于适应窗口状态。"""
        return self._fit_mode

    @property
    def zoom_factor(self) -> float:
        """返回逻辑缩放倍数。"""
        return self._zoom

    def set_fit_margin(self, margin: int) -> None:
        """设置适应窗口边距；PPT 放映模式使用 0 以贴近真实放映。"""
        self._fit_margin = max(0, int(margin))
        if self._fit_mode:
            self.fit_in_view()

    def set_powerpoint_mode(self, enabled: bool) -> None:
        """兼容旧调用，映射为放映或手势交互策略。"""
        self.set_interaction_mode("slideshow" if enabled else "gesture")

    @property
    def interaction_mode(self) -> str:
        """返回当前鼠标交互策略。"""
        return self._interaction_mode

    def set_interaction_mode(self, mode: str) -> None:
        """设置手势、预览或放映鼠标策略，并清理待处理点击。"""
        if mode not in self.VALID_INTERACTION_MODES:
            raise ValueError(f"未知页面交互模式：{mode}")
        self._interaction_mode = mode
        self._drag_start = None
        self._press_point = None
        if mode != "gesture":
            self.clear_laser_pointer()

    def _set_fit_mode(self, value: bool) -> None:
        if self._fit_mode != value:
            self._fit_mode = value
            self.fit_mode_changed.emit(value)

    def wheelEvent(self, event) -> None:  # noqa: N802
        """滚轮缩放；按住 Ctrl 时也支持缩放。"""
        if self._interaction_mode == "slideshow":
            delta = event.angleDelta().x() or event.angleDelta().y()
            if delta > 0:
                self.previous_requested.emit()
            elif delta < 0:
                self.next_requested.emit()
            event.accept()
            return
        if self._interaction_mode == "preview":
            event.accept()
            return
        delta = 0.1 if event.angleDelta().y() > 0 else -0.1
        self.change_zoom(delta)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """按住左键进入拖动模式。"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._interaction_mode != "gesture":
                self._press_point = event.position().toPoint()
                if self._interaction_mode == "slideshow":
                    self.slideshow_click_started.emit()
                event.accept()
                return
            self._drag_start = event.position().toPoint()
            self._press_point = self._drag_start
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """拖动已放大的图片。"""
        if self._interaction_mode != "gesture" and self._press_point is not None:
            event.accept()
            return
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
            if self._interaction_mode == "slideshow":
                if press_point is not None and (release_point - press_point).manhattanLength() < 7:
                    self.next_requested.emit()
                event.accept()
                return
            if self._interaction_mode == "preview":
                event.accept()
                return
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
        """将双击交给预览、放映或手势工作区处理。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_point = None
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def drawBackground(self, painter, rect) -> None:  # noqa: N802
        """绘制固定暗色渐变背景，避免单页舞台变成纯黑画布。"""
        painter.fillRect(rect, stage_background_gradient(rect))

    def resizeEvent(self, event) -> None:  # noqa: N802
        """适应窗口模式下随舞台大小重新计算显示比例。"""
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit_in_view()
