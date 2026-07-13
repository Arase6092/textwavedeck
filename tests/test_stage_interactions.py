import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from models.slide_project import SlidePage
from widgets.cylinder_carousel import CylinderCarousel


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
