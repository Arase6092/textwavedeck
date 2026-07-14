"""单页放映与圆柱滚筒之间的舞台重组过渡层。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from app.theme import FOCUS_BLUE, STAGE_SAFE_MARGIN, stage_background_gradient
from models.slide_project import SlidePage
from widgets.cylinder_geometry import CarouselLayer


class StageRecompositionOverlay(QWidget):
    """只在转场期间绘制页面快照，避免真实控件布局跳变。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._pages: list[SlidePage] = []
        self._layers: list[CarouselLayer] = []
        self._direction = "to_carousel"
        self._progress = 0.0
        self._pixmaps: dict[str, QPixmap] = {}
        self.hide()

    def configure(self, pages: list[SlidePage], layers: list[CarouselLayer], *, direction: str) -> None:
        """准备本次转场的页面和方向。"""
        self._pages = list(pages)
        self._layers = list(layers)
        self._direction = direction
        self._progress = 0.0
        self._pixmaps.clear()
        self.update()

    def get_progress(self) -> float:
        """返回动画进度。"""
        return self._progress

    def set_progress(self, value: float) -> None:
        """设置动画进度并重绘。"""
        self._progress = max(0.0, min(float(value), 1.0))
        self.update()

    progress = Property(float, get_progress, set_progress)

    def paintEvent(self, _event) -> None:  # noqa: N802
        """绘制固定背景和正在重组的页面。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), stage_background_gradient(QRectF(self.rect())))
        progress = self._ease(self._progress)
        for layer in sorted(self._layers, key=lambda layer: layer.z_value):
            pixmap = self._load_pixmap(layer.index)
            if pixmap.isNull():
                continue
            rect, opacity = self._layer_state(layer, pixmap, progress)
            painter.setOpacity(opacity)
            self._draw_shadow(painter, rect, layer.relative)
            painter.drawPixmap(rect, pixmap, QRectF(pixmap.rect()))
        painter.setOpacity(1.0)

    def _load_pixmap(self, index: int) -> QPixmap:
        """按需加载页面图，优先使用原图以保证转场清晰。"""
        if index < 0 or index >= len(self._pages):
            return QPixmap()
        path = self._pages[index].image_path or self._pages[index].thumbnail_path
        cached = self._pixmaps.get(path)
        if cached is not None:
            return cached
        pixmap = QPixmap(str(Path(path)))
        self._pixmaps[path] = pixmap
        return pixmap

    def _layer_state(self, layer: CarouselLayer, pixmap: QPixmap, progress: float) -> tuple[QRectF, float]:
        """计算页面在当前进度下的位置和透明度。"""
        stage = self._stage_rect(pixmap)
        carousel = self._carousel_rect(layer, pixmap)
        side = self._side_start_rect(layer, carousel)
        if layer.relative == 0:
            start = stage if self._direction == "to_carousel" else carousel
            end = carousel if self._direction == "to_carousel" else stage
            opacity_start = 1.0
            opacity_end = 1.0
        elif self._direction == "to_carousel":
            start = side
            end = carousel
            opacity_start = 0.0
            opacity_end = layer.opacity
        else:
            start = carousel
            end = side
            opacity_start = layer.opacity
            opacity_end = 0.0
        return self._lerp_rect(start, end, progress), opacity_start + (opacity_end - opacity_start) * progress

    def _stage_rect(self, pixmap: QPixmap) -> QRectF:
        """计算普通放映状态下的适应窗口矩形。"""
        available_width = max(1.0, self.width() - STAGE_SAFE_MARGIN * 2)
        available_height = max(1.0, self.height() - STAGE_SAFE_MARGIN * 2)
        factor = min(available_width / max(1, pixmap.width()), available_height / max(1, pixmap.height()))
        width = pixmap.width() * factor
        height = pixmap.height() * factor
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def _carousel_rect(self, layer: CarouselLayer, pixmap: QPixmap) -> QRectF:
        """计算圆柱滚筒目标矩形。"""
        center_x = self.width() / 2
        center_y = self.height() / 2 - 8
        radius = min(self.width() * 0.47, 620.0)
        target_height = self.height() * 0.58
        height = target_height * layer.scale
        aspect = pixmap.width() / max(1, pixmap.height())
        width = height * aspect * layer.horizontal_scale
        depth_drop = (1.0 - layer.scale) * 110.0
        return QRectF(center_x + layer.x_factor * radius - width / 2, center_y + depth_drop - height / 2, width, height)

    def _side_start_rect(self, layer: CarouselLayer, carousel: QRectF) -> QRectF:
        """侧页从舞台暗处进入或退场。"""
        direction = -1 if layer.relative < 0 else 1
        x = -carousel.width() * 0.72 if direction < 0 else self.width() - carousel.width() * 0.28
        y = carousel.y() + carousel.height() * 0.18
        return QRectF(x, y, carousel.width() * 0.82, carousel.height() * 0.82)

    def _draw_shadow(self, painter: QPainter, rect: QRectF, relative: int) -> None:
        """给页面绘制低调阴影和中央页焦点边框。"""
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 95 if relative == 0 else 55))
        painter.drawRoundedRect(rect.adjusted(0, 14, 0, 18), 8, 8)
        if relative == 0:
            painter.setPen(QColor(FOCUS_BLUE))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 4, 4)
        painter.restore()

    @staticmethod
    def _lerp_rect(start: QRectF, end: QRectF, progress: float) -> QRectF:
        """线性插值矩形。"""
        return QRectF(
            start.x() + (end.x() - start.x()) * progress,
            start.y() + (end.y() - start.y()) * progress,
            start.width() + (end.width() - start.width()) * progress,
            start.height() + (end.height() - start.height()) * progress,
        )

    @staticmethod
    def _ease(value: float) -> float:
        """平滑进度，让重组转场有轻微缓入缓出。"""
        value = max(0.0, min(float(value), 1.0))
        return value * value * (3.0 - 2.0 * value)
