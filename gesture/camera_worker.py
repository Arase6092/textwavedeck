"""摄像头采集和手部点线绘制线程。"""

from __future__ import annotations

import time
import os
import shutil
from pathlib import Path
from threading import Lock
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from app.runtime_paths import bundle_path
from gesture.hand_landmarks import HandLandmarks
from gesture.settings import GestureSettings


def _monotonic_ms() -> int:
    return int(time.perf_counter_ns() // 1_000_000)


class CameraWorker(QThread):
    """在后台读取摄像头，并把最新预览帧发送给 Qt 主线程。"""

    frame_ready = Signal(QImage)
    hands_ready = Signal(list, int)
    status_changed = Signal(str)

    def __init__(self, settings: GestureSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or GestureSettings()
        self._running = False
        now_ms = _monotonic_ms()
        self._diagnostic_lock = Lock()
        self._diagnostic: dict[str, Any] = {
            "phase": "idle",
            "phase_since_ms": now_ms,
            "last_capture_ms": None,
            "capture_duration_ms": None,
            "last_detect_ms": None,
            "detect_duration_ms": None,
            "last_result_ms": None,
            "result_count": 0,
            "read_failures": 0,
            "detector_failures": 0,
            "hand_count": 0,
        }

    def stop(self) -> None:
        """请求停止采集，实际释放在 run() 的 finally 中完成。"""
        self._running = False

    def run(self) -> None:  # noqa: D401
        """执行摄像头采集循环。"""
        self._set_diagnostic_phase("opencv_import")
        try:
            import cv2
        except ImportError:
            self._set_diagnostic_phase("opencv_missing")
            self.status_changed.emit("缺少 opencv-python，无法打开摄像头")
            return

        self._set_diagnostic_phase("opening")
        cap, capture_note = self._open_capture(cv2)
        if cap is None:
            self._set_diagnostic_phase("open_failed")
            self.status_changed.emit("摄像头不可用或被占用")
            return
        self._set_diagnostic_phase("configure")
        self.status_changed.emit(capture_note)

        detector: Any | None = None
        connections: Any | None = None

        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.capture_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.capture_height)
            cap.set(cv2.CAP_PROP_FPS, self.settings.capture_fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.status_changed.emit("正在跟踪")
            self._running = True
            frame_interval = 1.0 / max(1, self.settings.preview_fps)
            next_preview_at = 0.0
            last_hand_count: int | None = None
            consecutive_read_failures = 0
            consecutive_detector_failures = 0
            detector_load_started = False
            first_preview_sent = False
            while self._running:
                capture_started_ms = _monotonic_ms()
                self._set_diagnostic_phase("capture", capture_started_ms)
                ok, frame = cap.read()
                capture_finished_ms = _monotonic_ms()
                self._update_diagnostic(
                    last_capture_ms=capture_finished_ms,
                    capture_duration_ms=capture_finished_ms - capture_started_ms,
                )
                if not ok or frame is None:
                    consecutive_read_failures += 1
                    self._increment_diagnostic("read_failures")
                    if consecutive_read_failures == 1:
                        self.status_changed.emit("摄像头画面中断，正在恢复…")
                    if consecutive_read_failures >= self.settings.camera_read_retry_limit:
                        self.status_changed.emit("摄像头连续读取失败")
                        break
                    time.sleep(self.settings.camera_read_retry_delay_ms / 1000)
                    continue
                if consecutive_read_failures:
                    consecutive_read_failures = 0
                    self.status_changed.emit("摄像头画面已恢复")
                if self.settings.mirror:
                    frame = cv2.flip(frame, 1)

                landmarks = []
                if not first_preview_sent:
                    first_preview_sent = True
                    next_preview_at = time.perf_counter() + frame_interval
                    self._set_diagnostic_phase("preview")
                    self.frame_ready.emit(_preview_image(frame, [], None, cv2, self.settings))
                if not detector_load_started:
                    detector_load_started = True
                    self._set_diagnostic_phase("model_load")
                    detector, connections = self._create_hand_detector()
                if detector is not None:
                    detect_started_ms = _monotonic_ms()
                    self._set_diagnostic_phase("detect", detect_started_ms)
                    try:
                        rgb = _prepare_inference_rgb(frame, cv2, self.settings)
                        landmarks = detector.detect(rgb, int(time.perf_counter_ns() // 1_000_000))
                        detect_finished_ms = _monotonic_ms()
                        self._update_diagnostic(
                            last_detect_ms=detect_finished_ms,
                            detect_duration_ms=detect_finished_ms - detect_started_ms,
                        )
                        if consecutive_detector_failures:
                            consecutive_detector_failures = 0
                            self.status_changed.emit("手部识别已恢复")
                    except Exception:
                        detect_finished_ms = _monotonic_ms()
                        self._update_diagnostic(
                            last_detect_ms=detect_finished_ms,
                            detect_duration_ms=detect_finished_ms - detect_started_ms,
                        )
                        self._increment_diagnostic("detector_failures")
                        consecutive_detector_failures += 1
                        landmarks = []
                        if consecutive_detector_failures == 1:
                            self.status_changed.emit("手部识别暂时中断，正在恢复…")
                        if consecutive_detector_failures >= self.settings.detector_recreate_failure_limit:
                            try:
                                detector.close()
                            except Exception:
                                pass
                            detector, connections = self._create_hand_detector()
                            consecutive_detector_failures = 0
                if len(landmarks) != last_hand_count:
                    last_hand_count = len(landmarks)
                    self.status_changed.emit(
                        f"检测到 {last_hand_count} 只手" if last_hand_count else "未检测到手"
                    )
                now_ms = time.perf_counter_ns() // 1_000_000
                if detector is not None:
                    self.hands_ready.emit(landmarks, int(now_ms))
                    self._update_diagnostic(
                        last_result_ms=int(now_ms),
                        result_count=int(self._diagnostic_value("result_count")) + 1,
                        hand_count=len(landmarks),
                    )
                    self._set_diagnostic_phase("running")

                now = time.perf_counter()
                if now >= next_preview_at:
                    next_preview_at = now + frame_interval
                    self._set_diagnostic_phase("preview")
                    self.frame_ready.emit(_preview_image(frame, landmarks, connections, cv2, self.settings))
                    self._set_diagnostic_phase("running")
        finally:
            self._set_diagnostic_phase("stopping")
            if detector is not None:
                try:
                    detector.close()
                except Exception:
                    pass
            try:
                cap.release()
            except Exception:
                pass
            self._set_diagnostic_phase("stopped")
            self.status_changed.emit("手势已停用")

    def diagnostic_snapshot(self) -> dict[str, Any]:
        """返回不含画面和关键点的线程诊断快照。"""
        with self._diagnostic_lock:
            return dict(self._diagnostic)

    def _set_diagnostic_phase(self, phase: str, now_ms: int | None = None) -> None:
        now_ms = _monotonic_ms() if now_ms is None else int(now_ms)
        with self._diagnostic_lock:
            if self._diagnostic["phase"] != phase:
                self._diagnostic["phase"] = phase
                self._diagnostic["phase_since_ms"] = now_ms

    def _update_diagnostic(self, **values: Any) -> None:
        with self._diagnostic_lock:
            self._diagnostic.update(values)

    def _increment_diagnostic(self, key: str) -> None:
        with self._diagnostic_lock:
            self._diagnostic[key] = int(self._diagnostic.get(key) or 0) + 1

    def _diagnostic_value(self, key: str) -> Any:
        with self._diagnostic_lock:
            return self._diagnostic.get(key)

    def _create_hand_detector(self) -> tuple[Any | None, Any | None]:
        """初始化 MediaPipe 手部识别器，摄像头预览不等待它完成。"""
        try:
            import mediapipe as mp

            if hasattr(mp, "solutions"):
                _prepare_mediapipe_ascii_resources(mp)
                self.status_changed.emit("正在加载手部模型…")
                detector = _LegacyHandsDetector(mp, self.settings)
                connections = mp.solutions.hands.HAND_CONNECTIONS
                self.status_changed.emit("手部识别已启动")
                return detector, connections

            detector, connections = _create_tasks_detector(mp, self.settings, self.status_changed.emit)
            if detector is None:
                return None, None
            self.status_changed.emit("手部识别已启动")
            return detector, connections
        except ImportError:
            self.status_changed.emit("缺少 mediapipe，仅显示摄像头画面")
        except Exception as exc:
            self.status_changed.emit(f"手部模型加载失败：{exc}")
        return None, None

    def _open_capture(self, cv2: Any) -> tuple[Any | None, str]:
        """按多个后端和索引尝试打开摄像头，避免单一组合误判失败。"""
        candidates: list[tuple[str, int | None, int]] = [
            ("DirectShow", self.settings.camera_index, cv2.CAP_DSHOW),
            ("DirectShow", 0, cv2.CAP_DSHOW),
            ("DirectShow", 1, cv2.CAP_DSHOW),
            ("DirectShow", 2, cv2.CAP_DSHOW),
            ("MSMF", self.settings.camera_index, cv2.CAP_MSMF),
            ("MSMF", 0, cv2.CAP_MSMF),
            ("系统默认", self.settings.camera_index, cv2.CAP_ANY),
        ]
        seen: set[tuple[int | None, int]] = set()
        for backend_name, index, backend in candidates:
            key = (index, backend)
            if key in seen:
                continue
            seen.add(key)
            self.status_changed.emit(f"正在打开摄像头… {backend_name} {index}")
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.capture_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.capture_height)
            cap.set(cv2.CAP_PROP_FPS, self.settings.capture_fps)
            ok, frame = cap.read()
            if ok and frame is not None:
                note = f"摄像头已连接：{backend_name} {index}"
                return cap, note
            cap.release()
        return None, "摄像头不可用或被占用"


def _preview_image(
    frame: Any,
    landmarks: list[list[tuple[float, float, float]]],
    connections: Any | None,
    cv2: Any,
    settings: GestureSettings,
) -> QImage:
    """将采集帧转换为 Qt 预览图，并在预览尺寸上绘制关键点。"""
    preview = cv2.resize(
        frame,
        (settings.preview_width, settings.preview_height),
        interpolation=cv2.INTER_AREA,
    )
    if landmarks and connections is not None:
        _draw_landmarks_on_preview(preview, landmarks, connections, cv2)
    preview = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
    height, width, channels = preview.shape
    return QImage(
        preview.data,
        width,
        height,
        channels * width,
        QImage.Format.Format_RGB888,
    ).copy()


def _prepare_inference_rgb(frame: Any, cv2: Any, settings: GestureSettings) -> Any:
    """缩小推理帧，降低 MediaPipe 单帧延迟。"""
    inference_frame = cv2.resize(
        frame,
        (settings.inference_width, settings.inference_height),
        interpolation=cv2.INTER_AREA,
    )
    return cv2.cvtColor(inference_frame, cv2.COLOR_BGR2RGB)


def _draw_landmarks_on_preview(
    preview: Any,
    hands: list[list[tuple[float, float, float]]],
    connections: Any,
    cv2: Any,
) -> None:
    """在预览尺寸上重画手部骨架，避免原图缩小时点线消失。"""
    height, width = preview.shape[:2]
    line_color = (255, 111, 59)
    point_color = (255, 255, 255)
    for hand in hands:
        points = [
            (
                max(0, min(width - 1, int(x * width))),
                max(0, min(height - 1, int(y * height))),
            )
            for x, y, _ in hand
        ]
        for connection in connections:
            start, end = _connection_indices(connection)
            if start < len(points) and end < len(points):
                cv2.line(preview, points[start], points[end], line_color, 2, cv2.LINE_AA)
        for point in points:
            cv2.circle(preview, point, 3, point_color, -1, cv2.LINE_AA)
            cv2.circle(preview, point, 4, line_color, 1, cv2.LINE_AA)


def _connection_indices(connection: Any) -> tuple[int, int]:
    """兼容 tuple 和 MediaPipe connection 对象。"""
    if hasattr(connection, "start") and hasattr(connection, "end"):
        return int(connection.start), int(connection.end)
    return int(connection[0]), int(connection[1])


def _hand_landmarker_model_path() -> Path:
    """返回随项目发布的 Hand Landmarker 模型路径。"""
    return bundle_path("resources", "models", "hand_landmarker.task")


class _LegacyHandsDetector:
    """封装旧版 MediaPipe Hands，使主循环不关心具体 API。"""

    def __init__(self, mp: Any, settings: GestureSettings) -> None:
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=settings.max_hands,
            model_complexity=0,
            min_detection_confidence=settings.min_detection_confidence,
            min_tracking_confidence=settings.min_tracking_confidence,
        )

    def detect(self, rgb: Any, timestamp_ms: int) -> list[HandLandmarks]:
        """返回归一化手部关键点。"""
        result = self._hands.process(rgb)
        if not result.multi_hand_landmarks:
            return []
        handedness_items = result.multi_handedness or []
        hands: list[HandLandmarks] = []
        for index, hand_landmarks in enumerate(result.multi_hand_landmarks):
            label = _handedness_label(handedness_items[index] if index < len(handedness_items) else None)
            hands.append(
                HandLandmarks(
                    [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark],
                    label,
                )
            )
        return hands

    def close(self) -> None:
        self._hands.close()


class _TasksHandDetector:
    """封装新版 MediaPipe Tasks HandLandmarker。"""

    def __init__(self, detector: Any, mp_image_cls: Any, mp_image_format: Any) -> None:
        self._detector = detector
        self._image_cls = mp_image_cls
        self._image_format = mp_image_format

    def detect(self, rgb: Any, timestamp_ms: int) -> list[HandLandmarks]:
        image = self._image_cls(image_format=self._image_format.SRGB, data=rgb)
        result = self._detector.detect_for_video(image, timestamp_ms)
        handedness_items = result.handedness or []
        hands: list[HandLandmarks] = []
        for index, hand in enumerate(result.hand_landmarks):
            label = _handedness_label(handedness_items[index] if index < len(handedness_items) else None)
            hands.append(HandLandmarks([(lm.x, lm.y, lm.z) for lm in hand], label))
        return hands

    def close(self) -> None:
        self._detector.close()


def _handedness_label(item: Any) -> str | None:
    """提取 MediaPipe legacy/tasks 的 Left/Right 标签。"""
    if item is None:
        return None
    candidate = item
    if hasattr(item, "classification") and item.classification:
        candidate = item.classification[0]
    elif isinstance(item, (list, tuple)) and item:
        candidate = item[0]
    label = (
        getattr(candidate, "label", None)
        or getattr(candidate, "category_name", None)
        or getattr(candidate, "display_name", None)
    )
    if not label:
        return None
    normalized = str(label).strip().lower()
    if normalized == "right":
        return "Right"
    if normalized == "left":
        return "Left"
    return None


def _create_tasks_detector(mp: Any, settings: GestureSettings, report_status: Any) -> tuple[Any | None, Any | None]:
    """在新版 MediaPipe 中使用 Hand Landmarker Tasks API。"""
    model_path = _hand_landmarker_model_path()
    if not model_path.exists():
        report_status("缺少手部模型：resources/models/hand_landmarker.task")
        return None, None
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    report_status("正在加载手部模型…")
    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=settings.max_hands,
        min_hand_detection_confidence=settings.min_detection_confidence,
        min_tracking_confidence=settings.min_tracking_confidence,
    )
    detector = vision.HandLandmarker.create_from_options(options)
    return _TasksHandDetector(detector, mp.Image, mp.ImageFormat), vision.HandLandmarksConnections.HAND_CONNECTIONS


def _prepare_mediapipe_ascii_resources(mp: Any) -> None:
    """把 MediaPipe 模型资源映射到 ASCII 路径，避开中文路径加载失败。"""
    import mediapipe.python.solution_base as solution_base

    runtime_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GesturePPT" / "mediapipe_runtime"
    target_modules = runtime_root / "mediapipe" / "modules"
    marker = target_modules / "hand_landmark" / "hand_landmark_tracking_cpu.binarypb"
    if not marker.exists():
        source_modules = Path(mp.__file__).resolve().parent / "modules"
        target_modules.parent.mkdir(parents=True, exist_ok=True)
        if target_modules.exists():
            shutil.rmtree(target_modules)
        shutil.copytree(source_modules, target_modules)
    # SolutionBase 通过 __file__ 反推资源根目录；这里改到 ASCII 资源镜像。
    solution_base.__file__ = str(runtime_root / "mediapipe" / "python" / "solution_base.py")
