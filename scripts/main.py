"""
main.py — Unified entry point for SRT to video pipeline

Usage:
    # 单文件处理
    python scripts/main.py path/to/your.srt [options]

    # 批量处理目录
    python scripts/main.py --dir path/to/srt_folder [--recursive] [options]

Options:
    --template PATH        HTML template file (overrides config)
    --title TITLE          Base title for all parts
    --quality {draft,standard,high}  Render quality
    --split-parts N        Number of subtitles per part
    --workers N            Number of parallel render workers
    --dir DIR              Process all .srt files in directory
    --recursive            Scan subdirectories recursively (with --dir)
"""

import argparse
import os
import sys
import time
import datetime
import subprocess
import json
import shutil
import glob
from process_srt import split_srt_file, clean_filename
from video_renderer import render_srt_to_video
from concat_videos import concat_project

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(ROOT_DIR, "projects")
TEMPLATES_DIR = os.path.join(SCRIPTS_DIR, "templates")
DEFAULT_TEMPLATE = os.path.join(TEMPLATES_DIR, "podcast-enhanced-template.html")
CONFIG_PATH = os.path.join(SCRIPTS_DIR, "config.json")


def load_config():
    """Load configuration from config.json, return dict with defaults."""
    default_config = {
        "split_parts": 30,
        "quality": "standard",
        "workers": 1,
        "template": DEFAULT_TEMPLATE
    }
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            default_config.update(user_config)
        except Exception as e:
            print(f"  [WARNING] Failed to load config.json: {e}. Using defaults.")
    else:
        print(f"  [INFO] config.json not found. Using default values.")
    return default_config


def get_video_info(filepath):
    """尝试使用 ffprobe 获取视频的帧数。如果失败则返回 None。"""
    if not os.path.isfile(filepath):
        return None
    try:
        # 方法1：直接获取 nb_frames
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=nb_frames',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            frames = int(result.stdout.strip())
            return frames
        else:
            # 方法2：通过 duration 和 avg_frame_rate 估算
            cmd2 = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=duration,avg_frame_rate',
                '-of', 'default=noprint_wrappers=1',
                filepath
            ]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
            if result2.returncode == 0:
                lines = result2.stdout.strip().split('\n')
                duration = None
                fps = None
                for line in lines:
                    if 'duration=' in line:
                        duration = float(line.split('=')[1])
                    if 'avg_frame_rate=' in line:
                        fps_str = line.split('=')[1]
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            if den != '0':
                                fps = float(num) / float(den)
                if duration is not None and fps is not None:
                    return int(duration * fps)
            return None
    except Exception:
        return None


