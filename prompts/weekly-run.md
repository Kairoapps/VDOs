# VDOs weekly review (cloud, Sunday 12:00am ET)

Same setup as `prompts/daily-run.md` step 0 (clone without media, pillow, `VDOS_ROOT`). Don't stop to ask questions.

1. Refresh Buffer data exactly as in daily-run step 3 (40 days, `includeMetrics: true`, `sync-buffer` each page).
2. `python3 -m vdos weekly --no-git` — scores every sent post within its platform (views percentile + shares/saves rate at ~7 days), ranks video type, title style, on-screen line, alarm sound, length, time slot and hashtag set, updates the weights (70% to winners with ≥6 posts, 30% exploring), marks evergreen clips, retires used-up ones, writes `reports/weekly-<date>.md` and the dashboard.
3. **Experiments:** if the report says an experiment has enough data, lock the winner into `config.toml` (`posting.default_slots` or `experiments.hashtag_set.default`) and move `experiments.active` on (`time_slot` → `hashtag_set` → `none`). Note what won at the top of the weekly report.
4. **Double down:** for the top 3 active clips with fewer than 4 versions, add one new opening/title to `work/<clip>/edit.json` and write `work/<clip>/more.json` = `{"n": 2}` (the next daily run renders them).
5. `python3 -m vdos publish` (drops retired videos from the publish branch), publish the dashboard artifact, then `python3 -m vdos cloud-save -m "weekly review <date>"`.
6. One push notification: top video type, top title style, the biggest change, inventory, record-more shot list. Reply with the weekly report.
