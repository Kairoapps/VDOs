# VDOs daily run (cloud, 12:00am ET)

Runs entirely in Claude's cloud — Chika's Mac does not need to be on. Don't stop to ask questions; make the best call, keep going, note it in the summary.

**Where things live**
- GitHub `Kairoapps/VDOs` (public) `main`: code, raw clips (`media/raw/`, Git LFS, uploaded by the Mac), sounds, references, the database (`data/ledger.sqlite`), edits (`work/`), reports.
- Branch `publish`: the rendered videos Buffer downloads (`https://raw.githubusercontent.com/Kairoapps/VDOs/publish/<file>`).
- It runs at midnight Eastern and schedules the day that just started (`vdos plan` defaults to today in Eastern time). This run renders new clips, schedules Buffer, then saves the database/edits back to `main`.

## 0. Setup

1. `add_repo` owner `Kairoapps`, repo `VDOs`, access `push`, then clone **without downloading media**:
   `GIT_LFS_SKIP_SMUDGE=1 git clone --single-branch -b main https://github.com/Kairoapps/VDOs vdos && cd vdos` (main only: the publish branch is large)
2. `pip install -q --break-system-packages pillow` (ffmpeg and Python 3.11+ are already there).
3. `export VDOS_ROOT=$PWD` and run every command below from the repo as `python3 -m vdos …`. Always add `--no-git` to `ingest`, `retire` and `weekly` (saving happens in step 6).

## 1. New clips: ingest, edit, render

```
python3 -m vdos pending-raw          # new clips in media/raw (Mac, LFS) or media/inbox (web uploads, plain git)
git lfs pull -I "<the media/raw paths, comma-separated>"   # skip if only media/inbox files
python3 -m vdos ingest --no-git
python3 -m vdos prep --skip-transcribe
```
For each newly prepped clip (oldest first, at most 8): read `work/<clip>/context.md`, look at 6–10 frames spread across `work/<clip>/frames/` (Read them), find the frame where the challenge completes, and write `work/<clip>/edit.json` following `prompts/edit-clip.md` exactly (cuts, `dismiss_at`, `angle`, titles for `gotta` / `pov` / `crashing_out` with different emoji counts, `bed` alarm). Also read `references/` first.
`variants` picks each version's sound and speed level weighted by what has performed; don't override them. The on-screen CTA is off (`[cta] modes = ["none"]` since 2026-11-25), so new versions have no green "comment UNSNOOZE" text.
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
Every `video_url` and image URL must answer 200 (`curl -sI`) before you use it. Slots stay between 8:00am and 9:00pm Eastern (config). The plan has **4 slots a day (since 2026-11-25): 3 video slots (`kind: "video"`) → TikTok + Instagram Reels + Facebook Page Reels + YouTube Shorts, and exactly 1 slideshow slot (`kind: "slideshow"`) → TikTok photo post + Instagram carousel + Facebook multi-photo post (never YouTube).** So TikTok/Instagram/Facebook get 4 posts a day and YouTube 3. Post each slot only to the platforms in its `platforms` list. A slideshow every day is required: if the plan has no slideshow slot (and none is already scheduled today), say so loudly in the summary. `plan` still checks Buffer's rolling-24h limits (`platform_daily_max`; the plan's `limits` field shows any platform that got fewer slots); if a post fails with "daily posting limit", don't retry it. Schedule only today and skip if today is already scheduled.

