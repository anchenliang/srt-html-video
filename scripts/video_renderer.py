"""
video_renderer.py — Render a single SRT file to MP4 using HyperFrames

Handles parsing, scene generation, dependency setup, and rendering.
"""

import json, os, sys, subprocess, shutil

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBAL_NM_DIR = os.path.join(ROOT_DIR, "global_node_modules")

# ---------- 辅助函数（原 process_srt 中的部分） ----------
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
        # 解码为 UTF-8，忽略错误
        try:
            line = raw_line.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            line = raw_line.decode('gbk', errors='replace')
        # 直接写入二进制流，避免控制台编码问题
        sys.stdout.buffer.write(line.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
        sys.stdout.buffer.flush()
    process.wait()
    if process.returncode != 0:
        print(f"  [WARNING] Command exited with code {process.returncode}")
    return process.returncode

# ---------- 核心渲染函数 ----------
def render_srt_to_video(srt_path, project_parent_dir, video_output_path,
                        template_path, title, quality, workers=1):
    """
    处理单个 SRT 文件：解析 → 生成场景 → 渲染视频。
    所有输出均放在 project_parent_dir 下。
    返回 True 表示成功且视频文件存在；否则返回 False。
    """
    # 确保项目父目录存在
    os.makedirs(project_parent_dir, exist_ok=True)

    hf_dir = os.path.join(project_parent_dir, "srt-html-video")
    data_path = os.path.join(project_parent_dir, "srt_data.json")

    # 1. 解析 SRT（调用 parse_srt.py 子进程）
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

    # 2. 生成场景（调用 gen_scenes.py）
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

    # 4. 渲染视频（使用传入的 workers）
    print(f"\n[4/4] Rendering video ({quality} quality, {workers} worker(s))...")
    render_cmd = [
        "npx", "hyperframes", "render",
        "--output", video_output_path,
        "--gpu", "--workers", str(workers),
        "--quality", quality
    ]
    code = run_cmd(render_cmd, cwd=hf_dir)

    # 双重检查：进程成功 && 输出文件存在
    if code != 0:
        print(f"  [ERROR] Render process exited with code {code}", file=sys.stderr)
        return False

    if not os.path.isfile(video_output_path):
        print(f"  [ERROR] Render succeeded but output file missing: {video_output_path}", file=sys.stderr)
        return False

    return True