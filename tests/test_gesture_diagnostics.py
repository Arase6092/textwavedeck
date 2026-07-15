import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gesture.diagnostics import GestureRuntimeDiagnostics


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class FakeTarget:
    presentation_mode = "gesture"
    project = object()


class FakeCamera:
    def __init__(self):
        self.snapshot = {
            "camera_requested": True,
            "running": True,
            "last_hand_delivery_ms": 9_400,
            "last_frame_delivery_ms": 9_400,
            "max_timer_gap_ms": 8,
            "max_delivery_lag_ms": 8,
            "worker": {
                "phase": "detect",
                "phase_since_ms": 9_400,
                "last_result_ms": 9_400,
                "last_capture_ms": 9_390,
                "capture_duration_ms": 10,
                "detect_duration_ms": 40,
                "result_count": 120,
                "read_failures": 0,
                "detector_failures": 0,
                "hand_count": 1,
            },
        }

    def diagnostic_snapshot(self):
        return {
            **self.snapshot,
            "worker": dict(self.snapshot["worker"]),
        }


class FakeController:
    def __init__(self):
        self.snapshot = {
            "enabled": True,
            "locked": False,
            "last_input_ms": 9_400,
            "input_count": 120,
            "hand_count": 1,
            "state": "swipe_tracking",
            "swipe_points": 2,
            "multi_track_count": 0,
            "zoom_state": "idle",
            "last_command": None,
            "last_command_ms": None,
            "command_serial": 0,
        }

    def diagnostic_snapshot(self):
        return dict(self.snapshot)


def test_diagnostics_records_pipeline_stall_and_recovery_without_sensitive_data(qapp, tmp_path):
    camera = FakeCamera()
    controller = FakeController()
    path = tmp_path / "gesture-diagnostics.jsonl"
    diagnostics = GestureRuntimeDiagnostics(FakeTarget(), camera, controller, path=path)
    diagnostics.start()

    diagnostics.poll(now_ms=10_000)
    camera.snapshot["last_hand_delivery_ms"] = 10_045
    camera.snapshot["last_frame_delivery_ms"] = 10_045
    camera.snapshot["worker"]["phase"] = "running"
    camera.snapshot["worker"]["phase_since_ms"] = 10_040
    camera.snapshot["worker"]["last_result_ms"] = 10_040
    controller.snapshot["last_input_ms"] = 10_045
    diagnostics.poll(now_ms=10_050)
    diagnostics.stop()

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert any(
        record["event"] == "pipeline_stall" and record["worker_phase"] == "detect"
        for record in records
    )
    assert any(record["event"] == "pipeline_recovered" for record in records)
    serialized = path.read_text(encoding="utf-8").lower()
    for prohibited in ("landmark", "frame_data", "source_path", "pptx"):
        assert prohibited not in serialized
