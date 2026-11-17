# Writing `work/<clip>/edit.json`

You decide the edit; the worker renders it. First read `references/style.md` and `references/links.md` (open any linked posts you haven't seen with the browser tools, and look at `references/clips/` if there are any) so hooks, pacing and length match the style Chika wants. Then read `work/<clip>/context.md` (transcript with timestamps, silences) and look at the sampled frames (`frames/f_0001.jpg` is t=0, then one every 2 s).

```json
{
  "topic": "gym",
  "format": "pov",
  "summary": "One line: what happens and why someone would watch",
  "keep": [[0.0, 7.4], [9.1, 31.0]],
  "hooks": [
    {"type": "bold_claim", "start": 9.1, "text": "5am gym is overrated"},
    {"type": "mid_action", "start": 0.0},
    {"type": "question", "start": 0.0, "text": "Would you train like this?"}
  ],
  "moods": ["hype", "chill"],
  "unusable": false
}
```

**topic**: short lowercase noun for the subject (`gym`, `campus`, `cooking`, `coding`, `city`, `build`…). Keep the file-name topic unless it's clearly wrong; reuse existing topics rather than inventing near-duplicates.

**format** (pick one): `pov` (first-person moment / day-in-the-life), `tutorial` (shows how to do something), `storytime` (talking, narrative), `montage` (cuts set to music, little speech), `reaction`, `before_after`.

**keep**: the spans worth showing, in order, in source seconds. Remove dead air, fumbled starts, shaky or blank stretches, and anything private (faces of people who didn't agree, screens with personal info, addresses, license plates). Aim for 15–45 s total. Cut at word boundaries (use the transcript timestamps).

**hooks**: 2–4 different openings. The variant starts at `start` (everything before it in `keep` is dropped), so each hook is also a different start point.
- `mid_action`: start on the most visually interesting moment, no text
- `bold_claim`: a strong statement shown as on-screen text for the first ~2 s, true to the clip
- `question`: a question the viewer will want to answer in the comments
- `text_overlay`: a plain context line ("day 12 of learning to cook")
Overlay text: ≤ 6 words, no hashtags, no clickbait the clip doesn't pay off.

**moods**: subfolders of `media/music/` that fit the energy (`[]` for no music, e.g. a talking clip where music would distract).

**unusable**: true if nothing is worth posting (blurry, accidental recording, private content). The clip is then skipped forever.
