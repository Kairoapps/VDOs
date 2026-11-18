# VDOs

Turns raw Ray-Ban Meta clips into 3 short videos a day on Instagram Reels, TikTok and YouTube Shorts, posted through Buffer.

## How it works

1. **You** drop clips into `media/raw/` on your Mac. The Mac only names them and uploads them to GitHub (every 15 min).
2. **Claude's daily cloud run** (6:00 am ET, no laptop needed) edits new clips (muted audio, an alarm that stops the moment you finish the challenge, an emoji title), renders 3 versions of each, puts the videos on the `publish` branch, and schedules 3 posts in Buffer for Instagram, TikTok and YouTube. Each clip is used at most 3 times, a week apart.
3. **Claude's weekly cloud run** (Sunday afternoon) checks what performed best (video type, title style, sound, length, time, hashtags), shifts future posts toward it, updates the dashboard, and reminds you when to record more.

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

Long cuts get sped up a little so they feel snappy without looking fake. The original audio is muted, so nothing sounds chipmunked.

| Cut length at normal speed | Speed | Example: 40 s cut becomes |
|---|---|---|
| up to 20 s | 1.0x (real time) | — |
| 20–30 s | ~1.1–1.15x | — |
| over 30 s | **1.25–1.3x** | ~31–32 s |

- Never slower than 1.0x or faster than 1.3x; each version of a clip gets a slightly different speed so the weekly review can learn what works.
- Set `"speed": 1.3` in a clip's `work/<clip>/edit.json` to force a speed for that clip.
- Tunable in `config.toml` under `[variants]` (`speed_rules`, `speed_jitter`, `speed_max`).

File names follow [docs/naming.md](docs/naming.md). Full details: [docs/how-it-works.md](docs/how-it-works.md). Keep this repo private.
