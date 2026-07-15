from math import cos, radians, sin

import pytest

from gesture.controller import GestureController
from gesture.settings import GestureSettings


class FakeWorkspace:
    def __init__(self):
        self.mode = "carousel"
        self.zoom_factor = 1.0
        self.current_index = 0
        self.enter_stage_calls = []
        self.show_carousel_calls = 0
        self.laser_points = []
        self.laser_clear_count = 0

    def enter_stage(self, index=None):
        self.enter_stage_calls.append(self.current_index if index is None else index)
        self.current_index = self.enter_stage_calls[-1]
        self.mode = "stage"

    def show_carousel(self):
        self.show_carousel_calls += 1
        self.mode = "carousel"

    def show_laser_pointer(self, x, y):
        self.laser_points.append((x, y))

    def clear_laser_pointer(self):
        self.laser_clear_count += 1


class FakeTarget:
    def __init__(self):
        self.presentation_mode = "gesture"
        self.project = object()
        self.workspace = FakeWorkspace()
        self.next_calls = 0
        self.previous_calls = 0
        self.zoom_values = []
        self.pan_deltas = []

    def next_page(self):
        self.next_calls += 1

    def previous_page(self):
        self.previous_calls += 1

    def set_zoom_factor(self, value):
        self.zoom_values.append(value)
        self.workspace.zoom_factor = value

    def pan_page(self, delta_x, delta_y):
        self.pan_deltas.append((delta_x, delta_y))


class LabeledHand(list):
    def __init__(self, landmarks, handedness):
        super().__init__(landmarks)
        self.handedness = handedness


def open_hand(x=0.5, y=0.5):
    hand = [(x, y, 0.0) for _ in range(21)]
    for index, dx in ((5, -0.04), (9, 0.0), (13, 0.04), (17, 0.08)):
        hand[index] = (x + dx, y, 0.0)
    for tip, pip, dx in ((8, 6, -0.04), (12, 10, 0.0), (16, 14, 0.04), (20, 18, 0.08)):
        hand[pip] = (x + dx, y - 0.05, 0.0)
        hand[tip] = (x + dx, y - 0.16, 0.0)
    hand[4] = (x - 0.12, y - 0.04, 0.0)
    return hand


def rotate_hand(hand, angle_degrees, x=0.5, y=0.5):
    angle = radians(angle_degrees)
    cosine = cos(angle)
    sine = sin(angle)
    return [
        (
            x + (point_x - x) * cosine - (point_y - y) * sine,
            y + (point_x - x) * sine + (point_y - y) * cosine,
            point_z,
        )
        for point_x, point_y, point_z in hand
    ]


def rotated_open_hand(angle_degrees, x=0.5, y=0.5):
    """旋转张开的手掌，模拟挥手过程中自然变化的朝向。"""
    return rotate_hand(open_hand(x, y), angle_degrees, x, y)


def sideways_open_hand(x=0.5, y=0.5):
    return rotated_open_hand(90, x, y)


def closed_fist(x=0.5, y=0.5):
    hand = open_hand(x, y)
    for tip, _, dx in ((8, 6, -0.04), (12, 10, 0.0), (16, 14, 0.04), (20, 18, 0.08)):
        hand[tip] = (x + dx, y + 0.01, 0.0)
    hand[4] = (x - 0.03, y, 0.0)
    return hand


def index_only_hand(x=0.5, y=0.5):
    hand = open_hand(x, y)
    for tip, _, dx in ((12, 10, 0.0), (16, 14, 0.04), (20, 18, 0.08)):
        hand[tip] = (x + dx, y + 0.01, 0.0)
    hand[4] = (x - 0.03, y, 0.0)
    return hand


def pinch_hand(x=0.5, y=0.5):
    hand = index_only_hand(x, y)
    index_tip_x, index_tip_y, _ = hand[8]
    hand[4] = (index_tip_x + 0.006, index_tip_y + 0.006, 0.0)
    return hand


def ok_hand(x=0.5, y=0.5):
    hand = open_hand(x, y)
    hand[6] = (x - 0.035, y - 0.075, 0.0)
    hand[8] = (x - 0.020, y - 0.090, 0.0)
    hand[4] = (x - 0.002, y - 0.082, 0.0)
    return hand


