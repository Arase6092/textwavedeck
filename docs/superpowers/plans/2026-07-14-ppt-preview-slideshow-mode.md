# PPT Preview and Slideshow Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PowerPoint-like read-only preview mode with a left thumbnail pane and import button while preserving the current clean slideshow and all gesture-mode interactions.

**Architecture:** `MainWindow` owns separate `presentation_mode` and `ppt_view_mode` state. A new `PptPreviewWorkspace` sits beside the existing `StageWorkspace` in the main content stack; both synchronize through the main window's current-page coordinator. `SlideViewer` uses explicit `gesture`, `preview`, and `slideshow` interaction policies so preview/slideshow behavior cannot leak into gesture mode.

**Tech Stack:** Python 3.11, PySide6, pytest, pytest-qt/QTest, Pillow, existing PowerPoint COM import pipeline.

---

## File Map

- Create `widgets/ppt_preview_workspace.py`: assemble the read-only Normal View layout and expose preview-specific signals.
- Modify `widgets/slide_viewer.py`: replace the ambiguous PowerPoint boolean with explicit interaction modes and arbitrate single/double clicks.
- Modify `widgets/thumbnail_panel.py`: support silent selection synchronization and stable preview sizing.
- Modify `app/main_window.py`: own PPT submode state, switch content pages, synchronize current page, and apply mode-specific chrome.
- Modify `app/theme.py`: style the preview command strip, splitter, thumbnail pane, selected thumbnail, and status strip.
- Modify `tests/test_stage_interactions.py`: cover viewer policies, preview workspace, main-window transitions, and gesture regressions.
- Modify `tests/visual_stage_smoke.py`: capture preview mode at desktop and compact desktop sizes.
- Modify `README.md`: document preview/slideshow behavior and visible import entry.

### Task 1: Explicit Slide Viewer Interaction Modes

**Files:**
- Modify: `tests/test_stage_interactions.py`
- Modify: `widgets/slide_viewer.py`

- [ ] **Step 1: Write failing viewer-policy tests**

Add tests that use `QSignalSpy` and `QApplication.doubleClickInterval()`:

```python
def test_preview_viewer_click_is_idle_and_double_click_requests_slideshow(qapp, pages):
    viewer = SlideViewer()
    viewer.set_interaction_mode("preview")
    viewer.show_image(pages[0].image_path)
    next_spy = QSignalSpy(viewer.next_requested)
    double_spy = QSignalSpy(viewer.double_clicked)

    QTest.mouseClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert next_spy.count() == 0

    QTest.mouseDClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    QTest.qWait(QApplication.doubleClickInterval() + 20)
    assert double_spy.count() == 1
    assert next_spy.count() == 0


def test_slideshow_double_click_cancels_pending_single_click(qapp, pages):
    viewer = SlideViewer()
    viewer.set_interaction_mode("slideshow")
    viewer.show_image(pages[0].image_path)
    next_spy = QSignalSpy(viewer.next_requested)
    double_spy = QSignalSpy(viewer.double_clicked)

    QTest.mouseDClick(viewer.viewport(), Qt.MouseButton.LeftButton)
    QTest.qWait(QApplication.doubleClickInterval() + 20)

    assert double_spy.count() == 1
    assert next_spy.count() == 0
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -k "preview_viewer or slideshow_double_click" -v
```

Expected: FAIL because `set_interaction_mode` and `double_clicked` do not exist.

- [ ] **Step 3: Implement explicit modes and click arbitration**

In `SlideViewer`, add:

```python
double_clicked = Signal()
VALID_INTERACTION_MODES = {"gesture", "preview", "slideshow"}

def set_interaction_mode(self, mode: str) -> None:
    """设置手势、预览或放映鼠标策略，并清理待处理点击。"""
    if mode not in self.VALID_INTERACTION_MODES:
        raise ValueError(f"未知页面交互模式：{mode}")
    self._interaction_mode = mode
    self._single_click_timer.stop()
    self._drag_start = None
    self._press_point = None

def _emit_delayed_slideshow_click(self) -> None:
    """双击判定结束后再执行放映单击翻页。"""
    if self._interaction_mode == "slideshow":
        self.next_requested.emit()
```

