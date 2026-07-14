"""可拖动的圆柱形幻灯片滚筒。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QElapsedTimer, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsColorizeEffect,
    QGraphicsDropShadowEffect,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from app.theme import CONTROL_SURFACE, FOCUS_BLUE, PRIMARY_TEXT, STAGE_BACKGROUND, STRUCTURE_LINE, stage_background_gradient
from models.slide_project import SlidePage
from widgets.cylinder_geometry import cylinder_pose, inertia_target, snap_index


@dataclass(slots=True)
class _CarouselItem:
    root: QGraphicsRectItem
    pixmap: QGraphicsPixmapItem
    colorize: QGraphicsColorizeEffect
    shadow: QGraphicsDropShadowEffect


class CylinderCarousel(QGraphicsView):
    """以 2D 透视模拟圆柱曲面的页面选择控件。"""

    current_page_changed = Signal(int)
    stage_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor(STAGE_BACKGROUND))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self._pages: list[SlidePage] = []
        self._items: list[_CarouselItem] = []
        self._offset = 0.0
        self._current_index = 0
        self._drag_start_x: float | None = None
        self._drag_origin = 0.0
        self._last_x = 0.0
        self._drag_distance = 0.0
        self._velocity = 0.0
        self._elapsed = QElapsedTimer()
        self._animation_target = 0
        self._committed_index = 0
        self._reduced_motion = False
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(260)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(lambda value: self._set_offset(float(value)))
        self._animation.finished.connect(self._finish_animation)

    @property
    def current_index(self) -> int:
        """返回当前位于滚筒中央的页面。"""
        return self._current_index

    @property
    def reduced_motion(self) -> bool:
        """返回当前是否禁用惯性和吸附动画。"""
        return self._reduced_motion

    def set_pages(self, pages: list[SlidePage], current_index: int = 0) -> None:
        """重建滚筒页面并定位到指定索引。"""
        self._animation.stop()
        self.scene().clear()
        self._pages = list(pages)
        self._items = []
        for position, page in enumerate(self._pages):
            root = QGraphicsRectItem(-320, -180, 640, 360)
            root.setData(0, position)
            pixmap = QGraphicsPixmapItem(root)
            colorize = QGraphicsColorizeEffect()
            colorize.setColor(QColor(CONTROL_SURFACE))
            colorize.setStrength(0.0)
            pixmap.setGraphicsEffect(colorize)
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(34)
            shadow.setOffset(0, 12)
            shadow.setColor(QColor(59, 111, 255, 100))
            shadow.setEnabled(False)
            root.setGraphicsEffect(shadow)
            self.scene().addItem(root)
            self._items.append(_CarouselItem(root, pixmap, colorize, shadow))
        self._current_index = snap_index(float(current_index), len(self._pages))
        self._committed_index = self._current_index
        self._offset = float(self._current_index)
        self._update_scene_rect()
        self._layout_items()

    def select_page(self, index: int, *, animate: bool = True) -> None:
        """选择页面；越界索引会夹取到首尾页。"""
        if not self._pages:
            return
        target = max(0, min(int(index), len(self._pages) - 1))
        if not animate:
            self._set_offset(float(target), commit=True)
            return
        self._animate_to(target)

    def set_reduced_motion(self, reduced: bool) -> None:
        """减少动态时停止惯性，并让后续选页立即吸附。"""
        self._reduced_motion = bool(reduced)
        if self._reduced_motion:
            self._animation.stop()
            self._set_offset(float(snap_index(self._offset, len(self._pages))), commit=True)

    def activate_page(self, index: int) -> None:
        """侧页先居中；已居中的页面再次激活时进入舞台。"""
        if not self._pages:
            return
        target = max(0, min(int(index), len(self._pages) - 1))
        if target == self._current_index and abs(self._offset - target) < 0.08:
            self.stage_requested.emit(target)
        else:
            self.select_page(target)

    def _update_scene_rect(self) -> None:
        width = max(800, self.viewport().width())
        height = max(520, self.viewport().height())
        self.scene().setSceneRect(0, 0, width, height)

    def _ensure_pixmap(self, index: int) -> None:
        item = self._items[index]
        if not item.pixmap.pixmap().isNull():
            return
        pixmap = QPixmap(str(Path(self._pages[index].thumbnail_path)))
        if pixmap.isNull():
            return
        width, height = pixmap.width(), pixmap.height()
        item.root.setRect(-width / 2, -height / 2, width, height)
        item.pixmap.setPixmap(pixmap)
        item.pixmap.setOffset(-width / 2, -height / 2)
        item.pixmap.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def _layout_items(self) -> None:
        if not self._items:
            return
        scene_rect = self.sceneRect()
        center_x = scene_rect.center().x()
        center_y = scene_rect.center().y() - 8
        radius = min(scene_rect.width() * 0.47, 620.0)
        target_height = scene_rect.height() * 0.58
        for index, item in enumerate(self._items):
            relative = index - self._offset
            pose = cylinder_pose(relative)
            item.root.setVisible(pose.visible)
            if not pose.visible:
                item.pixmap.setPixmap(QPixmap())
                continue
            self._ensure_pixmap(index)
            height = max(1.0, item.root.rect().height())
            base_scale = target_height / height
            transform = QTransform().scale(
                base_scale * pose.scale * pose.horizontal_scale,
                base_scale * pose.scale,
            )
            item.root.setTransform(transform)
            depth_drop = (1.0 - pose.scale) * 110.0
            item.root.setPos(center_x + pose.x_factor * radius, center_y + depth_drop)
            item.root.setOpacity(pose.opacity)
            item.root.setZValue(pose.z_value)
            distance = abs(relative)
            item.colorize.setStrength(min(0.82, distance * 0.34))
            centered = distance < 0.35
            item.shadow.setEnabled(centered)
            pen = QPen(QColor(PRIMARY_TEXT) if centered else QColor(STRUCTURE_LINE))
            pen.setWidth(2 if centered else 1)
            pen.setCosmetic(True)
            item.root.setPen(pen)

    def _set_offset(self, value: float, *, commit: bool = False) -> None:
        if not self._pages:
            return
        self._offset = max(0.0, min(value, len(self._pages) - 1.0))
        nearest = snap_index(self._offset, len(self._pages))
        self._current_index = nearest
        if commit and nearest != self._committed_index:
            self._committed_index = nearest
            self.current_page_changed.emit(nearest)
        self._layout_items()

    def _animate_to(self, index: int) -> None:
        self._animation.stop()
        self._animation_target = index
        if self._reduced_motion:
            self._set_offset(float(index), commit=True)
            return
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(float(index))
        distance = abs(self._offset - index)
        self._animation.setDuration(max(180, min(320, round(180 + distance * 55))))
        self._animation.start()

    def _finish_animation(self) -> None:
        self._set_offset(float(self._animation_target), commit=True)

    def drawBackground(self, painter: QPainter, rect) -> None:  # noqa: N802
        """绘制固定暗场和不随滚筒移动的水平参照线。"""
        painter.fillRect(rect, stage_background_gradient(rect))
        pen = QPen(QColor(STRUCTURE_LINE))
        pen.setWidth(1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        y = self.sceneRect().center().y() + 8
        painter.drawLine(rect.left(), y, rect.right(), y)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """窗口变化时重新计算舞台半径和页面尺寸。"""
        super().resizeEvent(event)
        self._update_scene_rect()
        self._layout_items()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """记录滚筒拖动起点。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._animation.stop()
            self._drag_start_x = event.position().x()
            self._drag_origin = self._offset
            self._last_x = self._drag_start_x
            self._drag_distance = 0.0
            self._velocity = 0.0
            self._elapsed.start()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """根据水平位移连续旋转滚筒。"""
        if self._drag_start_x is not None:
            current_x = event.position().x()
            pixels_per_page = max(140.0, self.viewport().width() * 0.18)
            delta_x = current_x - self._drag_start_x
            self._drag_distance = max(self._drag_distance, abs(delta_x))
            elapsed = max(1, self._elapsed.restart())
            self._velocity = -(current_x - self._last_x) / pixels_per_page / elapsed
            self._last_x = current_x
            self._set_offset(self._drag_origin - delta_x / pixels_per_page)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """松手后加入短惯性并吸附，或将点击页面激活。"""
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_x is not None:
            self._drag_start_x = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if self._drag_distance >= 7:
                target = inertia_target(self._offset, self._velocity, len(self._pages))
                self._animate_to(target)
            else:
                graphics_item = self.itemAt(event.position().toPoint())
                while graphics_item is not None and graphics_item.data(0) is None:
                    graphics_item = graphics_item.parentItem()
                if graphics_item is not None:
                    self.activate_page(int(graphics_item.data(0)))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """滚轮按一个页面步长旋转滚筒。"""
        delta = event.angleDelta().x() or event.angleDelta().y()
        if delta:
            self._animation.stop()
            self.select_page(self._current_index + (-1 if delta > 0 else 1))
            event.accept()
            return
        super().wheelEvent(event)
