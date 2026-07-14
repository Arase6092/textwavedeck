import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.theme import (
    BOTTOM_CHROME_HEIGHT,
    FOCUS_BLUE,
    STAGE_BACKGROUND,
    STAGE_GRADIENT_BOTTOM,
    STAGE_GRADIENT_CENTER,
    STAGE_GRADIENT_TOP,
    STAGE_SAFE_MARGIN,
    application_stylesheet,
    line_icon,
    stage_background_qss,
    reduced_motion_enabled,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_dark_theme_exposes_approved_tokens():
    assert STAGE_BACKGROUND == "#07080B"
    assert FOCUS_BLUE == "#3B6FFF"
    stylesheet = application_stylesheet()
    assert STAGE_GRADIENT_TOP in stylesheet
    assert STAGE_GRADIENT_CENTER in stylesheet
    assert STAGE_GRADIENT_BOTTOM in stylesheet
    assert "#3B6FFF" in stylesheet
    assert "qlineargradient" in stage_background_qss()
    assert "Segoe UI Variable" in stylesheet


def test_chrome_children_are_transparent_and_stage_clears_bottom_bar():
    stylesheet = application_stylesheet()
    assert "QWidget#chromeGroup" in stylesheet
    assert STAGE_SAFE_MARGIN >= BOTTOM_CHROME_HEIGHT


@pytest.mark.parametrize("name", ["open", "grid", "fullscreen"])
def test_line_icons_keep_transparent_space(qapp, name):
    image = line_icon(name).pixmap(18, 18).toImage()
    opaque = sum(image.pixelColor(x, y).alpha() > 0 for y in range(image.height()) for x in range(image.width()))
    assert 10 < opaque < 180


def test_reduced_motion_can_be_forced_by_environment(monkeypatch):
    monkeypatch.setenv("GESTURE_PPT_REDUCED_MOTION", "1")
    assert reduced_motion_enabled()
    monkeypatch.setenv("GESTURE_PPT_REDUCED_MOTION", "0")
    assert not reduced_motion_enabled()
