import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtWidgets import QApplication, QSplitter, QToolBar

from app.main_window import MainWindow
from app.theme import STAGE_GRADIENT_BOTTOM, STAGE_GRADIENT_CENTER, STAGE_GRADIENT_TOP
from models.slide_project import SlidePage, SlideProject
from widgets.cylinder_carousel import CylinderCarousel
from widgets.slide_viewer import SlideViewer, classify_release
from widgets.stage_workspace import StageWorkspace


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def pages(tmp_path):
    result = []
    for index in range(4):
        thumbnail = tmp_path / f"thumb_{index}.jpg"
        Image.new("RGB", (640, 360), (245 - index * 10, 247, 250)).save(thumbnail, "JPEG")
        result.append(SlidePage(index, str(thumbnail), str(thumbnail)))
    return result


def test_carousel_selects_and_clamps_pages(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages, current_index=1)
    assert carousel.current_index == 1
    carousel.select_page(99, animate=False)
    assert carousel.current_index == len(pages) - 1
    carousel.select_page(-2, animate=False)
    assert carousel.current_index == 0


def test_center_page_activation_emits_stage_request(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages, current_index=0)
    emitted = []
    carousel.stage_requested.connect(emitted.append)
    carousel.activate_page(2)
    assert emitted == []
    carousel.select_page(2, animate=False)
    carousel.activate_page(2)
    assert emitted == [2]


def test_carousel_only_decodes_five_visible_thumbnails(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages * 25, current_index=50)
    loaded = sum(not item.pixmap.pixmap().isNull() for item in carousel._items)
    assert loaded <= 5


def test_reduced_motion_selects_without_animation(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages, current_index=0)
    carousel.set_reduced_motion(True)
    carousel.select_page(2)
    assert carousel.current_index == 2
    assert carousel._animation.state() == QAbstractAnimation.State.Stopped


def test_fit_mode_horizontal_release_requests_page_change():
    assert classify_release(-120, 10, fit_mode=True) == "next"
    assert classify_release(120, -8, fit_mode=True) == "previous"
    assert classify_release(20, 2, fit_mode=True) is None


def test_zoomed_release_never_changes_page():
    assert classify_release(-160, 10, fit_mode=False) is None


def test_viewer_fit_keeps_dark_stage_margin(qapp, pages):
    viewer = SlideViewer()
    viewer.resize(800, 600)
    viewer.show()
    viewer.show_image(pages[0].image_path)
    qapp.processEvents()
    bounds = viewer.mapFromScene(viewer._pixmap_item.boundingRect()).boundingRect()
    assert bounds.left() >= 30
    assert bounds.right() <= viewer.viewport().width() - 30
    assert bounds.top() >= 30
    assert bounds.bottom() <= viewer.viewport().height() - 30
    viewer.close()


def test_workspace_propagates_reduced_motion(qapp):
    workspace = StageWorkspace()
    workspace.set_reduced_motion(True)
    assert workspace.reduced_motion
    assert workspace.carousel.reduced_motion


def test_workspace_animates_mode_change_when_motion_is_enabled(qapp, pages):
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_project(project, current_index=1)
    workspace.enter_stage(1)
    assert workspace.mode == "stage"
    assert workspace._transition.state() == QAbstractAnimation.State.Running
    workspace._transition.stop()


def test_workspace_preserves_page_when_returning_to_carousel(qapp, pages):
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_project(project, current_index=2)
    workspace.enter_stage(2)
    assert workspace.mode == "stage"
    workspace.show_carousel()
    assert workspace.current_index == 2
    assert workspace.mode == "carousel"


def test_workspace_navigation_does_not_wrap(qapp, pages):
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_project(project, current_index=0)
    assert not workspace.previous_page()
    assert workspace.next_page()
    assert workspace.current_index == 1


def test_main_window_uses_full_stage_without_sidebar_or_toolbar(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    assert isinstance(window.workspace, StageWorkspace)
    assert window.findChildren(QSplitter) == []
    assert window.findChildren(QToolBar) == []
    window.close()


def test_main_window_uses_overlay_dark_chrome(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert window.top_bar.parent() is window.stage_root
    assert window.bottom_bar.parent() is window.stage_root
    assert window.content_stack.geometry() == window.stage_root.rect()
    stylesheet = window.styleSheet()
    assert "qlineargradient" in stylesheet
    assert STAGE_GRADIENT_TOP in stylesheet
    assert STAGE_GRADIENT_CENTER in stylesheet
    assert STAGE_GRADIENT_BOTTOM in stylesheet
    assert all(widget.isHidden() for widget in window.zoom_widgets)
    window.close()


def test_import_locks_chrome_visible(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window._set_importing_ui(True)
    assert window.chrome.locked
    assert not window.bottom_bar.isHidden()
    window._set_importing_ui(False)
    assert not window.chrome.locked
    window.close()
