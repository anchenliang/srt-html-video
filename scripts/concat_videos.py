"""
concat_videos.py — Concatenate multiple part videos into a single all.mp4

Usage:
    python scripts/concat_videos.py [project_name]

If no project_name is given, it lists all available projects in output/video/
and asks the user to choose one.

Example:
    python scripts/concat_videos.py Howto4_part4_shifted
"""

import os, sys, subprocess, glob, re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_VIDEO_DIR = os.path.join(ROOT_DIR, "output", "video")

def find_projects():
    """Return list of project directories under output/video/"""
    if not os.path.isdir(OUTPUT_VIDEO_DIR):
        return []
    dirs = [d for d in os.listdir(OUTPUT_VIDEO_DIR) if os.path.isdir(os.path.join(OUTPUT_VIDEO_DIR, d))]
    return sorted(dirs)

def get_part_files(project_dir):
    """Return sorted list of part*.mp4 files in the project directory"""
    pattern = os.path.join(project_dir, "part*.mp4")
    files = glob.glob(pattern)
    # Sort numerically by part number
    def extract_num(f):
        basename = os.path.basename(f)
        match = re.search(r'part(\d+)\.mp4', basename)
        return int(match.group(1)) if match else 0
    return sorted(files, key=extract_num)

def concat_videos(part_files, output_path):
    """
    Concatenate videos using ffmpeg concat demuxer.
    Requires all videos to have the same codec/resolution.
    """
    if len(part_files) < 2:
        print("  Need at least 2 videos to concatenate.")
        return False

    # Create a temporary file list for ffmpeg
    list_file = os.path.join(os.path.dirname(output_path), "concat_list.txt")
    with open(list_file, 'w', encoding='utf-8') as f:
        for p in part_files:
            # Escape special characters for ffmpeg
            escaped = p.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]
    print(f"  Concatenating {len(part_files)} videos...")
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Clean up temporary file
    try:
        os.remove(list_file)
    except OSError:
        pass

    if result.returncode != 0:
        print(f"  [ERROR] ffmpeg failed: {result.stderr}", file=sys.stderr)
        return False

    if os.path.isfile(output_path):
        print(f"  Success: {output_path}")
        return True
    else:
        print(f"  [ERROR] Output file not created: {output_path}", file=sys.stderr)
        return False

def concat_project(project_dir, overwrite=False):
    """
    Concatenate all part*.mp4 files in project_dir into all.mp4.
    
    Args:
        project_dir (str): Path to the project directory containing part*.mp4 files.
        overwrite (bool): Whether to overwrite existing all.mp4. (ffmpeg -y always overwrites)
    
    Returns:
        (bool, str or None): (success, output_path) or (False, None) on failure.
    """
    if not os.path.isdir(project_dir):
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        return False, None

    part_files = get_part_files(project_dir)
    if not part_files:
        print(f"No part*.mp4 files found in {project_dir}", file=sys.stderr)
        return False, None

    if len(part_files) < 2:
        print("Need at least 2 parts to concatenate.", file=sys.stderr)
        return False, None

    output_path = os.path.join(project_dir, "all.mp4")
    # 如果不想覆盖，可以检查文件存在性（但 ffmpeg -y 会强制覆盖，此处保留 overwrite 参数以便未来扩展）
    if os.path.isfile(output_path) and not overwrite:
        print(f"Output file {output_path} already exists. Use overwrite=True to force.", file=sys.stderr)
        return False, None

    success = concat_videos(part_files, output_path)
    return success, output_path if success else None


def main():
    args = sys.argv[1:]
    project_name = args[0] if args else None

    if not project_name:
        # List available projects
        projects = find_projects()
        if not projects:
            print("No projects found in output/video/.", file=sys.stderr)
            sys.exit(1)
        print("Available projects:")
        for i, p in enumerate(projects, start=1):
            print(f"  {i}. {p}")
        try:
            choice = input("Enter the number of the project to concatenate: ")
            idx = int(choice) - 1
            if idx < 0 or idx >= len(projects):
                print("Invalid choice.", file=sys.stderr)
                sys.exit(1)
            project_name = projects[idx]
        except (ValueError, KeyboardInterrupt):
            print("Aborted.", file=sys.stderr)
            sys.exit(1)

    project_dir = os.path.join(OUTPUT_VIDEO_DIR, project_name)
    if not os.path.isdir(project_dir):
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    part_files = get_part_files(project_dir)
    if not part_files:
        print(f"No part*.mp4 files found in {project_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = os.path.join(project_dir, "all.mp4")
    if os.path.isfile(output_path):
        overwrite = input(f"Output file {output_path} already exists. Overwrite? (y/n): ")
        if overwrite.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

    print(f"Project: {project_name}")
    print(f"Found {len(part_files)} parts: {[os.path.basename(p) for p in part_files]}")
    success = concat_videos(part_files, output_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()