# How to Actually Become a Happy Person

## Project Overview

This HyperFrames project converts the SRT subtitle file into a 1920x1080 video by creating animated HTML scenes for each subtitle sentence.

## Visual Style

- **Style:** Warm Personal Story (adapted from muban.html + Soft Signal)
- **Background:** Warm cream-to-beige radial gradient (#FBF8F4 -> #F4EFE8 -> #EAE3D7)
- **Text:** Dark brown (#1A1A1A), 56px Georgia/Segoe UI, centered
- **Accents:** Gold (#CF976B) accent lines and warm brown (#604A3E) ghost text
- **Animation:** Soft entrance (fade + slide up), slow ambient drift, smooth exits

## Project Structure

srt-html-video/
  index.html               Main composition
  DESIGN.md                Visual identity specification
  hyperframes.json         Project config
  compositions/            Scene sub-compositions (17 scenes)
  renders/                 Output video directory
  assets/                  Static assets

## Time Table

Total video duration: ~49.3 seconds (17 scenes from SRT)

## How to Use

### Prerequisites
- Node.js >= 22
- FFmpeg

### Commands

cd srt-html-video
npx hyperframes lint
npx hyperframes inspect
npx hyperframes preview
npx hyperframes render --output renders/happy-person.mp4

## Design Reference

The visual design is adapted from muban.html (warm podcast-style template).
