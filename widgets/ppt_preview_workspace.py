"""精简只读的 PowerPoint 预览工作区。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.theme import STAGE_SAFE_MARGIN, line_icon
from models.slide_project import SlidePage, SlideProject
from widgets.slide_viewer import SlideViewer
from widgets.thumbnail_panel import ThumbnailPanel


class PptPreviewWorkspace(QWidget):
    """展示缩略图和只读主页面，并将用户命令交给主窗口。"""

    page_selected = Signal(int)
    import_requested = Signal()
    slideshow_requested = Signal()
    MIN_THUMBNAIL_WIDTH = 190
    MAX_THUMBNAIL_WIDTH = 300
    DEFAULT_THUMBNAIL_WIDTH = 228

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pptPreviewRoot")
        self._pages: list[SlidePage] = []
        self.current_index = 0
        self._build_ui()

    def _build_ui(self) -> None:
        """按精简 Normal View 结构组装固定命令区和双栏内容。"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        command_bar = QFrame(self)
        command_bar.setObjectName("pptPreviewCommandBar")
        command_bar.setFixedHeight(52)
        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(14, 6, 12, 6)
        command_layout.setSpacing(8)

        self.file_label = QLabel("未打开项目", command_bar)
        self.file_label.setObjectName("pptPreviewFileName")
        command_layout.addWidget(self.file_label)
        command_layout.addStretch(1)

        self.import_button = QPushButton("导入 PPT", command_bar)
        self.import_button.setObjectName("pptPreviewImportButton")
        self.import_button.setIcon(line_icon("open"))
        self.import_button.setToolTip("导入 PowerPoint（Ctrl+O）")
        self.import_button.clicked.connect(self.import_requested.emit)
        command_layout.addWidget(self.import_button)

        self.slideshow_button = QToolButton(command_bar)
        self.slideshow_button.setObjectName("pptPreviewSlideshowButton")
        self.slideshow_button.setIcon(line_icon("stage"))
        self.slideshow_button.setToolTip("从当前页进入放映模式")
        self.slideshow_button.setFixedSize(40, 40)
        self.slideshow_button.clicked.connect(self.slideshow_requested.emit)
        command_layout.addWidget(self.slideshow_button)
        root_layout.addWidget(command_bar)

        self.thumbnail_panel = ThumbnailPanel()
        self.thumbnail_panel.setObjectName("pptThumbnailPane")
        self.thumbnail_panel.setMinimumWidth(self.MIN_THUMBNAIL_WIDTH)
        self.thumbnail_panel.setMaximumWidth(self.MAX_THUMBNAIL_WIDTH)
        self.thumbnail_panel.page_selected.connect(self._on_thumbnail_selected)

        self.viewer = SlideViewer()
        self.viewer.setObjectName("pptPreviewViewer")
        self.viewer.set_fit_margin(STAGE_SAFE_MARGIN // 2)
        self.viewer.set_interaction_mode("preview")
        self.viewer.double_clicked.connect(self.slideshow_requested.emit)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("pptPreviewSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.thumbnail_panel)
        self.splitter.addWidget(self.viewer)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([self.DEFAULT_THUMBNAIL_WIDTH, 972])
        root_layout.addWidget(self.splitter, 1)

        status_bar = QFrame(self)
        status_bar.setObjectName("pptPreviewStatusBar")
        status_bar.setFixedHeight(34)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(14, 0, 14, 0)
        status_layout.setSpacing(8)
        self.page_label = QLabel("幻灯片 0 / 0", status_bar)
        self.page_label.setObjectName("pptPreviewPageLabel")
        status_layout.addWidget(self.page_label)
        status_layout.addStretch(1)
        self.status_label = QLabel("预览模式", status_bar)
        self.status_label.setObjectName("pptPreviewStatusLabel")
        status_layout.addWidget(self.status_label)
        root_layout.addWidget(status_bar)

    def set_project(self, project: SlideProject, current_index: int = 0) -> None:
        """加载项目并同步缩略图和中央页面。"""
        self._pages = list(project.pages)
        self.file_label.setText(Path(project.source_path).name)
        self.file_label.setToolTip(project.source_path)
        self.thumbnail_panel.set_pages(self._pages)
        self.select_page(current_index, emit=False)

    def select_page(self, index: int, *, emit: bool = False) -> None:
        """显示指定页面，并按需向主窗口发出用户选择。"""
        if not 0 <= index < len(self._pages):
            return
        self.current_index = index
        self.thumbnail_panel.select_page(index, emit=False)
        self.viewer.show_image(self._pages[index].image_path)
        self.page_label.setText(f"幻灯片 {index + 1} / {len(self._pages)}")
        if emit:
            self.page_selected.emit(index)

    def set_status(self, text: str) -> None:
        """更新预览底部的中文项目状态。"""
        self.status_label.setText(text)

    def _on_thumbnail_selected(self, index: int) -> None:
        """响应用户缩略图选择并刷新中央页面。"""
        self.select_page(index, emit=True)
