from app.commands import NavigationState


def test_navigation_does_not_wrap_and_selects_valid_pages():
    state = NavigationState()
    state.set_page_count(3)
    assert not state.previous()
    assert state.next()
    assert state.current_page == 1
    assert state.select(2)
    assert not state.next()
    assert not state.select(3)


def test_zoom_is_clamped_and_reset():
    state = NavigationState(zoom=1.0)
    assert state.change_zoom(-10) == 0.25
    assert state.change_zoom(10) == 4.0
    state.reset_zoom()
    assert state.zoom == 1.0
