"""右上角摄像头实时预览窗口。"""

from __future__ import annotations

import os
import time
from threading import Lock

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from app.theme import CONTROL_SURFACE, FOCUS_BLUE, PRIMARY_TEXT, SECONDARY_TEXT
from gesture.camera_worker import CameraWorker
from gesture.settings import GestureSettings


class CameraPreviewWindow(QWidget):
    """独立显示摄像头画面和手部捕捉点线。"""

    hands_ready = Signal(list, int)
    status_changed = Signal(str)

    def __init__(self, settings: GestureSettings | None = None) -> None:
        super().__init__(None)
        self.settings = settings or GestureSettings()
        self._worker: CameraWorker | None = None
        self._received_frame = False
        self._camera_requested = False
        self._restart_attempts = 0
        self._gesture_control_status: str | None = None
        self._base_status = "未启用手势"
        self._current_action = "idle"
        self._latest_lock = Lock()
        self._pending_frame: QImage | None = None
        self._pending_hands: tuple[list, int] | None = None
        self._pending_status: str | None = None
        self._last_delivery_tick_ms: int | None = None
        self._last_hand_delivery_ms: int | None = None
        self._last_frame_delivery_ms: int | None = None
        self._max_timer_gap_ms = 0
        self._max_delivery_lag_ms = 0
        self._last_worker_diagnostic: dict | None = None
        self.setWindowTitle("手势摄像头")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFixedSize(self.settings.preview_width, self.settings.preview_height + 34)
        self.setStyleSheet(
            f"""
            QWidget {{
                background: {CONTROL_SURFACE};
                color: {PRIMARY_TEXT};
                border: 1px solid {FOCUS_BLUE};
            }}
            QLabel#cameraFrame {{
                background: #050607;
                border: 0;
            }}
            QLabel#cameraStatus {{
                background: transparent;
                color: {SECONDARY_TEXT};
                font-size: 12px;
                padding: 6px 8px;
                border: 0;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.frame_label = QLabel()
        self.frame_label.setObjectName("cameraFrame")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setFixedSize(self.settings.preview_width, self.settings.preview_height)
        self.status_label = QLabel(self._format_status_text())
        self.status_label.setObjectName("cameraStatus")
        layout.addWidget(self.frame_label)
        layout.addWidget(self.status_label)
        self._launch_timeout = QTimer(self)
        self._launch_timeout.setSingleShot(True)
        self._launch_timeout.timeout.connect(self._on_launch_timeout)
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(self._restart_camera)
        self._delivery_timer = QTimer(self)
        self._delivery_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._delivery_timer.setInterval(8)
        self._delivery_timer.timeout.connect(self._deliver_latest_results)

    @property
    def running(self) -> bool:
        """返回采集线程是否正在运行。"""
        return bool(self._worker and self._worker.isRunning())

    def start_camera(self) -> None:
        """打开摄像头并将窗口移动到主屏幕右上角。"""
        if not self._camera_requested:
            self._restart_attempts = 0
        self._camera_requested = True
        if os.environ.get("PYTEST_CURRENT_TEST"):
            self._set_status("测试模式不启动摄像头")
            self.show()
            return
        if self.running:
            self._move_to_screen_top_right()
            self.show()
            self.raise_()
            if not self._delivery_timer.isActive():
                self._delivery_timer.start()
            if not self._received_frame:
                self._launch_timeout.start(1200)
            return
        self._start_camera_worker(show_window=True)

    def prewarm_camera(self) -> None:
        """后台预热摄像头，进入手势模式时可直接显示。"""
        if os.environ.get("PYTEST_CURRENT_TEST") or self.running:
            return
        self._start_camera_worker(show_window=False)

    def hide_preview_keep_warm(self) -> None:
        """隐藏预览窗口但保持摄像头热启动。"""
        self._camera_requested = False
        self._restart_timer.stop()
        self._launch_timeout.stop()
        self.hide()

    def _start_camera_worker(self, *, show_window: bool) -> None:
        """创建采集线程；预热路径不展示窗口。"""
        self._received_frame = False
        self._last_delivery_tick_ms = None
        self._last_hand_delivery_ms = None
        self._last_frame_delivery_ms = None
        self._max_timer_gap_ms = 0
        self._max_delivery_lag_ms = 0
        self._last_worker_diagnostic = None
        with self._latest_lock:
            self._pending_frame = None
            self._pending_hands = None
            self._pending_status = None
        self._base_status = "正在打开摄像头…" if show_window else "正在预热摄像头…"
        self.status_label.setText(self._format_status_text())
        if show_window:
            self._move_to_screen_top_right()
            self.show()
            self.raise_()
            self._launch_timeout.start(3500)
            self._delivery_timer.start()
        self._worker = CameraWorker(self.settings)
        self._worker.frame_ready.connect(
            self._store_latest_frame,
            Qt.ConnectionType.DirectConnection,
        )
        self._worker.hands_ready.connect(
            self._store_latest_hands,
            Qt.ConnectionType.DirectConnection,
        )
        self._worker.status_changed.connect(
            self._store_latest_status,
            Qt.ConnectionType.DirectConnection,
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def stop_camera(self) -> None:
        """停止摄像头并隐藏窗口。"""
        self._camera_requested = False
        self._restart_timer.stop()
        self._launch_timeout.stop()
        self._delivery_timer.stop()
        self._gesture_control_status = None
        if self._worker:
            self._worker.stop()
            self._worker.wait(1200)
        with self._latest_lock:
            self._pending_frame = None
            self._pending_hands = None
            self._pending_status = None
        self.hide()

    def _store_latest_frame(self, image: QImage) -> None:
        """跨线程只保存最新预览，避免 Qt 事件队列积压旧帧。"""
        with self._latest_lock:
            self._pending_frame = image

    def _store_latest_hands(self, hands: list, timestamp_ms: int) -> None:
        """跨线程覆盖旧识别结果，手势控制始终消费最新状态。"""
        with self._latest_lock:
            self._pending_hands = (hands, timestamp_ms)

    def _store_latest_status(self, message: str) -> None:
        """合并高频检测状态，弱光抖动时不挤占主线程队列。"""
        with self._latest_lock:
            self._pending_status = message

    def _deliver_latest_results(self) -> None:
        """以 8 ms 周期向主线程交付最新结果，中间帧允许丢弃。"""
        now_ms = int(time.perf_counter_ns() // 1_000_000)
        if self._last_delivery_tick_ms is not None:
            self._max_timer_gap_ms = max(
                self._max_timer_gap_ms,
                now_ms - self._last_delivery_tick_ms,
            )
        self._last_delivery_tick_ms = now_ms
        with self._latest_lock:
            hands_result = self._pending_hands
            frame = self._pending_frame
            status = self._pending_status
            self._pending_hands = None
            self._pending_frame = None
            self._pending_status = None
        if hands_result is not None:
            self._last_hand_delivery_ms = now_ms
            self._max_delivery_lag_ms = max(
                self._max_delivery_lag_ms,
                max(0, now_ms - int(hands_result[1])),
            )
            self.hands_ready.emit(*hands_result)
        if status is not None:
            self._set_status(status)
            self.status_changed.emit(status)
        if frame is not None:
            self._last_frame_delivery_ms = now_ms
            self._set_frame(frame)

    def diagnostic_snapshot(self) -> dict:
        """返回不含画面和关键点的 UI 交付诊断快照。"""
        worker_snapshot = self._last_worker_diagnostic
        if self._worker is not None and hasattr(self._worker, "diagnostic_snapshot"):
            worker_snapshot = self._worker.diagnostic_snapshot()
        return {
            "camera_requested": self._camera_requested,
            "running": self.running,
            "last_hand_delivery_ms": self._last_hand_delivery_ms,
            "last_frame_delivery_ms": self._last_frame_delivery_ms,
            "max_timer_gap_ms": self._max_timer_gap_ms,
            "max_delivery_lag_ms": self._max_delivery_lag_ms,
            "worker": worker_snapshot,
        }

    def _set_frame(self, image: QImage) -> None:
        self._received_frame = True
        self._restart_attempts = 0
        self.frame_label.setPixmap(QPixmap.fromImage(image))

    def _set_status(self, message: str) -> None:
        self._base_status = message
        self.status_label.setText(self._format_status_text())

    def set_gesture_control_status(self, message: str) -> None:
        """锁定提示优先于摄像头手数状态，避免用户误以为识别失灵。"""
        if message.startswith(("手势已锁定", "手势已暂停")):
            self._gesture_control_status = message
        elif "解锁" in message:
            self._gesture_control_status = None
            self._base_status = message
        else:
            self._base_status = message
        self.status_label.setText(self._format_status_text())

    def set_current_action(self, action: str) -> None:
        """在状态栏附加当前识别到的功能名。"""
        self._current_action = action or "idle"
        self.status_label.setText(self._format_status_text())

    def _format_status_text(self) -> str:
        status = self._gesture_control_status or self._base_status
        return f"{status} | {self._current_action}"

    def _on_worker_finished(self) -> None:
        self._launch_timeout.stop()
        if not self._received_frame and self.status_label.text().startswith("正在打开"):
            self._set_status("摄像头不可用或被占用")
        if self._worker:
            if hasattr(self._worker, "diagnostic_snapshot"):
                self._last_worker_diagnostic = self._worker.diagnostic_snapshot()
            self._worker.deleteLater()
            self._worker = None
        if self._camera_requested:
            self._restart_attempts += 1
            delay_ms = min(500 * (2 ** (self._restart_attempts - 1)), 5000)
            self._set_status("手势服务中断，正在自动恢复…")
            self._restart_timer.start(delay_ms)

    def _restart_camera(self) -> None:
        """仅在手势模式仍要求摄像头时重启异常退出的线程。"""
        if self._camera_requested and not self.running:
            self.start_camera()

    def _on_launch_timeout(self) -> None:
        """启动超时兜底，只提示不强杀，避免误判慢设备为不可用。"""
        if self.running and not self._received_frame:
            self._set_status("摄像头响应较慢，正在继续等待…")

    def _move_to_screen_top_right(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        rect = screen.availableGeometry()
        self.move(rect.right() - self.width() - 16, rect.top() + 16)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.stop_camera()
        event.accept()
