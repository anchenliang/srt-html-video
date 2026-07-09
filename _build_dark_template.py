"""Build podcast-dark-template.html from tmp.html."""
import re

SRC = r"C:\Users\13515\Downloads\srt_html_video\codexPro\templates\tmp.html"
DST = r"C:\Users\13515\Downloads\srt_html_video\codexPro\templates\podcast-dark-template.html"

with open(SRC, encoding="utf-8") as f:
    html = f.read()

# Convert to HyperFrames template format
html = html.replace("<!DOCTYPE html>", '<template id="scene-XX-template">')
html = html.replace("<html lang=\"zh-CN\">", "")
html = html.replace("</html>", "</template>")

# Remove <head> section (keep styles inline)
html = re.sub(r"<head>.*?</head>", "", html, flags=re.DOTALL)

# Wrap in composition div
html = html.replace("<body>", "")
html = html.replace("</body>", "")
html = html.replace(
    '<div class="podcast-frame">',
    "<div data-composition-id=\"scene-XX\" data-width=\"1920\" data-height=\"1080\">\n  <div class=\"podcast-frame\">"
)
html = html.replace("</div>\n\n", "</div>\n  </div>\n\n", 1)  # Close composition div

# Add GSAP script reference before </template>
html = html.replace(
    "</template>",
    '  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>\n'
    '  <script>\n'
    '    window.__timelines = window.__timelines || {};\n'
    '    const tl = gsap.timeline({ paused: true });\n'
    '    tl.from(".main-content", { y: 60, opacity: 0, duration: 0.7, ease: "power3.out" }, 0);\n'
    '    tl.from(".top-bar", { y: -30, opacity: 0, duration: 0.5, ease: "power3.out" }, 0);\n'
    '    tl.from(".bottom-wave", { y: 20, opacity: 0, duration: 0.5, ease: "power3.out" }, 0.15);\n'
    '    tl.to(".main-content", { y: -30, opacity: 0, duration: 0.4, ease: "power2.in" }, "-=0.2");\n'
    '    tl.to(".top-bar", { y: -20, opacity: 0, duration: 0.3, ease: "power2.in" }, "-=0.15");\n'
    '    tl.to(".bottom-wave", { y: 15, opacity: 0, duration: 0.3, ease: "power2.in" }, "-=0.1");\n'
    '    window.__timelines["scene-XX"] = tl;\n'
    '  </script>\n'
    "</template>"
)

# Replace SVG character with <img> from allPicture
svg_start = html.find('<svg class="character-svg"')
svg_end = html.find("</svg>", svg_start) + 6
svg_block = html[svg_start:svg_end]
img_tag = '<img class="character-img" src="../allPicture/IMAGE_ID.png" alt="character" />'
html = html.replace(svg_block, img_tag)

# Add CSS for character-img
html = html.replace(
    ".character-svg {",
    ".character-img {\n            width: 220px;\n            height: 280px;\n            object-fit: contain;\n            filter: drop-shadow(0 20px 40px rgba(0,0,0,0.5));\n        }\n\n        .character-svg {"
)

# Replace 3 text lines with 1 SRT subtitle line
html = html.replace(
    '<span class="line">We kindly ask you</span>\n                <span class="line">to take a <span class="highlight">few minutes</span></span>\n                <span class="line">to participate in our survey.</span>',
    '<span class="line">SUBTITLE_TEXT</span>'
)

# Replace config numbers with placeholders
html = html.replace("current: 12,", "current: 1,")
html = html.replace("total: 120,", "total: TOTAL,")
html = html.replace("time: '00:12'", "time: '00:00'")

# Add scene counter and timestamp placeholders
html = html.replace(
    '<span id="sentenceIndex">句子 12 / 120</span>',
    '<span id="sentenceIndex">XX / TOTAL</span>'
)

# Replace highlight class with hl-STYLE
html = html.replace('class="highlight"', 'class="hl-STYLE"')

# Remove Google Fonts link (slow for render)
html = html.replace(
    '<link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,600;14..32,700;14..32,800&display=swap" rel="stylesheet" />',
    ""
)

# Add Inter font as system fallback comment
html = html.replace(
    "font-family: 'Inter', sans-serif;",
    "font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;"
)

# Remove the config script (replaced by placeholders)
html = re.sub(
    r'<script>\s*// 你可以在这里修改句子索引.*?</script>',
    "",
    html,
    flags=re.DOTALL
)

with open(DST, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Created {DST}")
print(f"Size: {len(html)} bytes")
