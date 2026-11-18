# VDOs daily run (cloud)

Runs entirely in Claude's cloud — Chika's Mac does not need to be on. Don't stop to ask questions; make the best call, keep going, note it in the summary.

**Where things live**
- GitHub `Kairoapps/VDOs` (public) `main`: code, raw clips (`media/raw/`, Git LFS, uploaded by the Mac), sounds, references, the database (`data/ledger.sqlite`), edits (`work/`), reports.
- Branch `publish`: the rendered videos Buffer downloads (`https://raw.githubusercontent.com/Kairoapps/VDOs/publish/<file>`).
- This run renders new clips, schedules Buffer, then saves the database/edits back to `main`.

## 0. Setup

1. `add_repo` owner `Kairoapps`, repo `VDOs`, access `push`, then clone **without downloading media**:
   `GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/Kairoapps/VDOs vdos && cd vdos`
2. `pip install -q --break-system-packages pillow` (ffmpeg and Python 3.11+ are already there).
3. `export VDOS_ROOT=$PWD` and run every command below from the repo as `python3 -m vdos …`. Always add `--no-git` to `ingest`, `retire` and `weekly` (saving happens in step 6).

## 1. New clips: ingest, edit, render

```
python3 -m vdos pending-raw          # raw clips the database doesn't know yet
git lfs pull -I "<those paths, comma-separated>"
python3 -m vdos ingest --no-git
python3 -m vdos prep --skip-transcribe
```
For each newly prepped clip (oldest first, at most 8): read `work/<clip>/context.md`, look at 6–10 frames spread across `work/<clip>/frames/` (Read them), find the frame where the challenge completes, and write `work/<clip>/edit.json` following `prompts/edit-clip.md` exactly (cuts, `dismiss_at`, three titles: `gotta` / `pov` / `crashing_out`, `bed` alarm). Also read `references/` first.
Then pull what rendering needs and render:
```
git lfs pull -I "media/raw/<clip files you edited>"
python3 -m vdos variants <clip>      # once per edited clip (3 versions each)
```
If the weekly review left `work/<clip>/more.json` (`{"n": 2}`), pull that clip's raw file, run `python3 -m vdos variants <clip> -n 2`, and rename the file to `more.done-<date>.json`.

## 2. Publish videos for Buffer

```
python3 -m vdos publish
```
This rebuilds the `publish` branch with every active version plus any video with a post still pending, and drops retired ones. `missing` in the output must be empty for anything you're about to schedule; if a needed file is missing, pull its raw clip and re-render that clip.

## 3. Sync with Buffer

Buffer org `6acd0dec0ee270b5947c74de` ("My organization"); channel IDs are in `config.toml` `[buffer]`.
1. `list_posts` with `dueAt.start` = 40 days ago, `includeMetrics: true`, `first: 100`, paging with `after`. Save each page's raw JSON to `work/buffer/posts-<n>.json`; run `python3 -m vdos sync-buffer work/buffer/posts-<n>.json`.
2. `python3 -m vdos retire --no-git`.

## 4. Plan and schedule today

```
python3 -m vdos plan
```
Every `video_url` must answer 200 (`curl -sI`) before you use it. Slots stay between 8:30am and 5pm Eastern (config). Buffer's plan allows 10 scheduled posts at once: schedule only today (3 slots × 3 platforms) and skip if today is already scheduled.

Captions in Chika's voice (`prompts/voice.md`, `references/style.md`), using the slot's `summary`, `topic`, `format`, `caption_text` (the on-screen title; echo it, don't just repeat it):
- **Instagram:** a hook line, a short line with a soft CTA ("unsnooze makes you actually get up. link in bio"), then the slot's hashtags.
- **TikTok:** one punchy line + hashtags; `metadata.tiktok.title` short.
- **YouTube Shorts:** `metadata.youtube.title` ≤ 70 chars with an emoji, `categoryId` "22"; description mentions Unsnooze + hashtags.

`create_post` per platform: `mode: "customScheduled"`, `dueAt` = slot `scheduled_at`, `schedulingType: "automatic"`, `assets: [{"video": {"url": <video_url>}}]`, Instagram `metadata.instagram = {"type": "reel", "shouldShareToFeed": true}`. Retry a failed create once, then record it as `"status": "error"`.

Write `work/buffer/created-<date>.json` (`{"slots": [{"variant_id", "scheduled_at", "time_slot", "hashtag_set", "posts": [{"platform", "channel_id", "buffer_post_id", "caption", "status"}]}]}`) and run `python3 -m vdos record work/buffer/created-<date>.json`.

## 5. Notify + dashboard

```
python3 -m vdos alerts --ack
python3 -m vdos dashboard
```
If `notify` is true, one push notification: inventory ("X days of clips left — record ~N, best: <shot_list>") when `heads_up`/`urgent`/`empty`, clips retired / made evergreen, failed posts. If `urgent`/`empty` and no "Record clips (VDOs)" event in the next 3 days, add a 45-min Google Calendar event on the next free evening with the shot list.
Publish `reports/dashboard.html` to the dashboard artifact (slug in `reports/dashboard_artifact.txt`; create once if missing and save the slug there).

## 6. Save

```
python3 -m vdos cloud-save -m "daily run <date>"
```
(commits `data/`, `work/`, `reports/`, `sounds/`, `config.toml` to `main` and pushes; it never touches LFS media.) If the push is rejected, `git pull --rebase` and push again.

## 7. Summary

3–5 lines: posts scheduled (times, clips, title styles), clips edited/rendered, failures, inventory level. Send it as a push notification too.
