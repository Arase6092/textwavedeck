"""手部关键点容器。"""

from __future__ import annotations


class HandLandmarks(list):
    """携带左右手标签的关键点列表，兼容原有 list 访问方式。"""

    def __init__(
        self,
        landmarks: list[tuple[float, float, float]],
        handedness: str | None = None,
    ) -> None:
        super().__init__(landmarks)
        self.handedness = handedness
