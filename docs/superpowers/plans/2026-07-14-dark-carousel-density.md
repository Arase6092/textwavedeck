# Dark Carousel Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将手势滚筒改为已确认的石墨青绿四段渐变，并通过共享响应式几何减少舞台留白、保持五页侧向提示和转场连续性。

**Architecture:** `widgets/cylinder_geometry.py` 提供不依赖 Qt 的舞台几何和页面适配函数，`CylinderCarousel` 与 `StageRecompositionOverlay` 只消费该结果，不再各自维护尺寸常量。`app/theme.py` 作为唯一颜色令牌来源，同时生成 QSS 和 QPainter 四段渐变。

**Tech Stack:** Python 3.11、PySide6、pytest、Pillow、Windows Qt 平台视觉烟测。

---

## 文件结构

- Modify: `app/theme.py` - 四段石墨青绿舞台渐变令牌和生成函数。
- Modify: `widgets/cylinder_geometry.py` - 共享滚筒舞台几何和页面宽高比适配。
- Modify: `widgets/cylinder_carousel.py` - 使用共享几何布局真实滚筒并降低蓝色阴影强度。
- Modify: `widgets/stage_recomposition_overlay.py` - 使用共享几何计算转场目标矩形。
- Modify: `tests/test_theme.py` - 锁定四段渐变色值与停点。
- Modify: `tests/test_cylinder_geometry.py` - 锁定双尺寸舞台参数与页面适配结果。
- Modify: `tests/test_stage_interactions.py` - 锁定真实滚筒和 overlay 的响应式尺寸。
- Verify: `tests/visual_stage_smoke.py` - 生成 PPT、滚筒、手势单页和返回 PPT 的双尺寸截图。
- Modify: `AGENTS.md` - 仅在出现新的可复用错误或边界时追加错误记录。

### Task 0: 建立干净执行基线

**Files:**
- Existing modifications: `AGENTS.md`
- Existing modifications: `README.md`
- Existing modifications: `app/main_window.py`
- Existing modifications: `widgets/slide_viewer.py`
- Existing modifications: `tests/test_stage_interactions.py`
- Existing modifications: `tests/visual_stage_smoke.py`

- [ ] **Step 1: 验证现有 PPT/手势交互修复**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q app widgets tests main.py
```

Expected: 全部测试通过，编译命令退出码为 `0`。

- [ ] **Step 2: 检查现有差异范围**

Run:

```powershell
git diff --check
git status --short
```

Expected: 仅出现已知 PPT/手势修复文件和未跟踪的 `.superpowers/`、`第一阶段执行方案.md`；不暂存未跟踪项。

- [ ] **Step 3: 提交现有交互修复**

```powershell
git add AGENTS.md README.md app/main_window.py widgets/slide_viewer.py tests/test_stage_interactions.py tests/visual_stage_smoke.py
git commit -m "fix: restore gesture stage interactions"
```

Expected: 形成独立基线提交，新视觉任务可以按文件完整暂存。

### Task 1: 共享响应式滚筒几何

**Files:**
- Modify: `tests/test_cylinder_geometry.py`
- Modify: `widgets/cylinder_geometry.py`

- [ ] **Step 1: 写入失败的舞台几何测试**

在 `tests/test_cylinder_geometry.py` 导入新接口：

```python
from widgets.cylinder_geometry import (
    carousel_viewport_geometry,
    cylinder_pose,
    fit_carousel_page,
    inertia_target,
    snap_index,
)
```

追加测试：

```python
def test_carousel_viewport_geometry_matches_approved_density():
    desktop = carousel_viewport_geometry(1440, 900)
    compact = carousel_viewport_geometry(1024, 768)

    assert desktop.target_height == pytest.approx(603.0)
    assert desktop.max_page_width == pytest.approx(1238.4)
    assert desktop.radius == pytest.approx(660.0)
    assert desktop.center_y == pytest.approx(446.0)
    assert desktop.depth_drop == pytest.approx(92.0)
    assert compact.target_height == pytest.approx(514.56)
    assert compact.radius == pytest.approx(501.76)


