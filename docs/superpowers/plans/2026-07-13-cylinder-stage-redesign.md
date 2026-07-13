# Cylinder Stage Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the conventional sidebar PPT browser with a full-window cylindrical page drum and single-page stage while upgrading PowerPoint exports to aspect-ratio-preserving 4K.

**Architecture:** Introduce a pure geometry module for deterministic cylinder layout, a `CylinderCarousel` graphics view for thumbnail interaction, and a `StageWorkspace` stacked container that coordinates carousel and full-slide modes. Upgrade project metadata and cache validation to schema 2, then make PowerPoint export dimensions derive from the presentation page ratio.

**Tech Stack:** Python 3.11, PySide6 6, PowerPoint COM via pywin32, Pillow, pytest.

---

## File Map

- Modify `models/slide_project.py`: schema 2 metadata and render profile constants.
- Modify `ppt/project_store.py`: schema 2, image readability and export dimension validation.
- Modify `ppt/powerpoint_exporter.py`: aspect-ratio-preserving 4K export and 640px thumbnails.
- Create `widgets/cylinder_geometry.py`: pure cylinder positioning and snap calculations.
- Create `widgets/cylinder_carousel.py`: draggable thumbnail drum with inertia and selection signals.
- Modify `widgets/slide_viewer.py`: smooth rendering, fit-state tracking, swipe navigation and double-click mode toggle.
- Create `widgets/stage_workspace.py`: switch between drum and single-page stage while preserving page state.
- Modify `app/main_window.py`: remove sidebar/splitter/toolbar and integrate the stage workspace with edge controls.
- Modify `tests/test_project_store.py`: schema 2 and cache invalidation coverage.
- Create `tests/test_powerpoint_exporter.py`: export dimension calculation coverage.
- Create `tests/test_cylinder_geometry.py`: position and snapping coverage.
- Create `tests/test_stage_interactions.py`: Qt interaction and state transition coverage.
- Modify `tests/integration_powerpoint_smoke.py`: verify 16:9 and 4:3 pixel output and cache hit.
- Modify `README.md`: document the drum/stage workflow and 4K cache migration.

### Task 1: Render Profile and Schema 2 Cache

**Files:**
- Modify: `models/slide_project.py`
- Modify: `ppt/project_store.py`
- Modify: `tests/test_project_store.py`

- [ ] **Step 1: Write failing schema 2 cache tests**

Add helpers that create real PNG/JPEG fixtures with Pillow, then assert schema 1 is invalid and schema 2 requires the expected render profile and actual image dimensions:

```python
from PIL import Image


def _write_image(path: Path, size: tuple[int, int], format_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path, format_name)


def test_schema_one_cache_is_invalid(tmp_path):
    source, cache, project = _valid_project(tmp_path)
    project.schema_version = 1
    save_project(project, cache)
    assert not is_cache_valid(cache, source)


def test_schema_two_requires_render_profile_and_dimensions(tmp_path):
    source, cache, project = _valid_project(tmp_path)
    save_project(project, cache)
    assert is_cache_valid(cache, source)
    metadata = json.loads((cache / "project.json").read_text(encoding="utf-8"))
    metadata["render_profile"] = "legacy"
    (cache / "project.json").write_text(json.dumps(metadata), encoding="utf-8")
    assert not is_cache_valid(cache, source)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_project_store.py -v`

Expected: FAIL because `SlideProject` still defaults to schema 1 and has no `render_profile`.

- [ ] **Step 3: Implement schema 2 metadata**

Add constants and fields in `models/slide_project.py`:

```python
SCHEMA_VERSION = 2
RENDER_PROFILE = "powerpoint-4k-v1"
THUMBNAIL_WIDTH = 640

export_width: int = 3840
export_height: int = 2160
render_profile: str = RENDER_PROFILE
thumbnail_width: int = THUMBNAIL_WIDTH
schema_version: int = SCHEMA_VERSION
```

