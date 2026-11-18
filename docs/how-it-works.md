# How VDOs works (details)

Turns raw Ray-Ban Meta clips into 3 short-form posts a day on Instagram Reels, TikTok and YouTube Shorts, through Buffer. Claude edits the clips and runs the daily and weekly jobs; this repo is the machinery.

**Edit style (current):** original audio muted; an alarm sound from `sounds/alarm/` loops from the first frame and cuts off the moment the challenge completes; a title at the top (white bold text, thick black outline, emojis) in one of several styles (`gotta`, `pov`, `crashing_out`) that the weekly review A/B tests.

**How it works:** clips you drop into `media/raw/` are renamed, deduplicated and committed (Git LFS). Claude reads each clip's transcript and sampled frames, decides the edit (`work/<clip>/edit.json`), and `vdos variants` renders 3 distinct 9:16 versions with ffmpeg (different openings, caption styles, licensed music, speeds). Every day Claude plans 3 slots, writes per-platform captions and schedules them in Buffer with videos served from your Mac through Tailscale Funnel. Each clip is used at most 3 times, 7+ days apart, then retired. Every week the analysis scores posts within each platform, ranks what works (video type, hook, captions, music, length, time, hashtags), shifts future choices toward the winners, and refreshes the dashboard. You get a push notification when clips retire or you're running low, plus a calendar block to record more.

## Layout

```
media/raw/            drop raw clips here (topic prefix optional: gym__anything.mov)   [Git LFS]
media/raw/_retired/   clips that used up their reuses                                  [Git LFS]
sounds/<category>/    all audio: alarms, effects; music in sounds/music-<mood>/          [Git LFS]
media/edited/         rendered variants, served publicly by `vdos serve`               [Git LFS]
work/<clip>/          transcript, frames, edit.json                                    [committed; frames ignored]
data/ledger.sqlite    clips, variants, slots, posts, metrics, weights                  [committed]
reports/              weekly reports + dashboard.html                                  [committed]
prompts/              the daily/weekly scheduled-task prompts, edit + voice guides
references/           style notes, links to posts to emulate, example clips (read before edits/captions)
config.toml           posting times, reuse rules, experiments, render settings
```

## Who does what

| Where | Runs | Does |
|---|---|---|
| **Mac worker** (launchd, every 15 min) | `vdos worker` | ingest + rename new clips/music, transcribe, sample frames, render variants from `edit.json`, delete retired renders, commit + push |
| **Mac server** (launchd, always on) | `vdos serve` + Tailscale Funnel | serves `media/edited/` to Buffer |
| **Claude daily task** | `prompts/daily-run.md` | writes `edit.json` for new clips, syncs Buffer, plans, writes captions, schedules posts, notifies, publishes the dashboard |
| **Claude weekly task** | `prompts/weekly-run.md` | metrics → rankings → weights, experiments, evergreen, extra variants for winners, report |

Claude's scheduled runs use a Linux shell that sees the connected repo folder (Python 3.10, no GitHub login), so they never run git or rendering; the worker does.

## Setup (Mac, once)

```
git clone https://github.com/Kairoapps/VDOs ~/Documents/Projects/VDOs && cd ~/Documents/Projects/VDOs
./scripts/setup-mac.sh
tailscale funnel --bg 8787          # then put the ts.net URL in .env as PUBLIC_BASE_URL
```

Then in the Claude desktop app, connect the `~/Documents/projects` folder (or the VDOs folder itself) and create two scheduled tasks that require this computer:
- **Daily, ~6:40am:** "Follow prompts/daily-run.md in ~/Documents/Projects/VDOs."
- **Weekly, Sunday ~7:40pm:** "Follow prompts/weekly-run.md in ~/Documents/Projects/VDOs."

## Naming

See [naming.md](naming.md).

## Commands

| Command | What it does |
|---|---|
| `vdos ingest` | register new clips + music, rename, dedupe, commit & push |
| `vdos prep [clip]` | transcribe (faster-whisper), sample frames, detect silences |
| `vdos variants [clip] [-n N] [--auto]` | render variants from `edit.json` (or an automatic silence-cut edit with `--auto`) |
| `vdos status [--all]` | clip table (uses / cap / next eligible / status) + inventory |
| `vdos plan [--date]` | today's slots: variant, public URL, time, hashtags, context for captions |
| `vdos record file.json` | store the Buffer posts Claude created |
| `vdos sync-buffer file.json` | update post status + metrics from saved Buffer `list_posts` output |
| `vdos retire` / `vdos unretire <clip>` | retire used-up clips / bring one back with a fresh cap |
| `vdos alerts [--ack]` | what to notify about: inventory level, retirements, evergreen, failures, shot list |
| `vdos weekly` | score posts, rank attributes, update weights, evergreen, report, dashboard |
| `vdos dashboard` | rebuild `reports/dashboard.html` |
| `vdos serve` | read-only video server for Tailscale Funnel (installed as a LaunchAgent) |

## Rules (config.toml)

- **Reuse:** a use = one daily slot (the same variant goes to all 3 platforms). Max 3 uses per clip, ≥7 days apart; top performers become *evergreen* (cap 5). A use counts once Buffer reports a post sent.
- **Inventory:** days of posting the library covers. Under 7 days → heads-up; under 3 → urgent push + calendar event; 0 → posting skipped. Posting 3/day with a 7-day gap needs ~21 clips in rotation, i.e. about 7 new clips a week.
- **Experiments:** one variable at a time (`time_slot` first, then `hashtag_set`), rotated for equal exposure; an arm needs ≥6 posts before it can win.
- **Scoring:** each post's 7-day views percentile within its platform (70%) + shares/saves rate percentile (30%). Weights: 70% to winners with enough data, 30% exploration.

## Notes

- Keep the repo **private**: licensed music in a public repo is redistribution, and raw clips are personal footage.
- GitHub's free Git LFS allowance is small; at ~7 clips/week you'll likely need an LFS data pack within a few months. Retired clips can be pruned from LFS when you no longer need them.
- Buffer must be able to fetch the video when it publishes, so keep the Mac awake and online during posting windows (or switch the host to Cloudflare R2 later; only the URL changes).
- Trending in-app sounds can't be added through Buffer; music comes from `sounds/` only.
