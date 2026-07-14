# Stage Recomposition Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a default single-slide presentation mode and a hidden `Ctrl+Alt+M` transition that visually recomposes the current slide into the 5-page cylindrical stage.

**Architecture:** Keep `MainWindow` responsible for commands and shortcuts, `StageWorkspace` responsible for mode state, and move the temporary transition drawing into a focused overlay widget. The carousel keeps its existing interaction model while exposing deterministic geometry for the overlay and tests.

**Tech Stack:** Python 3.11, PySide6 Graphics/View widgets, Qt property animations, pytest, existing visual smoke script.

---

## File Structure

- Modify `app/main_window.py`: add the hidden mode shortcut, default imported projects into single-slide presentation, update mode tooltips.
- Modify `widgets/stage_workspace.py`: add `stage` startup support, route animated mode changes through a recomposition overlay, keep reduced-motion fallback.
- Create `widgets/stage_recomposition_overlay.py`: draw temporary slide snapshots during the transition with a Qt `progress` property.
- Modify `widgets/cylinder_carousel.py`: expose current carousel target layout without changing drag, wheel, inertia, or activation behavior.
- Modify `widgets/cylinder_geometry.py`: add a small immutable layout data object used by carousel and overlay.
- Modify `tests/test_stage_interactions.py`: add default-stage, shortcut, overlay, and reduced-motion regression tests.
- Modify `tests/visual_stage_smoke.py`: capture default single-slide state first, then the carousel state after toggling.

---

### Task 1: Default Presentation Mode and Hidden Shortcut

**Files:**
- Modify: `app/main_window.py`
- Modify: `widgets/stage_workspace.py`
- Test: `tests/test_stage_interactions.py`

- [ ] **Step 1: Write failing tests for default stage mode and shortcut**

Add these tests to `tests/test_stage_interactions.py`:

```python
from types import SimpleNamespace
from PySide6.QtGui import QKeySequence


def test_workspace_can_start_in_single_slide_stage(qapp, pages):
    """导入后可直接进入普通单页放映，而不是先显示滚筒。"""
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_project(project, current_index=1, initial_mode="stage")
    assert workspace.mode == "stage"
    assert workspace.current_index == 1
    assert workspace.viewer.isVisible()
    assert workspace._transition.state() == QAbstractAnimation.State.Stopped


def test_main_window_import_defaults_to_single_slide_stage(qapp, monkeypatch, tmp_path, pages):
    """主窗口导入完成后默认是普通放映界面。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    assert window.workspace.mode == "stage"
    assert window.mode_button.toolTip() == "进入页面滚筒"
    window.close()


def test_hidden_mode_shortcut_is_ctrl_alt_m(qapp, monkeypatch, tmp_path):
    """隐藏模式快捷键固定为 Ctrl+Alt+M，避免占用翻页和系统常用键。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    assert window.toggle_presentation_mode_action.shortcut() == QKeySequence("Ctrl+Alt+M")
    window.close()
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -q
```

Expected: fails because `initial_mode` and `toggle_presentation_mode_action` do not exist, and import still defaults to carousel.

- [ ] **Step 3: Implement default stage mode in `StageWorkspace.set_project`**

Change the method signature and body in `widgets/stage_workspace.py`:

```python
def set_project(self, project: SlideProject, current_index: int = 0, *, initial_mode: str = "carousel") -> None:
    """加载项目，并按指定初始模式进入单页放映或滚筒。"""
    self._pages = list(project.pages)
    self._current_index = self._clamp_index(current_index)
    self.carousel.set_pages(self._pages, self._current_index)
    if initial_mode == "stage" and self._pages:
        self.viewer.show_image(self._pages[self._current_index].image_path)
        self._mode = "stage"
        self._finish_mode_immediately("stage")
        self.page_changed.emit(self._current_index)
        self.zoom_changed.emit(self.viewer.zoom_factor)
        return
    self._mode = "carousel"
    self._finish_mode_immediately("carousel")
```

