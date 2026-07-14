import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QAbstractAnimation, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QKeySequence, QPixmap, QWheelEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QListWidget, QSplitter, QToolBar

from app.main_window import MainWindow
from app.theme import STAGE_GRADIENT_BOTTOM, STAGE_GRADIENT_CENTER, STAGE_GRADIENT_TOP
from models.slide_project import SlidePage, SlideProject
from widgets.cylinder_carousel import CylinderCarousel
from widgets.cylinder_geometry import CarouselLayer
from widgets.slide_viewer import SlideViewer, classify_release
from widgets.stage_recomposition_overlay import StageRecompositionOverlay
from widgets.stage_workspace import StageWorkspace
from widgets.thumbnail_panel import ThumbnailPanel


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


def test_carousel_uses_denser_responsive_stage(qapp, pages):
    """桌面窗口中央页应接近舞台高度三分之二，并保留相邻页。"""
    carousel = CylinderCarousel()
    carousel.resize(1440, 900)
    carousel.show()
    carousel.set_pages(pages, current_index=1)
    qapp.processEvents()

    root = carousel._items[1].root
    center = root.mapRectToScene(root.rect())
    assert center.height() == pytest.approx(603.0, abs=2.0)
    assert center.width() == pytest.approx(1072.0, abs=2.0)
    assert center.center().y() == pytest.approx(446.0, abs=2.0)
    assert carousel._items[0].root.isVisible()
    assert carousel._items[2].root.isVisible()
    carousel.close()



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


def test_zoomed_horizontal_release_still_changes_page():
    """放大后长距离水平拖动仍应切页。"""
    assert classify_release(-160, 10, fit_mode=False) == "next"
    assert classify_release(160, -10, fit_mode=False) == "previous"


