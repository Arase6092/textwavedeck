# WaveDeck - Control Your Slides in the Air

[English README](README.md) · [Windows 下载包](https://github.com/LLK-LL/textwavedeck/releases/download/v0.1.0/WaveDeck-v0.1.0-windows-x64.zip) · [模式与手势说明](docs/gesture-controls.zh-CN.md) · [英文手势说明](docs/gesture-controls.md) · [全部 Releases](https://github.com/LLK-LL/textwavedeck/releases) · [Release Notes](docs/release-v0.1.0.md) · [隐私说明](docs/security-and-privacy.md)

WaveDeck 是一个面向 Windows 的本地优先 PPT 演示舞台。它把现成的 `.ppt` / `.pptx` 转成清晰的 4K 页面缓存，提供缩略图预览、纯净放映和黑匣子剧场式滚筒选页体验，并为后续手势控制保留了统一的导航命令层。

> 先把“看 PPT、切 PPT、放 PPT”这件事做到顺手，再把手势控制接上去。

![WaveDeck 封面](docs/screenshots/wavedeck-cover.png)

## 下载

如果你想最快试起来：

- 直接下载 Windows 包：[WaveDeck-v0.1.0-windows-x64.zip](https://github.com/LLK-LL/textwavedeck/releases/download/v0.1.0/WaveDeck-v0.1.0-windows-x64.zip)
- 目标机器仍需安装 Microsoft PowerPoint
- 下载包不需要额外安装 Python

## 为什么它更容易吸引人

- 不要求你重做 PPT，只是把现有 deck 变得更顺手
- 页面保持原色，但浏览方式明显更高级
- 不是只有一种“翻页窗口”，而是三种明确分工的演示表面
- 默认展示里不塞摄像头画面，更适合公开演示和项目展示

## 它能做什么

- 导入现成的 PowerPoint 文件，不改源文件。
- 通过 Microsoft PowerPoint COM 保真导出 PNG 页面。
- 将导出结果缓存在本机，重复打开更快。
- 提供三种浏览与演示表面：
  缩略图预览、单页放映、五页剧场滚筒。
- 支持键盘、鼠标、全屏、缩放、拖动与页码跳转。
- 整个导入和缓存流程都在本地完成，不上传 PPT 内容。

## 为什么做它

常见演示体验里总有一个问题：

- PowerPoint 保真，但浏览和切换不够轻快。
- 图片浏览器很快，但不懂 PowerPoint 的导出与页面关系。
- 很多“手势翻页”演示把镜头放在摄像头上，却没有把 PPT 本身的浏览体验做好。

WaveDeck 的思路正好相反：先把演示舞台做好，再把手势映射到稳定的本地翻页命令上。

## 前后对比

| 常见方式 | WaveDeck |
| --- | --- |
| 每次重新打开大 PPT 都等 PowerPoint | 首次导出后命中本地缓存 |
| 编辑视图和放映视图来回切 | 预览、放映、滚筒三种模式顺滑切换 |
| 缩略图栏拥挤、上下文弱 | 左侧独立缩略图轨道，中央专注看页 |
| 演示界面和媒体界面混在一起 | 保留 PPT 原色，用暗场舞台托起页面 |

## 使用截图

公开展示截图只展示页面体验，不包含摄像头画面。

![PPT 预览模式](docs/screenshots/ppt-preview.png)

![单页放映模式](docs/screenshots/ppt-slideshow.png)

![剧场滚筒模式](docs/screenshots/gesture-carousel.png)

![单页舞台模式](docs/screenshots/gesture-stage.png)

![导入状态](docs/screenshots/importing-state.png)

## 项目亮点

- PowerPoint 原生导出：直接调用 PowerPoint，自带更高保真度。
- 4K 本地缓存：16:9 导出 `3840x2160`，4:3 导出 `3840x2880`。
- 黑匣子剧场风格：页面保留原色，外层用石墨青绿暗场承托。
- 五页滚筒布局：中心页突出，前后两级页面同时保留上下文。
- 本地优先：不上传、不云转码、不把 PPT 内容写进日志。
- 手势就绪架构：后续手势层可以直接复用现有导航命令。

## 适合谁

- 经常重复查看大型 PPT 的演示者
- 需要快速找页、看上下文的研究者、顾问、教师
- 想在 Windows 真正演示链路上实验手势交互的开发者

## 快速开始

### 运行前提

- Windows 10 / 11
- Python 3.11
- Microsoft PowerPoint 2016 或更高版本

### 方案 A：直接下载可运行包

1. 下载 [WaveDeck-v0.1.0-windows-x64.zip](https://github.com/LLK-LL/textwavedeck/releases/download/v0.1.0/WaveDeck-v0.1.0-windows-x64.zip)
2. 解压
3. 运行 `WaveDeck.exe` 或 `Launch-WaveDeck.cmd`

### 方案 B：从源码运行

安装：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果默认源较慢，可使用：

```powershell
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

启动：

```powershell
启动手势控制PPT.cmd
```

或者：

```powershell
.venv\Scripts\python.exe main.py
```

## 一条典型工作流

1. 打开 `.ppt` 或 `.pptx`。
2. 等待程序完成首轮导出并建立缓存。
3. 在预览模式下用缩略图快速找页。
4. 双击进入放映模式，专注展示当前页。
5. 按 `Ctrl+Alt+M` 切到剧场滚筒，用空间化方式挑页。

更详细的流程见 [examples/quick-start.md](examples/quick-start.md) 和 [examples/presentation-modes.md](examples/presentation-modes.md)。

## 典型使用场景

- 命中缓存后快速重开大型 PPT
- 在单页舞台里放大查看密集图表
- 在滚筒里凭空间位置找相邻页面
- 保持本地离线的 Windows 演示流程

## 交互与快捷键

- `Ctrl+O`：打开 PPT
- `Ctrl+Alt+M`：切换 PPT 模式和剧场模式
- `PageDown` / `Right` / `Space` / `N`：下一页
- `PageUp` / `Left` / `P`：上一页
- `Home` / `End`：首页 / 末页
- `F11`：进入或退出全屏
- `Esc`：退出全屏，或从单页舞台回到滚筒
- 单页舞台滚轮：缩放
- 单页舞台拖动：平移或切页

更完整的公开控制说明，包括模式切换和手势映射总表，见 [docs/gesture-controls.zh-CN.md](docs/gesture-controls.zh-CN.md)。

## 目录结构

```text
app/        主窗口、主题、后台任务、导航绑定
gesture/    实验性手势运行时与诊断
models/     项目与页面元数据
ppt/        PowerPoint 导出、缓存、项目持久化
tests/      单元测试、COM 冒烟测试、视觉冒烟测试
widgets/    预览区、滚筒、单页舞台、覆盖层
docs/       发布说明、隐私说明、架构说明、截图
examples/   使用示例
scripts/    打包与发布辅助脚本
```

## 安全与隐私

- 导出与缓存全部在本机完成。
- 日志不记录 PPT 内容。
- 缓存替换采用原子流程，避免覆盖有效结果。
- 程序不会自动安装 PowerPoint、Python 或第三方包。

详见 [docs/security-and-privacy.md](docs/security-and-privacy.md)。
Windows 下载包结构见 [docs/windows-package.md](docs/windows-package.md)。

## 当前状态

`v0.1.0` 是公开首发版本。

当前稳定能力：

- PowerPoint 导入与 4K 导出
- 本地缓存校验
- 预览、放映、滚筒、单页舞台
- 鼠标与键盘导航
- 全屏与减少动态模式

仍在持续完善：

- 手势默认交互
- 更完整的诊断与引导

## 路线图

- 完善面向普通用户的发布包
- 在不让摄像头画面成为默认 UI 一部分的前提下继续优化手势控制
- 增加示例演示和展示素材
- 扩充自动化视觉验证

## 参与贡献

欢迎围绕 Windows 体验、PowerPoint 保真、缓存、测试、打包等方向提交贡献。

提交 PR 前请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，并确保：

- 不上传私有 PPT、密钥、客户数据
- README 和截图描述与真实行为一致
- 新改动附带匹配风险级别的验证

## 一句话总结

WaveDeck 把本地 PPT 变成一个更像“演示舞台”的体验，而不是一个只能翻页的文件窗口。
