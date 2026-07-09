import json
with open(r"C:\Users\13515\Downloads\srt_html_video\codexPro\projects\test6\srt_data.json", encoding="utf-8") as f:
    data = json.load(f)
print("SRT timing vs HTML duration:")
for i, e in enumerate(data):
    dur = round(e["end"] - e["start"], 3)
    if dur < 0.4:
        dur = 0.5
    next_s = data[i+1]["start"] if i+1 < len(data) else e["end"]
    gap = round(next_s - e["end"], 3)
    print(f"  Scene {e['idx']:03d}: start={e['start']:.3f}  end={e['end']:.3f}  duration={dur:.3f}s  (gap: {gap:.3f}s)")
print(f"Total video: {data[-1]['end'] - data[0]['start']:.3f}s")
