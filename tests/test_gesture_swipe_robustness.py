import random

import pytest

from gesture.controller import GestureController


class FakeWorkspace:
    def __init__(self):
        self.mode = "stage"
        self.zoom_factor = 1.0


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


def open_hand(x=0.5, y=0.5):
    hand = [(x, y, 0.0) for _ in range(21)]
    for index, dx in ((5, -0.04), (9, 0.0), (13, 0.04), (17, 0.08)):
        hand[index] = (x + dx, y, 0.0)
    for tip, pip, dx in ((8, 6, -0.04), (12, 10, 0.0), (16, 14, 0.04), (20, 18, 0.08)):
        hand[pip] = (x + dx, y - 0.05, 0.0)
        hand[tip] = (x + dx, y - 0.16, 0.0)
    hand[4] = (x - 0.12, y - 0.04, 0.0)
    return hand


def shifted_hand(hand, dx=0.0, dy=0.0):
    return [(x + dx, y + dy, z) for x, y, z in hand]


def neutral_hand(x=0.5, y=0.5):
    return [(x, y, 0.0) for _ in range(21)]


def closed_fist(x=0.5, y=0.5):
    hand = open_hand(x, y)
    for tip, _, dx in ((8, 6, -0.04), (12, 10, 0.0), (16, 14, 0.04), (20, 18, 0.08)):
        hand[tip] = (x + dx, y + 0.01, 0.0)
    hand[4] = (x - 0.03, y, 0.0)
    return hand


def test_duplicate_detection_of_one_hand_still_swipes_left():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, (offset, timestamp) in enumerate(((0.0, 0), (-0.05, 50), (-0.10, 100))):
        hand = open_hand(0.6 + offset)
        duplicate = shifted_hand(hand, dx=0.012, dy=0.006)
        hands = [hand, duplicate] if frame_index % 2 == 0 else [duplicate, hand]
        controller.process_hands(hands, timestamp)

    assert target.next_calls == 1
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_opposite_duplicate_bias_at_start_and_end_does_not_hide_right_swipe():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    start = open_hand(0.35)
    controller.process_hands([shifted_hand(start, 0.023, 0.0), start], 0)
    controller.process_hands([open_hand(0.41)], 50)
    end = open_hand(0.47)
    controller.process_hands([shifted_hand(end, -0.024, 0.0), end], 100)

    assert target.next_calls == 0
    assert target.previous_calls == 1
    assert target.zoom_values == []


def test_transient_distant_false_hand_does_not_break_swipe():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.60)], 0)
    controller.process_hands([open_hand(0.15), open_hand(0.55)], 50)
    controller.process_hands([open_hand(0.50)], 100)

    assert target.next_calls == 1
    assert target.previous_calls == 0
    assert target.zoom_values == []


@pytest.mark.parametrize("direction", (-1, 1))
@pytest.mark.parametrize("duplicate_offset", (0.0, 0.01, 0.025, 0.04))
def test_duplicate_offsets_and_order_swaps_preserve_both_swipe_directions(direction, duplicate_offset):
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)
    start_x = 0.65 if direction < 0 else 0.35

    for frame_index, timestamp in enumerate((0, 50, 100)):
        hand = open_hand(start_x + direction * frame_index * 0.05)
        duplicate = shifted_hand(hand, dx=duplicate_offset, dy=duplicate_offset / 2)
        hands = [hand, duplicate] if frame_index % 2 == 0 else [duplicate, hand]
        controller.process_hands(hands, timestamp)

    assert target.next_calls == (1 if direction < 0 else 0)
    assert target.previous_calls == (1 if direction > 0 else 0)
    assert target.zoom_values == []