Include `render_profile` and `thumbnail_width` in `to_dict()` and `from_dict()`.

- [ ] **Step 4: Implement strict schema 2 cache validation**

In `ppt/project_store.py`, require schema 2, `powerpoint-4k-v1`, width `3840`, positive height and thumbnail width `640`. Open each PNG and JPEG with Pillow, call `verify()`, then reopen the first PNG to assert its size matches project export dimensions.

- [ ] **Step 5: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_project_store.py -v`

Expected: all cache tests PASS.

Commit:

```powershell
git add models/slide_project.py ppt/project_store.py tests/test_project_store.py
git commit -m "feat: upgrade slide cache to 4k schema"
```

### Task 2: Aspect-Ratio-Preserving PowerPoint Export

**Files:**
- Modify: `ppt/powerpoint_exporter.py`
- Create: `tests/test_powerpoint_exporter.py`
- Modify: `tests/integration_powerpoint_smoke.py`

- [ ] **Step 1: Write failing dimension tests**

```python
from ppt.powerpoint_exporter import calculate_export_size


def test_calculate_export_size_for_widescreen():
    assert calculate_export_size(13.333, 7.5) == (3840, 2160)


def test_calculate_export_size_for_four_by_three():
    assert calculate_export_size(10.0, 7.5) == (3840, 2880)


def test_calculate_export_size_rejects_invalid_ratio():
    with pytest.raises(ExportError, match="页面比例"):
        calculate_export_size(0, 7.5)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_powerpoint_exporter.py -v`

Expected: FAIL because `calculate_export_size` does not exist.

- [ ] **Step 3: Implement size calculation and 4K export**

```python
EXPORT_WIDTH = 3840


def calculate_export_size(slide_width: float, slide_height: float) -> tuple[int, int]:
    if slide_width <= 0 or slide_height <= 0:
        raise ExportError("无法读取 PowerPoint 页面比例。")
    return EXPORT_WIDTH, max(1, round(EXPORT_WIDTH * slide_height / slide_width))
```

Read `presentation.PageSetup.SlideWidth` and `SlideHeight` once, pass the calculated dimensions to every `Slide.Export`, generate thumbnails with max size `(640, calculated_height)`, quality 90, and store actual dimensions in `SlideProject`.

- [ ] **Step 4: Expand COM integration smoke test**

Make `create_sample_presentation(path, layout)` set `presentation.PageSetup.SlideSize` or explicit `SlideWidth/SlideHeight`, then create both 16:9 and 4:3 files. Verify PNG sizes are `(3840, 2160)` and `(3840, 2880)` and the second import hits cache.

- [ ] **Step 5: Run unit and COM tests, then commit**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_powerpoint_exporter.py tests/test_project_store.py -v
.venv\Scripts\python.exe tests\integration_powerpoint_smoke.py
```

Expected: unit tests PASS and integration output reports both dimensions plus `cache_hit=True`.

Commit:

```powershell
git add ppt/powerpoint_exporter.py tests/test_powerpoint_exporter.py tests/integration_powerpoint_smoke.py
git commit -m "feat: export slides at aspect-aware 4k"
```

### Task 3: Pure Cylinder Geometry

**Files:**
- Create: `widgets/cylinder_geometry.py`
- Create: `tests/test_cylinder_geometry.py`

- [ ] **Step 1: Write failing geometry tests**

```python
from widgets.cylinder_geometry import cylinder_pose, snap_index


def test_center_page_is_front_facing_and_largest():
    center = cylinder_pose(0.0)
    side = cylinder_pose(1.0)
    assert center.x_factor == 0.0
    assert center.scale == 1.0
    assert center.opacity == 1.0
    assert abs(side.x_factor) > 0
    assert side.scale < center.scale
    assert side.opacity < center.opacity


def test_pose_is_symmetric():
    left = cylinder_pose(-1.0)
    right = cylinder_pose(1.0)
    assert left.x_factor == pytest.approx(-right.x_factor)
    assert left.scale == pytest.approx(right.scale)


def test_snap_index_clamps_to_page_boundaries():
    assert snap_index(-0.7, 5) == 0
    assert snap_index(2.6, 5) == 3
    assert snap_index(8.0, 5) == 4
```

