# VDOs

Turns raw Ray-Ban Meta clips into short videos posted through Buffer every day: 3 each on TikTok, Instagram Reels, Facebook Page Reels and YouTube Shorts.

## How it works

1. **You** upload clips on the [clip upload page](https://claude.ai/artifact/SgcMK984AZ2GY8vmVEhSb4): it compresses them in the browser (~6x smaller), then you drop them into [`media/inbox/` on GitHub](https://github.com/Kairoapps/VDOs/upload/main/media/inbox). No laptop setup needed. (The old Mac folder uploader in `scripts/setup-mac.sh` still works but is optional.) Page source: `tools/upload/index.html`.
2. **Claude's daily cloud run** (12:00am ET, plans the day that just started; no laptop needed) edits new clips (muted audio, an alarm that stops the moment you finish the challenge, an emoji title), renders 3 versions of each, puts the videos on the `publish` branch, and schedules 3 posts in Buffer for Instagram, TikTok and YouTube, between 8:30am and 8:30pm ET. Each clip is used at most 3 times, never twice in one day.
3. **Claude's weekly cloud run** (Sunday 12:00am ET) checks what performed best (video type, title style, sound, length, time, hashtags), shifts future posts toward it, updates the dashboard, and reminds you when to record more.

Dashboard https://claude.ai/artifact/LHT3nppU4oZTC9zEWMbrFk

## Setup (once, on your Mac)

```
cd ~/Documents/projects/VDOs
./scripts/setup-mac.sh
```

That installs the uploader. Nothing else needs to run on the Mac.

## Folders

| Folder | What's in it |
|---|---|
| `media/raw/` | your raw clips (optional topic prefix: `gym__anything.mov`) |
| `sounds/` | all audio, one subfolder per category: `alarm/`, `whoosh/`, … and background music in `music-<mood>/` |
| `references/` | examples and notes on the style you want |
| `prompts/` | instructions for Claude's daily and weekly runs |
| `reports/` | weekly reports and the dashboard |
| `config.toml` | posting times, reuse limits, experiments |

## Speed guidelines

Longer cuts get sped up more. The original audio is muted, so nothing sounds chipmunked. Each version of a clip picks a speed level (base / faster / fastest) for its length, weighted by results, so the weekly review learns how fast each length should go.

| Cut length at normal speed | base | faster | fastest |
|---|---|---|---|
| up to 15 s | 1.0x | 1.05x | 1.1x |
| 15–25 s | 1.05x | 1.15x | 1.25x |
| 25–35 s | 1.2x | 1.3x | 1.4x |
| over 35 s | 1.3x | 1.4x | **1.5x** |

- Never slower than 1.0x or faster than 1.5x.
- Set `"speed": 1.3` in a clip's `work/<clip>/edit.json` to force a speed for that clip.
- Tunable in `config.toml` under `[variants]` (`speed_tiers`, `speed_max`).

## What gets tested

- **Every post:** time slot and hashtag set (both rotating evenly; 3–5 relevant tags), post caption style and emoji count.
- **Every video version:** title style and emoji count, sound (and sound type: siren, ringtone, sci-fi…), speed level, and a green call to action under the title ("comment UNSNOOZE for the app": none / whole video / at the end) plus its wording.
- **Every clip:** topic and content angle (`challenge`, `sus`, `multi_challenge`).
The weekly review ranks all of these and shifts future choices toward winners (70%) while still exploring (30%).

File names follow [docs/naming.md](docs/naming.md). Full details: [docs/how-it-works.md](docs/how-it-works.md). Keep this repo private.