@pytest.mark.parametrize("direction", (-1, 1))
def test_seeded_swipes_survive_combined_duplicates_false_hands_dropouts_and_jitter(direction):
    for seed in range(500):
        randomizer = random.Random(seed)
        target = FakeTarget()
        controller = GestureController(target)
        controller.set_enabled(True)
        start_x = 0.65 if direction < 0 else 0.35
        false_hand_frames = set(randomizer.sample((1, 2, 3), randomizer.randint(0, 2)))
        dropout_frame = randomizer.choice((None, None, 1, 2, 3))

        for frame_index, timestamp in enumerate((0, 40, 80, 120, 160)):
            x = start_x + direction * frame_index * 0.03 + randomizer.uniform(-0.004, 0.004)
            y = 0.5 + randomizer.uniform(-0.004, 0.004)
            hand = open_hand(x, y)
            if frame_index == dropout_frame and frame_index not in false_hand_frames:
                hands = []
            elif frame_index in false_hand_frames:
                hands = [open_hand(0.12, 0.62), hand]
                if randomizer.random() < 0.5:
                    hands.reverse()
            elif randomizer.random() < 0.65:
                duplicate = shifted_hand(
                    hand,
                    dx=randomizer.uniform(-0.025, 0.025),
                    dy=randomizer.uniform(-0.012, 0.012),
                )
                hands = [hand, duplicate]
                if randomizer.random() < 0.5:
                    hands.reverse()
            else:
                hands = [hand]
            controller.process_hands(hands, timestamp)

        assert target.next_calls == (1 if direction < 0 else 0), seed
        assert target.previous_calls == (1 if direction > 0 else 0), seed
        assert target.zoom_values == [], seed


def test_vertical_duplicate_motion_does_not_turn_page():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, timestamp in enumerate((0, 50, 100)):
        hand = open_hand(0.5, 0.60 - frame_index * 0.05)
        controller.process_hands([hand, shifted_hand(hand, 0.012, 0.006)], timestamp)

    assert target.next_calls == 0
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_stationary_hand_with_transient_false_detection_does_nothing():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.5)], 0)
    controller.process_hands([open_hand(0.12), open_hand(0.5)], 50)
    controller.process_hands([open_hand(0.12), open_hand(0.5)], 100)
    controller.process_hands([open_hand(0.5)], 150)

    assert target.next_calls == 0
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_two_distinct_stable_hands_still_zoom_without_turning_page():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.30), open_hand(0.70)], 0)
    controller.process_hands([open_hand(0.30), open_hand(0.70)], 180)
    controller.process_hands([open_hand(0.25), open_hand(0.75)], 230)

    assert target.next_calls == 0
    assert target.previous_calls == 0
    assert target.zoom_values


def test_one_sided_motion_after_two_hand_hold_does_not_activate_zoom():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.30), open_hand(0.70)], 0)
    controller.process_hands([open_hand(0.30), open_hand(0.70)], 180)
    controller.process_hands([open_hand(0.25), open_hand(0.70)], 230)

    assert target.next_calls == 0
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_persistent_distant_false_hand_still_allows_single_moving_hand_to_swipe():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, timestamp in enumerate((0, 50, 100)):
        moving_hand = open_hand(0.65 - frame_index * 0.05)
        hands = [open_hand(0.12, 0.62), moving_hand]
        if frame_index % 2:
            hands.reverse()
        controller.process_hands(hands, timestamp)

    assert target.next_calls == 1
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_persistent_false_hand_cannot_poison_later_swipes_after_idle_time():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)
    false_hand = open_hand(0.12, 0.62)

    for frame_index, timestamp in enumerate((0, 50, 100)):
        controller.process_hands(
            [false_hand, open_hand(0.65 - frame_index * 0.05)],
            timestamp,
        )
    for timestamp in range(150, 851, 50):
        controller.process_hands([false_hand, open_hand(0.55)], timestamp)
    for frame_index, timestamp in enumerate((900, 950, 1000)):
        controller.process_hands(
            [false_hand, open_hand(0.55 - frame_index * 0.05)],
            timestamp,
        )

    assert target.next_calls == 2
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_swipe_track_survives_false_hand_then_one_empty_frame():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.65)], 0)
    controller.process_hands([open_hand(0.12, 0.62), open_hand(0.61)], 40)
    controller.process_hands([], 80)
    controller.process_hands([open_hand(0.56)], 120)

    assert target.next_calls == 1
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_two_hands_moving_together_do_not_masquerade_as_single_hand_swipe():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, timestamp in enumerate((0, 50, 100)):
        offset = -frame_index * 0.05
        controller.process_hands(
            [open_hand(0.35 + offset), open_hand(0.70 + offset)],
            timestamp,
        )

    assert target.next_calls == 0
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_non_open_false_hand_does_not_break_primary_hand_tracking():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, timestamp in enumerate((0, 50, 100)):
        controller.process_hands(
            [neutral_hand(0.12, 0.62), open_hand(0.65 - frame_index * 0.05)],
            timestamp,
        )

    assert target.next_calls == 1
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_false_fist_beside_real_open_hand_cannot_lock_or_block_swipe():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, timestamp in enumerate(range(0, 701, 50)):
        x = 0.65 - min(frame_index, 2) * 0.05
        controller.process_hands([closed_fist(0.12, 0.62), open_hand(x)], timestamp)

    assert controller.locked is False
    assert target.next_calls == 1
    assert target.previous_calls == 0
    assert target.zoom_values == []