- [ ] **Step 4: Add the hidden shortcut and default import behavior in `MainWindow`**

In `app/main_window.py`, create the action in `_create_actions`:

```python
self.toggle_presentation_mode_action = QAction("切换页面滚筒", self)
self.toggle_presentation_mode_action.setToolTip("切换单页放映/页面滚筒（Ctrl+Alt+M）")
self.toggle_presentation_mode_action.setShortcut(QKeySequence("Ctrl+Alt+M"))
self.toggle_presentation_mode_action.triggered.connect(self.toggle_workspace_mode)
```

Add it to the `self.addAction(...)` loop.

In `_on_import_completed`, load the project with:

```python
self.workspace.set_project(self.project, current, initial_mode="stage")
```

In `_on_workspace_mode_changed`, use:

```python
self.mode_button.setToolTip("进入页面滚筒" if is_stage else "返回单页放映")
self.status_label.setText("单页放映" if is_stage else "页面滚筒")
```

- [ ] **Step 5: Run focused tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -q
```

Expected: new tests pass, existing tests still pass or reveal transition-specific failures handled in later tasks.

Commit:

```powershell
git add app/main_window.py widgets/stage_workspace.py tests/test_stage_interactions.py
git commit -m "feat: default to single slide presentation mode"
```

---

### Task 2: Carousel Target Layout Interface

**Files:**
- Modify: `widgets/cylinder_geometry.py`
- Modify: `widgets/cylinder_carousel.py`
- Test: `tests/test_stage_interactions.py`

- [ ] **Step 1: Write failing tests for target layout**

Add this test:

```python
def test_carousel_exposes_five_target_layers(qapp, pages):
    """滚筒暴露稳定的五页目标布局，供重组转场复用。"""
    carousel = CylinderCarousel()
    carousel.resize(1200, 720)
    carousel.set_pages(pages * 3, current_index=4)
    layers = carousel.target_layers(4)
    assert [layer.index for layer in layers] == [2, 3, 4, 5, 6]
    assert layers[2].relative == 0
    assert layers[2].opacity == 1.0
    assert layers[0].opacity < layers[1].opacity < layers[2].opacity
    assert layers[4].opacity < layers[3].opacity < layers[2].opacity
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py::test_carousel_exposes_five_target_layers -q
```

Expected: fails because `target_layers` is not defined.

- [ ] **Step 3: Add `CarouselLayer` to `widgets/cylinder_geometry.py`**

```python
@dataclass(frozen=True, slots=True)
class CarouselLayer:
    """滚筒中可见页面的归一化目标布局。"""

    index: int
    relative: int
    x_factor: float
    scale: float
    horizontal_scale: float
    opacity: float
    z_value: float
```

- [ ] **Step 4: Add `target_layers` to `CylinderCarousel`**

```python
def target_layers(self, center_index: int | None = None) -> list[CarouselLayer]:
    """返回中心页左右两级共五页的目标布局。"""
    if not self._pages:
        return []
    center = self._current_index if center_index is None else max(0, min(int(center_index), len(self._pages) - 1))
    layers: list[CarouselLayer] = []
    for relative in range(-2, 3):
        index = center + relative
        if index < 0 or index >= len(self._pages):
            continue
        pose = cylinder_pose(float(relative))
        if not pose.visible:
            continue
        layers.append(
            CarouselLayer(
                index=index,
                relative=relative,
                x_factor=pose.x_factor,
                scale=pose.scale,
                horizontal_scale=pose.horizontal_scale,
                opacity=pose.opacity,
                z_value=pose.z_value,
            )
        )
    return layers
```

Update imports in `widgets/cylinder_carousel.py`:

```python
from widgets.cylinder_geometry import CarouselLayer, cylinder_pose, inertia_target, snap_index
```

- [ ] **Step 5: Run focused geometry tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cylinder_geometry.py tests\test_stage_interactions.py::test_carousel_exposes_five_target_layers -q
```

Expected: pass.

Commit:

