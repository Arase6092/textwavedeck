"""舞台顶部和底部控制层的定位与自动隐藏。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPropertyAnimation, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsOpacityEffect, QWidget

from app.theme import (
    BOTTOM_CHROME_HEIGHT,
    BOTTOM_REVEAL_HEIGHT,
    CHROME_FADE_DURATION_MS,
    CHROME_HIDE_DELAY_MS,
    TOP_CHROME_HEIGHT,
    TOP_REVEAL_HEIGHT,
)


class StageChrome(QObject):
    """将两个控制条覆盖在舞台边缘并按交互自动显隐。"""

    def __init__(
        self,
        host: QWidget,
        top_bar: QFrame,
        bottom_bar: QFrame,
        *,
        hide_delay_ms: int = CHROME_HIDE_DELAY_MS,
        fade_duration_ms: int = CHROME_FADE_DURATION_MS,
        reduced_motion: bool = False,
    ) -> None:
        super().__init__(host)
        self._host = host
        self._top_bar = top_bar
        self._bottom_bar = bottom_bar
        self._hide_delay_ms = max(0, hide_delay_ms)
        self._fade_duration_ms = max(0, fade_duration_ms)
        self._reduced_motion = reduced_motion
        self._locked = False
        self._suppressed = False
        self._disposed = False
        self._tracked: list[QWidget] = []
        self._hide_after_animation: dict[QWidget, bool] = {}
        self._effects: dict[QWidget, QGraphicsOpacityEffect] = {}
        self._animations: dict[QWidget, QPropertyAnimation] = {}

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_now)

        for bar in (self._top_bar, self._bottom_bar):
            effect = QGraphicsOpacityEffect(bar)
            effect.setOpacity(1.0)
            bar.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.finished.connect(lambda bar=bar: self._on_animation_finished(bar))
            self._effects[bar] = effect
            self._animations[bar] = animation
            self._hide_after_animation[bar] = False

        self._track_widget_tree(host)
        self._position_bars()
        self.reveal_all()

    @property
    def locked(self) -> bool:
        """返回控制层是否被导入或错误状态锁定。"""
        return self._locked

    def reveal_all(self, minimum_visible_ms: int = 1500) -> None:
        """显示两个控制层，并在最短可见时间后重新计时。"""
        if self._disposed:
            return
        if self._suppressed and not self._locked:
            return
        self._show_bar(self._top_bar)
        self._show_bar(self._bottom_bar)
        self._schedule_hide(max(self._hide_delay_ms, max(0, minimum_visible_ms)))

    def reveal_for_position(self, y: int, height: int) -> None:
        """鼠标进入上下边缘时只显示对应控制层。"""
        if self._disposed or height <= 0:
            return
        if self._suppressed and not self._locked:
            return
        revealed = False
        if 0 <= y <= TOP_REVEAL_HEIGHT:
            self._show_bar(self._top_bar)
            revealed = True
        if height - BOTTOM_REVEAL_HEIGHT <= y <= height:
            self._show_bar(self._bottom_bar)
            revealed = True
        if revealed:
            self._schedule_hide(self._hide_delay_ms)

    def hide_now(self) -> None:
        """立即开始隐藏；锁定或控制项持有焦点时保持可见。"""
        if self._disposed:
            return
        self._hide_timer.stop()
        if self._locked or (self._has_chrome_focus() and not self._suppressed):
            self._show_bar(self._top_bar)
            self._show_bar(self._bottom_bar)
            return
        self._hide_bar(self._top_bar)
        self._hide_bar(self._bottom_bar)

    def set_locked(self, locked: bool) -> None:
        """导入或错误状态下锁定控制层可见性。"""
        self._locked = bool(locked)
        if self._locked:
            self._hide_timer.stop()
            self._show_bar(self._top_bar)
            self._show_bar(self._bottom_bar)
        elif self._suppressed:
            self._hide_all_immediately()
        else:
            self.reveal_all()

    def set_suppressed(self, suppressed: bool) -> None:
        """PPT 放映模式下抑制应用控制层，保留锁定状态的中文提示。"""
        self._suppressed = bool(suppressed)
        if self._locked:
            self._show_bar(self._top_bar)
            self._show_bar(self._bottom_bar)
        elif self._suppressed:
            self._hide_all_immediately()
        else:
            self.reveal_all()

    def set_reduced_motion(self, reduced: bool) -> None:
        """切换到无淡变的减少动态模式。"""
        self._reduced_motion = bool(reduced)
        if self._reduced_motion:
            for animation in self._animations.values():
                animation.stop()

    def dispose(self) -> None:
        """停止计时器、动画和事件过滤器。"""
        if self._disposed:
            return
        self._disposed = True
        self._hide_timer.stop()
        for animation in self._animations.values():
            animation.stop()
        for widget in self._tracked:
            widget.removeEventFilter(self)
        self._tracked.clear()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if self._disposed:
            return False
        if watched is self._host and event.type() == QEvent.Type.Resize:
            self._position_bars()
        elif event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            local = self._host.mapFromGlobal(event.globalPosition().toPoint())
            if self._host.rect().contains(local):
                self.reveal_for_position(local.y(), self._host.height())
        elif event.type() == QEvent.Type.FocusIn and isinstance(watched, QWidget):
            if self._is_chrome_widget(watched):
                self.reveal_all()
        elif event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self._restart_after_focus)
        elif event.type() == QEvent.Type.ChildAdded:
            child = getattr(event, "child", lambda: None)()
            if isinstance(child, QWidget):
                self._track_widget_tree(child)
        return False

    def _track_widget_tree(self, root: QWidget) -> None:
        widgets = [root, *root.findChildren(QWidget)]
        for widget in widgets:
            if widget in self._tracked:
                continue
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
            self._tracked.append(widget)

    def _position_bars(self) -> None:
        width = self._host.width()
        height = self._host.height()
        self._top_bar.setGeometry(0, 0, width, TOP_CHROME_HEIGHT)
        self._bottom_bar.setGeometry(0, max(0, height - BOTTOM_CHROME_HEIGHT), width, BOTTOM_CHROME_HEIGHT)
        self._top_bar.raise_()
        self._bottom_bar.raise_()

    def _schedule_hide(self, delay_ms: int) -> None:
        if self._suppressed and not self._locked:
            self._hide_all_immediately()
            return
        if self._locked or self._has_chrome_focus():
            self._hide_timer.stop()
            return
        self._hide_timer.start(max(0, delay_ms))

    def _show_bar(self, bar: QFrame) -> None:
        self._animate_bar(bar, 1.0, hide_after=False)

    def _hide_bar(self, bar: QFrame) -> None:
        self._animate_bar(bar, 0.0, hide_after=True)

    def _hide_all_immediately(self) -> None:
        """PPT 放映模式下立即隐藏控制层，不保留淡出残影。"""
        self._hide_timer.stop()
        for bar in (self._top_bar, self._bottom_bar):
            self._animations[bar].stop()
            self._effects[bar].setOpacity(0.0)
            self._hide_after_animation[bar] = True
            bar.hide()

    def _animate_bar(self, bar: QFrame, target: float, *, hide_after: bool) -> None:
        animation = self._animations[bar]
        effect = self._effects[bar]
        animation.stop()
        self._hide_after_animation[bar] = hide_after
        if target > 0:
            bar.show()
            bar.raise_()
        duration = 0 if self._reduced_motion else self._fade_duration_ms
        if duration <= 0:
            effect.setOpacity(target)
            if hide_after:
                bar.hide()
            return
        animation.setDuration(duration)
        animation.setStartValue(effect.opacity())
        animation.setEndValue(target)
        animation.start()

    def _on_animation_finished(self, bar: QFrame) -> None:
        if self._hide_after_animation.get(bar):
            bar.hide()

    def _has_chrome_focus(self) -> bool:
        focus = QApplication.focusWidget()
        return bool(focus and self._is_chrome_widget(focus))

    def _is_chrome_widget(self, widget: QWidget) -> bool:
        return widget in (self._top_bar, self._bottom_bar) or self._top_bar.isAncestorOf(widget) or self._bottom_bar.isAncestorOf(widget)

    def _restart_after_focus(self) -> None:
        if not self._disposed and not self._has_chrome_focus():
            self._schedule_hide(self._hide_delay_ms)