def test_twenty_alternating_swipes_remain_usable_with_a_persistent_false_hand():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)
    false_hand = open_hand(0.12, 0.62)
    current_x = 0.65
    timestamp = 0

    for cycle in range(20):
        direction = -1 if cycle % 2 == 0 else 1
        for frame_index in range(3):
            x = current_x + direction * frame_index * 0.05
            controller.process_hands([false_hand, open_hand(x)], timestamp + frame_index * 50)
        current_x += direction * 0.10
        for hold_time in range(timestamp + 150, timestamp + 751, 50):
            controller.process_hands([false_hand, open_hand(current_x)], hold_time)
        timestamp += 800

    assert target.next_calls == 10
    assert target.previous_calls == 10
    assert target.zoom_values == []


def test_repeated_bilateral_zoom_cycles_release_cleanly():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for cycle in range(10):
        timestamp = cycle * 700
        controller.process_hands([open_hand(0.35), open_hand(0.65)], timestamp)
        controller.process_hands([open_hand(0.35), open_hand(0.65)], timestamp + 180)
        controller.process_hands([open_hand(0.33), open_hand(0.67)], timestamp + 230)
        controller.process_hands([], timestamp + 550)

    assert target.next_calls == 0
    assert target.previous_calls == 0
    assert len(target.zoom_values) == 10


def test_bilateral_inward_motion_zooms_out():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    controller.process_hands([open_hand(0.25), open_hand(0.75)], 0)
    controller.process_hands([open_hand(0.25), open_hand(0.75)], 180)
    controller.process_hands([open_hand(0.30), open_hand(0.70)], 230)

    assert target.zoom_values
    assert target.zoom_values[-1] < 1.0
    assert target.next_calls == 0
    assert target.previous_calls == 0


def test_mixed_swipe_zoom_lock_unlock_and_resume_sequence():
    target = FakeTarget()
    controller = GestureController(target)
    controller.set_enabled(True)

    for frame_index, timestamp in enumerate((0, 50, 100)):
        controller.process_hands([open_hand(0.65 - frame_index * 0.05)], timestamp)

    controller.process_hands([open_hand(0.35), open_hand(0.65)], 600)
    controller.process_hands([open_hand(0.35), open_hand(0.65)], 780)
    controller.process_hands([open_hand(0.33), open_hand(0.67)], 830)
    controller.process_hands([], 1200)

    for timestamp in range(1300, 2001, 100):
        controller.process_hands([closed_fist()], timestamp)
    for frame_index, timestamp in enumerate((2100, 2150, 2200)):
        controller.process_hands([open_hand(0.65 - frame_index * 0.05)], timestamp)

    controller.process_hands([], 2300)
    for timestamp in range(2400, 3101, 100):
        controller.process_hands([closed_fist(), open_hand(0.15, 0.65)], timestamp)
    controller.process_hands([], 3200)
    for frame_index, timestamp in enumerate((3300, 3350, 3400)):
        controller.process_hands([open_hand(0.35 + frame_index * 0.05)], timestamp)

    assert controller.locked is False
    assert target.next_calls == 1
    assert target.previous_calls == 1
    assert target.zoom_values
