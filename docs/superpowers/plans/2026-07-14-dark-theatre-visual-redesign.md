# Dark Theatre Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed light desktop chrome with a full-window dark theatre, a five-page cylindrical carousel, auto-hiding edge controls, restrained interruptible motion, and a reduced-motion mode while preserving all phase-one PPT behavior.

**Architecture:** Keep data, export, cache, and navigation contracts unchanged. Add semantic theme tokens and a focused `StageChrome` controller, extend pure carousel geometry for five visible layers and bounded inertia, then let `MainWindow` compose the existing workspace with overlay controls. Motion remains within Qt widgets and animations; reduced motion is read from Windows and can be forced in tests.

**Tech Stack:** Python 3.11, PySide6 Widgets/Graphics View, Pillow fixtures, pytest, Windows PowerPoint COM smoke tests.

---

## File Map

- Create `app/theme.py`: dark theatre tokens, stylesheet, icon tinting, and Windows reduced-motion detection.
- Create `widgets/stage_chrome.py`: overlay placement, reveal zones, fade timing, visibility locking, and mouse/focus tracking.
- Create `tests/test_theme.py`: semantic token and reduced-motion fallback tests.
- Create `tests/test_stage_chrome.py`: hide timer, reveal zones, and visibility-lock tests.
- Modify `AGENTS.md`: replace the superseded light Swiss UI rule with the approved dark-theatre rule.
- Modify `widgets/cylinder_geometry.py`: five-page poses and bounded inertia target calculation.
- Modify `widgets/cylinder_carousel.py`: dark rendering, two side layers, focus shadow, animation interruption, and reduced motion.
- Modify `widgets/slide_viewer.py`: dark background, 32px fit margin, and restrained entry scaling.
- Modify `widgets/stage_workspace.py`: reduced-motion propagation and carousel/stage crossfade.
- Modify `app/main_window.py`: full-window content with top/bottom overlay chrome and unified UI states.
- Modify `tests/test_cylinder_geometry.py`: exact five-layer and bounded-inertia expectations.
- Modify `tests/test_stage_interactions.py`: carousel loading limit, reduced-motion propagation, overlay structure, and state preservation.
- Modify `tests/visual_stage_smoke.py`: capture empty, chrome-visible, chrome-hidden, carousel, stage, importing, and failure-ready dark states.
- Modify `README.md`: describe dark theatre controls and automatic chrome behavior.

### Task 1: Dark Theme Foundation

**Files:**
- Create: `app/theme.py`
- Create: `tests/test_theme.py`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write failing theme tests**

```python
from app.theme import FOCUS_BLUE, STAGE_BACKGROUND, application_stylesheet, reduced_motion_enabled


def test_dark_theme_exposes_approved_tokens():
    assert STAGE_BACKGROUND == "#07080B"
    assert FOCUS_BLUE == "#3B6FFF"
    stylesheet = application_stylesheet()
    assert "#07080B" in stylesheet
    assert "#3B6FFF" in stylesheet
    assert "Segoe UI Variable" in stylesheet


def test_reduced_motion_can_be_forced_by_environment(monkeypatch):
    monkeypatch.setenv("GESTURE_PPT_REDUCED_MOTION", "1")
    assert reduced_motion_enabled()
    monkeypatch.setenv("GESTURE_PPT_REDUCED_MOTION", "0")
    assert not reduced_motion_enabled()
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run: `.venv\Scripts\python.exe -m pytest tests\test_theme.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.theme'`.

- [ ] **Step 3: Implement semantic tokens, stylesheet, and reduced-motion detection**

```python
STAGE_BACKGROUND = "#07080B"
CONTROL_SURFACE = "#111318"
HOVER_SURFACE = "#191D24"
STRUCTURE_LINE = "#303641"
PRIMARY_TEXT = "#F4F6FA"
SECONDARY_TEXT = "#A8AFBC"
DISABLED_TEXT = "#626A78"
FOCUS_BLUE = "#3B6FFF"
ERROR_RED = "#FF5C68"


def reduced_motion_enabled() -> bool:
    forced = os.environ.get("GESTURE_PPT_REDUCED_MOTION")
    if forced in {"0", "1"}:
        return forced == "1"
    if sys.platform != "win32":
        return False
    enabled = ctypes.c_bool(True)
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
    except (AttributeError, OSError):
        return False
    return bool(ok and not enabled.value)
```

`application_stylesheet()` must style the main window, overlay bars, labels, tool buttons, progress bars, message boxes, carousel, and viewer using only the approved semantic colors. It must set a maximum 4px radius, 40px tool-button hit targets, and visible blue focus borders.

- [ ] **Step 4: Update the durable UI rule**

Replace the light Swiss surface bullet in `AGENTS.md` with the approved full-window dark-theatre palette, five-page carousel, auto-hidden chrome, and reduced-motion requirement. Preserve every non-UI boundary and error record.

