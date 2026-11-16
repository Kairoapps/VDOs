# VDOs weekly review (scheduled task prompt, Sunday evening)

Run on Chika's Mac with the device shell, from `~/code/VDOs` with `.venv` activated. Don't stop to ask questions; make the best call and note it.

1. `git pull --rebase --autostash`
2. Refresh Buffer data exactly as in step 3 of `prompts/daily_run.md` (list_posts for the last 40 days with `includeMetrics: true`, save each page, `vdos sync-buffer <file>`).
3. Run the analysis:
   ```
   vdos weekly
   ```
   This scores every sent post within its platform (views percentile + shares/saves rate, at ~7 days old), ranks every attribute (video type, format, hook, caption style, music mood, length, time slot, hashtag set), updates the weights that variant generation and planning use (70% to winners with ≥6 posts, 30% exploration), promotes top clips to evergreen, retires used-up clips, writes `reports/weekly-<date>.md` and rebuilds the dashboard.
4. **Experiments:** read the "Experiment" section of the report. If it says there's enough data, edit `config.toml`: lock the winner in (put the winning time slots in `posting.default_slots`, or the winning hashtag set in `experiments.hashtag_set.default`), then move `experiments.active` to the next variable (`time_slot` → `hashtag_set` → `none`). Commit with a message saying what won.
5. **Double down:** for each of the top 3 clips this week that are still active and have fewer than 4 variants, generate 2 fresh variants with a different hook or start point: add a new hook to `work/<clip>/edit.json` if needed, then `vdos variants <clip> -n 2`.
6. Publish `reports/dashboard.html` to the dashboard artifact (slug in `reports/dashboard_artifact.txt`), commit and push `reports/`.
7. Send one push notification: top video type, the biggest change you made, inventory level, and the record-more shot list. Then reply with the full `reports/weekly-<date>.md` content.
