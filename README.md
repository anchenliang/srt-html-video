# SRT to HyperFrames Video

将 SRT 字幕文件一键转换为带动效的视频。无需 AI、无需 Codex、无需任何智能体工具，纯本地运行。

## 效果

- 暖色毛玻璃背景 + 毛绒光晕
- 居中大字英文字幕，每次一个单词高亮（5 种动效轮流）
- emoji 装饰图标 / 渐变进度条 / 场景编号
- GSAP 入场 + 浮动 + 退场动画
- 1920×1080 全高清 MP4



## 环境要求

| 工具 | 版本要求 | 说明 |
|---|---|---|
| Python | >= 3.10 | 解析 SRT、生成 HTML 场景 |
| Node.js | >= 22 | 运行 HyperFrames 渲染引擎 |
| FFmpeg | 任意版本 | 视频编码（HyperFrames 依赖） |
| Git | 任意版本 | （可选）克隆仓库 |

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

**如果缺少 FFmpeg：**

- **Windows**：`winget install ffmpeg` 或从 [ffmpeg.org](https://ffmpeg.org) 下载
- **macOS**：`brew install ffmpeg`
- **Linux**：`sudo apt install ffmpeg`

### 3. 一键生成视频

```bash
# 把 .srt 文件放到项目目录下
python scripts/process_srt.py 你的字幕文件.srt
```

首次运行会自动 `npm install`（会下载 Chromium 浏览器，约 300MB），然后自动渲染视频。

最终视频保存在 `projects/<srt文件名>/srt-html-video/renders/` 目录下。

### 完整示例

```bash
python scripts/process_srt.py my-talk.srt --title "My Podcast" --quality draft
```

### 参数说明

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--title` | 视频标题 | 由 SRT 文件名自动生成 |
| `--quality` | 渲染质量：`draft` / `standard` / `high` | `standard` |
| `--project-dir` | 输出目录 | `projects/<srt文件名>/` |
| `--template` | 场景模板 HTML | `templates/podcast-ref-template.html` |
| `--output` | 输出视频文件名 | `renders/<srt文件名>.mp4` |

## 项目结构

```
├── scripts/
│   ├── process_srt.py          ← 一键入口（解析 + 生成 + 渲染）
│   ├── parse_srt.py            ← SRT 解析器
│   └── gen_scenes.py           ← 场景生成器
├── templates/
│   └── podcast-ref-template.html  ← 画面设计模板
├── projects/                   ← 每个 SRT 的项目目录
│   └── <项目名>/
│       ├── 原始.srt
│       ├── srt_data.json
│       └── srt-html-video/
│           ├── compositions/   ← 场景 HTML 文件
│           ├── index.html
│           ├── hyperframes.json
│           └── renders/        ← 最终 MP4 视频
└── .gitignore
```

## 自定义画面风格

编辑 `templates/podcast-ref-template.html`，修改颜色、字体、布局、动画等，所有场景会自动继承。

```bash
# 使用自定义模板
python scripts/process_srt.py my-talk.srt --template templates/my-style.html
```

## 逐步执行（不想要一键）

```bash
# 1. 解析 SRT
python scripts/parse_srt.py input.srt projects/my-video/srt_data.json

# 2. 生成场景
python scripts/gen_scenes.py \
    --data projects/my-video/srt_data.json \
    --template templates/podcast-ref-template.html \
    --output projects/my-video/srt-html-video \
    --title "My Video"

# 3. 渲染
cd projects/my-video/srt-html-video
npm install
npx hyperframes render --output renders/final.mp4 --gpu --workers 2
```

## 技术栈

- **Python** — SRT 解析、HTML 模板生成
- **HyperFrames** (npm) — 基于 Chrome 的 HTML → 视频渲染引擎
- **GSAP** — 场景内动画（入场、浮动、退场）
- **FFmpeg** — 视频编码封装