def false_ok_open_hand(x=0.5, y=0.5):
    hand = open_hand(x, y)
    index_tip_x, index_tip_y, _ = hand[8]
    hand[4] = (index_tip_x + 0.020, index_tip_y + 0.010, 0.0)
    return hand


def two_finger_hand(x=0.5, y=0.5):
    hand = open_hand(x, y)
    for tip, _, dx in ((16, 14, 0.04), (20, 18, 0.08)):
        hand[tip] = (x + dx, y + 0.01, 0.0)
    hand[4] = (x - 0.03, y, 0.0)
    return hand


def left_index_only_hand(x=0.5, y=0.5):
    hand = index_only_hand(x, y)
    return [(x - (point_x - x), point_y, point_z) for point_x, point_y, point_z in hand]


def labeled_index_only_hand(handedness, x=0.5, y=0.5):
    return LabeledHand(index_only_hand(x, y), handedness)


def test_palm_facing_translation_turns_page_without_panning():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for x, timestamp in ((0.62, 0), (0.56, 50), (0.50, 100)):
        controller.process_hands([open_hand(x)], timestamp)

    assert target.pan_deltas == []
    assert target.next_calls == 1
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_ok_gesture_in_carousel_enters_current_page_stage():
    target = FakeTarget()
    target.workspace.mode = "carousel"
    target.workspace.current_index = 2
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([ok_hand()], 0)
    controller.process_hands([ok_hand()], 90)

    assert target.workspace.enter_stage_calls == [2]
    assert target.workspace.mode == "stage"
    assert target.pan_deltas == []
    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_ok_gesture_does_not_trigger_fist_pause_when_held():
    target = FakeTarget()
    target.workspace.mode = "carousel"
    target.workspace.current_index = 1
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 701, 100):
        controller.process_hands([ok_hand()], timestamp)

    assert target.workspace.enter_stage_calls == [1]
    assert controller.locked is False


def test_legacy_pinch_no_longer_enters_stage():
    target = FakeTarget()
    target.workspace.mode = "carousel"
    target.workspace.current_index = 2
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([pinch_hand()], 0)

    assert target.workspace.enter_stage_calls == []
    assert target.workspace.mode == "carousel"


def test_false_ok_open_palm_does_not_enter_stage():
    target = FakeTarget()
    target.workspace.mode = "carousel"
    target.workspace.current_index = 2
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 241, 40):
        controller.process_hands([false_ok_open_hand()], timestamp)

    assert target.workspace.enter_stage_calls == []
    assert target.workspace.mode == "carousel"


def test_ok_gesture_requires_short_stable_hold():
    target = FakeTarget()
    target.workspace.mode = "carousel"
    target.workspace.current_index = 2
    controller = GestureController(target, GestureSettings(ok_hold_ms=90))
    controller.set_enabled(True)

    controller.process_hands([ok_hand()], 0)
    controller.process_hands([index_only_hand()], 40)
    controller.process_hands([ok_hand()], 80)

    assert target.workspace.enter_stage_calls == []


def test_ok_gesture_toggles_stage_back_to_carousel_after_release():
    target = FakeTarget()
    target.workspace.mode = "carousel"
    target.workspace.current_index = 2
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([ok_hand()], 0)
    controller.process_hands([ok_hand()], 90)
    controller.process_hands([index_only_hand()], 130)
    controller.process_hands([ok_hand()], 170)
    controller.process_hands([ok_hand()], 260)

    assert target.workspace.enter_stage_calls == [2]
    assert target.workspace.show_carousel_calls == 1
    assert target.workspace.mode == "carousel"


