"""将手部关键点转换为现有页面命令。"""

from __future__ import annotations

from collections import deque
from math import hypot
import time
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from gesture.settings import GestureSettings


class GestureCommandTarget(Protocol):
    """GestureController 需要的主窗口命令接口。"""

    @property
    def presentation_mode(self) -> str: ...

    @property
    def project(self): ...

    @property
    def workspace(self): ...

    def next_page(self) -> None: ...

    def previous_page(self) -> None: ...

    def set_zoom_factor(self, value: float) -> None: ...

    def pan_page(self, delta_x: float, delta_y: float) -> None: ...


class GestureController(QObject):
    """实现锁定、张掌翻页、OK 进页、双指激光、食指平移和双手缩放。"""

    status_changed = Signal(str)
    action_changed = Signal(str)

    def __init__(self, target: GestureCommandTarget, settings: GestureSettings | None = None) -> None:
        super().__init__()
        self._target = target
        self._settings = settings or GestureSettings()
        self._enabled = False
        self._locked = False
        self._fist_since: int | None = None
        self._fist_latched = False
        self._last_fist_toggle = 0
        self._last_swipe_at = -10_000
        self._swipe_history: deque[tuple[int, float, float]] = deque(maxlen=16)
        self._multi_swipe_histories: list[deque[tuple[int, float, float]]] = []
        self._pan_last: tuple[int, float, float] | None = None
        self._pan_filtered: tuple[float, float] | None = None
        self._pan_reference: tuple[float, float] | None = None
        self._ok_candidate_since: int | None = None
        self._ok_latched = False
        self._laser_filtered: tuple[float, float] | None = None
        self._laser_anchor: tuple[float, float] | None = None
        self._laser_input_reference: tuple[float, float] | None = None
        self._laser_last_output: tuple[float, float] | None = None
        self._laser_last_seen_at: int | None = None
        self._laser_visible = False
        self._zoom_candidate_since: int | None = None
        self._zoom_ready_centers: tuple[tuple[float, float], tuple[float, float]] | None = None
        self._zoom_ready_distance: float | None = None
        self._zoom_baseline: float | None = None
        self._zoom_start = 1.0
        self._zoom_last_valid_at: int | None = None
        self._diagnostic_last_input_ms: int | None = None
        self._diagnostic_input_count = 0
        self._diagnostic_hand_count = 0
        self._diagnostic_state = "disabled"
        self._diagnostic_last_command: str | None = None
        self._diagnostic_last_command_ms: int | None = None
        self._diagnostic_command_serial = 0

    @property
    def locked(self) -> bool:
        """返回手势是否处于握拳锁定状态。"""
        return self._locked

    def set_enabled(self, enabled: bool) -> None:
        """启停手势命令映射，并清空候选状态。"""
        self._enabled = bool(enabled)
        self._clear_runtime_state(reset_lock=True)
        self._diagnostic_state = "ready" if self._enabled else "disabled"

    def _clear_runtime_state(self, reset_lock: bool = False) -> None:
        """清空跨帧状态，防止模式切换后继承旧动作。"""
        self._fist_since = None
        self._fist_latched = False
        self._last_fist_toggle = 0
        self._last_swipe_at = -10_000
        self._swipe_history.clear()
        self._multi_swipe_histories.clear()
        self._reset_pan_tracking()
        self._ok_candidate_since = None
        self._ok_latched = False
        self._clear_laser_pointer()
        self._reset_zoom_preparation()
        self._zoom_baseline = None
        self._zoom_last_valid_at = None
        if reset_lock:
            self._locked = False

    def process_hands(self, hands: list[list[tuple[float, float, float]]], timestamp_ms: int) -> None:
        """按互斥优先级处理当前帧关键点。"""
        self._diagnostic_last_input_ms = int(time.perf_counter_ns() // 1_000_000)
        self._diagnostic_input_count += 1
        if not self._can_execute():
            self._diagnostic_hand_count = len(hands)
            self._diagnostic_state = "gated"
            self._clear_runtime_state(reset_lock=True)
            return
        hands = _deduplicate_hands(hands, self._settings.duplicate_hand_distance)
        self._diagnostic_hand_count = len(hands)
        if self._handle_fist(hands, timestamp_ms):
            self._diagnostic_state = "locked" if self._locked else "fist_hold"
            return
        if self._locked:
            self._diagnostic_state = "locked"
            return
        if len(hands) >= 2:
            laser_hand = self._find_laser_pointer_hand(hands)
            if self._target.workspace.mode == "stage" and laser_hand is not None:
                self._handle_laser_pointer(laser_hand, timestamp_ms)
                return
            if self._keep_laser_during_dropout(timestamp_ms):
                self._diagnostic_state = "laser_dropout"
                self._swipe_history.clear()
                self._multi_swipe_histories.clear()
                self._reset_pan_tracking()
                return
            self._diagnostic_state = "two_hands"
            self._ok_candidate_since = None
            self._ok_latched = False
            self._clear_laser_pointer()
            if self._zoom_baseline is None:
                direction = self._track_two_hand_swipe_candidate(hands[:2], timestamp_ms)
                if direction is not None and self._execute_swipe(direction, timestamp_ms):
                    return
            else:
                self._multi_swipe_histories.clear()
            self._handle_two_hand_zoom(hands[:2], timestamp_ms)
            return
        self._adopt_matching_swipe_history(hands[0] if hands else None, timestamp_ms)
        self._reset_zoom_preparation()
        if self._keep_zoom_during_dropout(timestamp_ms):
            self._diagnostic_state = "zoom_dropout"
            self._swipe_history.clear()
            return
        if len(hands) == 1:
            self._handle_single_hand(hands[0], timestamp_ms)
        else:
            if self._keep_laser_during_dropout(timestamp_ms):
                self._diagnostic_state = "laser_dropout"
                self._reset_pan_tracking()
                return
            self._diagnostic_state = "no_hands"
            self._ok_candidate_since = None
            self._ok_latched = False
            self._reset_pan_tracking()
            self._clear_laser_pointer()

    def diagnostic_snapshot(self) -> dict:
        """返回不含关键点坐标的控制器状态快照。"""
        if self._zoom_baseline is not None:
            zoom_state = "active"
        elif self._zoom_ready_centers is not None:
            zoom_state = "ready"
        elif self._zoom_candidate_since is not None:
            zoom_state = "candidate"
        else:
            zoom_state = "idle"
        return {
            "enabled": self._enabled,
            "locked": self._locked,
            "last_input_ms": self._diagnostic_last_input_ms,
            "input_count": self._diagnostic_input_count,
            "hand_count": self._diagnostic_hand_count,
            "state": self._diagnostic_state,
            "swipe_points": len(self._swipe_history),
            "multi_track_count": len(self._multi_swipe_histories),
            "zoom_state": zoom_state,
            "last_command": self._diagnostic_last_command,
            "last_command_ms": self._diagnostic_last_command_ms,
            "command_serial": self._diagnostic_command_serial,
        }

    def _can_execute(self) -> bool:
        return bool(
            self._enabled
            and self._target.project
            and self._target.presentation_mode == "gesture"
        )

    def _handle_fist(self, hands: list[list[tuple[float, float, float]]], timestamp_ms: int) -> bool:
        fist_count = sum(1 for hand in hands if _is_fist(hand))
        if self._locked and any(not _is_fist(hand) for hand in hands):
            self._unlock_from_fist_pause()
            return True
        fist_found = fist_count == 1 if self._locked else len(hands) == 1 and fist_count == 1
        if not fist_found:
            self._fist_since = None
            self._fist_latched = False
            return False
        if self._fist_latched:
            return True
        if self._fist_since is None:
            self._fist_since = timestamp_ms
            return True
        if (
            timestamp_ms - self._fist_since >= self._settings.fist_hold_ms
            and timestamp_ms - self._last_fist_toggle >= self._settings.fist_hold_ms
        ):
            self._locked = not self._locked
            self._last_fist_toggle = timestamp_ms
            self._fist_since = None
            self._fist_latched = True
            self._swipe_history.clear()
            self._multi_swipe_histories.clear()
            self._reset_pan_tracking()
            self._reset_zoom_preparation()
            self._zoom_baseline = None
            self._zoom_last_valid_at = None
            self.status_changed.emit(
                "手势已暂停，换成非握拳手势即可恢复" if self._locked else "手势已解锁"
            )
        return True

    def _unlock_from_fist_pause(self) -> None:
        """握拳暂停后，任意非握拳手势立即恢复控制。"""
        self._locked = False
        self._fist_since = None
        self._fist_latched = False
        self._swipe_history.clear()
        self._multi_swipe_histories.clear()
        self._reset_zoom_preparation()
        self._zoom_baseline = None
        self._zoom_last_valid_at = None
        self._diagnostic_state = "auto_unlocked"
        self._reset_pan_tracking()
        self.status_changed.emit("手势已自动解锁")

    def _handle_two_hand_zoom(
        self,
        hands: list[list[tuple[float, float, float]]],
        timestamp_ms: int,
    ) -> None:
        if self._target.workspace.mode != "stage" or not all(_is_open_palm(hand) for hand in hands):
            self._diagnostic_state = "two_hands_not_zoomable"
            self._reset_zoom_preparation()
            self._keep_zoom_during_dropout(timestamp_ms)
            return
        if (
            self._zoom_baseline is None
            and timestamp_ms - self._last_swipe_at < self._settings.swipe_cooldown_ms
        ):
            self._diagnostic_state = "swipe_cooldown"
            self._reset_zoom_preparation()
            return
        centers = (_palm_center(hands[0]), _palm_center(hands[1]))
        if self._zoom_baseline is None:
            if self._zoom_ready_centers is None:
                if self._zoom_candidate_since is None:
                    self._zoom_candidate_since = timestamp_ms
                    self._diagnostic_state = "zoom_candidate"
                    return
                if timestamp_ms - self._zoom_candidate_since < self._settings.zoom_activation_ms:
                    self._diagnostic_state = "zoom_candidate"
                    return
                self._zoom_candidate_since = None
                self._zoom_ready_centers = centers
                self._zoom_ready_distance = max(0.01, _distance(*centers))
                self._diagnostic_state = "zoom_ready"
                return
            current_centers = _match_center_pair(self._zoom_ready_centers, centers)
            ready_distance = self._zoom_ready_distance or 0.01
            distance = _distance(*current_centers)
            ratio = distance / max(0.01, ready_distance)
            if abs(ratio - 1.0) < self._settings.zoom_deadzone:
                self._diagnostic_state = "zoom_ready"
                return
            if not _has_bilateral_zoom_intent(
                self._zoom_ready_centers,
                current_centers,
                self._settings.zoom_min_bilateral_contribution,
            ):
                self._diagnostic_state = "zoom_waiting_bilateral"
                return
            self._zoom_baseline = ready_distance
            self._zoom_start = self._target.workspace.zoom_factor
            self._zoom_last_valid_at = timestamp_ms
            self._reset_zoom_preparation()
            self._swipe_history.clear()
            self._multi_swipe_histories.clear()
            self._reset_pan_tracking()
            adjusted_ratio = ratio ** self._settings.zoom_sensitivity
            self._target.set_zoom_factor(self._zoom_start * adjusted_ratio)
            self._record_command("zoom_in" if adjusted_ratio > 1.0 else "zoom_out")
            return
        self._swipe_history.clear()
        self._multi_swipe_histories.clear()
        self._reset_pan_tracking()
        self._zoom_last_valid_at = timestamp_ms
        distance = _distance(*centers)
        ratio = distance / max(0.01, self._zoom_baseline)
        if abs(ratio - 1.0) < self._settings.zoom_deadzone:
            return
        adjusted_ratio = ratio ** self._settings.zoom_sensitivity
        self._target.set_zoom_factor(self._zoom_start * adjusted_ratio)
        self._diagnostic_state = "zoom_active"
        self._record_command("zoom_in" if adjusted_ratio > 1.0 else "zoom_out")

    def _keep_zoom_during_dropout(self, timestamp_ms: int) -> bool:
        """短暂漏检一只手时保留缩放基准，避免反复重新起步。"""
        if self._zoom_baseline is None or self._zoom_last_valid_at is None:
            return False
        if timestamp_ms - self._zoom_last_valid_at <= self._settings.zoom_dropout_grace_ms:
            return True
        self._zoom_baseline = None
        self._zoom_last_valid_at = None
        return False

    def _reset_zoom_preparation(self) -> None:
        self._zoom_candidate_since = None
        self._zoom_ready_centers = None
        self._zoom_ready_distance = None

    def _handle_single_hand(self, hand: list[tuple[float, float, float]], timestamp_ms: int) -> None:
        if _is_ok_gesture(hand, self._settings):
            if self._ok_latched:
                self._diagnostic_state = "ok_held"
                return
            self._swipe_history.clear()
            self._multi_swipe_histories.clear()
            self._reset_pan_tracking()
            self._reset_zoom_preparation()
            self._zoom_baseline = None
            self._zoom_last_valid_at = None
            self._clear_laser_pointer()
            if self._ok_candidate_since is None:
                self._ok_candidate_since = timestamp_ms
                self._diagnostic_state = "ok_candidate"
                return
            if timestamp_ms - self._ok_candidate_since < self._settings.ok_hold_ms:
                self._diagnostic_state = "ok_candidate"
                return
            self._ok_latched = True
            self._ok_candidate_since = None
            if self._target.workspace.mode == "carousel":
                self._target.workspace.enter_stage(self._target.workspace.current_index)
                self._diagnostic_state = "ok_enter_stage"
                self._record_command("enter_stage")
                return
            if self._target.workspace.mode == "stage":
                self._target.workspace.show_carousel()
                self._diagnostic_state = "ok_show_carousel"
                self._record_command("show_carousel")
                return
            return
        self._ok_candidate_since = None
        self._ok_latched = False
        if self._target.workspace.mode == "stage" and _is_laser_pointer(hand):
            self._handle_laser_pointer(hand, timestamp_ms)
            return
        if self._keep_laser_during_dropout(timestamp_ms):
            self._diagnostic_state = "laser_dropout"
            self._swipe_history.clear()
            self._multi_swipe_histories.clear()
            self._reset_pan_tracking()
            return
        self._clear_laser_pointer()
        if _is_index_only(hand):
            self._diagnostic_state = "index_pan_tracking"
            self._swipe_history.clear()
            self._handle_palm_pan(_index_tip(hand), timestamp_ms)
            return
        if not _is_open_palm(hand):
            self._diagnostic_state = "one_hand_not_open"
            self._swipe_history.clear()
            self._reset_pan_tracking()
            return
        self._diagnostic_state = "single_hand_tracking"
        center = _palm_center(hand)
        self._reset_pan_tracking()
        self._swipe_history.append((timestamp_ms, center[0], center[1]))
        _trim_swipe_history(self._swipe_history, timestamp_ms, self._settings.swipe_max_duration_ms)
        direction = _swipe_direction(self._swipe_history, timestamp_ms, self._settings)
        if direction is not None:
            self._execute_swipe(direction, timestamp_ms)
            return

    def _handle_palm_pan(self, center: tuple[float, float], timestamp_ms: int) -> None:
        if self._target.workspace.mode != "stage":
            self._start_pan_tracking(center, timestamp_ms)
            self._diagnostic_state = "palm_pan_ignored"
            return
        if self._pan_last is None or timestamp_ms - self._pan_last[0] > self._settings.palm_pan_max_gap_ms:
            self._start_pan_tracking(center, timestamp_ms)
            self._diagnostic_state = "palm_pan_ready"
            return
        self._pan_last = (timestamp_ms, center[0], center[1])
        previous_filtered = self._pan_filtered or center
        alpha = max(0.0, min(1.0, self._settings.palm_pan_smoothing))
        filtered = (
            previous_filtered[0] + (center[0] - previous_filtered[0]) * alpha,
            previous_filtered[1] + (center[1] - previous_filtered[1]) * alpha,
        )
        self._pan_filtered = filtered
        reference = self._pan_reference or filtered
        delta_x = (filtered[0] - reference[0]) * self._settings.palm_pan_sensitivity
        delta_y = (filtered[1] - reference[1]) * self._settings.palm_pan_sensitivity
        if _distance((0.0, 0.0), (delta_x, delta_y)) < self._settings.palm_pan_min_delta:
            self._diagnostic_state = "palm_pan_ready"
            return
        self._pan_reference = filtered
        self._target.pan_page(delta_x, delta_y)
        self._diagnostic_state = "palm_pan"
        self._record_command("pan_page")

    def _start_pan_tracking(self, center: tuple[float, float], timestamp_ms: int) -> None:
        self._pan_last = (timestamp_ms, center[0], center[1])
        self._pan_filtered = center
        self._pan_reference = center

    def _reset_pan_tracking(self) -> None:
        self._pan_last = None
        self._pan_filtered = None
        self._pan_reference = None

    def _find_laser_pointer_hand(
        self,
        hands: list[list[tuple[float, float, float]]],
    ) -> list[tuple[float, float, float]] | None:
        for hand in hands:
            if _is_laser_pointer(hand):
                return hand
        return None

    def _handle_laser_pointer(self, hand: list[tuple[float, float, float]], timestamp_ms: int) -> None:
        self._swipe_history.clear()
        self._multi_swipe_histories.clear()
        self._reset_pan_tracking()
        self._reset_zoom_preparation()
        self._zoom_baseline = None
        self._zoom_last_valid_at = None
        self._laser_last_seen_at = timestamp_ms
        self._laser_visible = True
        raw_laser_point = _laser_pointer_position(hand)
        if self._laser_last_output is None:
            # 以实际视口中心作为首帧平滑基准，避免下一帧跳回页面坐标中心。
            initial_point = (0.5, 0.5)
            workspace = self._target.workspace
            if hasattr(workspace, "show_laser_pointer_at_viewport_center"):
                viewport_center = workspace.show_laser_pointer_at_viewport_center()
                if viewport_center is not None:
                    initial_point = viewport_center
            else:
                workspace.show_laser_pointer(0.5, 0.5)
            self._laser_filtered = initial_point
            self._laser_anchor = initial_point
            self._laser_input_reference = raw_laser_point
            self._laser_last_output = initial_point
            self._diagnostic_state = "laser_pointer"
            self._record_command("laser_pointer")
            return
        laser_point = self._smooth_laser_pointer(self._relative_laser_pointer_position(raw_laser_point))
        if (
            self._laser_last_output is not None
            and _distance(laser_point, self._laser_last_output) < self._settings.laser_pointer_min_delta
        ):
            self._diagnostic_state = "laser_pointer_stable"
            return
        self._laser_last_output = laser_point
        self._target.workspace.show_laser_pointer(*laser_point)
        self._diagnostic_state = "laser_pointer"
        self._record_command("laser_pointer")

    def _keep_laser_during_dropout(self, timestamp_ms: int) -> bool:
        """短暂识别不稳时保留激光状态，避免清除后重建造成抖动。"""
        if (
            not self._laser_visible
            or self._laser_last_seen_at is None
            or self._target.workspace.mode != "stage"
        ):
            return False
        return timestamp_ms - self._laser_last_seen_at <= self._settings.laser_pointer_dropout_grace_ms

    def _clear_laser_pointer(self) -> None:
        was_visible = self._laser_visible
        self._laser_filtered = None
        self._laser_anchor = None
        self._laser_input_reference = None
        self._laser_last_output = None
        self._laser_last_seen_at = None
        self._laser_visible = False
        if was_visible and hasattr(self._target.workspace, "clear_laser_pointer"):
            self._target.workspace.clear_laser_pointer()

    def _smooth_laser_pointer(self, point: tuple[float, float]) -> tuple[float, float]:
        if self._laser_filtered is None:
            self._laser_filtered = point
            return point
        alpha = max(0.0, min(1.0, self._settings.laser_pointer_smoothing))
        self._laser_filtered = (
            self._laser_filtered[0] + (point[0] - self._laser_filtered[0]) * alpha,
            self._laser_filtered[1] + (point[1] - self._laser_filtered[1]) * alpha,
        )
        return self._laser_filtered

    def _relative_laser_pointer_position(self, point: tuple[float, float]) -> tuple[float, float]:
        """根据激活后的手势相对位移生成页面坐标，避免首帧跳变。"""
        anchor = self._laser_anchor
        reference = self._laser_input_reference
        if anchor is None or reference is None:
            return point
        return (
            max(0.0, min(1.0, anchor[0] + point[0] - reference[0])),
            max(0.0, min(1.0, anchor[1] + point[1] - reference[1])),
        )

    def _track_two_hand_swipe_candidate(
        self,
        hands: list[list[tuple[float, float, float]]],
        timestamp_ms: int,
    ) -> int | None:
        """缩放确认前分别跟踪两只检测，容忍持续存在的假手。"""
        ordered_hands = list(hands)
        if not self._multi_swipe_histories:
            self._multi_swipe_histories = [deque(maxlen=16), deque(maxlen=16)]
            if self._swipe_history:
                last_center = self._swipe_history[-1][1:]
                primary_index = min(
                    range(2),
                    key=lambda index: _distance(_palm_center(ordered_hands[index]), last_center),
                )
                self._multi_swipe_histories[primary_index].extend(self._swipe_history)
                self._swipe_history.clear()
        else:
            current_centers = [_palm_center(hand) for hand in ordered_hands]
            populated_indices = [
                index for index, history in enumerate(self._multi_swipe_histories) if history
            ]
            should_swap = False
            if len(populated_indices) == 2:
                previous_centers = [history[-1][1:] for history in self._multi_swipe_histories]
                direct_cost = _distance(previous_centers[0], current_centers[0]) + _distance(
                    previous_centers[1], current_centers[1]
                )
                swapped_cost = _distance(previous_centers[0], current_centers[1]) + _distance(
                    previous_centers[1], current_centers[0]
                )
                should_swap = swapped_cost < direct_cost
            elif len(populated_indices) == 1:
                track_index = populated_indices[0]
                previous_center = self._multi_swipe_histories[track_index][-1][1:]
                nearest_hand_index = min(
                    range(2),
                    key=lambda index: _distance(previous_center, current_centers[index]),
                )
                should_swap = track_index != nearest_hand_index
            if should_swap:
                ordered_hands.reverse()

        for history, hand in zip(self._multi_swipe_histories, ordered_hands, strict=True):
            if not _is_open_palm(hand):
                history.clear()
                continue
            center = _palm_center(hand)
            history.append((timestamp_ms, center[0], center[1]))
            _trim_swipe_history(history, timestamp_ms, self._settings.swipe_max_duration_ms)

        directions = [
            _swipe_direction(history, timestamp_ms, self._settings)
            for history in self._multi_swipe_histories
        ]
        moving_tracks = [index for index, direction in enumerate(directions) if direction is not None]
        if len(moving_tracks) != 1:
            return None
        moving_index = moving_tracks[0]
        other_index = 1 - moving_index
        if _history_displacement(self._multi_swipe_histories[other_index]) > self._settings.swipe_secondary_motion_max:
            return None
        return directions[moving_index]

    def _adopt_matching_swipe_history(
        self,
        hand: list[tuple[float, float, float]] | None,
        timestamp_ms: int,
    ) -> None:
        """第二只手消失后，把最近的候选轨迹接回单手状态机。"""
        if not self._multi_swipe_histories:
            return
        for history in self._multi_swipe_histories:
            _trim_swipe_history(history, timestamp_ms, self._settings.swipe_max_duration_ms)
        if hand is None:
            if not any(self._multi_swipe_histories):
                self._multi_swipe_histories.clear()
            return
        if hand is not None and self._zoom_baseline is None:
            center = _palm_center(hand)
            populated = [history for history in self._multi_swipe_histories if history]
            if populated:
                candidates = sorted(
                    (
                        _distance(history[-1][1:], center),
                        history,
                    )
                    for history in populated
                )
                nearest_distance, nearest = candidates[0]
                unambiguous = (
                    len(candidates) == 1
                    or candidates[1][0] - nearest_distance >= self._settings.swipe_track_ambiguity_margin
                )
                if nearest_distance <= self._settings.swipe_track_match_distance and unambiguous:
                    self._swipe_history = deque(nearest, maxlen=16)
        self._multi_swipe_histories.clear()

    def _execute_swipe(self, direction: int, timestamp_ms: int) -> bool:
        if timestamp_ms - self._last_swipe_at < self._settings.swipe_cooldown_ms:
            return False
        if direction < 0:
            self._target.next_page()
            command = "next_page"
        else:
            self._target.previous_page()
            command = "previous_page"
        self._last_swipe_at = timestamp_ms
        self._swipe_history.clear()
        self._multi_swipe_histories.clear()
        self._reset_pan_tracking()
        self._reset_zoom_preparation()
        self._diagnostic_state = command
        self._record_command(command)
        return True

    def _record_command(self, command: str) -> None:
        self._diagnostic_last_command = command
        self._diagnostic_last_command_ms = int(time.perf_counter_ns() // 1_000_000)
        self._diagnostic_command_serial += 1
        self.action_changed.emit(command)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _trim_swipe_history(
    history: deque[tuple[int, float, float]],
    timestamp_ms: int,
    max_duration_ms: int,
) -> None:
    while history and timestamp_ms - history[0][0] > max_duration_ms:
        history.popleft()


def _swipe_direction(
    history: deque[tuple[int, float, float]],
    timestamp_ms: int,
    settings: GestureSettings,
) -> int | None:
    if len(history) < 2:
        return None
    _, current_x, current_y = history[-1]
    for start_t, start_x, start_y in history:
        dt = timestamp_ms - start_t
        dx = current_x - start_x
        dy = current_y - start_y
        if (
            settings.swipe_min_duration_ms <= dt <= settings.swipe_max_duration_ms
            and abs(dx) >= settings.swipe_min_displacement
            and abs(dx) >= abs(dy) * settings.swipe_horizontal_ratio
        ):
            return -1 if dx < 0 else 1
    return None


def _history_displacement(history: deque[tuple[int, float, float]]) -> float:
    if len(history) < 2:
        return 0.0
    return _distance(history[0][1:], history[-1][1:])


def _match_center_pair(
    reference: tuple[tuple[float, float], tuple[float, float]],
    current: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    direct_cost = _distance(reference[0], current[0]) + _distance(reference[1], current[1])
    swapped_cost = _distance(reference[0], current[1]) + _distance(reference[1], current[0])
    return (current[1], current[0]) if swapped_cost < direct_cost else current


def _has_bilateral_zoom_intent(
    reference: tuple[tuple[float, float], tuple[float, float]],
    current: tuple[tuple[float, float], tuple[float, float]],
    min_contribution: float,
) -> bool:
    axis_x = reference[1][0] - reference[0][0]
    axis_y = reference[1][1] - reference[0][1]
    reference_distance = hypot(axis_x, axis_y)
    if reference_distance <= 0.01:
        return False
    axis_x /= reference_distance
    axis_y /= reference_distance
    first_projection = (
        (current[0][0] - reference[0][0]) * axis_x
        + (current[0][1] - reference[0][1]) * axis_y
    )
    second_projection = (
        (current[1][0] - reference[1][0]) * axis_x
        + (current[1][1] - reference[1][1]) * axis_y
    )
    distance_delta = _distance(*current) - reference_distance
    required = abs(distance_delta) * min_contribution
    if distance_delta > 0:
        return -first_projection >= required and second_projection >= required
    return first_projection >= required and -second_projection >= required


def _deduplicate_hands(
    hands: list[list[tuple[float, float, float]]],
    max_mean_distance: float,
) -> list[list[tuple[float, float, float]]]:
    """合并 MediaPipe 对同一只手产生的高度重合检测。"""
    unique_hands: list[list[tuple[float, float, float]]] = []
    merged_counts: list[int] = []
    for hand in hands:
        duplicate_index = next(
            (
                index
                for index, other in enumerate(unique_hands)
                if _mean_landmark_distance(hand, other) <= max_mean_distance
            ),
            None,
        )
        if duplicate_index is not None:
            count = merged_counts[duplicate_index]
            unique_hands[duplicate_index] = _average_landmarks(
                unique_hands[duplicate_index],
                hand,
                count,
            )
            merged_counts[duplicate_index] = count + 1
            continue
        unique_hands.append(hand)
        merged_counts.append(1)
    return unique_hands


def _average_landmarks(
    accumulated: list[tuple[float, float, float]],
    new_hand: list[tuple[float, float, float]],
    accumulated_count: int,
) -> list[tuple[float, float, float]]:
    if len(accumulated) != len(new_hand):
        return accumulated
    divisor = accumulated_count + 1
    return [
        (
            (old_x * accumulated_count + new_x) / divisor,
            (old_y * accumulated_count + new_y) / divisor,
            (old_z * accumulated_count + new_z) / divisor,
        )
        for (old_x, old_y, old_z), (new_x, new_y, new_z) in zip(
            accumulated,
            new_hand,
            strict=True,
        )
    ]


def _mean_landmark_distance(
    first: list[tuple[float, float, float]],
    second: list[tuple[float, float, float]],
) -> float:
    count = min(len(first), len(second))
    if count == 0:
        return float("inf")
    return sum(
        _distance((first[index][0], first[index][1]), (second[index][0], second[index][1]))
        for index in range(count)
    ) / count


def _palm_center(hand: list[tuple[float, float, float]]) -> tuple[float, float]:
    """使用腕点和四个掌指点估算掌心。"""
    indices = (0, 5, 9, 13, 17)
    x = sum(hand[i][0] for i in indices) / len(indices)
    y = sum(hand[i][1] for i in indices) / len(indices)
    return x, y


def _index_tip(hand: list[tuple[float, float, float]]) -> tuple[float, float]:
    return hand[8][0], hand[8][1]


def _palm_scale(hand: list[tuple[float, float, float]]) -> float:
    wrist = (hand[0][0], hand[0][1])
    return max(
        _distance(wrist, (hand[index][0], hand[index][1]))
        for index in (5, 9, 13, 17)
    )


def _finger_extended(hand: list[tuple[float, float, float]], tip: int, pip: int, factor: float = 1.05) -> bool:
    wrist = (hand[0][0], hand[0][1])
    tip_distance = _distance((hand[tip][0], hand[tip][1]), wrist)
    pip_distance = _distance((hand[pip][0], hand[pip][1]), wrist)
    return tip_distance > pip_distance * factor


def _is_ok_gesture(hand: list[tuple[float, float, float]], settings: GestureSettings) -> bool:
    if len(hand) < 21:
        return False
    wrist = (hand[0][0], hand[0][1])
    thumb_index_distance = _distance((hand[4][0], hand[4][1]), (hand[8][0], hand[8][1]))
    max_distance = max(settings.ok_max_distance, _palm_scale(hand) * settings.ok_max_scale_ratio)
    index_tip_distance = _distance((hand[8][0], hand[8][1]), wrist)
    index_pip_distance = _distance((hand[6][0], hand[6][1]), wrist)
    index_curled = index_tip_distance <= index_pip_distance * settings.ok_index_max_extension_ratio
    extended_count = sum(
        1 for tip, pip in ((12, 10), (16, 14), (20, 18)) if _finger_extended(hand, tip, pip, 1.05)
    )
    return thumb_index_distance <= max_distance and index_curled and extended_count >= 2


def _is_laser_pointer(hand: list[tuple[float, float, float]]) -> bool:
    if len(hand) < 21:
        return False
    return (
        _finger_extended(hand, 8, 6, 1.08)
        and _finger_extended(hand, 12, 10, 1.08)
        and not _finger_extended(hand, 16, 14, 1.05)
        and not _finger_extended(hand, 20, 18, 1.05)
    )


def _laser_pointer_position(hand: list[tuple[float, float, float]]) -> tuple[float, float]:
    return (hand[8][0] + hand[12][0]) / 2, (hand[8][1] + hand[12][1]) / 2


def _is_index_only(hand: list[tuple[float, float, float]]) -> bool:
    if len(hand) < 21:
        return False
    handedness = getattr(hand, "handedness", None)
    if handedness is not None and str(handedness).lower() != "right":
        return False
    wrist = (hand[0][0], hand[0][1])

    def extended(tip: int, pip: int) -> bool:
        tip_distance = _distance((hand[tip][0], hand[tip][1]), wrist)
        pip_distance = _distance((hand[pip][0], hand[pip][1]), wrist)
        return tip_distance > pip_distance * 1.08

    index_extended = extended(8, 6)
    other_folded = not any(extended(tip, pip) for tip, pip in ((12, 10), (16, 14), (20, 18)))
    thumb_tip_x = hand[4][0]
    palm_x = _palm_center(hand)[0]
    right_hand = True if handedness is not None else thumb_tip_x < palm_x
    return index_extended and other_folded and right_hand


def _is_open_palm(hand: list[tuple[float, float, float]]) -> bool:
    if len(hand) < 21:
        return False
    wrist = (hand[0][0], hand[0][1])
    extended = 0
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        tip_distance = _distance((hand[tip][0], hand[tip][1]), wrist)
        pip_distance = _distance((hand[pip][0], hand[pip][1]), wrist)
        if tip_distance > pip_distance * 1.05:
            extended += 1
    return extended >= 3


def _is_fist(hand: list[tuple[float, float, float]]) -> bool:
    if len(hand) < 21:
        return False
    wrist = (hand[0][0], hand[0][1])
    folded = 0
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        tip_distance = _distance((hand[tip][0], hand[tip][1]), wrist)
        pip_distance = _distance((hand[pip][0], hand[pip][1]), wrist)
        if tip_distance < pip_distance * 1.05:
            folded += 1
    palm_scale = max(
        _distance(wrist, (hand[index][0], hand[index][1]))
        for index in (5, 9, 13, 17)
    )
    thumb_close = _distance((hand[4][0], hand[4][1]), (hand[9][0], hand[9][1])) < max(
        0.04,
        palm_scale * 0.9,
    )
    return folded >= 4 and thumb_close
