"""
process_srt.py — One-click SRT to HyperFrames video (global node_modules)

Usage:
    python scripts/process_srt.py path/to/your.srt

Steps (all automated):
    1. Split SRT into parts (90 lines per part, adjustable)
    2. For each part (serially):
        a. Parse SRT -> srt_data.json
        b. Generate scene HTML files + index.html + hyperframes.json
        c. Create package.json + link shared node_modules
        d. Render to MP4
        e. Verify output MP4 exists; if not, abort immediately
"""

import argparse, json, os, sys, subprocess, re, shutil

# 导入 parse_srt 以复用解析函数（不修改原文件）
import parse_srt

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
PROJECTS_DIR = os.path.join(ROOT_DIR, "projects")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates")
GLOBAL_NM_DIR = os.path.join(ROOT_DIR, "global_node_modules")
DEFAULT_TEMPLATE = os.path.join(TEMPLATES_DIR, "podcast-enhanced-template.html")

# ---------- 工具函数 ----------
def clean_filename(name: str) -> str:
    """将文件名中的特殊字符替换为下划线，确保安全"""
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    return name if name else "video"

def format_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def split_srt_file(input_srt_path: str, output_dir: str, lines_per_part: int = 50) -> list:
    """
    将 SRT 文件按指定句数分割，每个片段重新编号并从 0 开始计时。
    返回分割后的文件路径列表。
    """
    entries = parse_srt.parse_srt(input_srt_path)
    total = len(entries)
    part_files = []
    os.makedirs(output_dir, exist_ok=True)

    for part_num, start_idx in enumerate(range(0, total, lines_per_part), start=1):
        part_entries = entries[start_idx:start_idx+lines_per_part]
        if not part_entries:
            break

        # 计算基准时间（该片段第一句的起始时间）
        base_time = part_entries[0]['start']

        # 重新编号并调整时间
        for i, entry in enumerate(part_entries, start=1):
            entry['idx'] = i
            entry['start'] = entry['start'] - base_time
            entry['end'] = entry['end'] - base_time

        # 生成 SRT 内容
        lines = []
        for entry in part_entries:
            start_str = format_time(entry['start'])
            end_str = format_time(entry['end'])
            lines.append(f"{entry['idx']}\n{start_str} --> {end_str}\n{entry['text']}\n")
        content = "\n".join(lines) + "\n"

        part_filename = f"part{part_num}.srt"
        part_path = os.path.join(output_dir, part_filename)
        with open(part_path, 'w', encoding='utf-8') as f:
            f.write(content)
        part_files.append(part_path)

    return part_files

# ---------- 原有功能封装 ----------
def ensure_global_deps():
    """Ensure the shared node_modules exists with hyperframes installed."""
    nm_path = os.path.join(GLOBAL_NM_DIR, "node_modules")
    bin_path = os.path.join(nm_path, ".bin", "hyperframes")

    if os.path.isdir(nm_path) and (os.path.isfile(bin_path) or os.path.islink(bin_path)):
        return

    print(f"  [setup] Initializing shared node_modules in {GLOBAL_NM_DIR}...")
    os.makedirs(GLOBAL_NM_DIR, exist_ok=True)

    pkg_path = os.path.join(GLOBAL_NM_DIR, "package.json")
    if not os.path.isfile(pkg_path):
        pkg = {
            "name": "global-hyperframes",
            "version": "1.0.0",
            "private": True,
            "dependencies": {"hyperframes": "^0.7.39"}
        }
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(pkg, f, indent=2)
            f.write("\n")

    run_cmd(["npm", "install"], cwd=GLOBAL_NM_DIR)

def link_node_modules(hf_dir):
    """Replace per-project node_modules with a junction to the shared one."""
    nm_path = os.path.join(hf_dir, "node_modules")

    if os.path.isdir(nm_path) or os.path.islink(nm_path):
        try:
            if os.path.islink(nm_path):
                os.unlink(nm_path)
            else:
                shutil.rmtree(nm_path, ignore_errors=True)
        except Exception:
            pass

    target = os.path.join(GLOBAL_NM_DIR, "node_modules")
    if not os.path.isdir(target):
        print("  [WARNING] Shared node_modules not found, running setup...")
        ensure_global_deps()

    print(f"  Linking node_modules -> {target}")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", nm_path, target],
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        print(f"  [WARNING] Junction creation failed: {result.stderr.strip()}")
        print(f"  Falling back to copying package.json only (npx will install on demand)")

def run_cmd(cmd, cwd=None):
    """Run a shell command and stream output in real-time."""
    print(f"> {' '.join(cmd)}")
    process = subprocess.Popen(cmd, cwd=cwd, shell=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=False, bufsize=0)
    for raw_line in process.stdout:
        line = raw_line.decode('utf-8', errors='replace')
        print(line, end='')
    process.wait()
    if process.returncode != 0:
        print(f"  [WARNING] Command exited with code {process.returncode}")
    return process.returncode