Create a single-shot `QTimer`, start it from a slideshow click release using `QApplication.doubleClickInterval()`, cancel it in `mouseDoubleClickEvent`, and emit `double_clicked`. Preview clicks do nothing; preview double-click emits `double_clicked`; gesture behavior remains the current zoom/drag/swipe implementation. Keep `set_powerpoint_mode()` only as a compatibility wrapper until all callers migrate.

- [ ] **Step 4: Run viewer and gesture interaction tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -k "viewer or powerpoint_mode or gesture_stage" -v
```

Expected: PASS, including existing gesture zoom/drag tests.

- [ ] **Step 5: Commit viewer policy**

```powershell
git add widgets\slide_viewer.py tests\test_stage_interactions.py
git commit -m "feat: separate preview and slideshow interactions"
```

### Task 2: Read-Only PPT Preview Workspace

**Files:**
- Create: `widgets/ppt_preview_workspace.py`
- Modify: `widgets/thumbnail_panel.py`
- Modify: `tests/test_stage_interactions.py`

- [ ] **Step 1: Write failing preview-workspace tests**

```python
def test_preview_workspace_builds_normal_view_and_exposes_import(qapp, pages):
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    preview = PptPreviewWorkspace()
    preview.set_project(project, current_index=1)
    preview.show()
    qapp.processEvents()

    assert preview.thumbnail_panel.count() == len(pages)
    assert preview.thumbnail_panel.currentRow() == 1
    assert preview.import_button.text() == "导入 PPT"
    assert preview.viewer.interaction_mode == "preview"
    assert preview.splitter.sizes()[0] >= preview.MIN_THUMBNAIL_WIDTH


def test_preview_workspace_silent_selection_does_not_reemit(qapp, pages):
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)
    preview = PptPreviewWorkspace()
    preview.set_project(project, current_index=0)
    selected = QSignalSpy(preview.page_selected)

    preview.select_page(2, emit=False)

    assert preview.current_index == 2
    assert selected.count() == 0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -k "preview_workspace" -v
```

Expected: FAIL because `PptPreviewWorkspace` does not exist.

- [ ] **Step 3: Implement thumbnail silent selection**

Change `ThumbnailPanel.select_page` to accept `emit: bool = True` and use `QSignalBlocker` when synchronizing:

```python
def select_page(self, index: int, *, emit: bool = True) -> None:
    """选中并显示指定缩略图；同步更新时可禁止重复发出信号。"""
    if not 0 <= index < self.count():
        return
    blocker = None if emit else QSignalBlocker(self)
    self.setCurrentRow(index)
    self.scrollToItem(self.item(index))
    del blocker
```

- [ ] **Step 4: Implement `PptPreviewWorkspace`**

Create a focused widget with signals:

```python
class PptPreviewWorkspace(QWidget):
    """只读 PowerPoint 预览工作区。"""

    page_selected = Signal(int)
    import_requested = Signal()
    slideshow_requested = Signal()
    MIN_THUMBNAIL_WIDTH = 190
    MAX_THUMBNAIL_WIDTH = 300

    def set_project(self, project: SlideProject, current_index: int = 0) -> None:
        """加载项目并同步缩略图和中央页面。"""
        self._pages = list(project.pages)
        self.file_label.setText(Path(project.source_path).name)
        self.thumbnail_panel.set_pages(self._pages)
        self.select_page(current_index, emit=False)

    def select_page(self, index: int, *, emit: bool = False) -> None:
        """显示指定页面，并按需向主窗口发出用户选择。"""
        if not 0 <= index < len(self._pages):
            return
        self.current_index = index
        self.thumbnail_panel.select_page(index, emit=False)
        self.viewer.show_image(self._pages[index].image_path)
        self.page_label.setText(f"幻灯片 {index + 1} / {len(self._pages)}")
        if emit:
            self.page_selected.emit(index)
```

Assemble a fixed top command strip, `QSplitter` containing `ThumbnailPanel` and a central `SlideViewer`, and a compact status strip. Configure the viewer as `preview`; connect its `double_clicked` and the visible slideshow button to `slideshow_requested`.

- [ ] **Step 5: Run preview-workspace tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -k "preview_workspace" -v
```

Expected: PASS.

- [ ] **Step 6: Commit preview workspace**

```powershell
git add widgets\ppt_preview_workspace.py widgets\thumbnail_panel.py tests\test_stage_interactions.py
git commit -m "feat: add read-only ppt preview workspace"
```

