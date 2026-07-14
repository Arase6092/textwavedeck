import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from app import theme
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
    stage_background_gradient,
    stage_background_qss,
    reduced_motion_enabled,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_dark_theme_exposes_approved_tokens():
    assert STAGE_BACKGROUND == "#080A0B"
    assert STAGE_GRADIENT_TOP == "#080A0B"
    assert theme.STAGE_GRADIENT_MID == "#111817"
    assert STAGE_GRADIENT_CENTER == "#18221F"
    assert STAGE_GRADIENT_BOTTOM == "#090B0E"
    assert FOCUS_BLUE == "#3B6FFF"
    stylesheet = application_stylesheet()
    for color in (
        STAGE_GRADIENT_TOP,
        theme.STAGE_GRADIENT_MID,
        STAGE_GRADIENT_CENTER,
        STAGE_GRADIENT_BOTTOM,
    ):
        assert color in stylesheet
    assert "#3B6FFF" in stylesheet
    assert "qlineargradient" in stage_background_qss()
    assert "stop: 0.35" in stage_background_qss()
    assert "stop: 0.64" in stage_background_qss()
    assert "Segoe UI Variable" in stylesheet


def test_painter_gradient_matches_qss_stops():
    """QPainter 与 QSS 必须使用同一组四段渐变。"""
    stops = stage_background_gradient(QRectF(0, 0, 100, 100)).stops()
    assert [position for position, _ in stops] == pytest.approx([0.0, 0.35, 0.64, 1.0])
    assert [color.name().upper() for _, color in stops] == [
        STAGE_GRADIENT_TOP,
        theme.STAGE_GRADIENT_MID,
        STAGE_GRADIENT_CENTER,
        STAGE_GRADIENT_BOTTOM,
    ]


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
