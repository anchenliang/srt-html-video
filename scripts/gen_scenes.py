import re, json, os, sys, argparse, random, shutil

STOP_WORDS = {"a","an","the","and","or","but","in","on","at","to","for","of","with","by",
              "that","this","it","is","are","was","were","be","been","being","have","has","had",
              "do","does","did","will","would","can","could","shall","should","may","might","must",
              "not","no","so","up","down","out","off","over","under","i","you","he","she",
              "we","they","me","him","her","us","them","my","your","his","its","our","their",
              "mine","yours","hers","theirs","am","if","as","just","like","really","very",
              "also","about","some","all","more","into","than","then","from","now","here","there"}

STYLES = ["bounce", "gradient", "marker", "glow", "underline"]

EMOJI_SETS = [
    [chr(0x1F399)+chr(0xFE0F),chr(0x1F3A7),chr(0x1F917),chr(0x2728),chr(0x1F4A1),chr(0x1F31F),chr(0x1F9E0),chr(0x1F604),chr(0x1F4C8)],
    [chr(0x1F308),chr(0x1F33B),chr(0x1F31F),chr(0x1F49B),chr(0x2601)+chr(0xFE0F),chr(0x1F338),chr(0x2728),chr(0x1F60A),chr(0x1F49A)],
    [chr(0x1F31F),chr(0x2728),chr(0x1F31B),chr(0x1F680),chr(0x1F525),chr(0x26A1),chr(0x1F929),chr(0x1F4A1),chr(0x1F48E)],
    [chr(0x1F929),chr(0x263A)+chr(0xFE0F),chr(0x1F49B),chr(0x1F308),chr(0x2728),chr(0x1F31F),chr(0x1F33B),chr(0x1F60A),chr(0x1F49A)],
    [chr(0x1F33F),chr(0x1F9E0),chr(0x1F4A1),chr(0x1F31F),chr(0x1F3AF),chr(0x1F9F3),chr(0x1F3B2),chr(0x1F308),chr(0x2728)],
    [chr(0x1F308),chr(0x1F31F),chr(0x2728),chr(0x1F929),chr(0x1F339),chr(0x1F33C),chr(0x1F49B),chr(0x1F60C),chr(0x1F30A)],
    [chr(0x1F4AA),chr(0x1F31F),chr(0x1F680),chr(0x2728),chr(0x1F525),chr(0x1F30A),chr(0x1F31B),chr(0x1F929),chr(0x1F48E)],
    [chr(0x1F970),chr(0x1F49B),chr(0x1F490),chr(0x1F339),chr(0x1F338),chr(0x1F498),chr(0x1F496),chr(0x1F929),chr(0x2764)+chr(0xFE0F)],
    [chr(0x1F44D),chr(0x1F3AF),chr(0x1F4CD),chr(0x1F31F),chr(0x1F929),chr(0x1F60A),chr(0x2728),chr(0x1F49A),chr(0x1F48E)],
    [chr(0x1F33B),chr(0x1F339),chr(0x1F308),chr(0x1F31F),chr(0x1F98B),chr(0x1F33A),chr(0x1F490),chr(0x1F60A),chr(0x2728)],
]

POSE_KEYWORDS = {
    "welcome": ["welcome", "hello", "hi", "hey", "guys", "glad", "pleasure", "introduce", "join", "channel", "back"],
    "celebrate": ["happy", "excited", "love", "amazing", "great", "wonderful", "beautiful", "perfect", "best", "fantastic", "awesome", "joy", "celebrate", "blessed", "grateful"],
    "think": ["think", "understand", "know", "believe", "consider", "reflect", "ponder", "imagine", "realize", "wonder", "thought", "mind", "brain", "idea", "meaning"],
    "point": ["this", "that", "here", "look", "see", "because", "so", "now", "first", "second", "finally", "next", "important", "key", "main", "focus", "specific", "exactly", "actually"],
    "explain": ["explain", "describe", "mean", "actually", "basically", "like", "means", "example", "way", "how", "what", "which", "reason", "process", "step", "today"],
    "confident": ["must", "will", "can", "should", "always", "never", "truth", "sure", "certain", "absolutely", "definitely", "powerful", "strong", "prove", "fact", "dedicated", "turn around"],
    "warm": ["feel", "care", "hope", "wish", "heart", "life", "journey", "share", "support", "kind", "gentle", "peace", "calm", "trust", "soul", "together", "lovely", "watching"],
}

