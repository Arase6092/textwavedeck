# Gesture PPT 第一阶段

这是一个 Windows 桌面 PPT 放映器。程序使用 Microsoft PowerPoint COM 将 `.ppt` / `.pptx` 按原始比例导出为接近 4K 的 PNG，默认以接近 PowerPoint Slide Show 的 PPT 模式显示当前页；按 `Ctrl+Alt+M` 可切换到黑匣子暗场中的五页圆柱滚筒手势模式，再按一次返回 PPT 模式。

## 运行前提

- Windows 10/11 64 位
- Python 3.11
- Microsoft PowerPoint 2016 或更高版本

## 安装与启动

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
启动手势控制PPT.cmd
```

如果默认包源下载 PySide6 超时，可使用：

```powershell
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

也可以直接执行 `.venv\Scripts\python.exe main.py`。

## 页面清晰度与缓存

- 16:9 页面导出为 `3840×2160`。
- 4:3 页面导出为 `3840×2880`。
- 其他比例按 `3840px` 宽度计算高度，不拉伸页面。
- 滚筒使用独立的 `640px` 宽 JPEG，单页舞台使用 4K PNG。
- 缓存 schema 已升级到版本 2，旧 1080p 缓存会自动失效并重新导出。

缓存位于 `%LOCALAPPDATA%\GesturePPT\projects\`，日志位于 `%LOCALAPPDATA%\GesturePPT\logs\gesture-ppt.log`。导出先写临时目录，完成校验后才替换正式缓存。

## 操作

### PPT 模式

- 导入完成后默认进入 PPT 模式，只显示当前幻灯片，不常驻显示应用工具栏。
- 16:9 页面在 16:9 窗口中贴合放映区域，其他比例保持原始比例并留黑边。
- `N` / `PageDown` / `Right` / `Down` / `Enter` / `Space`：下一页。
- `P` / `PageUp` / `Left` / `Up` / `Backspace`：上一页。
- `Home` / `End`：第一页 / 最后一页。
- 输入页码后按 `Enter`：跳转到指定页。
- `Esc`：退出全屏，不进入手势模式。
- `Ctrl+Alt+M`：进入手势模式。

### 手势模式

- 屏幕同时展示中央页和两级侧页共 5 页，侧页逐层压暗。
- 左右拖动：旋转滚筒，松手后吸附到最近页面。
- 快速拖动：保留短距离惯性，单次最多跨越 2 页。
- 点击侧面页面：将其移动到中央。
- 点击中央页面：返回 PPT 模式。
- 鼠标滚轮：按页旋转滚筒。
- `Ctrl+Alt+M`：返回 PPT 模式。

### 手势模式控制层

- 顶部和底部控制层在停止操作约 2 秒后自动隐藏。
- 鼠标靠近屏幕顶部或底部时，显示对应控制层。
- 导入期间控制层保持可见，底部显示进度和取消操作。
- 全屏模式同样通过屏幕边缘唤出控制层。
- 需要减少动画时，可在启动前设置 `GESTURE_PPT_REDUCED_MOTION=1`；此模式关闭惯性和大幅过渡。

### 键盘

- `Ctrl+O`：打开 PPT
- `Ctrl+Alt+M`：切换 PPT 模式 / 手势模式
- `PageUp` / `Left` / `P`：上一页
- `PageDown` / `Right` / `Space` / `N`：下一页
- `Home` / `End`：第一页 / 最后一页
- `F11`：进入或退出全屏

## 集成测试

```powershell
.venv\Scripts\python.exe tests\integration_powerpoint_smoke.py
```

测试会在 `D:\CodexCache` 创建临时的 16:9 与 4:3 PPT，验证 COM 导出像素、缩略图比例和缓存命中，结束后自动清理。

## 第一阶段边界

本阶段不包含摄像头、MediaPipe、手势识别、PPT 动画/音视频播放、编辑、批注和激光笔。第二阶段可将手势识别结果映射到现有的滚筒、翻页和视图命令。
