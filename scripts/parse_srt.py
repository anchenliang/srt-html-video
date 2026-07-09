"""
parse_srt.py — Convert any .srt file to srt_data.json

Usage:
    python scripts/parse_srt.py <input.srt> [output.json]

Examples:
    python scripts/parse_srt.py projects/my-video/subtitle.srt projects/my-video/srt_data.json
    python scripts/parse_srt.py subtitle.srt   # writes to srt_data.json in CWD
"""

import sys, re, json, os


def time_to_sec(t: str) -> float:
    """Convert SRT time format (HH:MM:SS,mmm) to seconds."""
    t = t.replace(',', '.')
    parts = t.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def parse_srt(filepath: str) -> list[dict]:
    """Parse an SRT file into a list of {idx, start, end, text}."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # Index line
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue

        # Time line
        time_match = re.match(
            r'(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})',
            lines[1]
        )
        if not time_match:
            continue

        start = round(time_to_sec(time_match.group(1)), 3)
        end = round(time_to_sec(time_match.group(2)), 3)

        # Text (may be multi-line)
        text = ' '.join(line.strip() for line in lines[2:]).strip()

        entries.append({"idx": idx, "start": start, "end": end, "text": text})

    return entries


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/parse_srt.py <input.srt> [output.json]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"Error: file not found -> {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[2] if len(sys.argv) > 2 else "srt_data.json"

    entries = parse_srt(input_path)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"OK - Parsed {len(entries)} SRT entries -> {output_path}")