def choose_keyword(text):
    words = re.findall(r"[A-Za-z]+", text)
    content_words = [w for w in words if w.lower() not in STOP_WORDS and len(w) > 2]
    if not content_words:
        content_words = [w for w in words if len(w) > 1]
    if not content_words:
        return words[0] if words else text[:8]
    content_words.sort(key=lambda w: (-len(w), w))
    for w in content_words:
        if len(w) <= 14:
            return w
    return content_words[0]

def choose_pose(text):
    text_lower = text.lower()
    scores = {}
    for pose, keywords in POSE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[pose] = score
    if scores:
        return max(scores, key=scores.get)
    return "explain"

def find_emojis(template, count=9):
    """Find emoji content at icon-1 through icon-N positions."""
    result = []
    for i in range(1, count + 1):
        marker = "icon-" + str(i) + '"'
        idx = template.find(marker)
        if idx >= 0:
            start = template.find(">", idx) + 1
            end = template.find("<", start)
            if end > start:
                result.append((start, end, template[start:end]))
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate HyperFrames scenes from SRT data")
    parser.add_argument("--data", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="My Video")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        entries = json.load(f)
    total = len(entries)

    with open(args.template, "r", encoding="utf-8") as f:
        template = f.read()

    comp_dir = os.path.join(args.output, "compositions")
    os.makedirs(comp_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output, "renders"), exist_ok=True)

    # Setup: copy random images from allPicture/ into assets/
    allpic_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allPicture")
    assets_dir = os.path.join(args.output, "assets")
    has_images = False
    image_map = {}
    if os.path.isdir(allpic_dir):
        all_images = sorted([f for f in os.listdir(allpic_dir) if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.gif'))])
        if all_images:
            has_images = True
            os.makedirs(assets_dir, exist_ok=True)
            # Pick N random images (one per scene, with replacement if more scenes than images)
            picked = random.choices(all_images, k=total) if total > len(all_images) else random.sample(all_images, total)
            for pi, fname in enumerate(picked):
                src_path = os.path.join(allpic_dir, fname)
                ext = os.path.splitext(fname)[1]
                dst_name = f"scene-{(pi+1):03d}{ext}"
                dst_path = os.path.join(assets_dir, dst_name)
                shutil.copy2(src_path, dst_path)
                image_map[pi] = dst_name

    for i, entry in enumerate(entries):
        idx = entry["idx"]
        text = entry["text"]
        keyword = choose_keyword(text)
        style = STYLES[i % len(STYLES)]
        pose = choose_pose(text)
        emojis = EMOJI_SETS[i % len(EMOJI_SETS)]
        progress = int((i + 1) * 100 / total)
        sid = f"scene-{idx:03d}"
        # Calculate scene duration and exit time
        scene_start = entry["start"]
        scene_end = entry["end"]
        scene_duration = max(0.5, round(scene_end - scene_start, 3))
        exit_time = round(max(0.5, scene_duration - 0.5), 2)

        # Highlight
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        hl_class = f"hl-{style}"
        span_open = f'<span class="{hl_class}">'
        span_close = "</span>"
        highlighted = pattern.sub(span_open + keyword + span_close, text, count=1)

        content = template

        # Basic placeholders
        content = content.replace("scene-XX", sid)
        content = content.replace("XX / 17", f"{idx:03d} / {total}")
        content = content.replace("KEYWORD", keyword.upper())
        content = content.replace("PROGRESS_PCT", str(progress) + "%")
        content = content.replace("POSENAME", pose)
        content = content.replace("SUBTITLE_TEXT", highlighted)
        # Replace old template sentence FIRST
        old_sentence = 'example sentence with a <span class="hl-STYLE">WORD</span>.'
        content = content.replace(old_sentence, highlighted)

        # Replace hl-STYLE in CSS
        content = content.replace("hl-STYLE", hl_class)

        # Replace EXIT_TIME with calculated value
        content = content.replace('"EXIT_TIME"', str(exit_time))

        # Replace random image path
        if has_images and i in image_map:
            img_rel = "assets/" + image_map[i]
            content = content.replace("RANDOM_IMG", img_rel)
        else:
            content = content.replace("RANDOM_IMG", "")

        # Replace emojis - support both template styles
        emoji_positions = find_emojis(content)
        if emoji_positions:
            # Process in reverse order to preserve positions
            for pi in range(min(len(emoji_positions), len(emojis)) - 1, -1, -1):
                s, e, _ = emoji_positions[pi]
                content = content[:s] + emojis[pi] + content[e:]
        else:
            for j in range(1, min(len(emojis), 6) + 1):
                content = content.replace(f"EMOJI_{j}", emojis[j-1])

        filepath = os.path.join(comp_dir, f"{sid}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{total}")

    # Generate index.html
    index_lines = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'<title>{args.title}</title>',
        '<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#F9F6F0}</style>',
        '</head>', '<body>',
        '<div data-composition-id="main-comp" data-start="0" data-width="1920" data-height="1080">'
    ]

    # Setup: copy random images from allPicture/ into assets/
    allpic_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allPicture")
    assets_dir = os.path.join(args.output, "assets")
    has_images = False
    image_map = {}
    if os.path.isdir(allpic_dir):
        all_images = sorted([f for f in os.listdir(allpic_dir) if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.gif'))])
        if all_images:
            has_images = True
            os.makedirs(assets_dir, exist_ok=True)
            # Pick N random images (one per scene, with replacement if more scenes than images)
            picked = random.choices(all_images, k=total) if total > len(all_images) else random.sample(all_images, total)
            for pi, fname in enumerate(picked):
                src_path = os.path.join(allpic_dir, fname)
                ext = os.path.splitext(fname)[1]
                dst_name = f"scene-{(pi+1):03d}{ext}"
                dst_path = os.path.join(assets_dir, dst_name)
                shutil.copy2(src_path, dst_path)
                image_map[pi] = dst_name

    for i, entry in enumerate(entries):
        idx = entry["idx"]
        start = entry["start"]
        end = entry["end"]
        duration = round(end - start, 3)
        if duration < 0.4:
            duration = 0.5
        sid = f"scene-{idx:03d}"
        index_lines.append(
            f'<div id="el-{idx}" data-composition-id="{sid}" '
            f'data-composition-src="compositions/{sid}.html" '
            f'data-start="{round(start,3)}" '
            f'data-duration="{duration}" '
            f'data-track-index="0"></div>'
        )

    index_lines.extend([
        '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>',
        '<script>',
        'window.__timelines=window.__timelines||{};',
        'const tl=gsap.timeline({paused:true});',
        'window.__timelines["main-comp"]=tl;',
        '</script>',
        '</div>',
        '</body>',
        '</html>'
    ])

    index_path = os.path.join(args.output, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))

    hf = {
        "name": os.path.basename(args.output),
        "version": "1.0.0",
        "description": args.title,
        "main": "index.html",
        "compositions": sorted([f"compositions/scene-{entry['idx']:03d}.html" for entry in entries])
    }
    hf_path = os.path.join(args.output, "hyperframes.json")
    with open(hf_path, "w", encoding="utf-8") as f:
        json.dump(hf, f, indent=2, ensure_ascii=False)

    print(f"== DONE! {total} scenes -> {args.output}")
    print(f"  Next: cd {args.output}")
    print(f"        npx hyperframes lint")
    print(f"        npx hyperframes render --output renders/final.mp4 --gpu --workers 2")

if __name__ == "__main__":
    main()
