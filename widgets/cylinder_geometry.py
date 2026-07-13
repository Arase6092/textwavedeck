"""圆柱滚筒的纯几何计算，不依赖 Qt。"""

from __future__ import annotations

import math
from dataclasses import dataclass

VISIBLE_RADIUS = 2.55


@dataclass(frozen=True, slots=True)
class CylinderPose:
    """单页在圆柱舞台中的归一化姿态。"""

    x_factor: float
    scale: float
    horizontal_scale: float
    opacity: float
    z_value: float
    visible: bool


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