def test_fit_carousel_page_caps_wide_slides_without_distortion():
    desktop = carousel_viewport_geometry(1440, 900)
    compact = carousel_viewport_geometry(1024, 768)

    assert fit_carousel_page(desktop, 16 / 9) == pytest.approx((1072.0, 603.0))
    assert fit_carousel_page(compact, 16 / 9) == pytest.approx((880.64, 495.36))
    assert fit_carousel_page(compact, 4 / 3) == pytest.approx((686.08, 514.56))
```

- [ ] **Step 2: 运行测试确认红灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_cylinder_geometry.py -k "carousel_viewport or fit_carousel"
```

Expected: 因 `carousel_viewport_geometry` 和 `fit_carousel_page` 尚未定义而失败。

- [ ] **Step 3: 实现最小纯几何接口**

在 `widgets/cylinder_geometry.py` 增加：

```python
CAROUSEL_HEIGHT_RATIO = 0.67
CAROUSEL_MAX_WIDTH_RATIO = 0.86
CAROUSEL_RADIUS_RATIO = 0.49
CAROUSEL_RADIUS_MAX = 660.0
CAROUSEL_CENTER_Y_OFFSET = -4.0
CAROUSEL_DEPTH_DROP = 92.0


@dataclass(frozen=True, slots=True)
class CarouselViewportGeometry:
    """滚筒和转场共享的舞台尺寸。"""

    center_x: float
    center_y: float
    radius: float
    target_height: float
    max_page_width: float
    depth_drop: float


def carousel_viewport_geometry(width: float, height: float) -> CarouselViewportGeometry:
    """按视口尺寸计算已确认的紧凑滚筒舞台。"""
    safe_width = max(1.0, float(width))
    safe_height = max(1.0, float(height))
    return CarouselViewportGeometry(
        center_x=safe_width / 2.0,
        center_y=safe_height / 2.0 + CAROUSEL_CENTER_Y_OFFSET,
        radius=min(safe_width * CAROUSEL_RADIUS_RATIO, CAROUSEL_RADIUS_MAX),
        target_height=safe_height * CAROUSEL_HEIGHT_RATIO,
        max_page_width=safe_width * CAROUSEL_MAX_WIDTH_RATIO,
        depth_drop=CAROUSEL_DEPTH_DROP,
    )


def fit_carousel_page(geometry: CarouselViewportGeometry, aspect_ratio: float) -> tuple[float, float]:
    """保持页面比例并应用高度目标和窄窗宽度上限。"""
    safe_aspect = max(0.01, float(aspect_ratio))
    height = geometry.target_height
    width = height * safe_aspect
    if width > geometry.max_page_width:
        width = geometry.max_page_width
        height = width / safe_aspect
    return width, height
```

- [ ] **Step 4: 运行几何测试确认绿灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_cylinder_geometry.py
```

Expected: `tests/test_cylinder_geometry.py` 全部通过。

- [ ] **Step 5: 提交共享几何**

```powershell
git add widgets/cylinder_geometry.py tests/test_cylinder_geometry.py
git commit -m "feat: add responsive carousel geometry"
```

### Task 2: 石墨青绿四段渐变

**Files:**
- Modify: `tests/test_theme.py`
- Modify: `app/theme.py`

- [ ] **Step 1: 写入失败的主题令牌测试**

在 `tests/test_theme.py` 导入 `STAGE_GRADIENT_MID` 和 `stage_background_gradient`，并将主题断言改为：

```python
def test_dark_theme_exposes_approved_tokens():
    assert STAGE_BACKGROUND == "#080A0B"
    assert STAGE_GRADIENT_TOP == "#080A0B"
    assert STAGE_GRADIENT_MID == "#111817"
    assert STAGE_GRADIENT_CENTER == "#18221F"
    assert STAGE_GRADIENT_BOTTOM == "#090B0E"
    assert FOCUS_BLUE == "#3B6FFF"
    stylesheet = application_stylesheet()
    for color in (
        STAGE_GRADIENT_TOP,
        STAGE_GRADIENT_MID,
        STAGE_GRADIENT_CENTER,
        STAGE_GRADIENT_BOTTOM,
    ):
        assert color in stylesheet
    assert "stop: 0.35" in stage_background_qss()
    assert "stop: 0.64" in stage_background_qss()
