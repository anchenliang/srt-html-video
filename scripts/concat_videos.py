#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
concat_videos.py — Concatenate multiple part videos into a single all.mp4
with freeze-frame gaps to preserve original timeline.

Usage:
    python scripts/concat_videos.py [project_name] [--srt SRT_PATH] [--split-parts N]

If no project_name is given, it lists all available projects.
"""

import os
import sys
import subprocess
import glob
import re
import json
import tempfile
import shutil
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_VIDEO_DIR = os.path.join(ROOT_DIR, "output", "video")

# 导入 parse_srt 以获取时间范围
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
from parse_srt import parse_srt


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

    def extract_num(f):
        basename = os.path.basename(f)
        match = re.search(r'part(\d+)\.mp4', basename)
        return int(match.group(1)) if match else 0

    return sorted(files, key=extract_num)


def get_video_params(filepath):
    """
    Extract video stream parameters using ffprobe.
    Returns (width, height, fps, pix_fmt) or raises exception.
    """
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,r_frame_rate,pix_fmt',
        '-of', 'json', filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data['streams'][0]
    width = int(stream['width'])
    height = int(stream['height'])
    fps_str = stream['r_frame_rate']  # e.g., "30000/1001"
    if '/' in fps_str:
        num, den = map(float, fps_str.split('/'))
        fps = num / den if den != 0 else 30.0
    else:
        fps = float(fps_str)
    pix_fmt = stream.get('pix_fmt', 'yuv420p')
    return width, height, fps, pix_fmt


def get_video_duration(filepath):
    """返回视频的实际时长（秒）"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def generate_freeze_frame_clip(input_video, output_path, duration, params):
    """
    Generate a short MP4 video of duration `duration` seconds by freezing the last frame of `input_video`.
    `params` is (width, height, fps, pix_fmt).
    """
    width, height, fps, pix_fmt = params
    last_frame_png = output_path + ".lastframe.png"

    # 方法1：使用 -ss 定位到末尾附近提取一帧（更稳定）
    success = False
    try:
        # 获取视频总时长
        cmd_duration = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', input_video
        ]
        result = subprocess.run(cmd_duration, capture_output=True, text=True, check=True)
        total_duration = float(result.stdout.strip())
        # 从倒数 0.05 秒处提取（避免末尾关键帧问题）
        seek_time = max(0, total_duration - 0.05)
        extract_cmd = [
            'ffmpeg', '-y', '-ss', str(seek_time), '-i', input_video,
            '-vframes', '1', '-f', 'image2', last_frame_png
        ]
        subprocess.run(extract_cmd, check=True, capture_output=True)
        success = True
    except Exception as e:
        print(f"  [WARN] -ss method failed: {e}, trying filter method...")

    # 方法2：使用 select=eq(n,N-1) 过滤器
    if not success:
        try:
            extract_cmd = [
                'ffmpeg', '-y', '-i', input_video,
                '-vf', 'select=eq(n,N-1)', '-vframes', '1', '-f', 'image2', last_frame_png
            ]
            subprocess.run(extract_cmd, check=True, capture_output=True)
            success = True
        except Exception as e:
            print(f"  [ERROR] Both extraction methods failed: {e}", file=sys.stderr)
            raise RuntimeError(f"Failed to extract last frame from {input_video}")

    # 生成冻结帧视频
    encode_cmd = [
        'ffmpeg', '-y', '-loop', '1', '-i', last_frame_png,
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-t', str(duration),
        '-r', str(fps),
        '-pix_fmt', pix_fmt,
        '-vf', f'scale={width}:{height}',
        '-an',  # 无音频
        output_path
    ]
    subprocess.run(encode_cmd, check=True, capture_output=True)

    # 清理临时图片
    os.remove(last_frame_png)


