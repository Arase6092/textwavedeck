"""圆柱滚筒的纯几何计算，不依赖 Qt。"""

from __future__ import annotations

import math
from dataclasses import dataclass

ANGLE_PER_PAGE = 0.52
MAX_ANGLE = 1.35
VISIBLE_RADIUS = 3.25


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
    angle = max(-MAX_ANGLE, min(MAX_ANGLE, relative_offset * ANGLE_PER_PAGE))
    front = max(0.0, math.cos(angle))
    return CylinderPose(
        x_factor=math.sin(angle),
        scale=0.62 + 0.38 * front,
        horizontal_scale=max(0.34, front),
        opacity=0.30 + 0.70 * front,
        z_value=front * 100.0,
        visible=abs(relative_offset) <= VISIBLE_RADIUS,
    )


def snap_index(offset: float, page_count: int) -> int:
    """将连续滚筒偏移吸附到最近的有效页面索引。"""
    if page_count <= 0:
        return 0
    nearest = math.floor(offset + 0.5)
    return max(0, min(nearest, page_count - 1))
