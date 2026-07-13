import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QSplitter, QToolBar

from app.main_window import MainWindow
from models.slide_project import SlidePage, SlideProject
from widgets.cylinder_carousel import CylinderCarousel
from widgets.slide_viewer import classify_release
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


def test_carousel_only_decodes_visible_thumbnails(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages * 25, current_index=50)
    loaded = sum(not item.pixmap.pixmap().isNull() for item in carousel._items)
    assert loaded <= 7


def test_fit_mode_horizontal_release_requests_page_change():
    assert classify_release(-120, 10, fit_mode=True) == "next"
    assert classify_release(120, -8, fit_mode=True) == "previous"
    assert classify_release(20, 2, fit_mode=True) is None


def test_zoomed_release_never_changes_page():
    assert classify_release(-160, 10, fit_mode=False) is None


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
