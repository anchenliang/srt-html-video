with open(r"C:\Users\13515\Downloads\srt_html_video\codexPro\projects\test6\srt-html-video\index.html", encoding="utf-8") as f:
    for line in f:
        if 'data-composition-id="scene-' in line and 'data-start' in line:
            parts = line.strip().split()
            sid = [p for p in parts if 'data-composition-id=' in p][0].split('"')[1]
            start = [p for p in parts if 'data-start=' in p][0].split('"')[1]
            dur = [p for p in parts if 'data-duration=' in p][0].split('"')[1]
            print(f"  {sid}: start={start}, dur={dur}")