def test_laser_pointer_starts_from_screen_center():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([two_finger_hand(0.50, 0.50)], 0)

    assert target.workspace.laser_points == [pytest.approx((0.50, 0.50))]
    assert target.pan_deltas == []
    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_laser_pointer_initial_activation_uses_viewport_center_when_available():
    class ViewportCenteredWorkspace(FakeWorkspace):
        def __init__(self):
            super().__init__()
            self.viewport_center_calls = 0

        def show_laser_pointer_at_viewport_center(self):
            self.viewport_center_calls += 1
            return 0.80, 0.25

    target = FakeTarget()
    target.workspace = ViewportCenteredWorkspace()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([two_finger_hand(0.50, 0.50)], 0)
    controller.process_hands([two_finger_hand(0.50, 0.50)], 30)
    controller.process_hands([two_finger_hand(0.58, 0.50)], 60)

    assert target.workspace.viewport_center_calls == 1
    assert target.workspace.laser_points == [pytest.approx((0.82, 0.25))]


def test_laser_pointer_jitter_is_smoothed():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([two_finger_hand(0.50, 0.50)], 0)
    controller.process_hands([two_finger_hand(0.50, 0.50)], 30)
    controller.process_hands([two_finger_hand(0.530, 0.470)], 60)

    first = target.workspace.laser_points[0]
    second = target.workspace.laser_points[1]
    assert 0.004 <= abs(second[0] - first[0]) < 0.030
    assert 0.004 <= abs(second[1] - first[1]) < 0.030


def test_laser_pointer_small_noise_does_not_visibly_jitter():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(
        target,
        GestureSettings(laser_pointer_smoothing=0.25, laser_pointer_min_delta=0.004),
    )
    controller.set_enabled(True)

    for frame_index, (x, y) in enumerate(
        (
            (0.500, 0.500),
            (0.502, 0.498),
            (0.499, 0.501),
            (0.503, 0.497),
            (0.501, 0.499),
        )
    ):
        controller.process_hands([two_finger_hand(x, y)], frame_index * 30)

    assert len(target.workspace.laser_points) == 1


def test_laser_pointer_survives_brief_recognition_dropout():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(
        target,
        GestureSettings(laser_pointer_dropout_grace_ms=180),
    )
    controller.set_enabled(True)

    controller.process_hands([two_finger_hand(0.50, 0.50)], 0)
    target.workspace.laser_clear_count = 0
    controller.process_hands([index_only_hand(0.55, 0.52)], 60)
    controller.process_hands([two_finger_hand(0.62, 0.50)], 90)

    first = target.workspace.laser_points[0]
    resumed = target.workspace.laser_points[-1]
    assert target.workspace.laser_clear_count == 0
    assert target.pan_deltas == []
    assert first[0] < resumed[0] < 0.60


def test_laser_pointer_clears_after_dropout_grace():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(
        target,
        GestureSettings(laser_pointer_dropout_grace_ms=120),
    )
    controller.set_enabled(True)

    controller.process_hands([two_finger_hand(0.50, 0.50)], 0)
    target.workspace.laser_clear_count = 0
    controller.process_hands([index_only_hand(0.55, 0.52)], 180)
    controller.process_hands([two_finger_hand(0.62, 0.50)], 220)

    assert target.workspace.laser_clear_count == 1
    assert target.workspace.laser_points[-1] == pytest.approx((0.50, 0.50))


def test_laser_pointer_clears_when_stage_gesture_changes():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([two_finger_hand()], 0)
    target.workspace.laser_clear_count = 0
    controller.process_hands([open_hand()], 260)

    assert target.workspace.laser_clear_count > 0


def test_right_index_only_translation_pans_page_without_turning_page():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for x, timestamp in ((0.50, 0), (0.56, 40), (0.62, 80), (0.68, 120)):
        controller.process_hands([index_only_hand(x)], timestamp)

    assert target.pan_deltas
    assert target.next_calls == 0
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_left_index_only_translation_does_not_pan_page():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for x, timestamp in ((0.50, 0), (0.56, 40), (0.62, 80), (0.68, 120)):
        controller.process_hands([left_index_only_hand(x)], timestamp)

    assert target.pan_deltas == []
    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_labeled_left_index_only_translation_does_not_pan_page():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for x, timestamp in ((0.50, 0), (0.56, 40), (0.62, 80), (0.68, 120)):
        controller.process_hands([labeled_index_only_hand("Left", x)], timestamp)

    assert target.pan_deltas == []
    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_labeled_right_index_only_translation_pans_page():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for x, timestamp in ((0.50, 0), (0.56, 40), (0.62, 80), (0.68, 120)):
        controller.process_hands([labeled_index_only_hand("Right", x)], timestamp)

    assert target.pan_deltas
    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_right_index_only_jitter_does_not_pan_page():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, (x, y) in enumerate(
        (
            (0.500, 0.500),
            (0.503, 0.497),
            (0.499, 0.502),
            (0.504, 0.498),
            (0.501, 0.501),
            (0.505, 0.499),
        )
    ):
        controller.process_hands([index_only_hand(x, y)], frame_index * 35)

    assert target.pan_deltas == []


