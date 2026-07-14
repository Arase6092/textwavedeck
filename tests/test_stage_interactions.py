import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QAbstractAnimation, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QKeySequence, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSplitter, QToolBar

from app.main_window import MainWindow
from app.theme import STAGE_GRADIENT_BOTTOM, STAGE_GRADIENT_CENTER, STAGE_GRADIENT_TOP
from models.slide_project import SlidePage, SlideProject
from widgets.cylinder_carousel import CylinderCarousel
from widgets.slide_viewer import SlideViewer, classify_release
from widgets.stage_workspace import StageWorkspace


def _send_wheel(viewer: SlideViewer, delta: int) -> None:
    """向查看器视口发送真实滚轮事件。"""
    position = QPointF(viewer.viewport().rect().center())
    event = QWheelEvent(
        position,
        QPointF(viewer.viewport().mapToGlobal(position.toPoint())),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(viewer.viewport(), event)


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


def test_carousel_exposes_five_target_layers(qapp, pages):
    """滚筒暴露稳定的五页目标布局，供重组转场复用。"""
    carousel = CylinderCarousel()
    carousel.resize(1200, 720)
    carousel.set_pages(pages * 3, current_index=4)
    layers = carousel.target_layers(4)
    assert [layer.index for layer in layers] == [2, 3, 4, 5, 6]
    assert layers[2].relative == 0
    assert layers[2].opacity == 1.0
    assert layers[0].opacity < layers[1].opacity < layers[2].opacity
    assert layers[4].opacity < layers[3].opacity < layers[2].opacity



def test_carousel_background_has_no_horizontal_reference_line(qapp):
    class FakePainter:
        """记录背景绘制调用，确保舞台中线不会回归。"""

        def __init__(self):
            self.fill_calls = 0
            self.line_calls = 0

        def fillRect(self, *_args):
            self.fill_calls += 1

        def drawLine(self, *_args):
            self.line_calls += 1

    carousel = CylinderCarousel()
    painter = FakePainter()
    carousel.drawBackground(painter, QRectF(0, 0, 800, 520))
    assert painter.fill_calls == 1
    assert painter.line_calls == 0

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


def test_viewer_can_match_powerpoint_slide_show_frame(qapp, tmp_path):
    """PPT 模式下 16:9 页面应像放映一样贴合 16:9 窗口。"""
    image_path = tmp_path / "slide.png"
    Image.new("RGB", (1600, 900), "#FFFFFF").save(image_path)
    viewer = SlideViewer()
    viewer.resize(1600, 900)
    viewer.set_fit_margin(0)
    viewer.show()
    viewer.show_image(str(image_path))
    qapp.processEvents()
    bounds = viewer.mapFromScene(viewer._pixmap_item.boundingRect()).boundingRect()
    assert bounds.left() <= 2
    assert bounds.top() <= 2
    assert bounds.right() >= viewer.viewport().width() - 2
    assert bounds.bottom() >= viewer.viewport().height() - 2
    viewer.close()



def test_workspace_can_start_in_single_slide_stage(qapp, pages):
    """导入后可直接进入普通单页放映，而不是先显示滚筒。"""
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_project(project, current_index=1, initial_mode="stage")
    workspace.show()
    qapp.processEvents()
    assert workspace.mode == "stage"
    assert workspace.current_index == 1
    assert workspace.viewer.isVisible()
    assert workspace._transition.state() == QAbstractAnimation.State.Stopped


def test_main_window_import_defaults_to_single_slide_stage(qapp, monkeypatch, tmp_path, pages):
    """主窗口导入完成后默认是普通放映界面。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    qapp.processEvents()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()
    assert window.presentation_mode == "ppt"
    assert window.workspace.mode == "stage"
    assert window.mode_button.toolTip() == "进入手势模式"
    assert window.top_bar.isHidden()
    assert window.bottom_bar.isHidden()
    window.close()


def test_mode_shortcut_toggles_gesture_and_powerpoint_modes(qapp, monkeypatch, tmp_path, pages):
    """同一快捷键进入手势模式，也能返回纯 PPT 放映模式。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    window.toggle_presentation_mode_action.trigger()
    qapp.processEvents()
    assert window.presentation_mode == "gesture"
    assert window.workspace.mode == "carousel"
    assert window.mode_button.toolTip() == "返回PPT模式"
    assert not window.top_bar.isHidden()

    window.toggle_presentation_mode_action.trigger()
    qapp.processEvents()
    assert window.presentation_mode == "ppt"
    assert window.workspace.mode == "stage"
    assert window.mode_button.toolTip() == "进入手势模式"
    assert window.top_bar.isHidden()
    assert window.bottom_bar.isHidden()
    window.close()


def test_gesture_mode_center_page_opens_gesture_stage(qapp, monkeypatch, tmp_path, pages):
    """手势滚筒中央页应进入原有单页舞台，并保留缩放控制。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    window.toggle_presentation_mode_action.trigger()
    qapp.processEvents()

    window.workspace.carousel.activate_page(window.workspace.current_index)
    qapp.processEvents()

    assert window.presentation_mode == "gesture"
    assert window.workspace.mode == "stage"
    assert window.zoom_in_action.isEnabled()
    assert all(not widget.isHidden() for widget in window.zoom_widgets)
    assert not window.top_bar.isHidden()
    window.close()


def test_escape_returns_gesture_stage_to_carousel(qapp, monkeypatch, tmp_path, pages):
    """手势单页舞台按 Esc 应返回滚筒，不触发 PPT 模式逻辑。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    window.toggle_presentation_mode_action.trigger()
    window.workspace.carousel.activate_page(window.workspace.current_index)
    qapp.processEvents()

    QTest.keyClick(window, Qt.Key.Key_Escape)

    assert window.presentation_mode == "gesture"
    assert window.workspace.mode == "carousel"
    window.close()


def test_mode_shortcut_returns_from_gesture_stage_to_powerpoint(qapp, monkeypatch, tmp_path, pages):
    """在手势单页舞台中也能用同一快捷键返回 PPT 模式。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    window.toggle_presentation_mode_action.trigger()
    window.workspace.carousel.activate_page(window.workspace.current_index)
    qapp.processEvents()

    window.toggle_presentation_mode_action.trigger()
    qapp.processEvents()

    assert window.presentation_mode == "ppt"
    assert window.workspace.mode == "stage"
    assert window.top_bar.isHidden()
    assert window.bottom_bar.isHidden()
    window.close()


def test_powerpoint_mode_uses_slide_show_keyboard_navigation(qapp, monkeypatch, tmp_path, pages):
    """PPT 模式对齐 PowerPoint Slide Show 的常用翻页键。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    QTest.keyClick(window, Qt.Key.Key_N)
    assert window.workspace.current_index == 1
    QTest.keyClick(window, Qt.Key.Key_P)
    assert window.workspace.current_index == 0
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert window.workspace.current_index == 1
    QTest.keyClick(window, Qt.Key.Key_Backspace)
    assert window.workspace.current_index == 0
    QTest.keyClick(window, Qt.Key.Key_End)
    assert window.workspace.current_index == len(pages) - 1
    QTest.keyClick(window, Qt.Key.Key_Home)
    assert window.workspace.current_index == 0
    window.close()


def test_powerpoint_mode_left_click_advances_slide(qapp, monkeypatch, tmp_path, pages):
    """PPT 放映中左键单击应像 PowerPoint 一样前进一页。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    QTest.mouseClick(window.workspace.viewer.viewport(), Qt.MouseButton.LeftButton)

    assert window.workspace.current_index == 1
    assert window.workspace.zoom_factor == pytest.approx(1.0)
    window.close()


def test_powerpoint_mode_wheel_navigates_without_zoom(qapp, monkeypatch, tmp_path, pages):
    """PPT 放映滚轮应翻页，不能沿用手势单页的缩放行为。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    _send_wheel(window.workspace.viewer, -120)

    assert window.workspace.current_index == 1
    assert window.workspace.zoom_factor == pytest.approx(1.0)
    window.close()


def test_gesture_stage_wheel_still_zooms(qapp, monkeypatch, tmp_path, pages):
    """手势单页舞台滚轮仍应缩放，不能被 PPT 鼠标策略覆盖。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.workspace.set_reduced_motion(True)
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    window.toggle_presentation_mode_action.trigger()
    window.workspace.carousel.activate_page(window.workspace.current_index)
    qapp.processEvents()

    _send_wheel(window.workspace.viewer, -120)

    assert window.workspace.current_index == 0
    assert window.workspace.zoom_factor == pytest.approx(0.9)
    window.close()


def test_powerpoint_mode_number_enter_jumps_to_slide(qapp, monkeypatch, tmp_path, pages):
    """PPT 放映支持输入页码再按 Enter 跳转。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    QTest.keyClicks(window, "3")
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert window.workspace.current_index == 2
    QTest.keyClicks(window, "99")
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert window.workspace.current_index == 2
    window.close()


def test_escape_in_powerpoint_mode_does_not_enter_gesture_mode(qapp, monkeypatch, tmp_path, pages):
    """Esc 按 PowerPoint 习惯处理，不再把 PPT 模式切到手势模式。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert window.workspace.mode == "stage"
    assert window.workspace.current_index == 0
    window.close()


def test_hidden_mode_shortcut_is_ctrl_alt_m(qapp, monkeypatch, tmp_path):
    """隐藏模式快捷键固定为 Ctrl+Alt+M，避免占用翻页和系统常用键。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    assert window.toggle_presentation_mode_action.shortcut() == QKeySequence("Ctrl+Alt+M")
    window.close()

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


def test_workspace_uses_recomposition_overlay_for_mode_change(qapp, pages):
    """普通放映进入滚筒时显示重组 overlay，并启动可中断动画。"""
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.resize(1200, 720)
    workspace.set_project(project, current_index=1, initial_mode="stage")
    workspace.show()
    qapp.processEvents()
    workspace.show_carousel()
    assert workspace.mode == "carousel"
    assert workspace._overlay.isVisible()
    assert workspace._transition.state() == QAbstractAnimation.State.Running
    workspace._transition.stop()
    workspace._finish_mode_immediately("carousel")


def test_reduced_motion_skips_recomposition_overlay(qapp, pages):
    """减少动态模式不播放大幅空间重组。"""
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_reduced_motion(True)
    workspace.set_project(project, current_index=1, initial_mode="stage")
    workspace.show()
    qapp.processEvents()
    workspace.show_carousel()
    assert workspace.mode == "carousel"
    assert not workspace._overlay.isVisible()
    assert workspace._transition.state() == QAbstractAnimation.State.Stopped


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


def test_finished_import_reapplies_powerpoint_chrome_policy(qapp, monkeypatch, tmp_path, pages):
    """后台导入结束后应重新隐藏 PPT 模式控制层，并禁止边缘唤出。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._set_importing_ui(True)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    window._on_worker_finished()
    qapp.processEvents()

    assert window.presentation_mode == "ppt"
    assert window.top_bar.isHidden()
    assert window.bottom_bar.isHidden()
    window.chrome.reveal_for_position(0, window.height())
    assert window.top_bar.isHidden()
    window.close()
