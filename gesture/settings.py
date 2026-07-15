"""第二阶段手势控制默认参数。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GestureSettings:
    """保存摄像头采集、预览和手势阈值。"""

    camera_index: int = 0
    capture_width: int = 1280
    capture_height: int = 720
    capture_fps: int = 30
    camera_read_retry_limit: int = 50
    camera_read_retry_delay_ms: int = 20
    inference_width: int = 640
    inference_height: int = 360
    preview_fps: int = 15
    preview_width: int = 320
    preview_height: int = 180
    mirror: bool = True
    max_hands: int = 2
    min_detection_confidence: float = 0.55
    min_tracking_confidence: float = 0.50
    detector_recreate_failure_limit: int = 5
    duplicate_hand_distance: float = 0.045
    swipe_cooldown_ms: int = 450
    swipe_min_duration_ms: int = 50
    swipe_max_duration_ms: int = 360
    swipe_min_displacement: float = 0.08
    swipe_horizontal_ratio: float = 1.10
    swipe_secondary_motion_max: float = 0.05
    swipe_track_match_distance: float = 0.20
    swipe_track_ambiguity_margin: float = 0.03
    ok_max_distance: float = 0.045
    ok_max_scale_ratio: float = 0.45
    ok_index_max_extension_ratio: float = 1.25
    ok_hold_ms: int = 90
    laser_pointer_smoothing: float = 0.25
    laser_pointer_min_delta: float = 0.004
    laser_pointer_dropout_grace_ms: int = 180
    palm_pan_min_delta: float = 0.018
    palm_pan_sensitivity: float = 1.35
    palm_pan_max_gap_ms: int = 160
    palm_pan_smoothing: float = 0.65
    fist_hold_ms: int = 650
    zoom_activation_ms: int = 180
    zoom_deadzone: float = 0.015
    zoom_sensitivity: float = 1.6
    zoom_min_bilateral_contribution: float = 0.20
    zoom_dropout_grace_ms: int = 250
