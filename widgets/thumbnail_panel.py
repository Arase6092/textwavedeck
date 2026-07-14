"""左侧缩略图列表。"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem


class ThumbnailPanel(QListWidget):
    """使用独立缩略图 JPEG，避免列表解码原图。"""

    page_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setIconSize(QSize(168, 95))
        self.setGridSize(QSize(188, 126))
        self.setSpacing(6)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.TopToBottom)
        self.setWrapping(False)
        self.setUniformItemSizes(True)
        self.setMovement(QListWidget.Movement.Static)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.currentRowChanged.connect(self._on_row_changed)

    def set_pages(self, pages) -> None:
        """重建缩略图列表并显示页码。"""
        # 批量重建时暂时屏蔽行变化信号，避免恢复页码被默认第 1 页覆盖。
        self.blockSignals(True)
        self.clear()
        for page in pages:
            item = QListWidgetItem(QIcon(QPixmap(page.thumbnail_path)), f"{page.index + 1:02d}")
            item.setData(Qt.ItemDataRole.UserRole, page.index)
            item.setToolTip(f"切换到第 {page.index + 1} 页")
            self.addItem(item)
        if self.count():
            self.setCurrentRow(0)
        self.blockSignals(False)

    def select_page(self, index: int, *, emit: bool = True) -> None:
        """选中并显示指定缩略图；同步更新时可禁止重复发出信号。"""
        if not 0 <= index < self.count():
            return
        blocker = None if emit else QSignalBlocker(self)
        self.setCurrentRow(index)
        self.scrollToItem(self.item(index))
        del blocker

    def _on_row_changed(self, row: int) -> None:
        """将列表行变化转成页面命令。"""
        if row >= 0:
            self.page_selected.emit(row)
