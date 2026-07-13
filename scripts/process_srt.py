"""
process_srt.py — One-click SRT to HyperFrames video (global node_modules)

Usage:
    python scripts/process_srt.py path/to/your.srt

Steps (all automated):
    1. Parse SRT -> srt_data.json
    2. Generate scene HTML files + index.html + hyperframes.json
    3. Create package.json + link shared node_modules
    4. Render to MP4
"""

import argparse, json, os, sys, subprocess, re, shutil

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
PROJECTS_DIR = os.path.join(ROOT_DIR, "projects")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates")
GLOBAL_NM_DIR = os.path.join(ROOT_DIR, "global_node_modules")
DEFAULT_TEMPLATE = os.path.join(TEMPLATES_DIR, "podcast-enhanced-template.html")


def ensure_global_deps():
    """Ensure the shared node_modules exists with hyperframes installed."""
    nm_path = os.path.join(GLOBAL_NM_DIR, "node_modules")
    bin_path = os.path.join(nm_path, ".bin", "hyperframes")

    if os.path.isdir(nm_path) and (os.path.isfile(bin_path) or os.path.islink(bin_path)):
        return  # already set up

    print(f"  [setup] Initializing shared node_modules in {GLOBAL_NM_DIR}...")
    os.makedirs(GLOBAL_NM_DIR, exist_ok=True)

    # Create package.json if missing
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

    # npm install (only once)
    run_cmd(["npm", "install"], cwd=GLOBAL_NM_DIR)


def link_node_modules(hf_dir):
    """Replace per-project node_modules with a junction to the shared one."""
    nm_path = os.path.join(hf_dir, "node_modules")

    # Remove existing node_modules (real dir or broken link)
    if os.path.isdir(nm_path) or os.path.islink(nm_path):
        try:
            if os.path.islink(nm_path):
                os.unlink(nm_path)
            else:
                shutil.rmtree(nm_path, ignore_errors=True)
        except Exception:
            pass

    # Create junction pointing to global node_modules
    target = os.path.join(GLOBAL_NM_DIR, "node_modules")
    if not os.path.isdir(target):
        print("  [WARNING] Shared node_modules not found, running setup...")
        ensure_global_deps()

    # Use mklink /J (junction) on Windows
    print(f"  Linking node_modules -> {target}")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", nm_path, target],
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        print(f"  [WARNING] Junction creation failed: {result.stderr.strip()}")
        print(f"  Falling back to copying package.json only (npx will install on demand)")


def get_project_name(srt_path):
    basename = os.path.splitext(os.path.basename(srt_path))[0]
    name = re.sub(r'[\\/*?:\"<>|]', '', basename)
    name = re.sub(r'\s+', '-', name.strip())
    if len(name) > 50:
        name = name[:50].rstrip('-')
    return name.lower()


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


def main():
    parser = argparse.ArgumentParser(
        description="Process an SRT file into a HyperFrames video (one-click)")
    parser.add_argument("input", help="Path to the .srt file")
    parser.add_argument("--project-dir", help="Output project directory")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE)
    parser.add_argument("--title", help="Video title")
    parser.add_argument("--quality", choices=["draft", "standard", "high"], default="standard")
    parser.add_argument("--output", help="Output video filename")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: SRT file not found -> {args.input}", file=sys.stderr)
        sys.exit(1)

    srt_path = os.path.abspath(args.input)
    project_name = get_project_name(srt_path)
    proj_dir = os.path.abspath(args.project_dir) if args.project_dir else os.path.join(PROJECTS_DIR, project_name)
    title = args.title or project_name.replace('-', ' ').title()
    template_path = os.path.abspath(args.template)
    hf_dir = os.path.join(proj_dir, "srt-html-video")
    data_path = os.path.join(proj_dir, "srt_data.json")

    print("=" * 50)
    print(f"  SRT:    {os.path.basename(srt_path)}")
    print(f"  Output: {proj_dir}")
    print("=" * 50)

    os.makedirs(proj_dir, exist_ok=True)

    # Step 1: Parse SRT
    print("\n[1/4] Parsing SRT...")
    parse_script = os.path.join(SCRIPTS_DIR, "parse_srt.py")
    result = subprocess.run([sys.executable, parse_script, srt_path, data_path],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout.strip())

    # Step 2: Generate scenes
    print("\n[2/4] Generating scenes...")
    gen_script = os.path.join(SCRIPTS_DIR, "gen_scenes.py")
    result = subprocess.run(
        [sys.executable, gen_script, "--data", data_path, "--template", template_path,
         "--output", hf_dir, "--title", title],
        capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout.strip())

    shutil.copy2(srt_path, proj_dir)

    # Step 3: Shared node_modules (lazy init + junction)
    print("\n[3/4] Setting up shared dependencies...")
    ensure_global_deps()

    # Create package.json in project dir (needed by npx)
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

    # Link project node_modules -> shared node_modules
    link_node_modules(hf_dir)

    # Step 4: Render
    output_name = args.output or f"renders/{project_name}.mp4"
    print(f"\n[4/4] Rendering video ({args.quality} quality)...")
    render_cmd = [
        "npx", "hyperframes", "render",
        "--output", output_name,
        "--gpu", "--workers", "1",
        "--quality", args.quality
    ]
    code = run_cmd(render_cmd, cwd=hf_dir)

    if code == 0:
        print(f"\n{'=' * 50}")
        print(f"  ALL DONE! Video saved to:")
        print(f"  {os.path.join(hf_dir, output_name)}")
        print(f"{'=' * 50}")
    else:
        print(f"\n  Render had issues (exit code {code}), but scene files are ready at:")
        print(f"  {hf_dir}")


if __name__ == "__main__":
    main()
