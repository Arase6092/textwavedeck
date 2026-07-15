from gesture.camera_worker import CameraWorker
from gesture.camera_worker import _LegacyHandsDetector
from gesture.camera_worker import _draw_landmarks_on_preview
from gesture.camera_worker import _create_tasks_detector
from gesture.camera_worker import _handedness_label
from gesture.camera_worker import _prepare_inference_rgb
from gesture.settings import GestureSettings


class FakeCapture:
    def __init__(self, opened: bool, read_ok: bool):
        self._opened = opened
        self._read_ok = read_ok
        self.released = False
        self.set_calls = []

    def isOpened(self):
        return self._opened

    def read(self):
        return self._read_ok, object() if self._read_ok else None

    def set(self, prop, value):
        self.set_calls.append((prop, value))

    def release(self):
        self.released = True


class FakeCv2:
    CAP_DSHOW = 1
    CAP_MSMF = 2
    CAP_ANY = 3
    CAP_PROP_FRAME_WIDTH = 10
    CAP_PROP_FRAME_HEIGHT = 11
    CAP_PROP_FPS = 12

    def __init__(self, captures):
        self.captures = captures
        self.calls = []

    def VideoCapture(self, index, backend):
        self.calls.append((index, backend))
        return self.captures[(index, backend)]


def test_open_capture_falls_back_until_it_reads_a_frame():
    worker = CameraWorker()
    cv2 = FakeCv2(
        {
            (0, 1): FakeCapture(False, False),
            (1, 1): FakeCapture(True, False),
            (2, 1): FakeCapture(True, True),
            (0, 2): FakeCapture(False, False),
            (0, 3): FakeCapture(False, False),
        }
    )

    cap, note = worker._open_capture(cv2)

    assert cap is cv2.captures[(2, 1)]
    assert note == "摄像头已连接：DirectShow 2"
    assert cv2.calls[:3] == [(0, 1), (1, 1), (2, 1)]


def test_draw_landmarks_on_preview_marks_pixels():
    import numpy as np

    preview = np.zeros((180, 320, 3), dtype=np.uint8)
    hand = [(0.5, 0.5, 0.0) for _ in range(21)]
    hand[5] = (0.4, 0.5, 0.0)
    hand[8] = (0.35, 0.35, 0.0)
    _draw_landmarks_on_preview(preview, [hand], [(5, 8)], cv2=__import__("cv2"))
    assert preview.sum() > 0


def test_inference_frame_is_downscaled_to_low_latency_size():
    import cv2
    import numpy as np

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    rgb = _prepare_inference_rgb(frame, cv2, GestureSettings())

    assert rgb.shape == (360, 640, 3)


def test_handedness_label_supports_legacy_and_tasks_shapes():
    class LegacyClassification:
        label = "Right"

    class LegacyHandedness:
        classification = [LegacyClassification()]

    class TasksCategory:
        category_name = "Left"
        display_name = ""

    assert _handedness_label(LegacyHandedness()) == "Right"
    assert _handedness_label([TasksCategory()]) == "Left"


def test_legacy_detector_uses_configured_confidence_thresholds():
    class FakeHands:
        kwargs = None

        def __init__(self, **kwargs):
            type(self).kwargs = kwargs

    class FakeMediaPipe:
        class solutions:
            class hands:
                Hands = FakeHands

    settings = GestureSettings(
        min_detection_confidence=0.62,
        min_tracking_confidence=0.68,
    )
    _LegacyHandsDetector(FakeMediaPipe(), settings)

    assert FakeHands.kwargs["min_detection_confidence"] == 0.62
    assert FakeHands.kwargs["min_tracking_confidence"] == 0.68


def test_tasks_detector_reports_missing_model(monkeypatch):
    messages = []
    monkeypatch.setattr("gesture.camera_worker._hand_landmarker_model_path", lambda: __import__("pathlib").Path("missing.task"))

    detector, connections = _create_tasks_detector(object(), CameraWorker().settings, messages.append)

    assert detector is None
    assert connections is None
    assert messages == ["缺少手部模型：resources/models/hand_landmarker.task"]


