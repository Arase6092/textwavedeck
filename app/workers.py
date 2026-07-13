"""导入后台线程，避免 PowerPoint 导出阻塞界面。"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ppt.importer import ImportResult, PPTImporter


class ImportWorker(QThread):
    """在 Qt 工作线程中执行 PPT 导入。"""

    progress_changed = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, importer: PPTImporter, source_path: str) -> None:
        super().__init__()
        self.importer = importer
        self.source_path = source_path
        self._cancelled = False

    def cancel(self) -> None:
        """请求取消导入；COM 调用返回后尽快退出。"""
        self._cancelled = True

    def run(self) -> None:
        """执行导入并通过信号传递结果。"""
        try:
            result = self.importer.import_file(
                self.source_path,
                progress=lambda value, message: self.progress_changed.emit(value, message),
                is_cancelled=lambda: self._cancelled,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
