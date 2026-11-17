# Writing `work/<clip>/edit.json`

You decide the edit; the worker renders it. First read `references/style.md` and `references/links.md` (open any linked posts you haven't seen with the browser tools, and read `references/clips/index.md`) so hooks, pacing and length match the style Chika wants. Then read `work/<clip>/context.md` (transcript with timestamps, silences) and look at the sampled frames (`frames/f_0001.jpg` is t=0, then one every 2 s).

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
  "premise": ["Gotta walk 200 steps to turn off my alarm", "My alarm makes me walk 200 steps every morning"],
  "sfx": [{"category": "alarm", "at": 0.0, "dur": 3.0}],
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

**premise** (for clips without useful speech, like the reference clips): 1–3 phrasings of one line that says what's happening, shown at the top of the screen for the whole video. Variants rotate through them, and the weekly review learns which wording wins. Keep each ≤ 9 words, first person, the struggle framing ("Gotta …"). No emojis in on-screen text (they don't render); put emojis in the post caption instead. Leave `premise` out when the clip has speech: word-by-word captions are used then.

**sfx**: sound effects to lay over the cut, by category (a subfolder of `media/sfx/`): `at` = seconds into the edited video, `dur` = how long to play it. Variants pick different files from the category. For alarm clips, put the alarm at `0.0` for ~3 s so the video opens on the alarm going off.

**moods**: subfolders of `media/music/` that fit the energy (`[]` for no music, e.g. a talking clip where music would distract).

**unusable**: true if nothing is worth posting (blurry, accidental recording, private content). The clip is then skipped forever.
