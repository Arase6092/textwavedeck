"""页面浏览统一命令。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NavigationState:
    """维护当前页面和缩放状态。"""

    page_count: int = 0
    current_page: int = 0
    zoom: float = 1.0

    def set_page_count(self, count: int) -> None:
        """设置页面数量并将当前页限制在有效范围。"""
        self.page_count = max(0, count)
        self.current_page = max(0, min(self.current_page, max(0, self.page_count - 1)))

    def previous(self) -> bool:
        """前往上一页，第一页时不循环。"""
        if self.current_page <= 0:
            return False
        self.current_page -= 1
        return True

    def next(self) -> bool:
        """前往下一页，最后一页时不循环。"""
        if self.current_page >= self.page_count - 1:
            return False
        self.current_page += 1
        return True

    def select(self, index: int) -> bool:
        """直接选页并校验边界。"""
        if not 0 <= index < self.page_count:
            return False
        changed = self.current_page != index
        self.current_page = index
        return changed

    def change_zoom(self, delta: float) -> float:
        """调整缩放并限制在 25% 到 400%。"""
        self.zoom = max(0.25, min(4.0, round(self.zoom + delta, 2)))
        return self.zoom

    def set_zoom_factor(self, value: float) -> float:
        """设置绝对缩放值并限制在 25% 到 400%。"""
        self.zoom = max(0.25, min(4.0, round(float(value), 2)))
        return self.zoom

    def reset_zoom(self) -> None:
        """重置为 100%。"""
        self.zoom = 1.0