def test_zoomed_viewer_horizontal_drag_requests_next_page(qapp, pages):
    """真实放大页面拖动路径必须发出下一页请求。"""
    viewer = SlideViewer()
    viewer.resize(800, 600)
    viewer.show()
    viewer.show_image(pages[0].image_path)
    viewer.change_zoom(0.5)
    next_spy = QSignalSpy(viewer.next_requested)
    start = viewer.viewport().rect().center() + QPoint(120, 0)
    end = viewer.viewport().rect().center() - QPoint(120, 0)

    QTest.mousePress(viewer.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(viewer.viewport(), end)
    QTest.mouseRelease(viewer.viewport(), Qt.MouseButton.LeftButton, pos=end)

    assert next_spy.count() == 1
    viewer.close()


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


def test_preview_viewer_click_is_idle_and_double_click_requests_slideshow(qapp, pages):
    """预览页单击不翻页，双击只请求进入放映。"""
    viewer = SlideViewer()
    viewer.resize(800, 600)
    viewer.show()
    viewer.show_image(pages[0].image_path)
    viewer.set_interaction_mode("preview")
    next_spy = QSignalSpy(viewer.next_requested)
    double_spy = QSignalSpy(viewer.double_clicked)

    QTest.mouseClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert next_spy.count() == 0

    QTest.mouseDClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    QTest.qWait(QApplication.doubleClickInterval() + 20)
    assert double_spy.count() == 1
    assert next_spy.count() == 0
    viewer.close()


def test_slideshow_single_click_advances_immediately(qapp, pages):
    """放映单击必须在释放时立即发出翻页请求。"""
    viewer = SlideViewer()
    viewer.resize(800, 600)
    viewer.show()
    viewer.show_image(pages[0].image_path)
    viewer.set_interaction_mode("slideshow")
    next_spy = QSignalSpy(viewer.next_requested)

    QTest.mouseClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    assert next_spy.count() == 1
    viewer.close()


def test_slideshow_double_click_reports_immediate_click_and_toggle(qapp, pages):
    """查看器立即报告首次单击，再报告双击供主窗口回滚页码。"""
    viewer = SlideViewer()
    viewer.resize(800, 600)
    viewer.show()
    viewer.show_image(pages[0].image_path)
    viewer.set_interaction_mode("slideshow")
    next_spy = QSignalSpy(viewer.next_requested)
    double_spy = QSignalSpy(viewer.double_clicked)

    QTest.mouseClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    QTest.mouseDClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    assert double_spy.count() == 1
    assert next_spy.count() == 1
    viewer.close()


def test_thumbnail_panel_can_select_page_without_reemitting(qapp, pages):
    """主窗口同步缩略图时不能递归触发页面选择。"""
    panel = ThumbnailPanel()
    panel.set_pages(pages)
    selected = QSignalSpy(panel.page_selected)

    panel.select_page(2, emit=False)

    assert panel.currentRow() == 2
    assert selected.count() == 0


def test_thumbnail_panel_keeps_page_numbers_visible(qapp, pages):
    """缩略图和两位页码应同时容纳在预览栏内。"""
    panel = ThumbnailPanel()
    panel.set_pages(pages)

    assert panel.iconSize().width() <= 168
    assert panel.viewMode() == QListWidget.ViewMode.IconMode
    assert panel.item(2).text() == "03"


def test_preview_workspace_builds_normal_view_and_exposes_import(qapp, pages):
    """预览工作区包含缩略图、只读主页面和明确导入入口。"""
    from widgets.ppt_preview_workspace import PptPreviewWorkspace

    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    preview = PptPreviewWorkspace()
    preview.resize(1200, 760)
    preview.set_project(project, current_index=1)
    preview.show()
    qapp.processEvents()

    assert preview.thumbnail_panel.count() == len(pages)
    assert preview.thumbnail_panel.currentRow() == 1
    assert preview.import_button.text() == "导入 PPT"
    assert preview.import_button.isVisible()
    assert preview.viewer.interaction_mode == "preview"
    assert preview.page_label.text() == f"幻灯片 2 / {len(pages)}"
    preview.close()


def test_preview_workspace_emits_user_page_and_slideshow_requests(qapp, pages):
    """缩略图选择与中央页双击通过清晰信号交给主窗口。"""
    from widgets.ppt_preview_workspace import PptPreviewWorkspace

    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    preview = PptPreviewWorkspace()
    preview.resize(1200, 760)
    preview.set_project(project, current_index=0)
    preview.show()
    qapp.processEvents()
    page_spy = QSignalSpy(preview.page_selected)
    slideshow_spy = QSignalSpy(preview.slideshow_requested)

    preview.thumbnail_panel.setCurrentRow(2)
    QTest.mouseDClick(preview.viewer.viewport(), Qt.MouseButton.LeftButton)

    assert page_spy.count() == 1
    assert page_spy.at(0) == [2]
    assert slideshow_spy.count() == 1
    preview.close()


def test_preview_layout_keeps_thumbnail_pane_bounded(qapp, pages):
    """较小桌面窗口仍应保留稳定缩略图宽度和足够的主页面空间。"""
    from widgets.ppt_preview_workspace import PptPreviewWorkspace

    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    preview = PptPreviewWorkspace()
    preview.resize(1024, 768)
    preview.set_project(project, current_index=0)
    preview.show()
    qapp.processEvents()

    thumbnail_width = preview.thumbnail_panel.width()
    assert preview.MIN_THUMBNAIL_WIDTH <= thumbnail_width <= preview.MAX_THUMBNAIL_WIDTH
    assert preview.viewer.viewport().width() > thumbnail_width * 2
    preview.close()



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


def test_main_window_import_defaults_to_ppt_preview_mode(qapp, monkeypatch, tmp_path, pages):
    """主窗口导入完成后默认显示带缩略图和导入按钮的预览界面。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    qapp.processEvents()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()
    assert window.presentation_mode == "ppt"
    assert window.ppt_view_mode == "preview"
    assert window.workspace.mode == "stage"
    assert window.content_stack.currentWidget() is window.preview_workspace
    assert window.preview_workspace.import_button.isVisible()
    assert window.mode_button.toolTip() == "进入手势模式"
    assert window.top_bar.isHidden()
    assert window.bottom_bar.isHidden()
    window.close()


def test_preview_and_slideshow_double_click_toggle_without_page_change(qapp, monkeypatch, tmp_path, pages):
    """中央页双击双向切换预览和放映，并保持当前页。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    window.select_page(1)
    qapp.processEvents()

    QTest.mouseDClick(window.preview_workspace.viewer.viewport(), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert window.ppt_view_mode == "slideshow"
    assert window.content_stack.currentWidget() is window.workspace

    QTest.mouseClick(window.workspace.viewer.viewport(), Qt.MouseButton.LeftButton)
    QTest.mouseDClick(window.workspace.viewer.viewport(), Qt.MouseButton.LeftButton)
    QTest.qWait(QApplication.doubleClickInterval() + 20)
    assert window.ppt_view_mode == "preview"
    assert window.state.current_page == 1
    assert window.workspace.current_index == 1
    window.close()


def test_preview_and_stage_keep_current_page_synchronized(qapp, monkeypatch, tmp_path, pages):
    """缩略图和舞台切页都同步到同一个当前页。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    window.preview_workspace.thumbnail_panel.setCurrentRow(2)
    assert window.workspace.current_index == 2
    assert window.state.current_page == 2

    window.workspace.select_page(1)
    assert window.preview_workspace.current_index == 1
    assert window.preview_workspace.thumbnail_panel.currentRow() == 1
    assert window.state.current_page == 1
    window.close()


def test_mode_shortcut_toggles_gesture_and_powerpoint_modes(qapp, monkeypatch, tmp_path, pages):
    """同一快捷键进入手势模式，也能返回最近的 PPT 子模式。"""
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
    assert window.ppt_view_mode == "preview"
    assert window.workspace.mode == "stage"
    assert window.content_stack.currentWidget() is window.preview_workspace
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
    window.set_ppt_view_mode("slideshow")
    window.toggle_presentation_mode_action.trigger()
    window.workspace.carousel.activate_page(window.workspace.current_index)
    qapp.processEvents()

    window.toggle_presentation_mode_action.trigger()
    qapp.processEvents()

    assert window.presentation_mode == "ppt"
    assert window.ppt_view_mode == "slideshow"
    assert window.workspace.mode == "stage"
    assert window.content_stack.currentWidget() is window.workspace
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
    window.set_ppt_view_mode("slideshow")
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
    window.set_ppt_view_mode("slideshow")
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
    window.set_ppt_view_mode("slideshow")
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
    window.set_ppt_view_mode("slideshow")
    qapp.processEvents()

    QTest.keyClicks(window, "3")
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert window.workspace.current_index == 2
    QTest.keyClicks(window, "99")
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert window.workspace.current_index == 2
    window.close()


def test_escape_in_slideshow_returns_to_preview(qapp, monkeypatch, tmp_path, pages):
    """PPT 放映按 Esc 返回预览，不进入手势模式。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    window.set_ppt_view_mode("slideshow")
    qapp.processEvents()

    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert window.presentation_mode == "ppt"
    assert window.ppt_view_mode == "preview"
    assert window.content_stack.currentWidget() is window.preview_workspace
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


def test_recomposition_overlay_matches_carousel_center_geometry(qapp, tmp_path):
    """重组转场的中央页目标应与真实滚筒使用相同紧凑尺寸。"""
    image_path = tmp_path / "slide.png"
    Image.new("RGB", (1600, 900), "#FFFFFF").save(image_path)
    overlay = StageRecompositionOverlay()
    overlay.resize(1440, 900)
    pixmap = QPixmap(str(image_path))
    center_layer = CarouselLayer(0, 0, 0.0, 1.0, 1.0, 1.0, 100.0)

    rect = overlay._carousel_rect(center_layer, pixmap)

    assert rect.width() == pytest.approx(1072.0, abs=2.0)
    assert rect.height() == pytest.approx(603.0, abs=2.0)
    assert rect.center().y() == pytest.approx(446.0, abs=2.0)


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


def test_main_window_keeps_sidebar_in_preview_only(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    assert isinstance(window.workspace, StageWorkspace)
    assert window.findChildren(QSplitter) == [window.preview_workspace.splitter]
    assert window.workspace.findChildren(QSplitter) == []
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
