"""手势运行时分层诊断，不记录画面、关键点坐标或 PPT 内容。"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer


DIAGNOSTICS_ENV = "GESTURE_PPT_DIAGNOSTICS"


def diagnostics_path() -> Path:
    """返回独立诊断日志路径。"""
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    return local_app_data / "GesturePPT" / "logs" / "gesture-diagnostics.jsonl"


def diagnostics_enabled() -> bool:
    return os.environ.get(DIAGNOSTICS_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


class GestureRuntimeDiagnostics(QObject):
    """定期汇总采集、推理、UI 和控制器状态，并标记停顿边界。"""

    def __init__(
        self,
        target: Any,
        camera_preview: Any,
        controller: Any,
        *,
        path: Path | None = None,
    ) -> None:
        super().__init__(target if isinstance(target, QObject) else None)
        self._target = target
        self._camera_preview = camera_preview
        self._controller = controller
        self.path = path or diagnostics_path()
        self._started = False
        self._last_tick_ms: int | None = None
        self._last_heartbeat_ms: int | None = None
        self._pipeline_stall_started_ms: int | None = None
        self._last_stall_report_ms: int | None = None
        self._delivery_stall_active = False
        self._controller_stall_active = False
        self._last_command_serial = 0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.poll)

    def start(self) -> None:
        if self._started:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.write_text("", encoding="utf-8")
        except OSError:
            return
        self._started = True
        self._write("session_start", {})
        self._timer.start()

    def stop(self) -> None:
        if not self._started:
            return
        self._timer.stop()
        self._write("session_end", {})
        self._started = False

    def poll(self, now_ms: int | None = None) -> None:
        """执行一次巡检；测试可传入固定单调时钟。"""
        if not self._started:
            return
        now_ms = _monotonic_ms() if now_ms is None else int(now_ms)
        camera = self._safe_snapshot(self._camera_preview)
        controller = self._safe_snapshot(self._controller)
        worker = camera.get("worker") if isinstance(camera.get("worker"), dict) else {}

        if self._last_tick_ms is not None:
            tick_gap_ms = now_ms - self._last_tick_ms
            if tick_gap_ms > 300:
                self._write("ui_stall", {"gap_ms": tick_gap_ms}, now_ms)
        self._last_tick_ms = now_ms

        self._check_pipeline(now_ms, camera, worker, controller)
        self._check_delivery(now_ms, camera, worker, controller)
        self._check_command(now_ms, controller)

        if self._last_heartbeat_ms is None or now_ms - self._last_heartbeat_ms >= 1_000:
            self._last_heartbeat_ms = now_ms
            self._write(
                "heartbeat",
                self._heartbeat_payload(now_ms, camera, worker, controller),
                now_ms,
            )

    def _check_pipeline(
        self,
        now_ms: int,
        camera: dict[str, Any],
        worker: dict[str, Any],
        controller: dict[str, Any],
    ) -> None:
        last_result_ms = _optional_int(worker.get("last_result_ms"))
        active = bool(camera.get("camera_requested") and camera.get("running"))
        result_age_ms = now_ms - last_result_ms if last_result_ms is not None else None
        stalled = active and (result_age_ms is None or result_age_ms > 300)
        if stalled:
            phase_since_ms = _optional_int(worker.get("phase_since_ms"))
            stall_ms = (
                now_ms - phase_since_ms
                if phase_since_ms is not None
                else result_age_ms
            )
            if self._pipeline_stall_started_ms is None:
                self._pipeline_stall_started_ms = now_ms
                self._last_stall_report_ms = now_ms
                self._write(
                    "pipeline_stall",
                    self._stall_payload(stall_ms, worker, controller),
                    now_ms,
                )
            elif self._last_stall_report_ms is None or now_ms - self._last_stall_report_ms >= 1_000:
                self._last_stall_report_ms = now_ms
                self._write(
                    "pipeline_stall_update",
                    self._stall_payload(stall_ms, worker, controller),
                    now_ms,
                )
            return
        if self._pipeline_stall_started_ms is not None:
            self._write(
                "pipeline_recovered",
                {
                    "duration_ms": now_ms - self._pipeline_stall_started_ms,
                    "worker_phase": worker.get("phase"),
                },
                now_ms,
            )
            self._pipeline_stall_started_ms = None
            self._last_stall_report_ms = None

    def _check_delivery(
        self,
        now_ms: int,
        camera: dict[str, Any],
        worker: dict[str, Any],
        controller: dict[str, Any],
    ) -> None:
        worker_result_ms = _optional_int(worker.get("last_result_ms"))
        delivery_ms = _optional_int(camera.get("last_hand_delivery_ms"))
        input_ms = _optional_int(controller.get("last_input_ms"))
        worker_fresh = worker_result_ms is not None and now_ms - worker_result_ms <= 300
        delivery_stalled = worker_fresh and (delivery_ms is None or now_ms - delivery_ms > 300)
        if delivery_stalled and not self._delivery_stall_active:
            self._delivery_stall_active = True
            self._write(
                "delivery_stall",
                {"worker_result_age_ms": now_ms - worker_result_ms},
                now_ms,
            )
        elif not delivery_stalled and self._delivery_stall_active:
            self._delivery_stall_active = False
            self._write("delivery_recovered", {}, now_ms)

        delivery_fresh = delivery_ms is not None and now_ms - delivery_ms <= 300
        controller_stalled = delivery_fresh and (input_ms is None or now_ms - input_ms > 300)
        if controller_stalled and not self._controller_stall_active:
            self._controller_stall_active = True
            self._write("controller_delivery_stall", {}, now_ms)
        elif not controller_stalled and self._controller_stall_active:
            self._controller_stall_active = False
            self._write("controller_delivery_recovered", {}, now_ms)

    def _check_command(self, now_ms: int, controller: dict[str, Any]) -> None:
        serial = int(controller.get("command_serial") or 0)
        if serial == self._last_command_serial:
            return
        self._last_command_serial = serial
        self._write(
            "command",
            {
                "command": controller.get("last_command"),
                "controller_state": controller.get("state"),
                "hand_count": controller.get("hand_count"),
            },
            now_ms,
        )

    def _heartbeat_payload(
        self,
        now_ms: int,
        camera: dict[str, Any],
        worker: dict[str, Any],
        controller: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "mode": getattr(self._target, "presentation_mode", None),
            "project_loaded": bool(getattr(self._target, "project", None)),
            "camera_requested": bool(camera.get("camera_requested")),
            "camera_running": bool(camera.get("running")),
            "worker_phase": worker.get("phase"),
            "worker_phase_age_ms": _age(now_ms, worker.get("phase_since_ms")),
            "result_age_ms": _age(now_ms, worker.get("last_result_ms")),
            "capture_duration_ms": worker.get("capture_duration_ms"),
            "detect_duration_ms": worker.get("detect_duration_ms"),
            "result_count": worker.get("result_count"),
            "read_failures": worker.get("read_failures"),
            "detector_failures": worker.get("detector_failures"),
            "detected_hand_count": worker.get("hand_count"),
            "delivery_age_ms": _age(now_ms, camera.get("last_hand_delivery_ms")),
            "max_timer_gap_ms": camera.get("max_timer_gap_ms"),
            "max_delivery_lag_ms": camera.get("max_delivery_lag_ms"),
            "controller_input_age_ms": _age(now_ms, controller.get("last_input_ms")),
            "controller_state": controller.get("state"),
            "controller_hand_count": controller.get("hand_count"),
            "locked": bool(controller.get("locked")),
            "swipe_points": controller.get("swipe_points"),
            "multi_track_count": controller.get("multi_track_count"),
            "zoom_state": controller.get("zoom_state"),
            "last_command": controller.get("last_command"),
            "last_command_age_ms": _age(now_ms, controller.get("last_command_ms")),
        }

    @staticmethod
    def _stall_payload(
        stall_ms: int | None,
        worker: dict[str, Any],
        controller: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "stall_ms": stall_ms,
            "worker_phase": worker.get("phase"),
            "capture_duration_ms": worker.get("capture_duration_ms"),
            "detect_duration_ms": worker.get("detect_duration_ms"),
            "read_failures": worker.get("read_failures"),
            "detector_failures": worker.get("detector_failures"),
            "detected_hand_count": worker.get("hand_count"),
            "controller_state": controller.get("state"),
            "locked": bool(controller.get("locked")),
            "zoom_state": controller.get("zoom_state"),
        }

    @staticmethod
    def _safe_snapshot(source: Any) -> dict[str, Any]:
        try:
            snapshot = source.diagnostic_snapshot()
        except Exception:
            return {}
        return snapshot if isinstance(snapshot, dict) else {}

    def _write(self, event: str, payload: dict[str, Any], now_ms: int | None = None) -> None:
        record = {
            "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "monotonic_ms": _monotonic_ms() if now_ms is None else now_ms,
            "event": event,
            **payload,
        }
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            pass


def _monotonic_ms() -> int:
    return int(time.perf_counter_ns() // 1_000_000)


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _age(now_ms: int, value: Any) -> int | None:
    timestamp = _optional_int(value)
    return now_ms - timestamp if timestamp is not None else None