```

增加 QPainter 停点测试：

```python
def test_painter_gradient_matches_qss_stops():
    stops = stage_background_gradient(QRectF(0, 0, 100, 100)).stops()
    assert [position for position, _ in stops] == pytest.approx([0.0, 0.35, 0.64, 1.0])
    assert [color.name().upper() for _, color in stops] == [
        STAGE_GRADIENT_TOP,
        STAGE_GRADIENT_MID,
        STAGE_GRADIENT_CENTER,
        STAGE_GRADIENT_BOTTOM,
    ]
```

- [ ] **Step 2: 运行主题测试确认红灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_theme.py -k "approved_tokens or painter_gradient"
```

Expected: 因新色值和 `STAGE_GRADIENT_MID` 缺失而失败。

- [ ] **Step 3: 实现四段渐变**

在 `app/theme.py` 设置：

```python
STAGE_BACKGROUND = "#080A0B"
STAGE_GRADIENT_TOP = "#080A0B"
STAGE_GRADIENT_MID = "#111817"
STAGE_GRADIENT_CENTER = "#18221F"
STAGE_GRADIENT_BOTTOM = "#090B0E"
```

`stage_background_qss()` 使用 `0.00 / 0.35 / 0.64 / 1.00` 四个停点；`stage_background_gradient()` 使用完全相同的停点和颜色。

- [ ] **Step 4: 运行主题测试确认绿灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_theme.py
```

Expected: `tests/test_theme.py` 全部通过。

- [ ] **Step 5: 提交主题修改**

```powershell
git add app/theme.py tests/test_theme.py
git commit -m "feat: apply graphite teal stage gradient"
```

### Task 3: 真实滚筒采用共享几何

**Files:**
- Modify: `tests/test_stage_interactions.py`
- Modify: `widgets/cylinder_carousel.py`

- [ ] **Step 1: 写入失败的真实滚筒尺寸测试**

在 `tests/test_stage_interactions.py` 增加：

```python
def test_carousel_uses_denser_responsive_stage(qapp, pages):
    carousel = CylinderCarousel()
    carousel.resize(1440, 900)
    carousel.show()
    carousel.set_pages(pages, current_index=1)
    qapp.processEvents()

    center = carousel._items[1].root.sceneBoundingRect()
    assert center.height() == pytest.approx(603.0, abs=2.0)
    assert center.width() == pytest.approx(1072.0, abs=2.0)
    assert center.center().y() == pytest.approx(446.0, abs=2.0)
    assert carousel._items[0].root.isVisible()
    assert carousel._items[2].root.isVisible()
    carousel.close()
```

- [ ] **Step 2: 运行测试确认红灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_stage_interactions.py::test_carousel_uses_denser_responsive_stage
```

Expected: 当前 `58%` 布局导致高度约 `522px`，断言失败。

- [ ] **Step 3: 将滚筒切换到共享几何**

在 `widgets/cylinder_carousel.py`：

```python
from widgets.cylinder_geometry import (
    CarouselLayer,
    carousel_viewport_geometry,
    cylinder_pose,
    fit_carousel_page,
    inertia_target,
    snap_index,
)
```

`_layout_items()` 对每个可见页面执行：

```python
geometry = carousel_viewport_geometry(scene_rect.width(), scene_rect.height())
aspect = item.root.rect().width() / max(1.0, item.root.rect().height())
base_width, base_height = fit_carousel_page(geometry, aspect)
base_scale = base_height / max(1.0, item.root.rect().height())
transform = QTransform().scale(
    base_scale * pose.scale * pose.horizontal_scale,
    base_scale * pose.scale,
)
depth_drop = (1.0 - pose.scale) * geometry.depth_drop
item.root.setPos(
    geometry.center_x + pose.x_factor * geometry.radius,
    geometry.center_y + depth_drop,
)
```

将中央页阴影颜色从 `QColor(59, 111, 255, 100)` 改为 `QColor(59, 111, 255, 72)`。

- [ ] **Step 4: 运行舞台交互测试确认绿灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_stage_interactions.py
```

Expected: 新尺寸测试和现有滚筒交互测试全部通过。

- [ ] **Step 5: 提交真实滚筒修改**

```powershell
git add widgets/cylinder_carousel.py tests/test_stage_interactions.py
git commit -m "feat: densify gesture carousel stage"
```

### Task 4: 重组 overlay 与滚筒目标对齐

**Files:**
- Modify: `tests/test_stage_interactions.py`
- Modify: `widgets/stage_recomposition_overlay.py`

- [ ] **Step 1: 写入失败的 overlay 目标测试**

先在 `tests/test_stage_interactions.py` 补充导入：

```python
from PySide6.QtGui import QKeySequence, QPixmap, QWheelEvent

