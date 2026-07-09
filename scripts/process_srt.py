"""
process_srt.py — One-click SRT to HyperFrames video

Usage:
    python scripts/process_srt.py path/to/your.srt

Steps (all automated):
    1. Parse SRT -> srt_data.json
    2. Generate scene HTML files + index.html + hyperframes.json
    3. Create package.json + npm install
    4. Render to MP4
"""

import argparse, json, os, sys, subprocess, re, shutil

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(os.path.dirname(SCRIPTS_DIR), "projects")
TEMPLATES_DIR = os.path.join(os.path.dirname(SCRIPTS_DIR), "templates")
DEFAULT_TEMPLATE = os.path.join(TEMPLATES_DIR, "podcast-ref-template.html")

PACKAGE_JSON = json.dumps({
    "name": "srt-html-video",
    "version": "1.0.0",
    "private": True,
    "dependencies": {
        "hyperframes": "^0.7.39"
    }
}, indent=2)


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

    # Step 2.5: Create package.json if missing
    pkg_path = os.path.join(hf_dir, "package.json")
    if not os.path.isfile(pkg_path):
        with open(pkg_path, "w", encoding="utf-8") as f:
            f.write(PACKAGE_JSON + "\n")

    # Step 3: npm install
    print("\n[3/4] Installing dependencies (npm install)...")
    node_modules = os.path.join(hf_dir, "node_modules")
    if not os.path.isdir(node_modules):
        run_cmd(["npm", "install"], cwd=hf_dir)
    else:
        print("  (node_modules already exists, skipping)")

    # Step 4: Render
    output_name = args.output or f"renders/{project_name}.mp4"
    print(f"\n[4/4] Rendering video ({args.quality} quality)...")
    render_cmd = [
        "npx", "hyperframes", "render",
        "--output", output_name,
        "--gpu", "--workers", "2",
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
