# References

What "good" looks like for this account. Claude reads this folder before editing clips and writing captions, so the more specific it is, the more the output looks like what you want.

- **`style.md`**: what you like and don't like, in plain words.
- **`links.md`**: links to posts you want to emulate, one line each, with what you like about it (hook, pacing, captions, music, length).
- **`clips/`**: optional short example videos of your own (stored with Git LFS). Prefer links for other creators' videos instead of downloading them.

## Naming

Reference clips: **`REF-<YYYYMMDD>-<seq>__<topic>__<short-description>.<ext>`**, lowercase, hyphens inside the description.
Example: `REF-20261116-001__unsnooze__walk-200-steps.mov` (date recorded, then a 3-digit number for that day).
Add one row per clip to `clips/index.md` (full rules: `docs/naming.md`) saying what it is and what to copy from it.