def test_right_index_only_near_threshold_noise_does_not_jitter_page():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, (x, y) in enumerate(
        (
            (0.500, 0.500),
            (0.509, 0.497),
            (0.501, 0.503),
            (0.512, 0.498),
            (0.503, 0.501),
            (0.511, 0.499),
        )
    ):
        controller.process_hands([index_only_hand(x, y)], frame_index * 35)

    assert target.pan_deltas == []


def test_small_open_palm_motion_does_not_turn_page_without_swipe_distance():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.62)], 0)
    controller.process_hands([open_hand(0.58)], 60)

    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_vertical_open_palm_motion_does_not_turn_page():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.62, 0.50)], 0)
    controller.process_hands([open_hand(0.62, 0.40)], 60)

    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_controller_emits_current_action_for_page_and_zoom_commands():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    actions = []
    controller.action_changed.connect(actions.append)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.62)], 0)
    controller.process_hands([open_hand(0.56)], 50)
    controller.process_hands([open_hand(0.50)], 100)
    controller.process_hands([open_hand(0.35), open_hand(0.65)], 600)
    controller.process_hands([open_hand(0.35), open_hand(0.65)], 780)
    controller.process_hands([open_hand(0.30), open_hand(0.70)], 830)

    assert "next_page" in actions
    assert "zoom_in" in actions


def test_open_palm_left_moves_to_next_page():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.07, 100), (-0.15, 220), (-0.24, 360)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)

    assert target.next_calls == 1
    assert target.previous_calls == 0


def test_short_fast_open_palm_left_moves_to_next_page():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.05, 60), (-0.10, 120), (-0.15, 180)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)

    assert target.next_calls == 1
    assert target.previous_calls == 0


def test_small_fast_open_palm_left_moves_to_next_page():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.05, 45), (-0.10, 90)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)

    assert target.next_calls == 1


def test_sideways_open_palm_translation_can_turn_page():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.05, 45), (-0.10, 90)):
        controller.process_hands([sideways_open_hand(0.6 + offset)], timestamp)

    assert target.next_calls == 1


def test_open_palm_cooldown_prevents_double_page_turn():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.05, 60), (-0.10, 120), (-0.15, 180)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)
    for offset, timestamp in ((0.0, 260), (-0.05, 320), (-0.10, 380), (-0.15, 440)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)

    assert target.next_calls == 1


def test_rotated_open_palm_does_not_lock_gestures_permanently():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.05, 45), (-0.10, 90)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)
    for timestamp in range(200, 901, 100):
        controller.process_hands([rotated_open_hand(180)], timestamp)
    for offset, timestamp in ((0.0, 1400), (-0.05, 1450), (-0.10, 1500)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)

    assert controller.locked is False
    assert target.next_calls == 2


def test_rotated_closed_fist_can_lock_gestures():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)
    fist = rotate_hand(closed_fist(), 180)

    for timestamp in range(0, 701, 100):
        controller.process_hands([fist], timestamp)

    assert controller.locked is True


def test_held_fist_toggles_lock_only_once_until_released():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 1501, 100):
        controller.process_hands([closed_fist()], timestamp)

    assert controller.locked is True


def test_non_fist_after_fist_lock_auto_unlocks_immediately():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 701, 100):
        controller.process_hands([closed_fist()], timestamp)
    assert controller.locked is True

    controller.process_hands([index_only_hand(0.65)], 701)

    assert controller.locked is False


