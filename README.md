# Gesture PPT 第一阶段

这是一个 Windows 桌面 PPT 页面舞台。程序使用 Microsoft PowerPoint COM 将 `.ppt` / `.pptx` 按原始比例导出为接近 4K 的 PNG，再通过圆柱滚筒选择页面，并在完整单页舞台中浏览、缩放和滑动翻页。

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

### 页面滚筒

- 左右拖动：旋转滚筒，松手后吸附到最近页面。
- 点击侧面页面：将其移动到中央。
- 点击中央页面：进入完整单页舞台。
- 鼠标滚轮：按页旋转滚筒。

### 单页舞台

- 适应窗口时左右拖动：上一页或下一页。
- 页面放大后拖动：平移画面，不触发翻页。
- 鼠标滚轮：缩放页面。
- 双击：在适应窗口与 `100%` 之间切换。
- `Esc`：非全屏时返回页面滚筒；全屏时先退出全屏。

### 键盘

- `Ctrl+O`：打开 PPT
- `PageUp` / `Left`：上一页
- `PageDown` / `Right` / `Space`：下一页
- `Home` / `End`：第一页 / 最后一页
- `F11`：进入或退出全屏

## 集成测试

```powershell
.venv\Scripts\python.exe tests\integration_powerpoint_smoke.py
```

测试会在 `D:\CodexCache` 创建临时的 16:9 与 4:3 PPT，验证 COM 导出像素、缩略图比例和缓存命中，结束后自动清理。

## 第一阶段边界

本阶段不包含摄像头、MediaPipe、手势识别、PPT 动画/音视频播放、编辑、批注和激光笔。第二阶段可将手势识别结果映射到现有的滚筒、翻页和视图命令。
