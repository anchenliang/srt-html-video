"""
process_srt.py — SRT file splitting utilities

Provides functions to split a large SRT file into smaller parts,
each with reindexed subtitles and reset timestamps.
"""

import re, os
import parse_srt  # 复用解析函数，不修改原文件

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
        part_entries = entries[start_idx:start_idx + lines_per_part]
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