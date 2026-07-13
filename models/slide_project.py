"""幻灯片项目数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SlidePage:
    """单页幻灯片及其缩略图路径。"""

    index: int
    image_path: str
    thumbnail_path: str

    def to_dict(self) -> dict[str, Any]:
        """将页面转换为可持久化字典。"""
        return {"index": self.index, "image_path": self.image_path, "thumbnail_path": self.thumbnail_path}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlidePage":
        """从字典恢复页面。"""
        return cls(int(data["index"]), str(data["image_path"]), str(data["thumbnail_path"]))


@dataclass(slots=True)
class SlideProject:
    """PPT 导出后的项目元数据。"""

    source_path: str
    cache_key: str
    source_size: int
    source_modified_at: float
    export_width: int = 1920
    export_height: int = 1080
    current_slide: int = 0
    pages: list[SlidePage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: int = 1

    @property
    def slide_count(self) -> int:
        """返回页面数量。"""
        return len(self.pages)

    def to_dict(self) -> dict[str, Any]:
        """序列化项目元数据。"""
        return {
            "schema_version": self.schema_version,
            "source_path": self.source_path,
            "source_size": self.source_size,
            "source_modified_at": self.source_modified_at,
            "cache_key": self.cache_key,
            "slide_count": self.slide_count,
            "current_slide": self.current_slide,
            "export_width": self.export_width,
            "export_height": self.export_height,
            "created_at": self.created_at,
            "pages": [page.to_dict() for page in self.pages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlideProject":
        """从 project.json 恢复项目。"""
        pages = [SlidePage.from_dict(item) for item in data.get("pages", [])]
        project = cls(
            source_path=str(data["source_path"]),
            cache_key=str(data.get("cache_key", "")),
            source_size=int(data["source_size"]),
            source_modified_at=float(data["source_modified_at"]),
            export_width=int(data.get("export_width", 1920)),
            export_height=int(data.get("export_height", 1080)),
            current_slide=int(data.get("current_slide", 0)),
            pages=pages,
            created_at=str(data.get("created_at", "")),
            schema_version=int(data.get("schema_version", 1)),
        )
        project.current_slide = max(0, min(project.current_slide, max(0, project.slide_count - 1)))
        return project


def source_signature(path: Path) -> tuple[int, float]:
    """读取源文件大小和修改时间，统一使用绝对路径。"""
    stat = path.resolve().stat()
    return stat.st_size, stat.st_mtime