- [ ] **Step 5: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\test_theme.py -v`

Expected: PASS.

```powershell
git add AGENTS.md app/theme.py tests/test_theme.py
git commit -m "feat: add dark theatre theme foundation"
```

### Task 2: Five-Page Geometry and Bounded Inertia

**Files:**
- Modify: `widgets/cylinder_geometry.py`
- Modify: `tests/test_cylinder_geometry.py`

- [ ] **Step 1: Add failing geometry and inertia tests**

```python
from widgets.cylinder_geometry import cylinder_pose, inertia_target


def test_five_page_layers_have_distinct_depth():
    center = cylinder_pose(0.0)
    first = cylinder_pose(1.0)
    second = cylinder_pose(2.0)
    assert center.opacity == 1.0
    assert first.opacity == pytest.approx(0.58)
    assert second.opacity == pytest.approx(0.18)
    assert center.scale > first.scale > second.scale
    assert cylinder_pose(3.0).visible is False


@pytest.mark.parametrize(
    "offset,velocity,count,expected",
    [(5.1, 1.0, 20, 7), (5.1, -1.0, 20, 3), (0.1, -2.0, 20, 0), (18.9, 2.0, 20, 19)],
)
def test_inertia_target_never_skips_more_than_two_pages(offset, velocity, count, expected):
    assert inertia_target(offset, velocity, count) == expected
```

- [ ] **Step 2: Verify the tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\test_cylinder_geometry.py -v`

Expected: FAIL because `inertia_target` is missing and the old pose exposes more than five pages.

- [ ] **Step 3: Implement the five-page pose and inertia clamp**

Use a smooth distance-based pose with these exact anchor values:

```python
VISIBLE_RADIUS = 2.55


def cylinder_pose(relative_offset: float) -> CylinderPose:
    distance = abs(relative_offset)
    clamped = min(distance, 2.0)
    direction = -1.0 if relative_offset < 0 else 1.0
    return CylinderPose(
        x_factor=direction * math.sin(clamped * 0.68) if distance else 0.0,
        scale=max(0.56, 1.0 - 0.22 * clamped),
        horizontal_scale=max(0.34, math.cos(clamped * 0.61)),
        opacity=max(0.18, 1.0 - 0.42 * clamped),
        z_value=max(0.0, 100.0 - 38.0 * clamped),
        visible=distance <= VISIBLE_RADIUS,
    )


def inertia_target(offset: float, velocity: float, page_count: int) -> int:
    if page_count <= 0:
        return 0
    current = snap_index(offset, page_count)
    predicted = snap_index(offset + velocity * 180.0, page_count)
    lower = max(0, current - 2)
    upper = min(page_count - 1, current + 2)
    return max(lower, min(predicted, upper))
```

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\test_cylinder_geometry.py -v`

Expected: PASS.

```powershell
git add widgets/cylinder_geometry.py tests/test_cylinder_geometry.py
git commit -m "feat: define five-page cylinder motion"
```

### Task 3: Auto-Hiding Stage Chrome

**Files:**
- Create: `widgets/stage_chrome.py`
- Create: `tests/test_stage_chrome.py`

- [ ] **Step 1: Write failing visibility tests**

```python
def test_chrome_hides_after_timeout(qapp):
    host, top, bottom = make_chrome_widgets()
    chrome = StageChrome(host, top, bottom, hide_delay_ms=20, fade_duration_ms=0)
    chrome.reveal_all()
    QTest.qWait(40)
    qapp.processEvents()
    assert top.isHidden()
    assert bottom.isHidden()


def test_visibility_lock_prevents_hiding(qapp):
    host, top, bottom = make_chrome_widgets()
    chrome = StageChrome(host, top, bottom, hide_delay_ms=20, fade_duration_ms=0)
    chrome.set_locked(True)
    chrome.hide_now()
    assert not top.isHidden()
    assert not bottom.isHidden()


def test_edge_zones_reveal_corresponding_bar(qapp):
    host, top, bottom = make_chrome_widgets()
    chrome = StageChrome(host, top, bottom, fade_duration_ms=0)
    chrome.hide_now()
    chrome.reveal_for_position(20, host.height())
    assert not top.isHidden()
    chrome.hide_now()
    chrome.reveal_for_position(host.height() - 20, host.height())
    assert not bottom.isHidden()