- [ ] **Step 2: Run test and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cylinder_geometry.py -v`

Expected: FAIL because the geometry module does not exist.

- [ ] **Step 3: Implement deterministic geometry**

Create a frozen `CylinderPose` dataclass with `x_factor`, `scale`, `horizontal_scale`, `opacity`, and `z_value`. Use a clamped angle of `offset * 0.52` radians, `sin(angle)` for x position, `cos(angle)` for horizontal compression, and bounded scale/opacity formulas. Implement `snap_index(offset, page_count)` with `round` and boundary clamping.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cylinder_geometry.py -v`

Expected: all geometry tests PASS.

Commit:

```powershell
git add widgets/cylinder_geometry.py tests/test_cylinder_geometry.py
git commit -m "feat: add cylinder page geometry"
```

### Task 4: Cylinder Carousel Widget

**Files:**
- Create: `widgets/cylinder_carousel.py`
- Create: `tests/test_stage_interactions.py`

- [ ] **Step 1: Write failing carousel state tests**

Use `QT_QPA_PLATFORM=offscreen` before importing PySide6. Build temporary thumbnail images, call `set_pages`, then verify current page, direct selection, boundary clamping and the central-page activation signal.

```python
def test_carousel_selects_and_clamps_pages(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages, current_index=1)
    assert carousel.current_index == 1
    carousel.select_page(99, animate=False)
    assert carousel.current_index == len(pages) - 1


def test_center_page_activation_emits_stage_request(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages, current_index=0)
    emitted = []
    carousel.stage_requested.connect(emitted.append)
    carousel.activate_page(0)
    assert emitted == [0]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage_interactions.py -v`

Expected: FAIL because `CylinderCarousel` does not exist.

- [ ] **Step 3: Implement the carousel**

Implement `CylinderCarousel(QGraphicsView)` with signals `current_page_changed(int)` and `stage_requested(int)`. Store a continuous `_offset`, create one `QGraphicsPixmapItem` and page-number text item per page, update item position/transform/opacity/z using `cylinder_pose(index - _offset)`, estimate drag velocity with `QElapsedTimer`, and animate `_offset` to the nearest page with `QVariantAnimation` using `OutCubic` easing.

Only render items whose relative offset is within a bounded visible radius, hiding distant pages. `activate_page` first centers a side page; when already centered it emits `stage_requested`.

- [ ] **Step 4: Run interaction tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage_interactions.py -v`

Expected: carousel tests PASS.

Commit:

```powershell
git add widgets/cylinder_carousel.py tests/test_stage_interactions.py
git commit -m "feat: add draggable cylinder carousel"
```

### Task 5: Swipe-Aware Viewer and Stage Workspace

**Files:**
- Modify: `widgets/slide_viewer.py`
- Create: `widgets/stage_workspace.py`
- Modify: `tests/test_stage_interactions.py`

- [ ] **Step 1: Add failing viewer and workspace tests**

Test `is_fit_mode`, swipe classification, mode transitions and page preservation. Expose a pure helper `classify_release(delta_x, delta_y, fit_mode, threshold=80)` for deterministic gesture tests.

```python
def test_fit_mode_horizontal_release_requests_next_page():
    assert classify_release(-120, 10, fit_mode=True) == "next"


def test_zoomed_release_never_changes_page():
    assert classify_release(-120, 10, fit_mode=False) is None


