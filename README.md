
# SRT to HyperFrames Video

将 SRT 字幕文件一键转换为带动效的全高清视频。纯本地运行，无需 AI、无需联网。

## 效果

- 暖色毛玻璃背景 + 毛绒光晕
- 居中大字英文字幕，每次一个单词高亮（5 种动效轮流）
- emoji 装饰图标 / 渐变进度条 / 场景编号
- GSAP 入场 + 浮动 + 退场动画
- 1920×1080 全高清 MP4
- 支持长字幕自动分段，分段视频自动拼接

## 环境要求

| 工具 | 版本要求 | 说明 |
|---|---|---|
| Python | >= 3.10 | 解析 SRT、生成 HTML 场景 |
| Node.js | >= 22 | 运行 HyperFrames 渲染引擎 |
| FFmpeg | 任意版本 | 视频编码（HyperFrames 依赖） |
| Git | 任意版本 | （可选）克隆仓库 |

**额外依赖（GUI 界面需要）**：

```bash
pip install customtkinter
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/anchenliang/srt-html-video.git
cd srt-html-video
```

### 2. 确认环境

```bash
python --version    # >= 3.10
node --version      # >= 22
ffmpeg -version     # 可用即可
```

**如果缺少 FFmpeg**：

- **Windows**：`winget install ffmpeg` 或从 [ffmpeg.org](https://ffmpeg.org) 下载  
- **macOS**：`brew install ffmpeg`  
- **Linux**：`sudo apt install ffmpeg`  

推荐使用安装工具：[https://github.com/oop7/ffmpeg-install-guide/releases](https://github.com/oop7/ffmpeg-install-guide/releases)

**安装 GUI 依赖**（若需图形界面）：

```bash
pip install customtkinter
```

### 3. 一键生成视频（两种方式任选）

#### 方式一：命令行（适合脚本集成）

```bash
python scripts/main.py 你的字幕文件.srt
```

首次运行会自动在 `global_node_modules/` 中安装 `hyperframes`（约 300MB），之后渲染会复用该依赖。

#### 方式二：图形界面（推荐新手）

```bash
python scripts/gui.py
```

界面支持：
- 浏览选择 SRT 文件
- 实时进度条和日志输出
- 在线调整分段行数、渲染质量、工作线程数、模板路径
- 完成后一键打开输出文件夹

### 完整示例（命令行）

```bash
python scripts/main.py my-talk.srt --title "My Podcast" --quality draft --split-parts 50 --workers 2
```

### 参数说明（命令行）

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--title` | 视频标题 | 由文件名自动生成 |
| `--quality` | 渲染质量：`draft` / `standard` / `high` | `standard` |
| `--split-parts` | 每个分段包含的字幕条数 | `30` |
| `--workers` | 并行渲染工作线程数 | `1` |
| `--template` | 自定义模板 HTML 路径 | `scripts/templates/podcast-enhanced-template.html` |

> 若在 GUI 中修改参数，仅本次运行生效；如需永久修改，请编辑 `scripts/config.json`。

## 输出与文件结构

```
output/video/<clean_name>/
├── part1.mp4          # 第1段视频
├── part2.mp4          # 第2段视频
├── ...
├── all.mp4            # 所有分段拼接后的完整视频
└── summary.txt        # 生成记录（参数、时长、帧数等）
```

## 项目结构

```
├── scripts/
│   ├── main.py                ← 命令行主入口
│   ├── gui.py                 ← 图形界面入口
│   ├── config.json            ← 默认参数配置
│   ├── video_renderer.py      ← 核心渲染流程
│   ├── gen_scenes.py          ← 场景 HTML 生成
│   ├── parse_srt.py           ← SRT 解析
│   ├── process_srt.py         ← 字幕分割工具
│   ├── concat_videos.py       ← 视频拼接
│   └── templates/
│       └── podcast-enhanced-template.html   ← 默认画面模板
├── allPicture/                ← 随机背景图片库（可自行替换）
├── global_node_modules/       ← 全局共享的 Node 依赖（避免重复下载）
├── projects/                  ← 每个任务的工作目录（含中间文件）
├── output/video/              ← 最终生成的视频
└── gsap/                      ← 本地 GSAP 库（CDN 备用）
```

## 自定义画面风格

编辑 `scripts/templates/podcast-enhanced-template.html`，修改颜色、字体、布局、动画等，所有场景会自动继承。

```bash
# 使用自定义模板（命令行）
python scripts/main.py my-talk.srt --template my-style.html
```

## 手动逐步执行（分步调试）

```bash
# 1. 解析 SRT
python scripts/parse_srt.py input.srt projects/my-video/srt_data.json

# 2. 生成场景
python scripts/gen_scenes.py \
    --data projects/my-video/srt_data.json \
    --template scripts/templates/podcast-enhanced-template.html \
    --output projects/my-video/srt-html-video \
    --title "My Video"

# 3. 渲染
cd projects/my-video/srt-html-video
npx hyperframes render --output renders/final.mp4 --gpu --workers 2
```

## 常见问题

**Q：渲染报错 `UnicodeEncodeError: 'gbk' codec can't encode character`**  
A：已修复于最新代码，如仍出现，请在命令行执行前设置 `set PYTHONIOENCODING=utf-8`。

**Q：Junction 创建失败（Windows 上）**  
A：该警告不影响功能，`npx` 会在项目目录按需安装依赖；若希望完全离线，可手动删除 `projects/<项目>/part*/srt-html-video/node_modules` 后重试。

**Q：如何更换背景图片？**  
A：将图片放入 `allPicture/` 目录（支持 png/jpg/webp/gif），程序会随机选取并适配。

## 技术栈

- **Python** — SRT 解析、HTML 模板生成、流程控制
- **HyperFrames** (npm) — 基于 Chrome 的 HTML → 视频渲染引擎
- **GSAP** — 场景内动画（入场、浮动、退场）
- **FFmpeg** — 视频编码封装
- **CustomTkinter** — 图形界面（仅 GUI 模式）
