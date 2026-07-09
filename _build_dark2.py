import re

with open(r"C:\Users\13515\Downloads\srt_html_video\codexPro\templates\tmp.html", encoding="utf-8") as f:
    html = f.read()

# Extract CSS
m = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
css = m.group(1) if m else ""

# Extract body content inside .podcast-frame  
m2 = re.search(r'<div class="podcast-frame">(.*?)</div>\s*</body>', html, re.DOTALL)
body_html = m2.group(1) if m2 else ""

# Replace SVG with img tag
svg_start = body_html.find('<svg class="character-svg"')
svg_end = body_html.find("</svg>", svg_start) + 6
if svg_start >= 0:
    old_svg = body_html[svg_start:svg_end]
    body_html = body_html.replace(old_svg, '<img class="character-img" src="../allPicture/IMAGE_ID.png" alt="character" />')

# Replace 3 text lines with single subtitle line
old_text = '<span class="line">We kindly ask you</span>\n                <span class="line">to take a <span class="highlight">few minutes</span></span>\n                <span class="line">to participate in our survey.</span>'
body_html = body_html.replace(old_text, '<span class="line">SUBTITLE_TEXT</span>')

body_html = body_html.replace('class="highlight"', 'class="hl-STYLE"')
body_html = body_html.replace("12 / 120", "XX / TOTAL")

# Remove config script
body_html = re.sub(r"<script>.*?</script>", "", body_html, flags=re.DOTALL)

# Remove icon-deco elements
body_html = re.sub(r'<div class="icon-deco[^>]*>.*?</div>', "", body_html)

# Build final template
out = []
out.append('<template id="scene-XX-template">')
out.append('  <div data-composition-id="scene-XX" data-width="1920" data-height="1080">')
out.append("    <style>")
out.append("      * { margin: 0; padding: 0; box-sizing: border-box; }")
out.append('      [data-composition-id="scene-XX"] { width: 100%; height: 100%; font-family: "Inter", "Segoe UI", system-ui, sans-serif; overflow: hidden; }')
out.append("      .podcast-frame { position: relative; width: 100%; height: 100%; background: radial-gradient(circle at 80% 20%, #1a2a4a, #0a0f1e 80%); overflow: hidden; display: flex; align-items: center; justify-content: center; }")

# Add filtered CSS
skip_patterns = ["googleapis", "fonts.googleapis", "max-width:", "max-height:", "width: 100vw", "height: 100vh"]
for line in css.split("\n"):
    stripped = line.strip()
    if any(p in stripped for p in skip_patterns):
        continue
    if stripped.startswith("body {") or stripped.startswith("html {") or stripped.startswith("* {"):
        continue
    if stripped == "}" or stripped == "":  
        out.append("      " + line)
        continue
    out.append("      " + line)

out.append("      .character-img { width: 220px; height: 280px; object-fit: contain; filter: drop-shadow(0 20px 40px rgba(0, 0, 0, 0.5)); }")
out.append("    </style>")

# Add body HTML
for line in body_html.split("\n"):
    out.append("    " + line)

# Add GSAP
out.append('')
out.append("    <script>")
out.append("      window.__timelines = window.__timelines || {};")
out.append("      const tl = gsap.timeline({ paused: true });")
out.append('      tl.from(".main-content", { y: 60, opacity: 0, duration: 0.7, ease: "power3.out" }, 0);')
out.append('      tl.from(".top-bar", { y: -30, opacity: 0, duration: 0.5, ease: "power3.out" }, 0);')
out.append('      tl.from(".bottom-wave", { y: 20, opacity: 0, duration: 0.5, ease: "power3.out" }, 0.15);')
out.append('      tl.to(".main-content", { y: -30, opacity: 0, duration: 0.4, ease: "power2.in" }, "-=0.2");')
out.append('      tl.to(".top-bar", { y: -20, opacity: 0, duration: 0.3, ease: "power2.in" }, "-=0.15");')
out.append('      tl.to(".bottom-wave", { y: 15, opacity: 0, duration: 0.3, ease: "power2.in" }, "-=0.1");')
out.append('      window.__timelines["scene-XX"] = tl;')
out.append("    </script>")
out.append("  </div>")
out.append("</template>")

result = "\n".join(out)
path = r"C:\Users\13515\Downloads\srt_html_video\codexPro\templates\podcast-dark-template.html"
with open(path, "w", encoding="utf-8") as f:
    f.write(result)
print(f"Created: {len(result)} bytes")
