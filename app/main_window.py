"""黑匣子剧场主窗口和 Qt 命令绑定。"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.commands import NavigationState
from app.theme import STAGE_SAFE_MARGIN, application_stylesheet, line_icon, reduced_motion_enabled
from app.workers import ImportWorker
from gesture.controller import GestureController
from gesture.diagnostics import GestureRuntimeDiagnostics, diagnostics_enabled
from gesture.settings import GestureSettings
from models.slide_project import SlideProject
from ppt.importer import PPTImporter
from ppt.project_store import project_dir, save_project
from widgets.camera_overlay import CameraPreviewWindow
from widgets.ppt_preview_workspace import PptPreviewWorkspace
from widgets.stage_chrome import StageChrome
from widgets.stage_workspace import StageWorkspace


class MainWindow(QMainWindow):
    """以暗场滚筒和自动隐藏覆盖层为主体的浏览窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Gesture PPT · 页面舞台")
        self.resize(1440, 900)
        self.setMinimumSize(980, 620)
        self.state = NavigationState()
        self.project: SlideProject | None = None
        self.worker: ImportWorker | None = None
        self.importer = PPTImporter()
        self.reduced_motion = reduced_motion_enabled()
        self._importing = False
        self._presentation_mode = "ppt"
        self._ppt_view_mode = "preview"
        self._slideshow_click_origin: int | None = None
        self._slide_number_buffer = ""
        self.gesture_settings = GestureSettings()
        self.gesture_controller = GestureController(self, self.gesture_settings)
        self.gesture_controller.status_changed.connect(self._on_gesture_status_changed)
        self.camera_preview = CameraPreviewWindow(self.gesture_settings)
        self.gesture_controller.status_changed.connect(
            self.camera_preview.set_gesture_control_status
        )
        self.gesture_controller.action_changed.connect(self.camera_preview.set_current_action)
        self.camera_preview.hands_ready.connect(self.gesture_controller.process_hands)
        self.camera_preview.status_changed.connect(self._on_gesture_status_changed)
        self._build_ui()
        self.gesture_diagnostics = GestureRuntimeDiagnostics(
            self,
            self.camera_preview,
            self.gesture_controller,
        )
        if diagnostics_enabled():
            self.gesture_diagnostics.start()
        self._restore_last_project()

    @property
    def presentation_mode(self) -> str:
        """返回顶层 PPT/手势模式，不混用工作区内部视图状态。"""
        return self._presentation_mode

    @property
    def ppt_view_mode(self) -> str:
        """返回 PPT 模式内部的预览/放映子状态。"""
        return self._ppt_view_mode

    def _build_ui(self) -> None:
        """构建完整暗场、舞台内容和覆盖式控制层。"""
        self.setStyleSheet(application_stylesheet())
        self._create_actions()

        self.stage_root = QWidget()
        self.stage_root.setObjectName("stageRoot")
        root_layout = QVBoxLayout(self.stage_root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.content_stack = self._create_content()
        root_layout.addWidget(self.content_stack)
        self.setCentralWidget(self.stage_root)

        self.top_bar = self._create_top_bar(self.stage_root)
        self.bottom_bar = self._create_bottom_bar(self.stage_root)
        self.chrome = StageChrome(
            self.stage_root,
            self.top_bar,
            self.bottom_bar,
            reduced_motion=self.reduced_motion,
        )
        self.workspace.set_reduced_motion(self.reduced_motion)
        self._set_project_controls_enabled(False)
        for widget in self.zoom_widgets:
            widget.hide()
        self._update_project_name()

    def _create_actions(self) -> None:
        """创建快捷键和覆盖层按钮共享的命令。"""
        self.open_action = QAction("打开", self)
        self.open_action.setIcon(line_icon("open"))
        self.open_action.setToolTip("打开 PPT（Ctrl+O）")
        self.open_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_action.triggered.connect(self.open_file)

        self.previous_action = QAction("上一页", self)
        self.previous_action.setShortcut(QKeySequence("PageUp"))
        self.previous_action.triggered.connect(self.previous_page)

        self.next_action = QAction("下一页", self)
        self.next_action.setShortcut(QKeySequence("PageDown"))
        self.next_action.triggered.connect(self.next_page)

        self.fullscreen_action = QAction("全屏", self)
        self.fullscreen_action.setIcon(line_icon("fullscreen"))
        self.fullscreen_action.setToolTip("进入或退出全屏（F11）")
        self.fullscreen_action.setShortcut(QKeySequence("F11"))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.toggle_presentation_mode_action = QAction("切换页面滚筒", self)
        self.toggle_presentation_mode_action.setToolTip("切换 PPT 模式/手势模式（Ctrl+Alt+M）")
        self.toggle_presentation_mode_action.setShortcut(QKeySequence("Ctrl+Alt+M"))
        self.toggle_presentation_mode_action.triggered.connect(self.toggle_workspace_mode)
        self.zoom_out_action = QAction("-", self)
        self.zoom_out_action.setToolTip("缩小")
        self.zoom_out_action.triggered.connect(lambda: self.change_zoom(-0.1))
        self.reset_action = QAction("100%", self)
        self.reset_action.setToolTip("显示原始比例")
        self.reset_action.triggered.connect(self.reset_zoom)
        self.zoom_in_action = QAction("+", self)
        self.zoom_in_action.setToolTip("放大")
        self.zoom_in_action.triggered.connect(lambda: self.change_zoom(0.1))
        self.fit_action = QAction("适应", self)
        self.fit_action.setToolTip("适应窗口")
        self.fit_action.triggered.connect(self.fit_view)

        for action in (
            self.open_action,
            self.previous_action,
            self.next_action,
            self.fullscreen_action,
            self.toggle_presentation_mode_action,
            self.zoom_out_action,
            self.reset_action,
            self.zoom_in_action,
            self.fit_action,
        ):
            self.addAction(action)

    def _action_button(self, action: QAction, *, text: bool = False) -> QToolButton:
        button = QToolButton()
        button.setDefaultAction(action)
        button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly if text else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        button.setFixedHeight(40)
        button.setFixedWidth(68 if text else 40)
        return button

    def _create_top_bar(self, parent: QWidget) -> QFrame:
        """创建文件信息、固定页码和模式按钮。"""
        bar = QFrame(parent)
        bar.setObjectName("topChrome")
        layout = QGridLayout(bar)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setHorizontalSpacing(8)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)

        left = QWidget(bar)
        left.setObjectName("chromeGroup")
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        self.open_button = self._action_button(self.open_action)
        left_layout.addWidget(self.open_button)
        self.file_label = QLabel("未打开项目")
        self.file_label.setObjectName("fileName")
        self.file_label.setMaximumWidth(380)
        left_layout.addWidget(self.file_label)
        left_layout.addStretch(1)
        layout.addWidget(left, 0, 0)

        self.folio = QLabel("00 / 00")
        self.folio.setObjectName("folio")
        self.folio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.folio.setFixedWidth(150)
        layout.addWidget(self.folio, 0, 1)

        right = QWidget(bar)
        right.setObjectName("chromeGroup")
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        right_layout.addStretch(1)
        self.mode_button = QToolButton()
        self.mode_button.setFixedSize(40, 40)
        self.mode_button.setIcon(line_icon("stage"))
        self.mode_button.setToolTip("进入手势模式")
        self.mode_button.clicked.connect(self.toggle_workspace_mode)
        right_layout.addWidget(self.mode_button)
        right_layout.addWidget(self._action_button(self.fullscreen_action))
        layout.addWidget(right, 0, 2)
        return bar

    def _create_bottom_bar(self, parent: QWidget) -> QFrame:
        """创建页面进度、导入状态和单页缩放控制。"""
        bar = QFrame(parent)
        bar.setObjectName("bottomChrome")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        self.status_label = QLabel("未打开项目")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumWidth(110)
        self.status_label.setMaximumWidth(260)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progress.hide()
        layout.addWidget(self.progress, 1)

        self.zoom_widgets: list[QWidget] = []
        for widget in (
            self._action_button(self.zoom_out_action),
            self._action_button(self.reset_action, text=True),
            self._action_button(self.zoom_in_action),
            self._action_button(self.fit_action, text=True),
        ):
            self.zoom_widgets.append(widget)
            layout.addWidget(widget)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(64, 40)
        self.cancel_button.clicked.connect(self.cancel_import)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)
        return bar

    def _create_content(self) -> QStackedWidget:
        """创建空状态和整窗舞台。"""
        self.preview_workspace = PptPreviewWorkspace()
        self.preview_workspace.page_selected.connect(self._on_preview_page_selected)
        self.preview_workspace.import_requested.connect(self.open_file)
        self.preview_workspace.slideshow_requested.connect(
            lambda: self.set_ppt_view_mode("slideshow")
        )

        self.workspace = StageWorkspace()
        self.workspace.page_changed.connect(self._on_workspace_page_changed)
        self.workspace.mode_changed.connect(self._on_workspace_mode_changed)
        self.workspace.zoom_changed.connect(self._on_workspace_zoom_changed)
        self.workspace.viewer.slideshow_click_started.connect(self._on_slideshow_click_started)
        self.workspace.viewer.double_clicked.connect(self._on_slideshow_double_clicked)

        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(32, 32, 32, 32)
        empty_layout.addStretch(2)
        empty_folio = QLabel("00")
        empty_folio.setObjectName("emptyFolio")
        empty_folio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_folio)
        open_button = QPushButton("打开 PPT")
        open_button.setIcon(self.open_action.icon())
        open_button.setFixedSize(128, 42)
        open_button.clicked.connect(self.open_file)
        empty_layout.addSpacing(16)
        empty_layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(3)

        stack = QStackedWidget()
        stack.addWidget(empty)
        stack.addWidget(self.preview_workspace)
        stack.addWidget(self.workspace)
        stack.setCurrentWidget(empty)
        self.empty_page = empty
        return stack

    def _set_project_controls_enabled(self, enabled: bool) -> None:
        for action in (
            self.previous_action,
            self.next_action,
            self.zoom_out_action,
            self.reset_action,
            self.zoom_in_action,
            self.fit_action,
            self.fullscreen_action,
        ):
            action.setEnabled(enabled)
        self.mode_button.setEnabled(enabled)

    def _set_importing_ui(self, importing: bool) -> None:
        """在导入期间锁定覆盖层并切换进度控件。"""
        self._importing = bool(importing)
        self.preview_workspace.import_button.setEnabled(not self._importing)
        self.chrome.set_locked(self._importing)
        self.cancel_button.setVisible(self._importing)
        if self._importing:
            self.progress.setRange(0, 100)
            self.progress.show()
        elif self.project:
            self.progress.setRange(0, max(1, self.state.page_count))
            self.progress.setValue(self.state.current_page + 1)
            self.progress.show()
        else:
            self.progress.hide()
        self._apply_mode_chrome()

    def open_file(self) -> None:
        """打开文件选择框并启动后台导入。"""
        if self.worker and self.worker.isRunning():
            return
        source, _ = QFileDialog.getOpenFileName(self, "打开 PowerPoint", "", "PowerPoint (*.ppt *.pptx)")
        if source:
            self.start_import(source)

    def start_import(self, source: str) -> None:
        """显示导入状态并创建工作线程。"""
        self.open_action.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText("正在准备导入…")
        self._set_importing_ui(True)
        self.worker = ImportWorker(self.importer, source)
        self.worker.progress_changed.connect(self._on_progress)
        self.worker.completed.connect(self._on_import_completed)
        self.worker.failed.connect(self._on_import_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def cancel_import(self) -> None:
        """请求取消后台导入。"""
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("正在取消导入…")

    def _on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.status_label.setText(message)

    def _on_import_completed(self, result) -> None:
        """加载项目并默认进入带缩略图的 PPT 预览模式。"""
        self.project = result.project
        self._presentation_mode = "ppt"
        self._ppt_view_mode = "preview"
        self.state.set_page_count(self.project.slide_count)
        current = max(0, min(self.project.current_slide, self.state.page_count - 1))
        self.state.current_page = current
        self.workspace.set_project(self.project, current, initial_mode="stage")
        self.preview_workspace.set_project(self.project, current)
        self.content_stack.setCurrentWidget(self.preview_workspace)
        self._set_project_controls_enabled(True)
        self._update_project_name()
        self._on_workspace_mode_changed(self.workspace.mode)
        status = "缓存命中" if result.cache_hit else "4K 页面已导出"
        self.status_label.setText(status)
        self.preview_workspace.set_status(status)
        self._update_counter()
        self._apply_mode_chrome()
        self.camera_preview.prewarm_camera()

    def _on_import_failed(self, message: str) -> None:
        self.status_label.setText("导入失败")
        self.chrome.set_locked(True)
        QMessageBox.warning(self, "导入失败", message)
        self.chrome.set_locked(False)
        self.open_button.setFocus()

    def _on_worker_finished(self) -> None:
        self.open_action.setEnabled(True)
        self._set_importing_ui(False)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def select_page(self, index: int) -> None:
        self._select_page(index, source="external")

    def previous_page(self) -> None:
        if self.project:
            self.workspace.previous_page()

    def next_page(self) -> None:
        if self.project:
            self.workspace.next_page()

    def change_zoom(self, delta: float) -> None:
        if self.project:
            self.state.zoom = self.workspace.change_zoom(delta)
            self._update_counter()

    def set_zoom_factor(self, value: float) -> None:
        """设置绝对缩放比例，供双手缩放手势调用。"""
        if self.project:
            zoom = self.workspace.set_zoom_factor(value)
            self.state.zoom = zoom
            self._update_counter()

    def pan_page(self, delta_x: float, delta_y: float) -> None:
        """按手掌平移量移动当前单页舞台。"""
        if self.project:
            self.workspace.pan_page(delta_x, delta_y)

    def fit_view(self) -> None:
        if self.project:
            self.workspace.fit_view()

    def reset_zoom(self) -> None:
        if self.project:
            self.workspace.reset_zoom()

    def set_ppt_view_mode(self, mode: str) -> None:
        """切换 PPT 预览/放映子模式，不改变当前页。"""
        if mode not in {"preview", "slideshow"}:
            raise ValueError(f"未知 PPT 视图模式：{mode}")
        if mode != self._ppt_view_mode:
            self._slideshow_click_origin = None
        self._ppt_view_mode = mode
        self._slide_number_buffer = ""
        if self._presentation_mode != "ppt" or not self.project:
            return
        if mode == "slideshow" and self.workspace.mode == "carousel":
            self.workspace.enter_stage(self.workspace.current_index)
        self._on_workspace_mode_changed(self.workspace.mode)

    def _on_slideshow_click_started(self) -> None:
        """记录首次单击前页码，供随后发生的双击恢复。"""
        if self.project and self._presentation_mode == "ppt" and self._ppt_view_mode == "slideshow":
            self._slideshow_click_origin = self.workspace.current_index

    def _on_slideshow_double_clicked(self) -> None:
        """恢复双击前页码并返回预览，避免最终停在下一页。"""
        if self._presentation_mode != "ppt" or self._ppt_view_mode != "slideshow":
            return
        origin = self._slideshow_click_origin
        if origin is not None:
            self._select_page(origin, source="external")
        self._slideshow_click_origin = None
        self.set_ppt_view_mode("preview")

    def toggle_workspace_mode(self) -> None:
        """切换顶层 PPT/手势模式，保留手势模式内部的两级视图。"""
        if not self.project:
            return
        self._slide_number_buffer = ""
        if self._presentation_mode == "ppt":
            self._presentation_mode = "gesture"
            self.content_stack.setCurrentWidget(self.workspace)
            self.workspace.show_carousel()
            self._set_gesture_runtime_enabled(True)
            return
        self._presentation_mode = "ppt"
        self._set_gesture_runtime_enabled(False)
        if self.workspace.mode == "carousel":
            self.workspace.enter_stage(self.workspace.current_index)
        else:
            self._on_workspace_mode_changed(self.workspace.mode)

    def toggle_fullscreen(self) -> None:
        """全屏沿用相同的边缘唤出和自动隐藏控制。"""
        if self.isFullScreen():
            self.showNormal()
            self.chrome.reveal_all()
        else:
            self.showFullScreen()
            self.chrome.hide_now()

    def _on_workspace_page_changed(self, index: int) -> None:
        self._select_page(index, source="workspace")

    def _on_preview_page_selected(self, index: int) -> None:
        """将预览缩略图选择同步到放映和手势工作区。"""
        self._select_page(index, source="preview")

    def _select_page(self, index: int, *, source: str) -> None:
        """统一同步预览、放映和项目页码，避免组件间递归调用。"""
        if not self.project or not 0 <= index < self.state.page_count:
            return
        self.state.select(index)
        self.project.current_slide = index
        if source != "workspace":
            self.workspace.select_page(index)
        self.preview_workspace.select_page(index, emit=False)
        self._update_counter()

    def _on_workspace_mode_changed(self, mode: str) -> None:
        is_ppt = self._presentation_mode == "ppt"
        is_ppt_slideshow = is_ppt and self._ppt_view_mode == "slideshow"
        is_gesture_stage = not is_ppt and mode == "stage"
        self.mode_button.setIcon(line_icon("grid" if is_ppt else "stage"))
        self.mode_button.setToolTip("进入手势模式" if is_ppt else "返回PPT模式")
        if is_ppt:
            self.status_label.setText("PPT模式 · 放映" if is_ppt_slideshow else "PPT模式 · 预览")
            self.content_stack.setCurrentWidget(
                self.workspace if is_ppt_slideshow else self.preview_workspace
            )
        else:
            self.status_label.setText("手势模式 · 单页" if is_gesture_stage else "手势模式 · 滚筒")
            self.content_stack.setCurrentWidget(self.workspace)
        self.workspace.viewer.set_interaction_mode("slideshow" if is_ppt_slideshow else "gesture")
        self.workspace.viewer.set_fit_margin(0 if is_ppt_slideshow else STAGE_SAFE_MARGIN)
        for action in (self.zoom_out_action, self.reset_action, self.zoom_in_action, self.fit_action):
            action.setEnabled(is_gesture_stage)
        for widget in self.zoom_widgets:
            widget.setVisible(is_gesture_stage)
        self.state.zoom = self.workspace.zoom_factor
        self._update_counter()
        self._apply_mode_chrome()

    def _apply_mode_chrome(self) -> None:
        """按 PPT/手势模式切换应用控制层显隐策略。"""
        if self._presentation_mode == "ppt" and self.project and not self._importing:
            self.chrome.set_suppressed(True)
            self.chrome.hide_now()
            return
        self.chrome.set_suppressed(False)
        self.chrome.reveal_all()

    def _set_gesture_runtime_enabled(self, enabled: bool) -> None:
        """进入手势模式显示热启动摄像头，退出时隐藏但保温。"""
        self.gesture_controller.set_enabled(enabled)
        if enabled:
            self.camera_preview.start_camera()
        else:
            self.camera_preview.hide_preview_keep_warm()

    def _on_gesture_status_changed(self, message: str) -> None:
        if self._presentation_mode == "gesture" and not self._importing:
            self.status_label.setText(message)

    def _on_workspace_zoom_changed(self, zoom: float) -> None:
        self.state.zoom = zoom
        self._update_counter()

    def _update_project_name(self) -> None:
        if not self.project:
            self.file_label.setText("未打开项目")
            self.file_label.setToolTip("")
            return
        source = Path(self.project.source_path)
        self.file_label.setText(source.name)
        self.file_label.setToolTip(str(source))

    def _update_counter(self) -> None:
        if not self.state.page_count:
            self.folio.setText("00 / 00")
            return
        self.folio.setText(f"{self.state.current_page + 1:02d} / {self.state.page_count:02d}")
        at_start = self.state.current_page <= 0
        at_end = self.state.current_page >= self.state.page_count - 1
        self.previous_action.setEnabled(not at_start)
        self.next_action.setEnabled(not at_end)
        self.reset_action.setText(f"{int(self.state.zoom * 100)}%")
        if not self._importing:
            self.progress.setRange(0, self.state.page_count)
            self.progress.setValue(self.state.current_page + 1)
            self.progress.show()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """处理舞台翻页、首尾页和两级 Esc 行为。"""
        key = event.key()
        if (
            self.project
            and self._presentation_mode == "ppt"
            and self._ppt_view_mode == "slideshow"
            and self._handle_powerpoint_key(event)
        ):
            return
        self._slide_number_buffer = ""
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Space):
            self.next_page()
            event.accept()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.previous_page()
            event.accept()
            return
        if key == Qt.Key.Key_Home and self.state.page_count:
            self.select_page(0)
            event.accept()
            return
        if key == Qt.Key.Key_End and self.state.page_count:
            self.select_page(self.state.page_count - 1)
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.chrome.reveal_all()
                event.accept()
                return
            if self._presentation_mode == "gesture" and self.workspace.mode == "stage":
                self.workspace.show_carousel()
                event.accept()
                return
        super().keyPressEvent(event)

    def _handle_powerpoint_key(self, event) -> bool:
        """对齐 PowerPoint Slide Show 的常用键盘放映交互。"""
        key = event.key()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            self._slide_number_buffer += event.text()
            event.accept()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._slide_number_buffer:
                target = int(self._slide_number_buffer) - 1
                self._slide_number_buffer = ""
                if 0 <= target < self.state.page_count:
                    self.select_page(target)
                event.accept()
                return True
            self.next_page()
            event.accept()
            return True
        self._slide_number_buffer = ""
        if key in (Qt.Key.Key_N, Qt.Key.Key_PageDown, Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Space):
            self.next_page()
            event.accept()
            return True
        if key in (Qt.Key.Key_P, Qt.Key.Key_PageUp, Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_Backspace):
            self.previous_page()
            event.accept()
            return True
        if key == Qt.Key.Key_Home and self.state.page_count:
            self.select_page(0)
            event.accept()
            return True
        if key == Qt.Key.Key_End and self.state.page_count:
            self.select_page(self.state.page_count - 1)
            event.accept()
            return True
        if key == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            self.set_ppt_view_mode("preview")
            event.accept()
            return True
        return False

    def _restore_last_project(self) -> None:
        """从用户配置恢复最近一次路径，失效时不弹窗打扰启动。"""
        settings = self._settings_path()
        if settings.exists():
            source = settings.read_text(encoding="utf-8").strip()
            if source and Path(source).exists():
                self.status_label.setText(f"正在恢复：{Path(source).name}")
                self.start_import(source)

    def closeEvent(self, event) -> None:  # noqa: N802
        """保存当前页并停止线程、计时器和动画。"""
        self.gesture_diagnostics.stop()
        self.gesture_controller.set_enabled(False)
        self.camera_preview.stop_camera()
        self.chrome.dispose()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)
        if self.project:
            self.project.current_slide = self.workspace.current_index
            save_project(self.project, project_dir(self.project.cache_key))
            settings = self._settings_path()
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text(self.project.source_path, encoding="utf-8")
        event.accept()

    @staticmethod
    def _settings_path() -> Path:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "GesturePPT" / "last_project.txt"


def run_application() -> int:
    """创建 Qt 应用并运行事件循环。"""
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Gesture PPT")
    window = MainWindow()
    window.show()
    return app.exec()
