"""左侧缩略图列表。"""

from __future__ import annotations

from PySide6.QtCore import Signal, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem


class ThumbnailPanel(QListWidget):
    """使用独立缩略图 JPEG，避免列表解码原图。"""

    page_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setIconSize(QSize(180, 102))
        self.setSpacing(10)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setMovement(QListWidget.Movement.Static)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.currentRowChanged.connect(self._on_row_changed)

    def set_pages(self, pages) -> None:
        """重建缩略图列表并显示页码。"""
        self.clear()
        for page in pages:
            item = QListWidgetItem(QIcon(QPixmap(page.thumbnail_path)), f"第 {page.index + 1:02d} 页")
            item.setData(Qt.ItemDataRole.UserRole, page.index)
            item.setToolTip(f"切换到第 {page.index + 1} 页")
            self.addItem(item)
        if self.count():
            self.setCurrentRow(0)

    def select_page(self, index: int) -> None:
        """选中指定页面并滚动到可见区域。"""
        if 0 <= index < self.count():
            self.setCurrentRow(index)
            self.scrollToItem(self.item(index))

    def _on_row_changed(self, row: int) -> None:
        """将列表行变化转成页面命令。"""
        if row >= 0:
            self.page_selected.emit(row)