from widgets.cylinder_geometry import CarouselLayer
from widgets.stage_recomposition_overlay import StageRecompositionOverlay
```

再增加：

```python
def test_recomposition_overlay_matches_carousel_center_geometry(qapp, tmp_path):
    image_path = tmp_path / "slide.png"
    Image.new("RGB", (1600, 900), "#FFFFFF").save(image_path)
    overlay = StageRecompositionOverlay()
    overlay.resize(1440, 900)
    pixmap = QPixmap(str(image_path))
    center_layer = CarouselLayer(0, 0, 0.0, 1.0, 1.0, 1.0, 100.0)

    rect = overlay._carousel_rect(center_layer, pixmap)

    assert rect.width() == pytest.approx(1072.0, abs=2.0)
    assert rect.height() == pytest.approx(603.0, abs=2.0)
    assert rect.center().y() == pytest.approx(446.0, abs=2.0)
```

- [ ] **Step 2: 运行测试确认红灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_stage_interactions.py::test_recomposition_overlay_matches_carousel_center_geometry
```

Expected: overlay 仍使用 `58% / 47% / 110px`，尺寸断言失败。

- [ ] **Step 3: 将 overlay 切换到共享几何**

在 `widgets/stage_recomposition_overlay.py` 导入：

```python
from widgets.cylinder_geometry import (
    CarouselLayer,
    carousel_viewport_geometry,
    fit_carousel_page,
)
```

将 `_carousel_rect()` 改为：

```python
geometry = carousel_viewport_geometry(self.width(), self.height())
aspect = pixmap.width() / max(1, pixmap.height())
base_width, base_height = fit_carousel_page(geometry, aspect)
width = base_width * layer.scale * layer.horizontal_scale
height = base_height * layer.scale
depth_drop = (1.0 - layer.scale) * geometry.depth_drop
return QRectF(
    geometry.center_x + layer.x_factor * geometry.radius - width / 2,
    geometry.center_y + depth_drop - height / 2,
    width,
    height,
)
```

- [ ] **Step 4: 运行 overlay 与模式测试确认绿灯**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_stage_interactions.py
```

Expected: overlay 几何、模式切换和手势交互测试全部通过。

- [ ] **Step 5: 提交 overlay 修改**

```powershell
git add widgets/stage_recomposition_overlay.py tests/test_stage_interactions.py
git commit -m "fix: align carousel transition geometry"
```

### Task 5: 全量验证与视觉验收

**Files:**
- Verify: `tests/visual_stage_smoke.py`
- Modify only if needed: `AGENTS.md`

- [ ] **Step 1: 运行全量自动化验证**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q app widgets tests main.py
git diff --check
```

Expected: 所有测试通过、编译退出码 `0`、差异检查无错误。

- [ ] **Step 2: 运行 Windows 双尺寸视觉烟测**

Run:

```powershell
.\.venv\Scripts\python.exe tests\visual_stage_smoke.py
```

Expected: `D:\CodexCache\gesture-ppt-dark-theatre-qa` 生成 `1440 × 900` 与 `1024 × 768` 的全部状态截图，并输出 `VISUAL_OK`。

- [ ] **Step 3: 人工检查关键截图**

检查：

```text
gesture-chrome-1440x900.png
gesture-hidden-1440x900.png
gesture-chrome-1024x768.png
gesture-stage-1024x768.png
ppt-mode-1440x900.png
ppt-return-1440x900.png
```

验收：背景呈四段石墨青绿渐变；中央页明显大于旧版；侧页仍可辨识；控制层无重叠；PPT 模式页面框架不变。

- [ ] **Step 4: 记录新的可复用错误或边界**

仅当本次实施出现新的可复现问题时，按 `AGENTS.md` 格式追加：

```text
日期 | 文件/命令 | 现象 | 根因 | 修复/预防
```

没有新问题时不制造错误记录。

- [ ] **Step 5: 提交必要的验证文档调整**

若 `AGENTS.md` 有实际新增记录：

```powershell
git add AGENTS.md
git commit -m "docs: record carousel visual implementation lesson"
```

没有文档变化时跳过该提交。