def format_time_sec(seconds):
    """将秒数格式化为 mm:ss 或 hh:mm:ss"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        m = int(seconds // 60)
        s = seconds % 60
        return f"{m}m {s:.1f}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}h {m}m {s:.1f}s"


def process_single_srt(srt_path, args):
    """
    处理单个 SRT 文件，生成视频并拼接。
    返回 (success, all_path, error_message)
    """
    if not os.path.isfile(srt_path):
        return False, None, f"File not found: {srt_path}"

    srt_path = os.path.abspath(srt_path)
    base_name = os.path.splitext(os.path.basename(srt_path))[0]
    clean_name = clean_filename(base_name)
    title = args.title or clean_name.replace('_', ' ').title()

    # 输出目录
    video_output_root = os.path.join(ROOT_DIR, "output", "video", clean_name)
    os.makedirs(video_output_root, exist_ok=True)

    # 分割 SRT
    parts_dir = os.path.join(PROJECTS_DIR, clean_name, "parts")
    print("=" * 50)
    print(f"  Splitting SRT into parts ({args.split_parts} lines each)...")
    part_files = split_srt_file(srt_path, parts_dir, args.split_parts)
    total_parts = len(part_files)
    print(f"  Generated {total_parts} part(s).")
    print("=" * 50)

    # 准备 summary.txt
    summary_path = os.path.join(video_output_root, "summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("  HYPERFRAMES VIDEO GENERATION SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Input file        : {srt_path}\n")
        f.write(f"Clean name        : {clean_name}\n")
        f.write(f"Title             : {title}\n")
        f.write(f"Split lines/part  : {args.split_parts}\n")
        f.write(f"Quality           : {args.quality}\n")
        f.write(f"Workers           : {args.workers}\n")
        f.write(f"Template          : {args.template}\n")
        f.write(f"Total parts       : {total_parts}\n")
        f.write(f"Generation started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n" + "-" * 60 + "\n\n")

    # 记录每个 part 的信息
    part_records = []

    for idx, part_path in enumerate(part_files, start=1):
        part_num = idx
        print(f"\n{'='*50}")
        print(f"  Processing Part {part_num}/{total_parts}")
        print(f"  SRT: {os.path.basename(part_path)}")
        print("=" * 50)

        part_title = f"{title} Part {part_num}"
        project_dir = os.path.join(PROJECTS_DIR, clean_name, f"part{part_num}")
        video_output = os.path.join(video_output_root, f"part{part_num}.mp4")

        start_time = time.time()
        success = render_srt_to_video(
            srt_path=part_path,
            project_parent_dir=project_dir,
            video_output_path=video_output,
            template_path=os.path.abspath(args.template),
            title=part_title,
            quality=args.quality,
            workers=args.workers
        )
        end_time = time.time()
        elapsed = end_time - start_time

        record = {
            "part": part_num,
            "video": video_output,
            "success": success,
            "elapsed": elapsed,
            "start_time": datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S'),
        }

        if success:
            frames = get_video_info(video_output)
            record["frames"] = frames if frames is not None else "N/A"
            try:
                size_bytes = os.path.getsize(video_output)
                size_mb = size_bytes / (1024 * 1024)
                record["size_mb"] = f"{size_mb:.2f} MB"
            except OSError:
                record["size_mb"] = "N/A"
            print(f"  Part {part_num} completed: {video_output}")
        else:
            record["frames"] = "N/A"
            record["size_mb"] = "N/A"
            print(f"\n[FATAL] Part {part_num} failed. Aborting remaining parts.", file=sys.stderr)

        part_records.append(record)

        with open(summary_path, 'a', encoding='utf-8') as f:
            f.write(f"Part {part_num}:\n")
            f.write(f"  Video           : {os.path.basename(video_output)}\n")
            f.write(f"  Status          : {'SUCCESS' if success else 'FAILED'}\n")
            f.write(f"  Elapsed time    : {format_time_sec(elapsed)}\n")
            f.write(f"  Start           : {record['start_time']}\n")
            f.write(f"  End             : {record['end_time']}\n")
            if success:
                f.write(f"  Frames          : {record['frames']}\n")
                f.write(f"  File size       : {record['size_mb']}\n")
            else:
                f.write(f"  Frames          : N/A (render failed)\n")
            f.write("\n")

        if not success:
            print(f"\n[FATAL] Aborted at Part {part_num}. Check summary.txt for details.", file=sys.stderr)
            return False, None, f"Part {part_num} rendering failed"

    # 全部成功，写入总结尾
    with open(summary_path, 'a', encoding='utf-8') as f:
        f.write("-" * 60 + "\n")
        f.write(f"All {total_parts} parts processed successfully.\n")
        f.write(f"Completion time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n")

    # 拼接所有 part 为 all.mp4
    print("\n" + "=" * 50)
    print("  Concatenating parts into all.mp4...")
    success, all_path = concat_project(
        video_output_root,
        overwrite=True,
        srt_path=srt_path,
        split_parts=args.split_parts
    )
    if success:
        print(f"  All parts concatenated successfully: {all_path}")
        with open(summary_path, 'a', encoding='utf-8') as f:
            f.write(f"\nConcatenated video: {all_path}\n")

        # 复制 all.mp4 到 output/video_all
        video_all_dir = os.path.join(ROOT_DIR, "output", "video_all")
        os.makedirs(video_all_dir, exist_ok=True)
        dst_filename = f"{clean_name}_all.mp4"
        dst_path = os.path.join(video_all_dir, dst_filename)
        try:
            shutil.copy2(all_path, dst_path)
            print(f"  Copied all.mp4 to: {dst_path}")
        except Exception as e:
            print(f"  [WARNING] Failed to copy all.mp4: {e}", file=sys.stderr)
    else:
        print("  [WARNING] Concatenation failed, but individual parts are available.", file=sys.stderr)

    print("=" * 50)
    print(f"  All parts processed successfully. Videos saved in: {video_output_root}")
    print(f"  Summary log: {summary_path}")
    if success:
        print(f"  Concatenated video: {all_path}")
        print(f"  Copy saved to: {dst_path}")
    print("=" * 50)

    return success, all_path if success else None, None


def collect_srt_files(directory, recursive=False):
    """收集指定目录下的所有 .srt 文件"""
    pattern = "**/*.srt" if recursive else "*.srt"
    search_path = os.path.join(directory, pattern)
    files = glob.glob(search_path, recursive=recursive)
    return sorted(set(os.path.abspath(f) for f in files))


def main():
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Process an SRT file into multiple HyperFrames videos (one-click) or batch process a directory.",
        epilog="Examples:\n"
               "  python scripts/main.py video.srt\n"
               "  python scripts/main.py --dir batchSRC\n"
               "  python scripts/main.py --dir batchSRC --recursive"
    )
    parser.add_argument("input", nargs="?", help="Path to the .srt file (single file mode)")
    parser.add_argument("--dir", help="Process all .srt files in this directory (batch mode)")
    parser.add_argument("--recursive", action="store_true", help="Scan subdirectories recursively (with --dir)")
    parser.add_argument("--template", default=config.get("template"),
                        help="Path to template HTML file (overrides config)")
    parser.add_argument("--title", help="Base title for all parts")
    parser.add_argument("--quality", choices=["draft", "standard", "high"],
                        default=config.get("quality"),
                        help="Render quality (overrides config)")
    parser.add_argument("--split-parts", type=int,
                        default=config.get("split_parts"),
                        help="Number of subtitles per part (overrides config)")
    parser.add_argument("--workers", type=int,
                        default=config.get("workers"),
                        help="Number of parallel render workers (overrides config)")
    args = parser.parse_args()

    # 设置默认值
    if args.split_parts is None:
        args.split_parts = 30
    if args.quality is None:
        args.quality = "standard"
    if args.workers is None:
        args.workers = 1
    if args.template is None:
        args.template = DEFAULT_TEMPLATE

    # 决定模式
    if args.dir:
        # 批量模式
        if not os.path.isdir(args.dir):
            print(f"Error: Directory not found: {args.dir}", file=sys.stderr)
            sys.exit(1)

        srt_files = collect_srt_files(args.dir, args.recursive)
        if not srt_files:
            print(f"No .srt files found in {args.dir}" + (" (recursive)" if args.recursive else ""), file=sys.stderr)
            sys.exit(1)

        print(f"\n批量处理模式: 共发现 {len(srt_files)} 个 SRT 文件")
        print(f"参数: split-parts={args.split_parts}, quality={args.quality}, workers={args.workers}")
        if args.recursive:
            print("递归扫描子目录")
        print("=" * 60)

        results = []
        total = len(srt_files)
        for idx, srt_path in enumerate(srt_files, 1):
            print(f"\n>>> [{idx}/{total}] 处理文件: {os.path.basename(srt_path)}")
            start_time = time.time()
            success, all_path, error = process_single_srt(srt_path, args)
            elapsed = time.time() - start_time
            status = "✅ 成功" if success else "❌ 失败"
            print(f"{status}  耗时 {elapsed:.1f}s")
            results.append((srt_path, success, elapsed, all_path, error))

        # 汇总
        print("\n" + "=" * 60)
        print("批量处理完成! 汇总:")
        success_count = sum(1 for _, s, _, _, _ in results if s)
        fail_count = total - success_count
        for srt_path, success, elapsed, all_path, error in results:
            status = "✅" if success else "❌"
            print(f"  {status} {os.path.basename(srt_path)} - {'成功' if success else f'失败: {error}'} (耗时 {elapsed:.1f}s)")
        print(f"\n总计: {success_count} 成功, {fail_count} 失败")
        if fail_count > 0:
            sys.exit(1)  # 存在失败则返回非0

    else:
        # 单文件模式
        if not args.input:
            parser.error("Please provide an SRT file path or use --dir for batch processing.")

        if not os.path.isfile(args.input):
            print(f"Error: SRT file not found -> {args.input}", file=sys.stderr)
            sys.exit(1)

        success, all_path, error = process_single_srt(args.input, args)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()