def process_single_srt(srt_path, project_parent_dir, video_output_path,
                       template_path, title, quality):
    """
    处理单个 SRT 文件：解析 → 生成场景 → 渲染视频。
    所有输出均放在 project_parent_dir 下。
    返回 True 表示成功且视频文件存在；否则返回 False。
    """
    # 确保项目父目录存在
    os.makedirs(project_parent_dir, exist_ok=True)

    hf_dir = os.path.join(project_parent_dir, "srt-html-video")
    data_path = os.path.join(project_parent_dir, "srt_data.json")

    # 1. 解析 SRT
    print(f"\n[1/4] Parsing SRT: {os.path.basename(srt_path)}")
    parse_script = os.path.join(SCRIPTS_DIR, "parse_srt.py")
    result = subprocess.run(
        [sys.executable, parse_script, srt_path, data_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return False
    print(result.stdout.strip())

    # 2. 生成场景
    print("\n[2/4] Generating scenes...")
    gen_script = os.path.join(SCRIPTS_DIR, "gen_scenes.py")
    result = subprocess.run(
        [sys.executable, gen_script,
         "--data", data_path,
         "--template", template_path,
         "--output", hf_dir,
         "--title", title],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return False
    print(result.stdout.strip())

    # 复制原始 SRT 到项目目录（可选）
    shutil.copy2(srt_path, project_parent_dir)

    # 3. 依赖设置
    print("\n[3/4] Setting up shared dependencies...")
    ensure_global_deps()

    pkg_path = os.path.join(hf_dir, "package.json")
    if not os.path.isfile(pkg_path):
        pkg = {
            "name": os.path.basename(hf_dir),
            "version": "1.0.0",
            "private": True,
            "dependencies": {"hyperframes": "^0.7.39"}
        }
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(pkg, f, indent=2)
            f.write("\n")

    link_node_modules(hf_dir)

    # 4. 渲染视频
    print(f"\n[4/4] Rendering video ({quality} quality)...")
    render_cmd = [
        "npx", "hyperframes", "render",
        "--output", video_output_path,
        "--gpu", "--workers", "1",
        "--quality", quality
    ]
    code = run_cmd(render_cmd, cwd=hf_dir)

    # ========== 双重检查：进程成功 && 输出文件存在 ==========
    if code != 0:
        print(f"  [ERROR] Render process exited with code {code}", file=sys.stderr)
        return False

    if not os.path.isfile(video_output_path):
        print(f"  [ERROR] Render succeeded but output file missing: {video_output_path}", file=sys.stderr)
        return False

    return True

# ---------- 主函数 ----------
def main():
    parser = argparse.ArgumentParser(
        description="Process an SRT file into a HyperFrames video (one-click)")
    parser.add_argument("input", help="Path to the .srt file")
    parser.add_argument("--project-dir", help="Output project directory (used as base for parts)")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE)
    parser.add_argument("--title", help="Video title (base name for parts)")
    parser.add_argument("--quality", choices=["draft", "standard", "high"], default="standard")
    parser.add_argument("--output", help="Output video filename (ignored in split mode)")
    parser.add_argument("--split-parts", type=int, default=30,
                        help="Number of subtitles per part (default: 30)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: SRT file not found -> {args.input}", file=sys.stderr)
        sys.exit(1)

    srt_path = os.path.abspath(args.input)
    base_name = os.path.splitext(os.path.basename(srt_path))[0]
    clean_name = clean_filename(base_name)
    title = args.title or clean_name.replace('_', ' ').title()

    # 准备目录
    video_output_root = os.path.join(ROOT_DIR, "output", "video", clean_name)
    os.makedirs(video_output_root, exist_ok=True)

    # 分割 SRT
    parts_dir = os.path.join(PROJECTS_DIR, clean_name, "parts")
    print("=" * 50)
    print(f"  Splitting SRT into parts ({args.split_parts} lines each)...")
    part_files = split_srt_file(srt_path, parts_dir, args.split_parts)
    print(f"  Generated {len(part_files)} part(s).")
    print("=" * 50)

    # 串行处理每个 part
    for idx, part_path in enumerate(part_files, start=1):
        part_num = idx
        print(f"\n{'='*50}")
        print(f"  Processing Part {part_num}/{len(part_files)}")
        print(f"  SRT: {os.path.basename(part_path)}")
        print("=" * 50)

        part_title = f"{title} Part {part_num}"
        project_dir = os.path.join(PROJECTS_DIR, clean_name, f"part{part_num}")
        video_output = os.path.join(video_output_root, f"part{part_num}.mp4")

        success = process_single_srt(
            srt_path=part_path,
            project_parent_dir=project_dir,
            video_output_path=video_output,
            template_path=os.path.abspath(args.template),
            title=part_title,
            quality=args.quality
        )

        if not success:
            print(f"\n[FATAL] Part {part_num} failed. Aborting remaining parts.", file=sys.stderr)
            sys.exit(1)

        print(f"  Part {part_num} completed: {video_output}")

    print("\n" + "=" * 50)
    print(f"  All parts processed successfully. Videos saved in: {video_output_root}")
    print("=" * 50)

if __name__ == "__main__":
    main()