from app.theme import FOCUS_BLUE, STAGE_BACKGROUND, application_stylesheet, reduced_motion_enabled


def test_dark_theme_exposes_approved_tokens():
    assert STAGE_BACKGROUND == "#07080B"
    assert FOCUS_BLUE == "#3B6FFF"
    stylesheet = application_stylesheet()
    assert "#07080B" in stylesheet
    assert "#3B6FFF" in stylesheet
    assert "Segoe UI Variable" in stylesheet


def test_reduced_motion_can_be_forced_by_environment(monkeypatch):
    monkeypatch.setenv("GESTURE_PPT_REDUCED_MOTION", "1")
    assert reduced_motion_enabled()
    monkeypatch.setenv("GESTURE_PPT_REDUCED_MOTION", "0")
    assert not reduced_motion_enabled()
