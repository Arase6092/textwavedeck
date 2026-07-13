"""PPT 文件校验和导入编排。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from models.slide_project import SlideProject, source_signature
from ppt.powerpoint_exporter import PowerPointExporter
from ppt.project_store import calculate_cache_key, is_cache_valid, load_project, project_dir


class ImportErrorMessage(RuntimeError):
    """带中文提示的导入异常。"""


@dataclass(slots=True)
class ImportResult:
    """导入结果及缓存命中状态。"""

    project: SlideProject
    cache_hit: bool


class PPTImporter:
    """负责校验源文件、命中缓存或调用导出器。"""

    SUPPORTED_SUFFIXES = {".ppt", ".pptx"}

    def __init__(self, cache_base: Path | None = None, exporter: PowerPointExporter | None = None) -> None:
        self.cache_base = cache_base
        self.exporter = exporter or PowerPointExporter()

    def validate_source(self, source_path: str | Path) -> Path:
        """校验文件存在性和扩展名。"""
        path = Path(source_path).expanduser().resolve()
        if not path.exists():
            raise ImportErrorMessage("文件不存在，请选择有效的 PPT 文件。")
        if path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ImportErrorMessage("仅支持 .ppt 和 .pptx 文件。")
        if not path.is_file():
            raise ImportErrorMessage("选择的路径不是文件。")
        return path

    def import_file(
        self,
        source_path: str | Path,
        progress: Callable[[int, str], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ImportResult:
        """执行缓存命中或后台导出。"""
        source = self.validate_source(source_path)
        key = calculate_cache_key(source)
        directory = project_dir(key, self.cache_base)
        if is_cache_valid(directory, source):
            if progress:
                progress(100, "已命中缓存")
            return ImportResult(load_project(directory), True)
        if is_cancelled and is_cancelled():
            raise ImportErrorMessage("用户已取消导入。")
        size, modified = source_signature(source)
        project = self.exporter.export(
            source,
            directory,
            source_size=size,
            source_modified_at=modified,
            progress=progress,
            is_cancelled=is_cancelled,
        )
        return ImportResult(project, False)