def test_empty_frame_after_fist_lock_does_not_unlock():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 701, 100):
        controller.process_hands([closed_fist()], timestamp)
    assert controller.locked is True

    controller.process_hands([], 701)

    assert controller.locked is True


def test_open_palm_after_fist_lock_auto_unlocks_and_swipes_immediately():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 701, 100):
        controller.process_hands([closed_fist()], timestamp)
    assert controller.locked is True

    controller.process_hands([open_hand(0.65)], 800)
    for frame_index, timestamp in enumerate((1030, 1080, 1130)):
        controller.process_hands([open_hand(0.65 - frame_index * 0.05)], timestamp)

    assert controller.locked is False
    assert target.next_calls == 1


def test_released_fist_can_toggle_lock_again():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 701, 100):
        controller.process_hands([closed_fist()], timestamp)
    controller.process_hands([], 800)
    for timestamp in range(900, 1601, 100):
        controller.process_hands([closed_fist()], timestamp)

    assert controller.locked is False


def test_locked_gestures_can_unlock_when_a_false_second_hand_is_present():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for timestamp in range(0, 701, 100):
        controller.process_hands([closed_fist()], timestamp)
    controller.process_hands([], 800)
    for timestamp in range(900, 1601, 100):
        controller.process_hands([closed_fist(), open_hand(0.15, 0.65)], timestamp)

    assert controller.locked is False


def test_leaving_gesture_mode_clears_partial_swipe_state():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.60)], 0)
    target.presentation_mode = "ppt"
    controller.process_hands([open_hand(0.55)], 50)
    target.presentation_mode = "gesture"
    controller.process_hands([open_hand(0.50)], 100)

    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_two_open_hands_set_absolute_zoom_in_stage():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.35), open_hand(0.65)], 0)
    controller.process_hands([open_hand(0.35), open_hand(0.65)], 180)
    controller.process_hands([open_hand(0.25), open_hand(0.75)], 230)

    assert target.zoom_values
    assert target.zoom_values[-1] > 1.0


def test_two_hand_zoom_reacts_to_small_distance_change():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.35), open_hand(0.65)], 0)
    controller.process_hands([open_hand(0.35), open_hand(0.65)], 180)
    controller.process_hands([open_hand(0.347), open_hand(0.653)], 230)

    assert target.zoom_values
    assert target.zoom_values[-1] > 1.01


def test_two_hand_zoom_keeps_baseline_during_brief_one_hand_dropout():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.35), open_hand(0.65)], 0)
    controller.process_hands([open_hand(0.35), open_hand(0.65)], 180)
    controller.process_hands([open_hand(0.33), open_hand(0.67)], 230)
    controller.process_hands([open_hand(0.33)], 280)
    controller.process_hands([open_hand(0.30), open_hand(0.70)], 330)

    assert target.zoom_values
    assert target.zoom_values[-1] > 1.0


def test_brief_false_second_hand_does_not_zoom_or_block_swiping():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target, GestureSettings(swipe_cooldown_ms=100))
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.05, 50), (-0.10, 100)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)
    controller.process_hands([open_hand(0.50), open_hand(0.75)], 150)
    controller.process_hands([open_hand(0.45), open_hand(0.75)], 200)
    for offset, timestamp in ((0.0, 250), (-0.05, 300), (-0.10, 350)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)

    assert (target.zoom_values, target.next_calls) == ([], 2)


def test_second_hand_after_swipe_cannot_zoom_during_swipe_cooldown():
    target = FakeTarget()
    target.workspace.mode = "stage"
    controller = GestureController(target)
    controller.set_enabled(True)

    for offset, timestamp in ((0.0, 0), (-0.05, 50), (-0.10, 100)):
        controller.process_hands([open_hand(0.6 + offset)], timestamp)
    controller.process_hands([open_hand(0.45), open_hand(0.75)], 150)
    controller.process_hands([open_hand(0.45), open_hand(0.75)], 330)
    controller.process_hands([open_hand(0.40), open_hand(0.80)], 380)

    assert target.next_calls == 1
    assert target.zoom_values == []