```powershell
git add widgets/cylinder_geometry.py widgets/cylinder_carousel.py tests/test_stage_interactions.py
git commit -m "feat: expose carousel target layers"
```

---

### Task 3: Stage Recomposition Overlay

**Files:**
- Create: `widgets/stage_recomposition_overlay.py`
- Modify: `widgets/stage_workspace.py`
- Test: `tests/test_stage_interactions.py`

- [ ] **Step 1: Write failing overlay tests**

Add these tests:

```python
def test_workspace_uses_recomposition_overlay_for_mode_change(qapp, pages):
    """普通放映进入滚筒时显示重组 overlay，并启动可中断动画。"""
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.resize(1200, 720)
    workspace.set_project(project, current_index=1, initial_mode="stage")
    workspace.show_carousel()
    assert workspace.mode == "carousel"
    assert workspace._overlay.isVisible()
    assert workspace._transition.state() == QAbstractAnimation.State.Running
    workspace._transition.stop()
    workspace._finish_mode_immediately("carousel")


def test_reduced_motion_skips_recomposition_overlay(qapp, pages):
    """减少动态模式不播放大幅空间重组。"""
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_reduced_motion(True)
    workspace.set_project(project, current_index=1, initial_mode="stage")
    workspace.show_carousel()
    assert workspace.mode == "carousel"
    assert not workspace._overlay.isVisible()
    assert workspace._transition.state() == QAbstractAnimation.State.Stopped
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py::test_workspace_uses_recomposition_overlay_for_mode_change tests\test_stage_interactions.py::test_reduced_motion_skips_recomposition_overlay -q
```

Expected: fails because `_overlay` does not exist.

- [ ] **Step 3: Create `StageRecompositionOverlay`**

Create `widgets/stage_recomposition_overlay.py` with:

```python
"""单页放映与圆柱滚筒之间的舞台重组过渡层。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from app.theme import FOCUS_BLUE, STAGE_SAFE_MARGIN, stage_background_gradient
from models.slide_project import SlidePage
from widgets.cylinder_geometry import CarouselLayer


class StageRecompositionOverlay(QWidget):
    """只在转场期间绘制页面快照，避免真实控件布局跳变。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._pages: list[SlidePage] = []
        self._layers: list[CarouselLayer] = []
        self._direction = "to_carousel"
        self._progress = 0.0
        self._pixmaps: dict[str, QPixmap] = {}
        self.hide()

    def configure(self, pages: list[SlidePage], layers: list[CarouselLayer], *, direction: str) -> None:
        """准备本次转场的页面和方向。"""
        self._pages = list(pages)
        self._layers = list(layers)
        self._direction = direction
        self._progress = 0.0
        self._pixmaps.clear()
        self.update()

    def get_progress(self) -> float:
        """返回动画进度。"""
        return self._progress

    def set_progress(self, value: float) -> None:
        """设置动画进度并重绘。"""
        self._progress = max(0.0, min(float(value), 1.0))
        self.update()

    progress = Property(float, get_progress, set_progress)
```

Then add paint helpers in the same class:

```python
    def paintEvent(self, _event) -> None:  # noqa: N802
        """绘制固定背景和正在重组的页面。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), stage_background_gradient(QRectF(self.rect())))
        progress = self._ease(self._progress)
        ordered = sorted(self._layers, key=lambda layer: layer.z_value)
        for layer in ordered:
            pixmap = self._load_pixmap(layer.index)
            if pixmap.isNull():
                continue
            rect, opacity = self._layer_state(layer, pixmap, progress)
            painter.setOpacity(opacity)
            self._draw_shadow(painter, rect, layer.relative)
            painter.drawPixmap(rect, pixmap, QRectF(pixmap.rect()))
        painter.setOpacity(1.0)

    def _load_pixmap(self, index: int) -> QPixmap:
        """按需加载页面图，优先使用原图以保证转场清晰。"""
        if index < 0 or index >= len(self._pages):
            return QPixmap()
        path = self._pages[index].image_path or self._pages[index].thumbnail_path
        cached = self._pixmaps.get(path)
        if cached is not None:
            return cached
        pixmap = QPixmap(str(Path(path)))
        self._pixmaps[path] = pixmap
        return pixmap

    def _layer_state(self, layer: CarouselLayer, pixmap: QPixmap, progress: float) -> tuple[QRectF, float]:
        """计算页面在当前进度下的位置和透明度。"""
        stage = self._stage_rect(pixmap)
        carousel = self._carousel_rect(layer, pixmap)
        side = self._side_start_rect(layer, carousel)
        if layer.relative == 0:
            start = stage if self._direction == "to_carousel" else carousel
            end = carousel if self._direction == "to_carousel" else stage
            opacity_start = 1.0
            opacity_end = 1.0
        elif self._direction == "to_carousel":
            start = side
            end = carousel
            opacity_start = 0.0
            opacity_end = layer.opacity
        else:
            start = carousel
            end = side
            opacity_start = layer.opacity
            opacity_end = 0.0
        return self._lerp_rect(start, end, progress), opacity_start + (opacity_end - opacity_start) * progress
```

Then add the remaining helpers:

```python
    def _stage_rect(self, pixmap: QPixmap) -> QRectF:
        """计算普通放映状态下的适应窗口矩形。"""
        available_width = max(1.0, self.width() - STAGE_SAFE_MARGIN * 2)
        available_height = max(1.0, self.height() - STAGE_SAFE_MARGIN * 2)
        factor = min(available_width / max(1, pixmap.width()), available_height / max(1, pixmap.height()))
        width = pixmap.width() * factor
        height = pixmap.height() * factor
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def _carousel_rect(self, layer: CarouselLayer, pixmap: QPixmap) -> QRectF:
        """计算圆柱滚筒目标矩形。"""
        center_x = self.width() / 2
        center_y = self.height() / 2 - 8
        radius = min(self.width() * 0.47, 620.0)
        target_height = self.height() * 0.58
        height = target_height * layer.scale
        aspect = pixmap.width() / max(1, pixmap.height())
        width = height * aspect * layer.horizontal_scale
        depth_drop = (1.0 - layer.scale) * 110.0
        return QRectF(center_x + layer.x_factor * radius - width / 2, center_y + depth_drop - height / 2, width, height)

    def _side_start_rect(self, layer: CarouselLayer, carousel: QRectF) -> QRectF:
        """侧页从舞台暗处进入或退场。"""
        direction = -1 if layer.relative < 0 else 1
        x = -carousel.width() * 0.72 if direction < 0 else self.width() - carousel.width() * 0.28
        y = carousel.y() + carousel.height() * 0.18
        return QRectF(x, y, carousel.width() * 0.82, carousel.height() * 0.82)

    def _draw_shadow(self, painter: QPainter, rect: QRectF, relative: int) -> None:
        """给页面绘制低调阴影和中央页焦点边框。"""
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 95 if relative == 0 else 55))
        painter.drawRoundedRect(rect.adjusted(0, 14, 0, 18), 8, 8)
        if relative == 0:
            painter.setPen(QColor(FOCUS_BLUE))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 4, 4)
        painter.restore()

    @staticmethod
    def _lerp_rect(start: QRectF, end: QRectF, progress: float) -> QRectF:
        """线性插值矩形。"""
        return QRectF(
            start.x() + (end.x() - start.x()) * progress,
            start.y() + (end.y() - start.y()) * progress,
            start.width() + (end.width() - start.width()) * progress,
            start.height() + (end.height() - start.height()) * progress,
        )

    @staticmethod
    def _ease(value: float) -> float:
        """平滑进度，让重组转场有轻微缓入缓出。"""
        value = max(0.0, min(float(value), 1.0))
        return value * value * (3.0 - 2.0 * value)
```

- [ ] **Step 4: Wire overlay into `StageWorkspace`**

In `widgets/stage_workspace.py`, import:

```python
from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, Signal
from widgets.stage_recomposition_overlay import StageRecompositionOverlay
```