```

- [ ] **Step 2: Verify the missing module failure**

Run: `.venv\Scripts\python.exe -m pytest tests\test_stage_chrome.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'widgets.stage_chrome'`.

- [ ] **Step 3: Implement `StageChrome`**

`StageChrome(QObject)` must:

- own a single-shot hide timer;
- position 52px top and 64px bottom sibling frames over the full-size host on resize;
- install event filters on the host widget tree for mouse movement and focus changes;
- reveal only the top bar inside the top 56px and only the bottom bar inside the bottom 72px;
- fade with `QGraphicsOpacityEffect` and `QPropertyAnimation` when motion is enabled;
- hide instantly when reduced motion is enabled or `fade_duration_ms == 0`;
- keep both bars visible while locked or while focus is inside a bar;
- stop its timer and animations in `dispose()`.

The public API consists of the read-only `locked` property and the methods `reveal_all(minimum_visible_ms=1500)`, `reveal_for_position(y, height)`, `hide_now()`, `set_locked(locked)`, `set_reduced_motion(reduced)`, and `dispose()`.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\test_stage_chrome.py -v`

Expected: PASS.

```powershell
git add widgets/stage_chrome.py tests/test_stage_chrome.py
git commit -m "feat: add auto-hiding stage chrome"
```

### Task 4: Dark Five-Page Carousel

**Files:**
- Modify: `widgets/cylinder_carousel.py`
- Modify: `tests/test_stage_interactions.py`

- [ ] **Step 1: Add failing carousel tests**

```python
def test_carousel_only_decodes_five_visible_thumbnails(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages * 25, current_index=50)
    loaded = sum(not item.pixmap.pixmap().isNull() for item in carousel._items)
    assert loaded <= 5


def test_reduced_motion_selects_without_animation(qapp, pages):
    carousel = CylinderCarousel()
    carousel.set_pages(pages, current_index=0)
    carousel.set_reduced_motion(True)
    carousel.select_page(2)
    assert carousel.current_index == 2
    assert carousel._animation.state() == QAbstractAnimation.State.Stopped
```

- [ ] **Step 2: Verify the new expectations fail**

Run: `.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -v`

Expected: FAIL because the old carousel can load seven thumbnails and has no reduced-motion API.

- [ ] **Step 3: Implement dark rendering and motion behavior**

Update the carousel to:

- use `STAGE_BACKGROUND`, `STRUCTURE_LINE`, `PRIMARY_TEXT`, and `FOCUS_BLUE` from `app.theme`;
- draw a stationary horizontal reference line in `drawBackground()` behind all pages;
- remove per-slide number labels;
- add a `QGraphicsDropShadowEffect` to each root item, enabled only for the centered page;
- add a `QGraphicsColorizeEffect` to each pixmap, increasing neutral colorization with distance;
- keep only offsets within `VISIBLE_RADIUS` decoded;
- call `inertia_target()` on release;
- cap animation duration to 180–320ms;
- stop an active animation on mouse press, wheel input, or another selection;
- emit the committed page only after snap completion;
- select immediately when reduced motion is enabled.

Expose `reduced_motion` as a read-only property so the workspace and tests do not depend on private fields.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\test_cylinder_geometry.py tests\test_stage_interactions.py -v`

Expected: PASS.

```powershell
git add widgets/cylinder_carousel.py tests/test_stage_interactions.py
git commit -m "feat: render dark five-page carousel"
```

### Task 5: Dark Viewer and Workspace Transitions

**Files:**
- Modify: `widgets/slide_viewer.py`
- Modify: `widgets/stage_workspace.py`
- Modify: `tests/test_stage_interactions.py`

- [ ] **Step 1: Add failing workspace tests**

```python
def test_workspace_propagates_reduced_motion(qapp):
    workspace = StageWorkspace()
    workspace.set_reduced_motion(True)
    assert workspace.carousel.reduced_motion
    assert workspace.reduced_motion


def test_stage_transition_preserves_page(qapp, pages):
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    workspace = StageWorkspace()
    workspace.set_project(project, current_index=2)
    workspace.enter_stage(2)
    assert workspace.current_index == 2
    workspace.show_carousel()
    assert workspace.current_index == 2
```

- [ ] **Step 2: Verify the missing API failure**

Run: `.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -v`

Expected: FAIL because `StageWorkspace.set_reduced_motion` does not exist.

- [ ] **Step 3: Implement viewer margins and transition choreography**

`SlideViewer.fit_in_view()` must calculate a fit transform using a 32px viewport margin instead of filling to the edge. Add `animate_entry(duration_ms=260)` that applies a 0.96-to-1.0 scale plus opacity transition and can be interrupted by user input.

`StageWorkspace` must:

- use `QStackedLayout.StackAll` with opacity effects for both views;
- crossfade side pages out within 180ms and the viewer in within 260ms;
- reverse the transition when returning to the carousel;
- skip scaling and use at most a 120ms fade in reduced-motion mode;
- disable the outgoing view during the transition;
- stop existing transition animations before starting another;
- preserve the shared current index in every path.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py tests\test_slide_navigation.py -v`

Expected: PASS.

