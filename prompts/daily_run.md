# VDOs daily run (scheduled task prompt)

You are running the VDOs posting pipeline on Chika's Mac. Work through every step without stopping to ask questions; when something is ambiguous, make the best call, keep going, and note it in the final summary.

Use the device shell (`device_bash`) for every command. The repo lives at `$VDOS_REPO` (default `~/code/VDOs`); every command below runs from there inside its virtualenv:

```
cd ~/code/VDOs && source .venv/bin/activate
```

## 1. Sync the repo and ingest

```
git pull --rebase --autostash
vdos ingest
```

New files in `media/raw/` are renamed to `R<date>-<seq>__<topic>`, deduplicated and committed (Git LFS). New music in `media/music/<mood>/` is catalogued.

## 2. Prep and edit new clips

```
vdos prep
```

For every clip it prepped, read `work/<clip>/context.md` and look at a spread of the sampled frames in `work/<clip>/frames/`. To view frames, stage 6–10 of them into your workspace with `device_stage_files` and open them with Read. Then write `work/<clip>/edit.json` following the schema in `prompts/edit_clip.md`. Then render:

```
vdos variants
```

If there are more than 6 new clips, edit the 6 oldest by hand and run `vdos variants --auto` for the rest, so the run finishes.

## 3. Sync with Buffer

1. Buffer `get_account` → organization ID. `list_channels` → the Instagram, TikTok and YouTube channel IDs. Cache them in `.env` as `BUFFER_ORG_ID`, `BUFFER_CH_INSTAGRAM`, `BUFFER_CH_TIKTOK`, `BUFFER_CH_YOUTUBE` if they aren't there yet.
2. `list_posts` for the organization with `dueAt.start` = 40 days ago, `includeMetrics: true`, `first: 100`, paging with `after` until done. Save each page's raw JSON to the Mac as `work/buffer/posts-<n>.json` and run `vdos sync-buffer work/buffer/posts-<n>.json` for each page.
3. `vdos retire` (moves clips whose final use was sent to `media/raw/_retired/` and commits).

## 4. Plan and schedule today's posts

```
vdos plan
```

If `PUBLIC_BASE_URL` isn't set or a `video_url` doesn't answer `curl -sfI <url>` with 200, fix it first (`vdos serve` running under launchd, `tailscale funnel status`). Never create a post with an unreachable URL.

For each slot in the plan, write a caption per platform in Chika's voice (see `prompts/voice.md`), using the slot's `summary`, `transcript`, `topic`, `format`, `hook_type` and `overlay_text`:
- **Instagram:** a 1-line hook, 1–2 short lines of context, a soft CTA (follow/comment prompt), then the slot's `hashtags` (3–5).
- **TikTok:** a punchy 1–2 lines plus the hashtags.
- **YouTube Shorts:** title ≤ 70 characters (no hashtags in the title), then the description with 1–2 lines + hashtags.

Create one Buffer post per platform with `create_post`:
- `mode: "customScheduled"`, `dueAt` = the slot's `scheduled_at`, `schedulingType: "automatic"`
- `assets: [{"video": {"url": <video_url>}}]`
- Instagram: `metadata.instagram = {"type": "reel", "shouldShareToFeed": true}`
- YouTube: `metadata.youtube = {"title": <title>, "categoryId": "22"}`
- TikTok: `metadata.tiktok = {"title": <short title>}`

If a create fails, retry once; if it still fails, record it with `"status": "error"` and the error text.

Then write what you created to `work/buffer/created-<date>.json` and record it:

```json
{"slots": [{"variant_id": "...", "scheduled_at": "...", "time_slot": "...", "hashtag_set": "...",
  "posts": [{"platform": "instagram", "channel_id": "...", "buffer_post_id": "...", "caption": "...", "status": "scheduled"}]}]}
```

```
vdos record work/buffer/created-<date>.json
```

If the plan has a `shortfall` (not enough eligible clips), schedule what you can.

## 5. Notify

```
vdos alerts --ack
```

If `notify` is true, send one push notification (PushNotification) that covers, in this order and only what applies:
- inventory: "X days of clips left — record ~N clips (best: <shot_list>)" when level is `heads_up`, `urgent` or `empty` (`empty` = today's posts were skipped)
- clips retired today, clips promoted to evergreen
- failed posts

If the level is `urgent` or `empty` and there's no "Record clips" event in the next 3 days, create a 45-minute Google Calendar event "Record clips (VDOs)" on the next free evening, with the shot list in the description.

## 6. Dashboard

```
vdos dashboard
```

Publish `reports/dashboard.html` to the existing dashboard artifact (slug in `reports/dashboard_artifact.txt`; create the artifact once if the file is missing and save its slug there). Then `git add reports && git commit -m "daily: dashboard" && git push`.

## 7. Finish

End with a 3–5 line summary: posts scheduled (times + clips), anything that failed, inventory level, any judgment calls you made.
