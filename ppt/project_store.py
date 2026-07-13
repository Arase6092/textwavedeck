"""项目缓存目录和 project.json 读写。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from models.slide_project import SlideProject, source_signature


def cache_root() -> Path:
    """返回当前用户的缓存根目录。"""
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "GesturePPT" / "projects"


def calculate_cache_key(source_path: str | Path) -> str:
    """根据绝对路径、文件大小和修改时间计算稳定 SHA-256 键。"""
    path = Path(source_path).resolve()
    size, modified = source_signature(path)
    payload = f"{path}|{size}|{modified:.6f}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def project_dir(cache_key: str, root: Path | None = None) -> Path:
    """返回指定缓存键的目录。"""
    return (root or cache_root()) / cache_key


def save_project(project: SlideProject, directory: Path) -> None:
    """原子写入 project.json，避免写入中断导致 JSON 损坏。"""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "project.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def load_project(directory: Path) -> SlideProject:
    """读取项目元数据。"""
    data = json.loads((directory / "project.json").read_text(encoding="utf-8"))
    return SlideProject.from_dict(data)


def is_cache_valid(directory: Path, source_path: str | Path) -> bool:
    """校验源文件、schema、页面数量和所有图片是否可读。"""
    try:
        source = Path(source_path).resolve()
        metadata = json.loads((directory / "project.json").read_text(encoding="utf-8"))
        project = SlideProject.from_dict(metadata)
        size, modified = source_signature(source)
        if project.schema_version != 1 or project.source_path != str(source):
            return False
        if project.source_size != size or abs(project.source_modified_at - modified) > 1e-3:
            return False
        if project.cache_key != calculate_cache_key(source):
            return False
        if not project.pages or int(metadata.get("slide_count", -1)) != project.slide_count:
            return False
        if [page.index for page in project.pages] != list(range(project.slide_count)):
            return False
        return all(Path(page.image_path).is_file() and Path(page.thumbnail_path).is_file() for page in project.pages)
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return False


def remove_cache(directory: Path) -> None:
    """删除指定缓存目录，失败时保留异常给调用方处理。"""
    if directory.exists():
        shutil.rmtree(directory)