def test_worker_recovers_after_one_transient_camera_read_failure(monkeypatch):
    import numpy as np

    worker = CameraWorker()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    class IntermittentCapture:
        def __init__(self):
            self.read_calls = 0
            self.released = False

        def read(self):
            self.read_calls += 1
            if self.read_calls == 2:
                return False, None
            if self.read_calls == 3:
                worker.stop()
            return True, frame.copy()

        def set(self, *_args):
            return True

        def release(self):
            self.released = True

    class Detector:
        def __init__(self):
            self.detect_calls = 0
            self.closed = False

        def detect(self, _rgb, _timestamp_ms):
            self.detect_calls += 1
            return []

        def close(self):
            self.closed = True

    capture = IntermittentCapture()
    detector = Detector()
    monkeypatch.setattr(worker, "_open_capture", lambda _cv2: (capture, "摄像头已连接"))
    monkeypatch.setattr(worker, "_create_hand_detector", lambda: (detector, []))

    worker.run()

    assert capture.read_calls == 3
    assert detector.detect_calls == 2
    assert capture.released is True
    assert detector.closed is True


def test_worker_recovers_after_one_transient_detector_failure(monkeypatch):
    import numpy as np

    worker = CameraWorker()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    class Capture:
        def __init__(self):
            self.read_calls = 0

        def read(self):
            self.read_calls += 1
            if self.read_calls == 3:
                worker.stop()
            return True, frame.copy()

        def set(self, *_args):
            return True

        def release(self):
            pass

    class IntermittentDetector:
        def __init__(self):
            self.detect_calls = 0
            self.closed = False

        def detect(self, _rgb, _timestamp_ms):
            self.detect_calls += 1
            if self.detect_calls == 2:
                raise RuntimeError("transient detector error")
            return []

        def close(self):
            self.closed = True

    capture = Capture()
    detector = IntermittentDetector()
    monkeypatch.setattr(worker, "_open_capture", lambda _cv2: (capture, "摄像头已连接"))
    monkeypatch.setattr(worker, "_create_hand_detector", lambda: (detector, []))

    worker.run()

    assert capture.read_calls == 3
    assert detector.detect_calls == 3
    assert detector.closed is True


def test_worker_survives_long_stream_with_periodic_capture_and_detector_failures(monkeypatch):
    import numpy as np

    settings = GestureSettings(
        capture_width=64,
        capture_height=36,
        inference_width=64,
        inference_height=36,
        preview_width=32,
        preview_height=18,
        preview_fps=1,
        camera_read_retry_delay_ms=0,
    )
    worker = CameraWorker(settings)
    frame = np.zeros((36, 64, 3), dtype=np.uint8)

    class Capture:
        def __init__(self):
            self.read_calls = 0
            self.released = False

        def read(self):
            self.read_calls += 1
            if self.read_calls == 1000:
                worker.stop()
            if self.read_calls % 73 == 0:
                return False, None
            return True, frame.copy()

        def set(self, *_args):
            return True

        def release(self):
            self.released = True

    class Detector:
        def __init__(self):
            self.detect_calls = 0
            self.closed = False

        def detect(self, _rgb, _timestamp_ms):
            self.detect_calls += 1
            if self.detect_calls % 113 == 0:
                raise RuntimeError("periodic detector error")
            return []

        def close(self):
            self.closed = True

    capture = Capture()
    detector = Detector()
    monkeypatch.setattr(worker, "_open_capture", lambda _cv2: (capture, "摄像头已连接"))
    monkeypatch.setattr(worker, "_create_hand_detector", lambda: (detector, []))

    worker.run()

    assert capture.read_calls == 1000
    assert detector.detect_calls > 950
    assert capture.released is True
    assert detector.closed is True
