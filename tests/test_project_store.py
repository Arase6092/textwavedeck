import json
import os
import time
from pathlib import Path

from models.slide_project import SlidePage, SlideProject
from ppt.project_store import calculate_cache_key, is_cache_valid, load_project, save_project


def _make_source(tmp_path: Path) -> Path:
    source = tmp_path / "演示 文稿.pptx"
    source.write_bytes(b"ppt-fixture")
    return source


def test_cache_key_changes_when_source_changes(tmp_path):
    source = _make_source(tmp_path)
    first = calculate_cache_key(source)
    time.sleep(0.01)
    source.write_bytes(b"ppt-fixture-updated")
    os.utime(source, None)
    assert calculate_cache_key(source) != first


def test_project_round_trip_and_cache_validation(tmp_path):
    source = _make_source(tmp_path)
    cache = tmp_path / "cache"
    slide = cache / "slides" / "slide_001.png"
    thumb = cache / "thumbnails" / "slide_001.jpg"
    slide.parent.mkdir(parents=True)
    thumb.parent.mkdir(parents=True)
    slide.write_bytes(b"png")
    thumb.write_bytes(b"jpg")
    stat = source.stat()
    project = SlideProject(
        source_path=str(source.resolve()),
        cache_key=calculate_cache_key(source),
        source_size=stat.st_size,
        source_modified_at=stat.st_mtime,
        pages=[SlidePage(0, str(slide), str(thumb))],
    )
    save_project(project, cache)
    restored = load_project(cache)
    assert restored.slide_count == 1
    assert is_cache_valid(cache, source)
    data = json.loads((cache / "project.json").read_text(encoding="utf-8"))
    data["schema_version"] = 99
    (cache / "project.json").write_text(json.dumps(data), encoding="utf-8")
    assert not is_cache_valid(cache, source)
