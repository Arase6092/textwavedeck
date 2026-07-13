"""第一阶段主窗口和 Qt 命令绑定。"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.commands import NavigationState
from app.workers import ImportWorker
from models.slide_project import SlideProject
from ppt.importer import PPTImporter
from ppt.project_store import project_dir, save_project
from widgets.slide_viewer import SlideViewer
from widgets.thumbnail_panel import ThumbnailPanel

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Swiss 风格的 PPT 图片浏览主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Gesture PPT · 演示浏览器")
        self.resize(1440, 900)
        self.setMinimumSize(980, 620)
        self.state = NavigationState()
        self.project: SlideProject | None = None
        self.worker: ImportWorker | None = None
        self.importer = PPTImporter()
        self._build_ui()
        self._restore_last_project()

    def _build_ui(self) -> None:
        """构建菜单、工具栏、缩略图和预览区。"""
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f5f7fa; color: #142033; font-family: 'Segoe UI'; }
            QToolBar { background: #ffffff; border: 0; border-bottom: 1px solid #dfe5ec; spacing: 6px; padding: 8px 14px; }
            QToolButton, QPushButton { background: #ffffff; border: 1px solid #d7dee8; border-radius: 6px; padding: 7px 12px; color: #24364b; }
            QToolButton:hover, QPushButton:hover { background: #edf4ff; border-color: #83aef4; }
            QToolButton:pressed, QPushButton:pressed { background: #dceaff; }
            QListWidget { background: #ffffff; border: 1px solid #dfe5ec; border-radius: 8px; padding: 12px; outline: none; }
            QListWidget::item { padding: 8px; border-radius: 6px; color: #526173; }
            QListWidget::item:selected { background: #e6f0ff; color: #1254a6; border: 1px solid #8db6f5; }
            QGraphicsView { background: #e9edf3; border: 1px solid #dfe5ec; border-radius: 8px; }
            QStatusBar { background: #ffffff; border-top: 1px solid #dfe5ec; color: #607086; }
            QProgressBar { border: 0; background: #e9eef5; border-radius: 4px; height: 8px; text-align: center; }
            QProgressBar::chunk { background: #2764d8; border-radius: 4px; }
            QLabel#emptyState { color: #718096; font-size: 18px; }
            QLabel#pageCounter { color: #44566d; font-weight: 600; padding: 0 12px; }
            """
        )
        self._create_actions()
        self._create_toolbar()
        self._create_content()
        self._create_status_bar()

    def _create_actions(self) -> None:
        """创建可被快捷键和工具栏共同调用的统一命令。"""
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
        self.addAction(self.open_action)
        self.addAction(self.previous_action)
        self.addAction(self.next_action)
        self.addAction(self.fullscreen_action)

    def _create_toolbar(self) -> None:
        """创建带分组层级的顶部操作栏。"""
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        toolbar.addSeparator()
        toolbar.addAction(self.previous_action)
        toolbar.addAction(self.next_action)
        toolbar.addSeparator()
        zoom_out = QAction("缩小", self)
        zoom_out.triggered.connect(lambda: self.change_zoom(-0.1))
        zoom_in = QAction("放大", self)
        zoom_in.triggered.connect(lambda: self.change_zoom(0.1))
        fit = QAction("适应窗口", self)
        fit.triggered.connect(self.fit_view)
        reset = QAction("100%", self)
        reset.triggered.connect(self.reset_zoom)
        toolbar.addAction(zoom_out)
        toolbar.addAction(reset)
        toolbar.addAction(zoom_in)
        toolbar.addAction(fit)
        toolbar.addSeparator()
        toolbar.addAction(self.fullscreen_action)
        self.addToolBar(toolbar)

    def _create_content(self) -> None:
        """创建左侧缩略图和中央阅读台。"""
        self.thumbnails = ThumbnailPanel()
        self.thumbnails.setFixedWidth(240)
        self.thumbnails.page_selected.connect(self.select_page)
        self.viewer = SlideViewer()
        self.empty_state = QLabel("打开一个 PPT 文件开始浏览")
        self.empty_state.setObjectName("emptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setMinimumHeight(220)
        self.empty_state.setStyleSheet("background:#e9edf3; border:1px solid #dfe5ec; border-radius:8px;")
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.viewer)
        layout.addWidget(self.empty_state)
        self.viewer.hide()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.thumbnails)
        splitter.addWidget(center)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

    def _create_status_bar(self) -> None:
        """创建状态栏和导入进度。"""
        status = QStatusBar(self)
        self.setStatusBar(status)
        self.page_counter = QLabel("未打开项目")
        self.page_counter.setObjectName("pageCounter")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedWidth(180)
        self.progress.hide()
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedWidth(64)
        self.cancel_button.clicked.connect(self.cancel_import)
        self.cancel_button.hide()
        status.addWidget(self.page_counter)
        status.addPermanentWidget(self.progress)
        status.addPermanentWidget(self.cancel_button)

    def open_file(self) -> None:
        """打开文件选择框并启动后台导入。"""
        if self.worker and self.worker.isRunning():
            return
        source, _ = QFileDialog.getOpenFileName(self, "打开 PowerPoint", "", "PowerPoint (*.ppt *.pptx)")
        if source:
            self.start_import(source)

    def start_import(self, source: str) -> None:
        """显示导入状态并创建工作线程。"""
        self.progress.setValue(0)
        self.progress.show()
        self.cancel_button.show()
        self.page_counter.setText("正在准备导入…")
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
            self.page_counter.setText("正在取消导入…")

    def _on_progress(self, value: int, message: str) -> None:
        """更新进度和中文状态。"""
        self.progress.setValue(value)
        self.page_counter.setText(message)

    def _on_import_completed(self, result) -> None:
        """显示导入结果并恢复当前页。"""
        self.project = result.project
        self.state.set_page_count(self.project.slide_count)
        self.state.current_page = self.project.current_slide
        self.thumbnails.set_pages(self.project.pages)
        self.thumbnails.select_page(self.state.current_page)
        self._show_current_page()
        self.page_counter.setText(f"第 {self.state.current_page + 1} / {self.state.page_count} 页  |  {'缓存命中' if result.cache_hit else '已导出'}")
        self.statusBar().showMessage("项目已加载", 3000)

    def _on_import_failed(self, message: str) -> None:
        """显示中文错误提示，不影响已有项目。"""
        self.page_counter.setText("导入失败")
        QMessageBox.warning(self, "导入失败", message)

    def _on_worker_finished(self) -> None:
        """收起导入控件并释放线程引用。"""
        self.progress.hide()
        self.cancel_button.hide()
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def select_page(self, index: int) -> None:
        """统一选页命令。"""
        if self.state.select(index):
            self._show_current_page()

    def previous_page(self) -> None:
        """执行上一页命令。"""
        if self.state.previous():
            self.thumbnails.select_page(self.state.current_page)
            self._show_current_page()

    def next_page(self) -> None:
        """执行下一页命令。"""
        if self.state.next():
            self.thumbnails.select_page(self.state.current_page)
            self._show_current_page()

    def change_zoom(self, delta: float) -> None:
        """调整预览缩放并同步状态栏。"""
        if self.project:
            self.state.zoom = self.viewer.change_zoom(delta)
            self._update_counter()

    def fit_view(self) -> None:
        """执行适应窗口命令。"""
        self.viewer.fit_in_view()
        self.state.zoom = 1.0
        self._update_counter()

    def reset_zoom(self) -> None:
        """执行原始比例命令。"""
        self.viewer.reset_zoom()
        self.state.zoom = 1.0
        self._update_counter()

    def toggle_fullscreen(self) -> None:
        """进入或退出全屏。"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """补齐方案约定的翻页、首尾页和退出全屏快捷键。"""
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
        if key == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_current_page(self) -> None:
        """加载当前页图片并更新界面。"""
        if not self.project or not self.project.pages:
            return
        page = self.project.pages[self.state.current_page]
        self.viewer.show_image(page.image_path)
        self.viewer.show()
        self.empty_state.hide()
        self._update_counter()

    def _update_counter(self) -> None:
        """刷新页码与缩放百分比。"""
        if self.state.page_count:
            self.page_counter.setText(f"第 {self.state.current_page + 1} / {self.state.page_count} 页  |  {int(self.state.zoom * 100)}%")

    def _restore_last_project(self) -> None:
        """从用户配置恢复最近一次路径，失效时不弹窗打扰启动。"""
        settings = self._settings_path()
        if settings.exists():
            source = settings.read_text(encoding="utf-8").strip()
            if source and Path(source).exists():
                self.statusBar().showMessage(f"最近项目：{source}", 5000)
                # 最近项目恢复走统一导入流程，优先命中缓存，不阻塞窗口初始化。
                self.start_import(source)

    def closeEvent(self, event) -> None:  # noqa: N802
        """保存最近一次项目路径并在退出时取消线程。"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)
        if self.project:
            # 关闭前保存当前页，下一次导入缓存时恢复阅读位置。
            self.project.current_slide = self.state.current_page
            save_project(self.project, project_dir(self.project.cache_key))
            settings = self._settings_path()
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text(self.project.source_path, encoding="utf-8")
        event.accept()

    @staticmethod
    def _settings_path() -> Path:
        """返回最近项目配置文件路径。"""
        import os
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "GesturePPT" / "last_project.txt"


def run_application() -> int:
    """创建 Qt 应用并运行事件循环。"""
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Gesture PPT")
    window = MainWindow()
    window.show()
    return app.exec()
