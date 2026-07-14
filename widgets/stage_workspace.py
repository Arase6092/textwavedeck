"""圆柱滚筒与单页舞台的统一工作区。"""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtWidgets import QStackedLayout, QWidget

from models.slide_project import SlidePage, SlideProject
from widgets.cylinder_carousel import CylinderCarousel
from widgets.slide_viewer import SlideViewer
from widgets.stage_recomposition_overlay import StageRecompositionOverlay


class StageWorkspace(QWidget):
    """在滚筒选页和单页舞台间切换并保持共享页码。"""

    page_changed = Signal(int)
    mode_changed = Signal(str)
    zoom_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.carousel = CylinderCarousel()
        self.viewer = SlideViewer()
        self.carousel.setObjectName("cylinderCarousel")
        self.viewer.setObjectName("slideViewer")
        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self._stack.addWidget(self.carousel)
        self._stack.addWidget(self.viewer)
        self._pages: list[SlidePage] = []
        self._current_index = 0
        self._mode = "carousel"
        self._reduced_motion = False
        self._transition_target = "carousel"
        self.viewer.hide()
        self._overlay = StageRecompositionOverlay(self)
        self._transition = QPropertyAnimation(self._overlay, b"progress", self)
        self._transition.finished.connect(self._finish_transition)
        self.carousel.current_page_changed.connect(self._on_carousel_page_changed)
        self.carousel.stage_requested.connect(self.enter_stage)
        self.viewer.previous_requested.connect(self.previous_page)
        self.viewer.next_requested.connect(self.next_page)
        self.viewer.double_clicked.connect(self._on_viewer_double_clicked)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def page_count(self) -> int:
        return len(self._pages)

    @property
    def zoom_factor(self) -> float:
        return self.viewer.zoom_factor

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    def set_project(self, project: SlideProject, current_index: int = 0, *, initial_mode: str = "carousel") -> None:
        """加载项目，并按指定初始模式进入单页放映或滚筒。"""
        self._pages = list(project.pages)
        self._current_index = self._clamp_index(current_index)
        self.carousel.set_pages(self._pages, self._current_index)
        if initial_mode == "stage" and self._pages:
            self.viewer.show_image(self._pages[self._current_index].image_path)
            self._mode = "stage"
            self._finish_mode_immediately("stage")
            self.page_changed.emit(self._current_index)
            self.zoom_changed.emit(self.viewer.zoom_factor)
            return
        self._mode = "carousel"
        self._finish_mode_immediately("carousel")

    def set_reduced_motion(self, reduced: bool) -> None:
        """同步滚筒与模式切换的减少动态设置。"""
        self._reduced_motion = bool(reduced)
        self.carousel.set_reduced_motion(self._reduced_motion)
        if self._transition.state() == QAbstractAnimation.State.Running:
            self._transition.stop()
            self._finish_mode_immediately(self._mode)

    def select_page(self, index: int, *, animate: bool = True) -> bool:
        """选择有效页面，并让当前视图同步显示。"""
        if not self._pages:
            return False
        target = self._clamp_index(index)
        changed = target != self._current_index
        self._current_index = target
        if self._mode == "carousel":
            self.carousel.select_page(target, animate=animate)
        else:
            self.viewer.show_image(self._pages[target].image_path)
            self.zoom_changed.emit(self.viewer.zoom_factor)
        if changed:
            self.page_changed.emit(target)
        return changed

    def previous_page(self) -> bool:
        """前往上一页，第一页时不循环。"""
        if self._current_index <= 0:
            return False
        return self.select_page(self._current_index - 1)

    def next_page(self) -> bool:
        """前往下一页，最后一页时不循环。"""
        if self._current_index >= len(self._pages) - 1:
            return False
        return self.select_page(self._current_index + 1)

    def enter_stage(self, index: int | None = None) -> None:
        """将指定页面放入完整单页舞台。"""
        if not self._pages:
            return
        if index is not None:
            self._current_index = self._clamp_index(index)
        self.viewer.show_image(self._pages[self._current_index].image_path)
        self._set_mode("stage")
        self.page_changed.emit(self._current_index)
        self.zoom_changed.emit(self.viewer.zoom_factor)

    def show_carousel(self) -> None:
        """返回滚筒并保持当前页面位于中央。"""
        if not self._pages:
            return
        self.carousel.select_page(self._current_index, animate=False)
        self._set_mode("carousel")

    def _on_viewer_double_clicked(self) -> None:
        """仅在手势单页中用双击返回滚筒。"""
        if self._mode == "stage" and self.viewer.interaction_mode == "gesture":
            self.show_carousel()

    def change_zoom(self, delta: float) -> float:
        """仅在单页舞台中改变缩放。"""
        if self._mode != "stage":
            return self.viewer.zoom_factor
        zoom = self.viewer.change_zoom(delta)
        self.zoom_changed.emit(zoom)
        return zoom

    def fit_view(self) -> None:
        if self._mode == "stage":
            self.viewer.fit_in_view()
            self.zoom_changed.emit(self.viewer.zoom_factor)

    def reset_zoom(self) -> None:
        if self._mode == "stage":
            self.viewer.reset_zoom()
            self.zoom_changed.emit(self.viewer.zoom_factor)

    def _clamp_index(self, index: int) -> int:
        if not self._pages:
            return 0
        return max(0, min(int(index), len(self._pages) - 1))

    def _on_carousel_page_changed(self, index: int) -> None:
        if index != self._current_index:
            self._current_index = index
            self.page_changed.emit(index)

    def _set_mode(self, mode: str) -> None:
        changed = self._mode != mode
        self._mode = mode
        self._start_transition(mode)
        if changed:
            self.mode_changed.emit(mode)

    def _start_transition(self, mode: str) -> None:
        """用舞台重组 overlay 切换滚筒和单页放映。"""
        self._transition.stop()
        self._transition_target = mode
        if self._reduced_motion:
            self._finish_mode_immediately(mode)
            return

        direction = "to_carousel" if mode == "carousel" else "to_stage"
        if mode == "carousel":
            self.carousel.select_page(self._current_index, animate=False)
        layers = self.carousel.target_layers(self._current_index)
        self._overlay.setGeometry(self.rect())
        self._overlay.configure(self._pages, layers, direction=direction)
        self._overlay.show()
        self._overlay.raise_()
        self.carousel.setEnabled(False)
        self.viewer.setEnabled(False)
        self._transition.setStartValue(0.0)
        self._transition.setEndValue(1.0)
        self._transition.setDuration(720)
        self._transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._transition.start()

    def _finish_transition(self) -> None:
        self._finish_mode_immediately(self._transition_target)

    def _finish_mode_immediately(self, mode: str) -> None:
        target = self.carousel if mode == "carousel" else self.viewer
        outgoing = self.viewer if mode == "carousel" else self.carousel
        self._overlay.hide()
        target.show()
        target.setEnabled(True)
        outgoing.hide()
        outgoing.setEnabled(True)
        self._stack.setCurrentWidget(target)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """窗口变化时让转场 overlay 覆盖整个舞台。"""
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())
