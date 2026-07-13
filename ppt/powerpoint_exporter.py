"""PowerPoint COM 导出器。"""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable

from PIL import Image

from models.slide_project import SlidePage, SlideProject
from ppt.project_store import calculate_cache_key, save_project

LOGGER = logging.getLogger(__name__)


class ExportError(RuntimeError):
    """导出失败时向界面传递的中文异常。"""


class PowerPointExporter:
    """使用 PowerPoint COM 将每页导出为 PNG。"""

    def export(
        self,
        source: Path,
        target_dir: Path,
        *,
        source_size: int,
        source_modified_at: float,
        progress: Callable[[int, str], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> SlideProject:
        """在临时目录完成导出、校验并原子替换正式缓存。"""
        # 先创建缓存父目录，再在同一文件系统内写临时目录，确保 replace 是原子的。
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="gesture-ppt-", dir=target_dir.parent))
        powerpoint = presentation = None
        started = time.perf_counter()
        try:
            try:
                import pythoncom
                import win32com.client
            except ImportError as exc:
                raise ExportError("未安装 pywin32，无法调用 PowerPoint。请先安装依赖。") from exc
            pythoncom.CoInitialize()
            try:
                powerpoint = win32com.client.DispatchEx("PowerPoint.Application")
                powerpoint.Visible = False
                presentation = powerpoint.Presentations.Open(str(source), ReadOnly=True, WithWindow=False)
            except Exception as exc:
                raise ExportError("无法启动或打开 Microsoft PowerPoint，请确认已安装并检查文件是否损坏或受密码保护。") from exc
            slides_dir = temporary / "slides"
            thumbnails_dir = temporary / "thumbnails"
            slides_dir.mkdir()
            thumbnails_dir.mkdir()
            count = int(presentation.Slides.Count)
            if count <= 0:
                raise ExportError("演示文稿没有可导出的页面。")
            if progress:
                progress(5, f"正在导出 {count} 页")
            pages: list[SlidePage] = []
            for index in range(1, count + 1):
                if is_cancelled and is_cancelled():
                    raise ExportError("用户已取消导入。")
                raw = temporary / f"raw_{index:03d}.png"
                presentation.Slides(index).Export(str(raw), "PNG", 1920, 1080)
                image_path = slides_dir / f"slide_{index:03d}.png"
                thumbnail_path = thumbnails_dir / f"slide_{index:03d}.jpg"
                raw.replace(image_path)
                with Image.open(image_path) as image:
                    image.load()
                    thumb = image.convert("RGB")
                    thumb.thumbnail((240, 135), Image.Resampling.LANCZOS)
                    thumb.save(thumbnail_path, "JPEG", quality=88, optimize=True)
                pages.append(SlidePage(index=index - 1, image_path=str(image_path), thumbnail_path=str(thumbnail_path)))
                if progress:
                    progress(5 + int(index / count * 90), f"已导出第 {index} / {count} 页")
            project = SlideProject(
                source_path=str(source),
                cache_key=calculate_cache_key(source),
                source_size=source_size,
                source_modified_at=source_modified_at,
                pages=pages,
            )
            if target_dir.exists():
                shutil.rmtree(target_dir)
            temporary.replace(target_dir)
            # 替换目录后路径需要指向正式缓存目录，而不是临时目录。
            for page in project.pages:
                page.image_path = str(target_dir / "slides" / Path(page.image_path).name)
                page.thumbnail_path = str(target_dir / "thumbnails" / Path(page.thumbnail_path).name)
            save_project(project, target_dir)
            LOGGER.info("PPT 导出完成：%s，页面数=%s，耗时=%.2fs", source, count, time.perf_counter() - started)
            if progress:
                progress(100, "导入完成")
            return project
        except ExportError:
            raise
        except Exception as exc:
            LOGGER.exception("PPT 导出异常：%s", source)
            raise ExportError(f"导出失败：{exc}") from exc
        finally:
            try:
                if presentation is not None:
                    presentation.Close()
                if powerpoint is not None:
                    powerpoint.Quit()
            except Exception:
                LOGGER.exception("关闭 PowerPoint 进程时发生异常")
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except (ImportError, Exception):
                pass
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
