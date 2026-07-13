"""圆柱滚筒舞台主窗口和 Qt 命令绑定。"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.commands import NavigationState
from app.workers import ImportWorker
from models.slide_project import SlideProject
from ppt.importer import PPTImporter
from ppt.project_store import project_dir, save_project
from widgets.stage_workspace import StageWorkspace


class MainWindow(QMainWindow):
    """以整窗圆柱滚筒和单页舞台为主体的浏览窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Gesture PPT · 页面舞台")
        self.resize(1440, 900)
        self.setMinimumSize(980, 620)
        self.state = NavigationState()
        self.project: SlideProject | None = None
        self.worker: ImportWorker | None = None
        self.importer = PPTImporter()
        self._build_ui()
        self._restore_last_project()

    def _build_ui(self) -> None:
        """构建 Swiss 风格边缘控制和整窗舞台。"""
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f7f7f8;
                color: #20242b;
                font-family: 'Segoe UI';
                letter-spacing: 0px;
            }
            QFrame#edgeBar {
                background: #ffffff;
                border: 0;
                border-bottom: 1px solid #d9dde3;
            }
            QFrame#statusStrip {
                background: #ffffff;
                border: 0;
                border-top: 1px solid #d9dde3;
            }
            QFrame#separator {
                background: #d9dde3;
                min-width: 1px;
                max-width: 1px;
            }
            QToolButton, QPushButton {
                background: #ffffff;
                color: #20242b;
                border: 1px solid #d9dde3;
                border-radius: 2px;
                padding: 6px 10px;
            }
            QToolButton:hover, QPushButton:hover {
                color: #002fa7;
                border-color: #002fa7;
            }
            QToolButton:pressed, QPushButton:pressed {
                background: #f0f3fa;
            }
            QToolButton:disabled, QPushButton:disabled {
                color: #a7adb7;
                border-color: #e7e9ed;
            }
            QLabel#folio {
                color: #002fa7;
                font-size: 20px;
                font-weight: 700;
                padding: 0 14px;
            }
            QLabel#emptyFolio {
                color: #002fa7;
                font-size: 82px;
                font-weight: 700;
            }
            QLabel#emptyTitle {
                color: #20242b;
                font-size: 23px;
                font-weight: 600;
            }
            QLabel#statusLabel {
                color: #5d6470;
                font-size: 12px;
            }
            QProgressBar {
                border: 0;
                background: #e4e7eb;
                height: 6px;
                text-align: center;
            }
            QProgressBar::chunk { background: #002fa7; }
            QGraphicsView#cylinderCarousel {
                background: #f7f7f8;
                border: 0;
            }
            QGraphicsView#slideViewer {
                background: #e9ebee;
                border: 0;
            }
            """
        )
        self._create_actions()
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.edge_bar = self._create_edge_bar()
        self.content_stack = self._create_content()
        self.status_strip = self._create_status_strip()
        root_layout.addWidget(self.edge_bar)
        root_layout.addWidget(self.content_stack, 1)
        root_layout.addWidget(self.status_strip)
        self.setCentralWidget(root)
        self._set_project_controls_enabled(False)

    def _create_actions(self) -> None:
        """创建快捷键和边缘按钮共享的命令。"""
        self.open_action = QAction("打开", self)
        self.open_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.open_action.setToolTip("打开 PPT（Ctrl+O）")
        self.open_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_action.triggered.connect(self.open_file)

        self.previous_action = QAction("上一页", self)
        self.previous_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
        self.previous_action.setToolTip("上一页（PageUp / Left）")
        self.previous_action.setShortcut(QKeySequence("PageUp"))
        self.previous_action.triggered.connect(self.previous_page)

        self.next_action = QAction("下一页", self)
        self.next_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
        self.next_action.setToolTip("下一页（PageDown / Right / Space）")
        self.next_action.setShortcut(QKeySequence("PageDown"))
        self.next_action.triggered.connect(self.next_page)

        self.fullscreen_action = QAction("全屏", self)
        self.fullscreen_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton))
        self.fullscreen_action.setToolTip("进入或退出全屏（F11）")
        self.fullscreen_action.setShortcut(QKeySequence("F11"))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.zoom_out_action = QAction("−", self)
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
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        button.setFixedHeight(34)
        if not text:
            button.setFixedWidth(38)
        return button

    def _create_edge_bar(self) -> QFrame:
        """创建舞台顶部的轻量命令边。"""
        bar = QFrame()
        bar.setObjectName("edgeBar")
        bar.setFixedHeight(54)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 9, 16, 9)
        layout.setSpacing(7)
        layout.addWidget(self._action_button(self.open_action, text=True))
        separator = QFrame()
        separator.setObjectName("separator")
        layout.addWidget(separator)
        layout.addWidget(self._action_button(self.previous_action))
        layout.addWidget(self._action_button(self.next_action))
        self.folio = QLabel("00 / 00")
        self.folio.setObjectName("folio")
        layout.addWidget(self.folio)
        layout.addStretch(1)
        self.mode_button = QToolButton()
        self.mode_button.setText("进入舞台")
        self.mode_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
        self.mode_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.mode_button.setFixedHeight(34)
        self.mode_button.setToolTip("在页面滚筒和单页舞台之间切换")
        self.mode_button.clicked.connect(self.toggle_workspace_mode)
        layout.addWidget(self.mode_button)
        layout.addWidget(self._action_button(self.zoom_out_action))
        layout.addWidget(self._action_button(self.reset_action, text=True))
        layout.addWidget(self._action_button(self.zoom_in_action))
        layout.addWidget(self._action_button(self.fit_action, text=True))
        layout.addWidget(self._action_button(self.fullscreen_action))
        return bar

    def _create_content(self) -> QStackedWidget:
        """创建空状态和整窗舞台。"""
        self.workspace = StageWorkspace()
        self.workspace.page_changed.connect(self._on_workspace_page_changed)
        self.workspace.mode_changed.connect(self._on_workspace_mode_changed)
        self.workspace.zoom_changed.connect(self._on_workspace_zoom_changed)

        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(72, 48, 72, 48)
        empty_layout.addStretch(1)
        empty_folio = QLabel("00")
        empty_folio.setObjectName("emptyFolio")
        empty_layout.addWidget(empty_folio, 0, Qt.AlignmentFlag.AlignLeft)
        empty_title = QLabel("尚未打开项目")
        empty_title.setObjectName("emptyTitle")
        empty_layout.addWidget(empty_title, 0, Qt.AlignmentFlag.AlignLeft)
        open_button = QPushButton("打开 PPT")
        open_button.setIcon(self.open_action.icon())
        open_button.setFixedSize(118, 38)
        open_button.clicked.connect(self.open_file)
        empty_layout.addSpacing(18)
        empty_layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)
        empty_layout.addStretch(2)

        stack = QStackedWidget()
        stack.addWidget(empty)
        stack.addWidget(self.workspace)
        stack.setCurrentWidget(empty)
        self.empty_page = empty
        return stack

    def _create_status_strip(self) -> QFrame:
        """创建紧贴舞台底部的状态和导入进度。"""
        strip = QFrame()
        strip.setObjectName("statusStrip")
        strip.setFixedHeight(36)
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(8)
        self.status_label = QLabel("未打开项目")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(220)
        self.progress.hide()
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(62, 26)
        self.cancel_button.clicked.connect(self.cancel_import)
        self.cancel_button.hide()
        layout.addWidget(self.progress)
        layout.addWidget(self.cancel_button)
        return strip

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
        self.progress.show()
        self.cancel_button.show()
        self.status_label.setText("正在准备导入…")
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
        """加载项目并定位到上次使用的滚筒页。"""
        self.project = result.project
        self.state.set_page_count(self.project.slide_count)
        current = max(0, min(self.project.current_slide, self.state.page_count - 1))
        self.state.current_page = current
        self.workspace.set_project(self.project, current)
        self.content_stack.setCurrentWidget(self.workspace)
        self._set_project_controls_enabled(True)
        self._on_workspace_mode_changed(self.workspace.mode)
        self.status_label.setText("缓存命中" if result.cache_hit else "4K 页面已导出")
        self._update_counter()

    def _on_import_failed(self, message: str) -> None:
        self.status_label.setText("导入失败")
        QMessageBox.warning(self, "导入失败", message)

    def _on_worker_finished(self) -> None:
        self.open_action.setEnabled(True)
        self.progress.hide()
        self.cancel_button.hide()
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def select_page(self, index: int) -> None:
        if self.project:
            self.workspace.select_page(index)

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

    def fit_view(self) -> None:
        if self.project:
            self.workspace.fit_view()

    def reset_zoom(self) -> None:
        if self.project:
            self.workspace.reset_zoom()

    def toggle_workspace_mode(self) -> None:
        """在滚筒选页和完整单页舞台之间切换。"""
        if not self.project:
            return
        if self.workspace.mode == "carousel":
            self.workspace.enter_stage(self.workspace.current_index)
        else:
            self.workspace.show_carousel()

    def toggle_fullscreen(self) -> None:
        """进入全屏时隐藏全部边缘控制。"""
        if self.isFullScreen():
            self.showNormal()
            self.edge_bar.show()
            self.status_strip.show()
        else:
            self.edge_bar.hide()
            self.status_strip.hide()
            self.showFullScreen()

    def _on_workspace_page_changed(self, index: int) -> None:
        self.state.current_page = index
        if self.project:
            self.project.current_slide = index
        self._update_counter()

    def _on_workspace_mode_changed(self, mode: str) -> None:
        is_stage = mode == "stage"
        self.mode_button.setText("进入舞台" if mode == "carousel" else "页面滚筒")
        self.status_label.setText("页面滚筒" if mode == "carousel" else "单页舞台")
        for action in (self.zoom_out_action, self.reset_action, self.zoom_in_action, self.fit_action):
            action.setEnabled(is_stage)
        self.state.zoom = self.workspace.zoom_factor
        self._update_counter()

    def _on_workspace_zoom_changed(self, zoom: float) -> None:
        self.state.zoom = zoom
        self._update_counter()

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

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """处理舞台翻页、首尾页和两级 Esc 行为。"""
        key = event.key()
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
                self.edge_bar.show()
                self.status_strip.show()
                event.accept()
                return
            if self.workspace.mode == "stage":
                self.workspace.show_carousel()
                event.accept()
                return
        super().keyPressEvent(event)

    def _restore_last_project(self) -> None:
        """从用户配置恢复最近一次路径，失效时不弹窗打扰启动。"""
        settings = self._settings_path()
        if settings.exists():
            source = settings.read_text(encoding="utf-8").strip()
            if source and Path(source).exists():
                self.status_label.setText(f"正在恢复：{Path(source).name}")
                self.start_import(source)

    def closeEvent(self, event) -> None:  # noqa: N802
        """保存当前页并在退出时取消工作线程。"""
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
