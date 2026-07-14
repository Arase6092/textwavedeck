"""真实 Windows Qt 平台的滚筒与单页舞台截图冒烟测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT = Path(r"D:\CodexCache\gesture-ppt-dark-theatre-qa")
os.environ["LOCALAPPDATA"] = str(OUTPUT / "localapp")
os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

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
    """捕获两种窗口尺寸下的暗场、覆盖层和舞台状态。"""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    project = _make_project()
    for width, height in ((1440, 900), (1024, 768)):
        window = MainWindow()
        window.resize(width, height)
        window.show()
        app.processEvents()
        empty_path = OUTPUT / f"empty-{width}x{height}.png"
        assert window.grab().save(str(empty_path))

        window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
        app.processEvents()
        stage_default_path = OUTPUT / f"stage-default-{width}x{height}.png"
        assert window.grab().save(str(stage_default_path))
        window.toggle_workspace_mode()
        QTest.qWait(850)
        app.processEvents()
        carousel_chrome_path = OUTPUT / f"carousel-chrome-{width}x{height}.png"
        assert window.grab().save(str(carousel_chrome_path))
        window.chrome.hide_now()
        QTest.qWait(200)
        app.processEvents()
        carousel_hidden_path = OUTPUT / f"carousel-hidden-{width}x{height}.png"
        assert window.grab().save(str(carousel_hidden_path))

        window.workspace.enter_stage(3)
        QTest.qWait(300)
        window.chrome.reveal_all()
        app.processEvents()
        stage_chrome_path = OUTPUT / f"stage-chrome-{width}x{height}.png"
        assert window.grab().save(str(stage_chrome_path))
        window.chrome.hide_now()
        QTest.qWait(200)
        app.processEvents()
        stage_hidden_path = OUTPUT / f"stage-hidden-{width}x{height}.png"
        assert window.grab().save(str(stage_hidden_path))

        window.status_label.setText("正在导出第 4 / 7 页")
        window._set_importing_ui(True)
        window.progress.setValue(57)
        QTest.qWait(200)
        app.processEvents()
        assert not window.top_bar.isHidden()
        assert not window.bottom_bar.isHidden()
        importing_path = OUTPUT / f"importing-{width}x{height}.png"
        assert window.grab().save(str(importing_path))
        window._set_importing_ui(False)
        window.project = None
        window.close()
        app.processEvents()
        print(
            "VISUAL_OK",
            empty_path,
            stage_default_path,
            carousel_chrome_path,
            carousel_hidden_path,
            stage_chrome_path,
            stage_hidden_path,
            importing_path,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