### Task 3: Main Window PPT Submode State and Synchronization

**Files:**
- Modify: `app/main_window.py`
- Modify: `tests/test_stage_interactions.py`

- [ ] **Step 1: Replace old import-default assertion with preview-state tests**

```python
def test_import_defaults_to_ppt_preview_mode(qapp, monkeypatch, tmp_path, pages):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = MainWindow()
    window.show()
    project = SlideProject("source.pptx", "key", 1, 1.0, pages=pages)

    window._on_import_completed(SimpleNamespace(project=project, cache_hit=False))
    qapp.processEvents()

    assert window.presentation_mode == "ppt"
    assert window.ppt_view_mode == "preview"
    assert window.content_stack.currentWidget() is window.preview_workspace
    assert window.preview_workspace.import_button.isVisible()


def test_preview_and_slideshow_double_click_toggle_without_page_change(qapp, monkeypatch, tmp_path, pages):
    window = loaded_window(qapp, monkeypatch, tmp_path, pages)
    start_index = window.state.current_page

    QTest.mouseDClick(window.preview_workspace.viewer.viewport(), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert window.ppt_view_mode == "slideshow"

    QTest.mouseDClick(window.workspace.viewer.viewport(), Qt.MouseButton.LeftButton)
    QTest.qWait(QApplication.doubleClickInterval() + 20)
    assert window.ppt_view_mode == "preview"
    assert window.state.current_page == start_index
```

Also add tests for thumbnail-to-stage synchronization, stage-to-thumbnail synchronization, and `Ctrl+Alt+M` preserving the last PPT submode.

- [ ] **Step 2: Run main-window PPT submode tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -k "ppt_preview_mode or preview_and_slideshow or mode_shortcut" -v
```

Expected: FAIL because `ppt_view_mode` and `preview_workspace` are missing.

- [ ] **Step 3: Add PPT submode state and content page**

In `MainWindow.__init__`:

```python
self._presentation_mode = "ppt"
self._ppt_view_mode = "preview"
```

Expose a read-only property and add `PptPreviewWorkspace` in `_create_content`. Connect `import_requested`, `slideshow_requested`, and `page_selected` to existing import and new mode-selection handlers.

- [ ] **Step 4: Add explicit PPT view switching**

```python
def set_ppt_view_mode(self, mode: str) -> None:
    """切换 PPT 预览/放映子模式，不改变当前页。"""
    if mode not in {"preview", "slideshow"}:
        raise ValueError(f"未知 PPT 视图模式：{mode}")
    self._ppt_view_mode = mode
    if self._presentation_mode != "ppt" or not self.project:
        return
    target = self.preview_workspace if mode == "preview" else self.workspace
    self.content_stack.setCurrentWidget(target)
    self.workspace.viewer.set_interaction_mode("slideshow" if mode == "slideshow" else "gesture")
    self._apply_mode_chrome()
```

The preview double-click calls `set_ppt_view_mode("slideshow")`; slideshow double-click calls `set_ppt_view_mode("preview")`.

- [ ] **Step 5: Centralize page synchronization**

Add one internal coordinator:

```python
def _select_page(self, index: int, *, source: str) -> None:
    """统一同步预览、放映和项目页码，避免组件间递归调用。"""
    if not self.project or not 0 <= index < self.state.page_count:
        return
    self.state.current_page = index
    self.project.current_slide = index
    if source != "workspace":
        self.workspace.select_page(index)
    self.preview_workspace.select_page(index, emit=False)
    self._update_counter()
```

Route preview selection and `StageWorkspace.page_changed` through this method. On import, load both workspaces then select `preview`. On gesture toggle, preserve `_ppt_view_mode`; set the slideshow interaction policy only when PPT slideshow is actually visible.

- [ ] **Step 6: Apply mode-specific chrome policy**

Update `_apply_mode_chrome`:

- PPT preview: suppress stage overlay chrome because preview has fixed local controls.
- PPT slideshow: suppress and hide stage chrome exactly as before.
- Gesture: reveal and auto-hide existing stage chrome.
- Importing: keep current progress/cancel controls visible regardless of submode.

- [ ] **Step 7: Run main-window and gesture regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -v
```

