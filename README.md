# VDOs

Turns raw Ray-Ban Meta clips into 3 short videos a day on Instagram Reels, TikTok and YouTube Shorts, posted through Buffer.

## How it works

1. **You** drop clips into `media/raw/` and licensed music into `media/music/<mood>/`.
2. **The Mac worker** (every 15 min) transcribes new clips and renders edited 9:16 versions with captions and music.
3. **Claude's daily run** decides the edits, writes captions and schedules 3 posts in Buffer. Each clip is used at most 3 times, a week apart.
4. **Claude's weekly run** checks what performed best (video type, hook, captions, music, time, hashtags), shifts future posts toward it, updates the dashboard, and reminds you when to record more.

## Setup (once, on your Mac)

```
cd ~/Documents/projects/VDOs
./scripts/setup_mac.sh
tailscale funnel --bg 8787
```

Put the `https://….ts.net` address it prints into `.env` as `PUBLIC_BASE_URL`.

## Folders

| Folder | What's in it |
|---|---|
| `media/raw/` | your raw clips (optional topic prefix: `gym__anything.mov`) |
| `media/music/` | licensed tracks, one subfolder per mood |
| `references/` | examples and notes on the style you want |
| `prompts/` | instructions for Claude's daily and weekly runs |
| `reports/` | weekly reports and the dashboard |
| `config.toml` | posting times, reuse limits, experiments |

Full details: [docs/how-it-works.md](docs/how-it-works.md). Keep this repo private.