```powershell
git add widgets/slide_viewer.py widgets/stage_workspace.py tests/test_stage_interactions.py
git commit -m "feat: animate dark stage transitions"
```

### Task 6: Full-Window Main Window and UI States

**Files:**
- Modify: `app/main_window.py`
- Modify: `tests/test_stage_interactions.py`
- Modify: `README.md`

- [ ] **Step 1: Add failing main-window structure tests**

```python
def test_main_window_uses_overlay_dark_chrome(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    assert window.top_bar.parent() is window.stage_root
    assert window.bottom_bar.parent() is window.stage_root
    assert window.content_stack.geometry() == window.stage_root.rect()
    assert window.styleSheet().find("#07080B") >= 0
    window.close()


def test_import_locks_chrome_visible(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window._set_importing_ui(True)
    assert window.chrome.locked
    assert not window.bottom_bar.isHidden()
    window._set_importing_ui(False)
    assert not window.chrome.locked
    window.close()
```

- [ ] **Step 2: Verify the structure tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -v`

Expected: FAIL because the current main window uses `edge_bar` and `status_strip` in a vertical layout.

- [ ] **Step 3: Recompose the main window**

Create `stage_root` with the content stack filling its complete rect. Create 52px `top_bar` and 64px `bottom_bar` as direct children of `stage_root`, then pass them to `StageChrome`.

Top bar:

- left group: icon-only open button plus elided current filename;
- centered fixed-width folio using tabular digits;
- right group: icon-only mode and fullscreen buttons.

Bottom bar:

- status label and thin page/import progress line;
- stage-only zoom-out, percentage, zoom-in, and fit controls;
- import-only cancel control.

Use tinted Qt standard icons so every visible icon is monochrome and follows the current text color. Do not add a new icon dependency.

Refactor state changes through `_set_importing_ui(importing)`, `_update_chrome_mode(mode)`, and `_update_project_name()`. Lock chrome during imports and errors, reveal it for at least 1.5 seconds after project or mode changes, and return focus to the open button after an import error.

Empty state must contain only a large `00`, the open action, and “打开 PPT”. Fullscreen must no longer permanently hide bars; it must rely on the same edge-reveal controller.

- [ ] **Step 4: Run automated tests and update README**

Run: `.venv\Scripts\python.exe -m pytest`

Expected: all tests PASS.

Update README operation text for the black theatre, five-page carousel, edge-revealed controls, reduced-motion environment override, and unchanged launcher.

- [ ] **Step 5: Commit**

```powershell
git add app/main_window.py tests/test_stage_interactions.py README.md
git commit -m "feat: replace window chrome with dark theatre"
```

### Task 7: Visual and Windows Regression Verification

**Files:**
- Modify: `tests/visual_stage_smoke.py`
- Modify: `AGENTS.md` only if a new reusable failure is found

- [ ] **Step 1: Expand the visual smoke capture**

Generate screenshots under `D:\CodexCache\gesture-ppt-dark-theatre-qa` for each viewport (`1440×900`, `1024×768`):

- `empty-*`
- `carousel-chrome-*`
- `carousel-hidden-*`
- `stage-chrome-*`
- `stage-hidden-*`
- `importing-*`

The helper must restore any environment variables and close every window before exiting.

- [ ] **Step 2: Run full automated verification**

Run:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m compileall -q app models ppt widgets tests main.py
```

Expected: zero test failures and both commands exit 0.

- [ ] **Step 3: Run and inspect visual screenshots**

Run: `.venv\Scripts\python.exe tests\visual_stage_smoke.py`

Expected: every named screenshot is created. Inspect all screenshots for dark coverage, five visible layers, no overlap, stable folio, intact text, and nonblank PPT content.

- [ ] **Step 4: Run PowerPoint COM regression**

Run: `.venv\Scripts\python.exe tests\integration_powerpoint_smoke.py`

Expected: `COM_EXPORT_OK 16x9=3840x2160 4x3=3840x2880 cache_hit=True`, followed by final `POWERPNT` process count 0.

- [ ] **Step 5: Run launcher smoke test**

Launch `启动手势控制PPT.cmd` with `GESTURE_PPT_NO_PAUSE=1` and `QT_QPA_PLATFORM=offscreen`. Confirm exactly one child project Python process starts, then terminate only that owned child and verify no project process remains.

- [ ] **Step 6: Record reusable failures, clean task outputs, and commit**

If a reusable issue is discovered, append one dated row to `AGENTS.md` before committing. Delete only `D:\CodexCache\gesture-ppt-dark-theatre-qa` after visual inspection.

```powershell
git add tests/visual_stage_smoke.py AGENTS.md
git commit -m "test: cover dark theatre visual states"
```

Final expected state: tracked files clean; only the pre-existing `.superpowers/` and `第一阶段执行方案.md` remain untracked if they were not intentionally added.