def test_workspace_preserves_page_when_returning_to_carousel(qapp, project):
    workspace = StageWorkspace()
    workspace.set_project(project, current_index=2)
    workspace.enter_stage(2)
    workspace.show_carousel()
    assert workspace.current_index == 2
    assert workspace.mode == "carousel"
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage_interactions.py -v`

Expected: FAIL because swipe classification and `StageWorkspace` are missing.

- [ ] **Step 3: Implement viewer gesture rules**

Add signals `previous_requested`, `next_requested`, and `fit_mode_changed`. Track `_fit_mode`; set it in `fit_in_view`, `reset_zoom` and `change_zoom`. At fit mode, accumulate drag without moving scrollbars and classify release; when zoomed, preserve existing panning. Add `mouseDoubleClickEvent` to toggle fit/100% and set `QGraphicsPixmapItem.TransformationMode` to `SmoothTransformation`.

- [ ] **Step 4: Implement StageWorkspace**

Use `QStackedLayout` to host `CylinderCarousel` and `SlideViewer`. Keep `pages`, `current_index`, and `mode`. Connect carousel selection and stage request; connect viewer swipe signals. Emit `page_changed(int)` and `mode_changed(str)`. Public methods: `set_project`, `select_page`, `previous_page`, `next_page`, `enter_stage`, `show_carousel`, `fit_view`, `reset_zoom`, `change_zoom`.

- [ ] **Step 5: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage_interactions.py -v`

Expected: all stage interaction tests PASS.

Commit:

```powershell
git add widgets/slide_viewer.py widgets/stage_workspace.py tests/test_stage_interactions.py
git commit -m "feat: add swipe-aware stage workspace"
```

### Task 6: Main Window Stage UI and End-to-End Verification

**Files:**
- Modify: `app/main_window.py`
- Modify: `README.md`
- Test: `tests/test_commands.py`
- Test: `tests/test_project_store.py`
- Test: `tests/test_powerpoint_exporter.py`
- Test: `tests/test_cylinder_geometry.py`
- Test: `tests/test_stage_interactions.py`

- [ ] **Step 1: Replace conventional layout with full-window stage**

Remove `QSplitter`, `ThumbnailPanel`, and the fixed `QToolBar`. Set `StageWorkspace` as the central widget. Add a slim top edge bar with open, carousel/overview, zoom, fit and fullscreen icon actions; add a large asymmetric folio label and a compact import progress strip. Keep surfaces `#FFFFFF`/`#F7F7F8`, accent `#002FA7`, 1px rules and no gradients.

- [ ] **Step 2: Rewire navigation and state persistence**

Route `select_page`, `previous_page`, `next_page`, zoom and fit commands through `StageWorkspace`. On import completion, call `workspace.set_project(project, project.current_slide)` and default to carousel mode. Make non-fullscreen `Esc` return to carousel. Save `workspace.current_index` on close.

- [ ] **Step 3: Update documentation**

Document 4K export dimensions, automatic schema 2 cache refresh, drum dragging, central-page activation, stage swipe rules and `Esc` behavior in `README.md`.

- [ ] **Step 4: Run all automated tests and compilation**

Run:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m compileall -q .
```

Expected: all tests PASS and compile exits 0.

- [ ] **Step 5: Run PowerPoint COM integration**

Run: `.venv\Scripts\python.exe tests\integration_powerpoint_smoke.py`

Expected: reports correct 16:9 and 4:3 dimensions and cache hits, with no remaining `POWERPNT.EXE` process.

- [ ] **Step 6: Run Windows visual QA**

Launch with `QT_QPA_PLATFORM=windows` and isolated `LOCALAPPDATA`, load the generated integration project, capture `1440×900` and `1024×768` screenshots, and inspect them for nonblank page images, readable Chinese text, no overlap, visible curved side pages and correct central focus.

- [ ] **Step 7: Verify launcher and commit**

Run the `.cmd` with `GESTURE_PPT_NO_PAUSE=1`, confirm it starts one project Python process, then stop only that test process and verify no residual PowerPoint process.

Commit:

```powershell
git add app/main_window.py README.md
git commit -m "feat: replace PPT browser with cylinder stage"
```
