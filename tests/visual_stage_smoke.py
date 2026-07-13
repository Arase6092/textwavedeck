"""真实 Windows Qt 平台的滚筒与单页舞台截图冒烟测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT = Path(r"D:\CodexCache\gesture-ppt-stage-qa")
os.environ["LOCALAPPDATA"] = str(OUTPUT / "localapp")
os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from models.slide_project import SlidePage, SlideProject


def _make_project() -> SlideProject:
    """生成带明显构图差异的七页测试项目。"""
    slides = OUTPUT / "slides"
    thumbnails = OUTPUT / "thumbnails"
    slides.mkdir(parents=True, exist_ok=True)
    thumbnails.mkdir(parents=True, exist_ok=True)
    colors = ["#002FA7", "#E4002B", "#20242B", "#4B5563", "#2563EB", "#111827", "#6B7280"]
    pages: list[SlidePage] = []
    for index, color in enumerate(colors):
        image = Image.new("RGB", (1600, 900), "#FFFFFF")
        draw = ImageDraw.Draw(image)
        draw.rectangle((90, 80, 1510, 94), fill=color)
        draw.rectangle((90, 150, 650, 198), fill="#20242B")
        draw.rectangle((90, 230, 520, 250), fill="#C7CCD4")
        draw.rectangle((820, 150, 1510, 760), fill="#E4E7EB")
        draw.rectangle((1030, 310, 1300, 600), fill=color)
        draw.text((90, 720), f"PAGE {index + 1:02d}", fill=color)
        image_path = slides / f"slide_{index + 1:03d}.png"
        thumbnail_path = thumbnails / f"slide_{index + 1:03d}.jpg"
        image.save(image_path, "PNG")
        thumb = image.copy()
        thumb.thumbnail((640, 360), Image.Resampling.LANCZOS)
        thumb.save(thumbnail_path, "JPEG", quality=90)
        pages.append(SlidePage(index, str(image_path), str(thumbnail_path)))
    return SlideProject("visual-smoke.pptx", "visual-smoke", 1, 1.0, current_slide=3, pages=pages)


def main() -> int:
    """捕获两种窗口尺寸下的滚筒与单页舞台。"""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    project = _make_project()
    for width, height in ((1440, 900), (1024, 768)):
        window = MainWindow()
        window.resize(width, height)
        window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
        window.show()
        app.processEvents()
        carousel_path = OUTPUT / f"carousel-{width}x{height}.png"
        assert window.grab().save(str(carousel_path))
        window.workspace.enter_stage(3)
        app.processEvents()
        stage_path = OUTPUT / f"stage-{width}x{height}.png"
        assert window.grab().save(str(stage_path))
        window.project = None
        window.close()
        app.processEvents()
        print(f"VISUAL_OK {carousel_path} {stage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
