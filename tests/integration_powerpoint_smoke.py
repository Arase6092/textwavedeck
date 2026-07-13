"""Windows + PowerPoint 真机冒烟测试，默认不被 pytest 自动收集。"""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

import pythoncom
import win32com.client
from PIL import Image

# 手动执行 tests 下脚本时，显式加入项目根目录以导入应用包。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ppt.importer import PPTImporter


def create_sample_presentation(path: Path, width: float, height: float) -> None:
    """通过 PowerPoint COM 创建一页含中文文本的测试演示文稿。"""
    powerpoint = presentation = None
    pythoncom.CoInitialize()
    try:
        powerpoint = win32com.client.DispatchEx("PowerPoint.Application")
        presentation = powerpoint.Presentations.Add()
        presentation.PageSetup.SlideWidth = width
        presentation.PageSetup.SlideHeight = height
        slide = presentation.Slides.Add(1, 12)  # 12 = ppLayoutBlank
        text_box = slide.Shapes.AddTextbox(1, 120, 120, 900, 180)
        text_box.TextFrame.TextRange.Text = "手势控制 PPT 集成测试"
        presentation.SaveAs(str(path), 24)  # 24 = ppSaveAsOpenXMLPresentation
    finally:
        if presentation is not None:
            presentation.Close()
        if powerpoint is not None:
            powerpoint.Quit()
        pythoncom.CoUninitialize()


def main() -> int:
    """创建样本、导出图片并验证第二次导入命中缓存。"""
    base = Path(r"D:\CodexCache")
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gesture-ppt-integration-", dir=base) as temporary:
        root = Path(temporary)
        importer = PPTImporter(cache_base=root / "cache")
        cases = [
            ("16x9", 960.0, 540.0, (3840, 2160), (640, 360)),
            ("4x3", 720.0, 540.0, (3840, 2880), (640, 480)),
        ]
        results: list[str] = []
        for name, width, height, expected_image, expected_thumbnail in cases:
            source = root / f"中文 路径 {name} 集成测试.pptx"
            create_sample_presentation(source, width, height)
            first = importer.import_file(source)
            assert first.project.slide_count == 1
            assert not first.cache_hit
            page = first.project.pages[0]
            with Image.open(page.image_path) as image:
                assert image.size == expected_image
                image.verify()
            with Image.open(page.thumbnail_path) as thumbnail:
                assert thumbnail.size == expected_thumbnail
                thumbnail.verify()
            second = importer.import_file(source)
            assert second.cache_hit
            results.append(f"{name}={expected_image[0]}x{expected_image[1]}")
        print(f"COM_EXPORT_OK {' '.join(results)} cache_hit=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