Expected: PASS; update only assertions whose intended default changed from slideshow to preview.

- [ ] **Step 8: Commit main-window integration**

```powershell
git add app\main_window.py tests\test_stage_interactions.py
git commit -m "feat: add ppt preview and slideshow submodes"
```

### Task 4: Preview Styling and Responsive Visual Validation

**Files:**
- Modify: `app/theme.py`
- Modify: `tests/test_stage_interactions.py`
- Modify: `tests/visual_stage_smoke.py`

- [ ] **Step 1: Add failing structure and sizing assertions**

```python
def test_preview_layout_keeps_thumbnail_pane_bounded(qapp, pages):
    preview = PptPreviewWorkspace()
    preview.resize(1024, 768)
    preview.set_project(SlideProject("source.pptx", "key", 1, 1.0, pages=pages), 0)
    preview.show()
    qapp.processEvents()

    thumbnail_width = preview.thumbnail_panel.width()
    assert preview.MIN_THUMBNAIL_WIDTH <= thumbnail_width <= preview.MAX_THUMBNAIL_WIDTH
    assert preview.viewer.viewport().width() > thumbnail_width * 2
```

- [ ] **Step 2: Run sizing test and verify failure before constraints are applied**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py::test_preview_layout_keeps_thumbnail_pane_bounded -v
```

Expected: FAIL until splitter constraints and stretch factors are final.

- [ ] **Step 3: Add preview-specific theme rules**

Use the existing graphite-teal palette and `#3B6FFF` focus color. Style object names rather than broad widget types:

```css
#pptPreviewRoot { background: #111817; }
#pptPreviewCommandBar, #pptPreviewStatusBar { background: #171E1D; border-color: #2A3532; }
#pptThumbnailPane { background: #0E1313; border: 0; }
#pptThumbnailPane::item:selected { background: #202A28; border: 2px solid #3B6FFF; }
#pptPreviewSplitter::handle { background: #2A3532; width: 1px; }
```

Keep cards at 8 px radius or less, use existing line icons, and ensure all icon buttons have tooltips.

- [ ] **Step 4: Extend visual smoke capture**

Capture preview mode at `1440x900` and `1024x768`. Verify:

- visible import button;
- bounded left pane;
- full central slide with no clipping;
- no text/control overlap;
- current thumbnail selection visible;
- current page unchanged when entering slideshow and returning.

- [ ] **Step 5: Run interaction and visual smoke suites**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stage_interactions.py -v
.\.venv\Scripts\python.exe tests\visual_stage_smoke.py
```

Expected: all automated tests PASS and both preview screenshots are generated without overlap warnings.

- [ ] **Step 6: Commit styling and visual coverage**

```powershell
git add app\theme.py tests\test_stage_interactions.py tests\visual_stage_smoke.py
git commit -m "style: align ppt preview with normal view"
```

### Task 5: Documentation and Full Verification

**Files:**
- Modify: `README.md`
- Modify only if a reusable issue is discovered: `docs/agent-error-log.md`

- [ ] **Step 1: Document user-visible behavior**

Add concise Chinese instructions to `README.md`:

```markdown
- 导入或恢复 PPT 后默认进入预览模式，左侧缩略图可直接选页。
- 预览模式顶部的“导入 PPT”可随时打开其他演示文稿。
- 双击中央页面可进入放映；放映中双击返回预览且不会误翻页。
- 放映中单击、滚轮和 PowerPoint 常用键用于翻页。
- `Ctrl+Alt+M` 在 PPT 模式和手势模式之间双向切换。
```

- [ ] **Step 2: Run the full automated suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run startup smoke test**

Run:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication; from app.main_window import MainWindow; app=QApplication([]); window=MainWindow(); print(window.presentation_mode, window.ppt_view_mode)"
```

Expected output: `ppt preview`, with no uncaught exception.

- [ ] **Step 4: Review diff and workspace boundaries**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; unrelated pre-existing changes remain untouched.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md
git commit -m "docs: explain ppt preview workflow"
```

- [ ] **Step 6: Record durable project knowledge**

Save the architectural decision that PPT preview/slideshow state belongs to `MainWindow`, while `StageWorkspace.mode` remains gesture-only. If click arbitration reveals a reusable Qt event-order pitfall, append it to `docs/agent-error-log.md` and save a solution memory.