def concat_with_freeze_frames(part_files, output_path, srt_path, split_parts):
    """
    Concatenate part videos, inserting freeze-frame clips between parts to fill the original timeline gaps.
    `srt_path` is the original SRT file, `split_parts` is lines per part.
    """
    if len(part_files) < 2:
        print("  Need at least 2 videos to concatenate.")
        return False

    # Parse original SRT to get absolute time ranges for each part
    entries = parse_srt(srt_path)
    total = len(entries)
    ranges = []
    for start_idx in range(0, total, split_parts):
        part_entries = entries[start_idx:start_idx + split_parts]
        if not part_entries:
            break
        start_time = part_entries[0]['start']
        end_time = part_entries[-1]['end']
        ranges.append((start_time, end_time))

    if len(part_files) != len(ranges):
        print(f"  Warning: number of part files ({len(part_files)}) does not match number of time ranges ({len(ranges)})", file=sys.stderr)
        return concat_videos_direct(part_files, output_path)

    # 获取每个part视频的实际时长
    part_durations = []
    for f in part_files:
        try:
            dur = get_video_duration(f)
        except Exception as e:
            print(f"  [ERROR] Failed to get duration for {f}: {e}", file=sys.stderr)
            return False
        part_durations.append(dur)

    # 计算每个part对应的SRT段落时长（以第一句起始为0）
    srt_durations = [end - start for start, end in ranges]

    # 计算偏差 (actual - srt)
    deltas = [actual - srt for actual, srt in zip(part_durations, srt_durations)]

    # 打印调试信息
    print("  Part | SRT duration | Actual duration | Delta")
    for i, (srt_d, act_d, delta) in enumerate(zip(srt_durations, part_durations, deltas), 1):
        print(f"  {i:4d} | {srt_d:12.3f}s | {act_d:15.3f}s | {delta:8.3f}s")

    # 获取视频参数
    params = get_video_params(part_files[0])

    list_file = os.path.join(os.path.dirname(output_path), "concat_list.txt")
    freeze_files = []
    with open(list_file, 'w', encoding='utf-8') as f:
        for i, part_file in enumerate(part_files):
            escaped = part_file.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

            if i < len(part_files) - 1:
                end_current = ranges[i][1]
                start_next = ranges[i+1][0]
                gap = start_next - end_current
                # 补偿当前part的偏差：实际结束时间 = end_current + deltas[i]
                # 需要插入的冻结帧时长 = start_next - (end_current + deltas[i]) = gap - deltas[i]
                effective_gap = gap - deltas[i]
                if effective_gap < 0:
                    print(f"  [WARN] Negative effective gap for part {i+1}: {effective_gap:.3f}s, setting to 0")
                    effective_gap = 0
                if effective_gap > 0.01:
                    freeze_file = os.path.join(os.path.dirname(output_path), f"freeze_{i}.mp4")
                    print(f"  Generating freeze frame for effective gap {effective_gap:.3f}s (original gap {gap:.3f}s, delta {deltas[i]:.3f}s)")
                    generate_freeze_frame_clip(part_file, freeze_file, effective_gap, params)
                    escaped_freeze = freeze_file.replace("'", "'\\''")
                    f.write(f"file '{escaped_freeze}'\n")
                    freeze_files.append(freeze_file)

    # 执行concat
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]
    print(f"  Concatenating {len(part_files)} parts with adjusted freeze frames...")
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # 清理临时冻结帧和列表文件
    for f in freeze_files:
        if os.path.isfile(f):
            os.remove(f)
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


def concat_videos_direct(part_files, output_path):
    """Direct concatenation (no gaps) - fallback method."""
    list_file = os.path.join(os.path.dirname(output_path), "concat_list.txt")
    with open(list_file, 'w', encoding='utf-8') as f:
        for p in part_files:
            escaped = p.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
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


def concat_project(project_dir, overwrite=False, srt_path=None, split_parts=None):
    """
    Concatenate all part*.mp4 files in project_dir into all.mp4.
    If srt_path and split_parts are provided, gaps are filled with freeze frames.
    Otherwise, direct concatenation is used.
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
    if os.path.isfile(output_path) and not overwrite:
        print(f"Output file {output_path} already exists. Use overwrite=True to force.", file=sys.stderr)
        return False, None

    # Choose method
    if srt_path and split_parts and os.path.isfile(srt_path):
        print("  Using freeze-frame gap filling method.")
        success = concat_with_freeze_frames(part_files, output_path, srt_path, split_parts)
    else:
        print("  Using direct concatenation (no gaps filled).")
        success = concat_videos_direct(part_files, output_path)

    return success, output_path if success else None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Concatenate part videos with freeze-frame gaps")
    parser.add_argument("project_name", nargs="?", help="Project directory name under output/video/")
    parser.add_argument("--srt", help="Path to original SRT file (required for gap filling)")
    parser.add_argument("--split-parts", type=int, help="Lines per part (required with --srt)")
    args = parser.parse_args()

    project_name = args.project_name
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

    # Check if we have srt and split-parts
    srt_path = args.srt
    split_parts = args.split_parts
    if srt_path and not os.path.isfile(srt_path):
        print(f"Warning: SRT file not found: {srt_path}", file=sys.stderr)
        srt_path = None
    if srt_path and not split_parts:
        print("Warning: --split-parts required with --srt. Falling back to direct concat.")
        srt_path = None

    # Ask for overwrite if all.mp4 exists
    output_path = os.path.join(project_dir, "all.mp4")
    if os.path.isfile(output_path):
        response = input(f"Output file {output_path} already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

    success, out = concat_project(project_dir, overwrite=True, srt_path=srt_path, split_parts=split_parts)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()