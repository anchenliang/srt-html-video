# DESIGN.md — Warm Personal Story

Inspired by `muban.html` and the Soft Signal visual style. Created for an English self-help video about becoming a happy person.

## Style Prompt
A warm, intimate, personal video style — like a close friend sharing wisdom over coffee. Creamy beige backgrounds with gentle radial warmth, soft brown accents, and clean humanist typography. Each scene places a single subtitle at the center as the hero element, with subtle ambient decorative elements (ghost text, warm glows) for depth. The feel is calm, hopeful, and inviting.

## Colors
- Background base: #FBF8F4 (warm cream)
- Background mid: #F4EFE8 (warm beige)
- Background edge: #EAE3D7 (deep cream)
- Primary text: #1A1A1A (near-black)
- Accent brown: #604A3E (warm brown)
- Accent gold: #CF976B (warm gold)
- Muted: #A69B8C (warm gray)
- Soft white: #FFFFFF

## Typography
- Headlines: Georgia, 'Times New Roman', serif (warm, humanist, trustworthy)
- Body/Subtitles: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif (clean, readable)
- Subtitle text: 700 weight, 48-56px, 1.4 line-height
- Secondary text: 400 weight, 20-24px

## Scene Structure
Each scene shows one subtitle sentence centered on screen, with:
1. A warm radial gradient background (same palette across all scenes)
2. Ghost text ("Happy" / "Authentic" / "Purpose") at 3-5% opacity, large, subtle drift
3. The subtitle text in warm brown (#604A3E and #1A1A1A)
4. A subtle accent line or decorative element
5. Slow, gentle entrance/exit animation (Soft Signal style)

## Motion Rules
- Entrance: fade up + slight y offset (0 → -20px), 0.6s, sine.inOut
- Exit: fade out + slight y, 0.4s, sine.inOut
- Ambient: ghost text slow drift (breathing, 8s cycle)
- No aggressive motion, no snaps, no overshoots

## What NOT to Do
- No harsh colors or high contrast
- No corporate or tech-like styling
- No more than 10-12 words per line (use line breaks for readability)
- No decorative elements that distract from the subtitle text