Captions in Chika's voice (`prompts/voice.md`, `references/style.md`), using the slot's `summary`, `topic`, `format`, `angle`, `caption_text` (the on-screen title; echo it, don't just repeat it). **Each slot is a caption test — follow it exactly, on every platform in the slot:**
- **First line on every platform: "Download the Unsnooze app"** (its own line, at the very start of the caption/description; not counted in `post_emoji`). Then the caption.
- `post_caption_style`: `hook_cta` / `relatable` / `question` (definitions in `prompts/voice.md`).
- `post_emoji`: exactly that many emojis in the caption text (`0`, `1`, or `2-3`), hashtags not counted.
- Hashtags: use the slot's `hashtags` exactly (3–5 tags, already chosen) — don't add, drop or swap any, so the hashtag test stays clean.
- Never ask people to comment "UNSNOOZE" (or any keyword) in a caption — dropped 2026-11-25. If a slot's `cta` is ever not `none` (an old version), say so in the summary.
Per platform:
- **Instagram:** "Download the Unsnooze app", then the caption in the slot's style, then the hashtags. `hook_cta` uses the soft CTA ("unsnooze makes you actually get up. link in bio").
- **TikTok:** "Download the Unsnooze app", then one punchy line in the slot's style + hashtags; `metadata.tiktok.title` short.
- **YouTube Shorts:** `metadata.youtube.title` ≤ 70 chars in the slot's style (emoji count from `post_emoji`), `categoryId` "22"; description starts with "Download the Unsnooze app", then a line in the slot's style + the hashtags.
- **Facebook Page (Reel):** the same caption as Instagram ("Download the Unsnooze app" first, slot's style, line breaks, then the hashtags in the same text — Reels have one description field, no title). Buffer channel `facebook` in `config.toml`.

`create_post` per platform (video slots): `mode: "customScheduled"`, `dueAt` = slot `scheduled_at`, `schedulingType: "automatic"`, `assets: [{"video": {"url": <video_url>}}]`, Instagram `metadata.instagram = {"type": "reel", "shouldShareToFeed": true}`, Facebook `metadata.facebook = {"type": "reel"}`. Retry a failed create once, then record it as `"status": "error"`.

**Slideshow slot** (`kind: "slideshow"`): an illustrated story about one challenge (`slideshow` = its name, e.g. `shake`, `math`), 6–8 slides, the last one is the "Download Unsnooze Today" slide. Look at slides 1 and 2 (`image_urls.tiktok[0..1]`) so the caption matches the story. Same caption rules as above (first line "Download the Unsnooze app", the slot's `post_caption_style`, `post_emoji`, `hashtags` exactly). Never say the app is free (subscription after a trial).
- **TikTok photo post:** `assets` = one `{"image": {"url": u, "metadata": {"altText": ""}}}` per URL in `image_urls.tiktok` (9:16, in order), `metadata.tiktok.title` ≤ 90 chars (the hook), caption = "Download the Unsnooze app" + one punchy line + hashtags. `schedulingType: "automatic"`, unless the slot's `tiktok_notify_for_music` is true → `"notification"` (Chika adds a sound in the TikTok app). Buffer can't attach music, so automatic photo posts go out silent.
- **Instagram carousel:** `assets` from `image_urls.instagram` (4:5), `metadata.instagram = {"type": "post", "shouldShareToFeed": true}`, caption like the Instagram Reel caption + "swipe 👉" fits well.
- **Facebook multi-photo post:** `assets` from `image_urls.facebook` (4:5), `metadata.facebook = {"type": "post"}`, same caption as Instagram.
If a slideshow create fails, retry once; if TikTok rejects image posts entirely, record it as `"error"` with the message and say so in the summary (don't fall back to a video).

Write `work/buffer/created-<date>.json` and run `python3 -m vdos record work/buffer/created-<date>.json`. Format: `{"slots": [ ... ]}` with, per video slot, `{"kind": "video", "variant_id", "scheduled_at", "time_slot", "hashtag_set", "post_caption_style", "post_emoji", "posts": [{"platform", "channel_id", "buffer_post_id", "caption", "status"}]}` and, for the slideshow slot, `{"kind": "slideshow", "slideshow", "scheduled_at", "time_slot", "hashtag_set", "post_caption_style", "post_emoji", "posts": [...]}`.

## 5. Notify + dashboard

```
python3 -m vdos alerts --ack
python3 -m vdos dashboard
```
`python3 -m vdos slides` shows slideshow inventory; if `days_left_fresh` < 7 (or the plan's slideshow `note` says it reused one), include "build more slideshows" in the notification.
If `notify` is true, one push notification: inventory ("X days of clips left — record ~N, best: <shot_list>") when `heads_up`/`urgent`/`empty`, clips retired / made evergreen, failed posts. If `urgent`/`empty` and no "Record clips (VDOs)" event in the next 3 days, add a 45-min Google Calendar event on the next free evening with the shot list.
Publish `reports/dashboard.html` to the dashboard artifact with publish_files (as index.html; slug in `reports/dashboard_artifact.txt`, base_version from get_artifact). Always republish to that slug, never create a new one.

## 6. Save

```
python3 -m vdos cloud-save -m "daily run <date>"
```
(commits `data/`, `work/`, `reports/`, `sounds/`, `config.toml` to `main` and pushes; it never touches LFS media.) If the push is rejected, `git pull --rebase` and push again.

## 7. Summary

3–5 lines: posts scheduled (times, clips, which slots went to YouTube; Facebook included; which slideshow and at what time), clips edited/rendered, failures, inventory level (clips and slideshows). Send it as a push notification too.
