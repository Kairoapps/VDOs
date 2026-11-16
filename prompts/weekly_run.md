# VDOs weekly review (scheduled task prompt, Sunday evening)

Same setup and division of labor as `prompts/daily_run.md` (start every `device_bash` call with the `REPO=...; cd "$REPO" && export VDOS_ROOT="$REPO"` line; no git, no `vdos worker`/`prep`/`variants` — the Mac worker owns those). Don't stop to ask questions; make the best call and note it.

1. Refresh Buffer data exactly as in step 2 of `prompts/daily_run.md` (list_posts for the last 40 days with `includeMetrics: true`, save each page, `python3 -m vdos sync-buffer <file>`).
2. Run the analysis:
   ```
   python3 -m vdos weekly --no-git
   ```
   This scores every sent post within its platform (views percentile + shares/saves rate at ~7 days old), ranks every attribute (video type, format, hook, caption style, music mood, length, time slot, hashtag set), updates the weights that variant generation and planning use (70% to winners with ≥6 posts, 30% exploration), promotes top clips to evergreen, retires used-up clips, writes `reports/weekly-<date>.md` and rebuilds the dashboard.
3. **Experiments:** read the report's "Experiment" section. If it says there's enough data, edit `config.toml`: lock in the winner (winning times into `posting.default_slots`, or the winning set into `experiments.hashtag_set.default`), then move `experiments.active` to the next variable (`time_slot` → `hashtag_set` → `none`). Note what won at the top of the weekly report file.
4. **Double down:** for each of the top 3 clips this week that are still active and have fewer than 4 variants: add one new hook (a different opening or start point, following `prompts/edit_clip.md`) to `work/<clip>/edit.json`, then write `work/<clip>/more.json` containing `{"n": 2}`. The worker renders them within ~15 minutes.
5. Stage `<repo>/reports/dashboard.html` and publish it to the dashboard artifact (slug in `reports/dashboard_artifact.txt`).
6. Send one push notification: top video type, the biggest change you made, inventory level, and the record-more shot list. Then reply with the full `reports/weekly-<date>.md` content.
