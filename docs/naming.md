# Naming conventions

One rule set for every file in the repo. When in doubt: **lowercase, words joined with `-`, fields separated with `__`**.

## Code and docs

| Kind | Convention | Examples |
|---|---|---|
| Python modules | `snake_case.py` (Python requires it) | `vdos/buffer_sync.py`, `tests/test_core.py` |
| Docs, prompts, notes | `kebab-case.md` | `docs/how-it-works.md`, `prompts/daily-run.md` |
| Folder entry docs | `README.md` (the only uppercase name; GitHub shows it) | `references/README.md` |
| Folder indexes | `index.md` | `references/clips/index.md` |
| Shell scripts | `kebab-case.sh` | `scripts/setup-mac.sh` |
| macOS LaunchAgents | reverse-DNS `com.kairoapps.vdos.<name>.plist` (macOS convention) | `scripts/com.kairoapps.vdos.worker.plist` |
| Config | `config.toml`, `.env` (from `.env.example`) | |
| Folders | lowercase, kebab-case | `media/raw`, `media/sfx/alarm` |

## Media

IDs start with an uppercase prefix so they stand out: `R` = raw clip, `REF` = reference clip.

| Kind | Pattern | Example |
|---|---|---|
| Raw clip (drop in) | `<topic>__<anything>.<ext>` — the topic prefix is optional | `walk__IMG_4410.MOV` |
| Raw clip (after ingest, automatic) | `R<YYYYMMDD>-<seq>__<topic>.<ext>` | `R20261117-001__walk.mov` |
| Rendered variant (automatic) | `<clip-id>__v<n>__<random6>.mp4` | `R20261117-001__v2__k7f3q9.mp4` |
| Music | `media/music/<mood>/<artist>__<title>__<source>.mp3` | `media/music/hype/lumen__drift__artlist.mp3` |
| Sound effect | `media/sfx/<category>/<description>__<source>.mp3` | `media/sfx/alarm/scifi-alarm-02__epidemic.mp3` |
| Reference clip | `references/clips/REF-<YYYYMMDD>-<seq>__<topic>__<description>.<ext>` | `REF-20261116-001__unsnooze__walk-200-steps.mov` |

- `<YYYYMMDD>` is the day the clip was recorded; `<seq>` is a 3-digit counter for that day.
- `<source>` is where an audio file came from (`epidemic`, `artlist`, `mixkit`, `pixabay`, …), so a copyright claim can be traced.
- `<topic>`, `<mood>`, `<category>` are short lowercase words reused across files (`walk`, `shake`, `memory`; `hype`, `chill`; `alarm`, `whoosh`).

## Generated files

| Kind | Pattern |
|---|---|
| Per-clip work folder | `work/<clip-id>/` with `transcript.json`, `context.md`, `edit.json`, `frames/f_0001.jpg` |
| Buffer exports | `work/buffer/posts-<n>.json`, `work/buffer/created-<YYYY-MM-DD>.json` |
| Weekly report | `reports/weekly-<YYYY-MM-DD>.md` (+ `.json`) |
| Dashboard | `reports/dashboard.html` |
| Ledger | `data/ledger.sqlite` |
