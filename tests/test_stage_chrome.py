import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QWidget

from widgets.stage_chrome import StageChrome


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_chrome_widgets(qapp):
    host = QWidget()
    host.resize(640, 480)
    top = QFrame(host)
    bottom = QFrame(host)
    host.show()
    qapp.processEvents()
    return host, top, bottom


def test_chrome_hides_after_timeout(qapp):
    host, top, bottom = make_chrome_widgets(qapp)
    chrome = StageChrome(host, top, bottom, hide_delay_ms=20, fade_duration_ms=0)
    chrome.reveal_all(minimum_visible_ms=0)
    QTest.qWait(40)
    qapp.processEvents()
    assert top.isHidden()
    assert bottom.isHidden()
    chrome.dispose()
    host.close()


def test_visibility_lock_prevents_hiding(qapp):
    host, top, bottom = make_chrome_widgets(qapp)
    chrome = StageChrome(host, top, bottom, hide_delay_ms=20, fade_duration_ms=0)
    chrome.set_locked(True)
    chrome.hide_now()
    assert chrome.locked
    assert not top.isHidden()
    assert not bottom.isHidden()
    chrome.dispose()
    host.close()


def test_edge_zones_reveal_corresponding_bar(qapp):
    host, top, bottom = make_chrome_widgets(qapp)
    chrome = StageChrome(host, top, bottom, fade_duration_ms=0)
    chrome.hide_now()
    chrome.reveal_for_position(20, host.height())
    assert not top.isHidden()
    assert bottom.isHidden()
    chrome.hide_now()
    chrome.reveal_for_position(host.height() - 20, host.height())
    assert top.isHidden()
    assert not bottom.isHidden()
    chrome.dispose()
    host.close()