Create the overlay and animation in `__init__`:

```python
self._overlay = StageRecompositionOverlay(self)
self._transition = QPropertyAnimation(self._overlay, b"progress", self)
self._transition.finished.connect(self._finish_transition)
```

Replace `_start_transition` with overlay-driven logic:

```python
def _start_transition(self, mode: str) -> None:
    """用舞台重组 overlay 切换滚筒和单页放映。"""
    self._transition.stop()
    self._transition_target = mode
    if self._reduced_motion:
        self._finish_mode_immediately(mode)
        return
    direction = "to_carousel" if mode == "carousel" else "to_stage"
    if mode == "carousel":
        self.carousel.select_page(self._current_index, animate=False)
    layers = self.carousel.target_layers(self._current_index)
    self._overlay.setGeometry(self.rect())
    self._overlay.configure(self._pages, layers, direction=direction)
    self._overlay.show()
    self._overlay.raise_()
    self.carousel.setEnabled(False)
    self.viewer.setEnabled(False)
    self._transition.setStartValue(0.0)
    self._transition.setEndValue(1.0)
    self._transition.setDuration(720)
    self._transition.setEasingCurve(QEasingCurve.Type.OutCubic)
    self._transition.start()
```

Update `_finish_mode_immediately` to hide the overlay and restore real widgets.

Add resize handling:

```python
def resizeEvent(self, event) -> None:  # noqa: N802
    """窗口变化时让转场 overlay 覆盖整个舞台。"""
    super().resizeEvent(event)
    self._overlay.setGeometry(self.rect())
```

- [ ] **Step 5: Run overlay tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -q
```

Expected: pass.

Commit:

```powershell
git add widgets/stage_recomposition_overlay.py widgets/stage_workspace.py tests/test_stage_interactions.py
git commit -m "feat: add stage recomposition transition"
```

---

### Task 4: Visual Smoke and Full Verification

**Files:**
- Modify: `tests/visual_stage_smoke.py`
- Optional Modify: `AGENTS.md` only if a new reusable pitfall is discovered

- [ ] **Step 1: Update visual smoke screenshots**

In `tests/visual_stage_smoke.py`, after `_on_import_completed`, rename the first imported screenshot from carousel to stage:

```python
stage_default_path = OUTPUT / f"stage-default-{width}x{height}.png"
assert window.grab().save(str(stage_default_path))
window.toggle_workspace_mode()
QTest.qWait(850)
app.processEvents()
carousel_chrome_path = OUTPUT / f"carousel-chrome-{width}x{height}.png"
assert window.grab().save(str(carousel_chrome_path))
```

Also include `stage_default_path` in the printed `VISUAL_OK` line.

- [ ] **Step 2: Run full automated tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all tests pass.

- [ ] **Step 3: Run compile check**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app widgets tests main.py
```

Expected: no output and exit code 0.

- [ ] **Step 4: Run visual smoke test**

Run:

```powershell
.\.venv\Scripts\python.exe tests\visual_stage_smoke.py
```

Expected: `VISUAL_OK` lines and screenshots under `D:\CodexCache\gesture-ppt-dark-theatre-qa`.

- [ ] **Step 5: Final commit**

Run:

```powershell
git status --short
git add tests/visual_stage_smoke.py
git commit -m "test: update visual smoke for presentation mode"
```

If `git status --short` shows no visual smoke changes, skip this commit and report that the earlier implementation commits contain all source changes.

---

## Self-Review

- Spec coverage: default single-slide start, `Ctrl+Alt+M`, visible recomposition, reduced motion, non-global shortcut, and first-phase exclusions are each covered by a task.
- Placeholder scan: no incomplete markers remain in the plan body.
- Type consistency: `initial_mode`, `target_layers`, `CarouselLayer`, `_overlay`, and `StageRecompositionOverlay.progress` are introduced before later use.
- Scope check: this plan only changes viewing mode, animation, shortcut, and tests; it does not introduce gesture recognition, PPT object animation, presenter notes, or multi-display behavior.