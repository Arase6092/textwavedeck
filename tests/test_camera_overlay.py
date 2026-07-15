import os
from threading import Event

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThread, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from widgets.camera_overlay import CameraPreviewWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class FinishedWorker:
    def __init__(self):
        self.deleted = False

    def deleteLater(self):
        self.deleted = True


class BurstWorker(QThread):
    frame_ready = Signal(object)
    hands_ready = Signal(list, int)
    status_changed = Signal(str)

    def __init__(self, _settings):
        super().__init__()
        self.running = False
        self.burst_done = Event()

    def run(self):
        self.running = True
        for timestamp_ms in range(500):
            self.hands_ready.emit([[timestamp_ms]], timestamp_ms)
            self.status_changed.emit(f"status-{timestamp_ms}")
        self.burst_done.set()
        while self.running:
            self.msleep(1)

    def stop(self):
        self.running = False


class CountingWorker(QThread):
    frame_ready = Signal(object)
    hands_ready = Signal(list, int)
    status_changed = Signal(str)
    created = 0

    def __init__(self, _settings):
        super().__init__()
        CountingWorker.created += 1
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            self.msleep(1)

    def stop(self):
        self.running = False

def test_unexpected_worker_finish_schedules_automatic_restart(qapp):
    window = CameraPreviewWindow()
    worker = FinishedWorker()
    window._worker = worker
    window._camera_requested = True
    window._received_frame = True

    window._on_worker_finished()

    assert worker.deleted is True
    assert window._worker is None
    assert window._restart_timer.isActive()
    assert window.status_label.text() == "手势服务中断，正在自动恢复… | idle"
    window._restart_timer.stop()
    window.close()


def test_user_stop_does_not_schedule_automatic_restart(qapp):
    window = CameraPreviewWindow()
    worker = FinishedWorker()
    window._worker = worker
    window._camera_requested = False

    window._on_worker_finished()

    assert worker.deleted is True
    assert window._worker is None
    assert not window._restart_timer.isActive()
    window.close()


def test_hands_burst_delivers_only_latest_result_without_ui_backlog(qapp, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("widgets.camera_overlay.CameraWorker", BurstWorker)
    window = CameraPreviewWindow()
    received = []
    statuses = []
    window.hands_ready.connect(lambda hands, timestamp_ms: received.append((hands, timestamp_ms)))
    window.status_changed.connect(statuses.append)

    window.start_camera()
    assert window._worker.burst_done.wait(1.0)
    QTest.qWait(30)

    assert received == [([[499]], 499)]
    assert statuses == ["status-499"]
    window.stop_camera()
    window.close()


def test_prewarmed_camera_is_reused_when_preview_is_shown(qapp, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("widgets.camera_overlay.CameraWorker", CountingWorker)
    CountingWorker.created = 0
    window = CameraPreviewWindow()

    window.prewarm_camera()
    QTest.qWait(20)
    worker = window._worker
    assert CountingWorker.created == 1
    assert worker is not None
    assert window.running
    assert not window.isVisible()

    window.start_camera()
    QTest.qWait(20)

    assert window._worker is worker
    assert CountingWorker.created == 1
    assert window.isVisible()
    window.stop_camera()
    window.close()


def test_hide_preview_keeps_prewarmed_camera_running(qapp, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("widgets.camera_overlay.CameraWorker", CountingWorker)
    CountingWorker.created = 0
    window = CameraPreviewWindow()

    window.prewarm_camera()
    QTest.qWait(20)
    worker = window._worker
    window.show()
    window.hide_preview_keep_warm()

    assert window._worker is worker
    assert window.running
    assert not window.isVisible()
    window.stop_camera()
    window.close()


def test_lock_status_is_not_overwritten_by_camera_hand_count(qapp):
    window = CameraPreviewWindow()

    window.set_gesture_control_status("手势已暂停，换成非握拳手势即可恢复")
    window.set_current_action("zoom_in")
    window._set_status("检测到 1 只手")
    assert window.status_label.text() == "手势已暂停，换成非握拳手势即可恢复 | zoom_in"

    window.set_gesture_control_status("手势已自动解锁")
    assert window.status_label.text() == "手势已自动解锁 | zoom_in"
    window.close()


def test_camera_status_bar_includes_current_action(qapp):
    window = CameraPreviewWindow()

    window._set_status("检测到 2 只手")
    window.set_current_action("zoom_out")

    assert window.status_label.text() == "检测到 2 只手 | zoom_out"
    window.close()
