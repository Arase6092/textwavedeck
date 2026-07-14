"""圆柱滚筒的纯几何计算，不依赖 Qt。"""

from __future__ import annotations

import math
from dataclasses import dataclass

VISIBLE_RADIUS = 2.55
CAROUSEL_HEIGHT_RATIO = 0.67
CAROUSEL_MAX_WIDTH_RATIO = 0.86
CAROUSEL_RADIUS_RATIO = 0.49
CAROUSEL_RADIUS_MAX = 660.0
CAROUSEL_CENTER_Y_OFFSET = -4.0
CAROUSEL_DEPTH_DROP = 92.0


@dataclass(frozen=True, slots=True)
class CylinderPose:
    """单页在圆柱舞台中的归一化姿态。"""

    x_factor: float
    scale: float
    horizontal_scale: float
    opacity: float
    z_value: float
    visible: bool


@dataclass(frozen=True, slots=True)
class CarouselLayer:
    """滚筒中可见页面的归一化目标布局。"""

    index: int
    relative: int
    x_factor: float
    scale: float
    horizontal_scale: float
    opacity: float
    z_value: float


@dataclass(frozen=True, slots=True)
class CarouselViewportGeometry:
    """滚筒和转场共享的响应式舞台尺寸。"""

    center_x: float
    center_y: float
    radius: float
    target_height: float
    max_page_width: float
    depth_drop: float


def carousel_viewport_geometry(width: float, height: float) -> CarouselViewportGeometry:
    """按视口尺寸计算已确认的紧凑滚筒舞台。"""
    safe_width = max(1.0, float(width))
    safe_height = max(1.0, float(height))
    return CarouselViewportGeometry(
        center_x=safe_width / 2.0,
        center_y=safe_height / 2.0 + CAROUSEL_CENTER_Y_OFFSET,
        radius=min(safe_width * CAROUSEL_RADIUS_RATIO, CAROUSEL_RADIUS_MAX),
        target_height=safe_height * CAROUSEL_HEIGHT_RATIO,
        max_page_width=safe_width * CAROUSEL_MAX_WIDTH_RATIO,
        depth_drop=CAROUSEL_DEPTH_DROP,
    )


def fit_carousel_page(geometry: CarouselViewportGeometry, aspect_ratio: float) -> tuple[float, float]:
    """保持页面比例并应用高度目标和窄窗宽度上限。"""
    safe_aspect = max(0.01, float(aspect_ratio))
    height = geometry.target_height
    width = height * safe_aspect
    if width > geometry.max_page_width:
        width = geometry.max_page_width
        height = width / safe_aspect
    return width, height


def cylinder_pose(relative_offset: float) -> CylinderPose:
    """根据页面相对滚筒中心的偏移计算透视姿态。"""
    distance = abs(relative_offset)
    clamped = min(distance, 2.0)
    direction = -1.0 if relative_offset < 0 else 1.0
    return CylinderPose(
        x_factor=direction * math.sin(clamped * 0.68) if distance else 0.0,
        scale=max(0.56, 1.0 - 0.22 * clamped),
        horizontal_scale=max(0.34, math.cos(clamped * 0.61)),
        opacity=max(0.18, 1.0 - 0.42 * clamped),
        z_value=max(0.0, 100.0 - 38.0 * clamped),
        visible=distance <= VISIBLE_RADIUS,
    )


def snap_index(offset: float, page_count: int) -> int:
    """将连续滚筒偏移吸附到最近的有效页面索引。"""
    if page_count <= 0:
        return 0
    nearest = math.floor(offset + 0.5)
    return max(0, min(nearest, page_count - 1))


def inertia_target(offset: float, velocity: float, page_count: int) -> int:
    """按释放速度预测目标页，并限制单次惯性最多跨越两页。"""
    if page_count <= 0:
        return 0
    current = snap_index(offset, page_count)
    predicted = snap_index(offset + velocity * 180.0, page_count)
    lower = max(0, current - 2)
    upper = min(page_count - 1, current + 2)
    return max(lower, min(predicted, upper))
