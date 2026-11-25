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
  "dismiss_at": 48.2,
  "premise": [
    {"style": "gotta", "text": "Gotta walk 200 steps to turn off my alarm 😭😭😭"},
    {"style": "pov", "text": "POV: your alarm makes you walk 200 steps 💀"},
    {"style": "crashing_out", "text": "crashing out because my alarm won't stop until I walk 200 steps 😭"}
  ],
  "bed": {"category": "alarm"},
  "angle": "challenge",
  "moods": [],
  "unusable": false
}
```

**topic**: the Unsnooze challenge shown on the phone screen. Uploads don't say which challenge it is (the file name says `misc`), so **always work it out from the frames** and set it here: `memory` (color/sequence game), `pushup`, `shake`, `tap`, `walk` (step count), `squat`. A new challenge gets a short lowercase noun; reuse existing topics rather than inventing near-duplicates. This value replaces the file-name topic everywhere.

**format** (pick one): `pov` (first-person moment / day-in-the-life), `tutorial` (shows how to do something), `storytime` (talking, narrative), `montage` (cuts set to music, little speech), `reaction`, `before_after`.

**keep**: the spans worth showing, in order, in source seconds. Remove dead air, fumbled starts, shaky or blank stretches, and anything private (faces of people who didn't agree, screens with personal info, addresses, license plates). Aim for 15–45 s total. Cut at word boundaries (use the transcript timestamps).

**Never cut the alarm going off (Chika's rule).** Every video must show the moment the alarm starts ringing: Chika still lying there / looking at the ceiling, then the alarm hits and she grabs the phone. Set **`alarm_at`** on every clip = the source second the alarm starts (usually where the long silence in `context.md` ends, confirmed in the frames: the first movement toward the phone), and start `keep` **1 s before `alarm_at`**. Every hook's `start` must equal the first `keep` second; vary openings with hook *type* and on-screen text, never by starting later. The video is silent until `alarm_at`, then the alarm bed starts. `vdos variants` enforces this: a hook that starts after `alarm_at` is moved back to the start of `keep`. Only exception: if the moment shows something that must be cut (a stranger's face on screen), start at the first frame after it and note why in `summary`.

**hooks**: 2–4 different openings (all starting at the first `keep` second, see above). The variant starts at `start` (everything before it in `keep` is dropped), so each hook is also a different start point.
- `mid_action`: start on the most visually interesting moment, no text
- `bold_claim`: a strong statement shown as on-screen text for the first ~2 s, true to the clip
- `question`: a question the viewer will want to answer in the comments
- `text_overlay`: a plain context line ("day 12 of learning to cook")
Overlay text: ≤ 6 words, no hashtags, no clickbait the clip doesn't pay off.

**The sound**: the original clip audio is always muted. The soundtrack is the **bed**: a sound from `sounds/<category>/` (default `alarm`) that loops from the first frame (short sounds repeat with a smooth crossfade) and cuts off exactly at **`dismiss_at`** — the source second the challenge completes (the "Good morning/evening" screen appears). Find it frame by frame. End `keep` ~2 s after it so the video ends on the dismissed screen in silence. Variants rotate the alarm sound. Optional `sfx`: extra one-shot effects, `[{"category": "whoosh", "at": 1.5, "dur": 1.0}]` (seconds into the edited video).

**angle** — the content angle, ranked weekly (which angles to record more of):
- `challenge`: the plain challenge (alarm → do the challenge → dismissed).
- `sus`: a sus setup before the alarm (see below).
- `multi_challenge`: one alarm with several challenges back to back (e.g. memory game, then pushups, then a photo). Keep every challenge (trim each to its clearest seconds), set `dismiss_at` to the moment the **last** one completes, and play on the stacking in the titles: "my alarm made me do 3 challenges just to turn off 😭", "POV: your alarm has a whole obstacle course 💀".
A clip can only have one angle; sus beats multi_challenge if it's both. New angles are fine (short snake_case).

**Sus setups (on purpose)**: some clips open with Chika scrolling something that looks suspicious (e.g. feet pics) *before* the alarm goes off; the alarm interrupting is the joke. Recognize these from the frames (a few seconds of browsing/watching the phone before the alarm screen appears). For them:
- This is intentional comedy, not private content: don't mark it `unusable` and don't cut the setup. Keep it short (2–5 s, the clearest glimpse), then the alarm.
- Set **`alarm_at`**: the source second the alarm screen first appears. The video stays silent before it and the alarm bed starts there (until `dismiss_at` as usual).
- Every hook must start at or before the setup (`start` ≤ first setup second); use `mid_action` from the setup, not a later point.
- Titles play on getting caught, e.g. `caught`: "my alarm caught me in 4k 💀", `pov`: "POV: your alarm goes off at the worst possible moment 😭", plus one `crashing_out`. Keep it innuendo-level; never describe what's on screen explicitly.
- Set `"angle": "sus"` in edit.json so the weekly review can compare these against normal clips.
- If the screen is actually explicit (nudity, sexual acts) or shows a real stranger identifiably, cut that part; if nothing usable is left, `unusable: true`.

**speed** (optional): leave it out. Longer cuts are sped up more (up to 1.5x) and each version tests a speed level for its length (see README "Speed guidelines"). Set e.g. `"speed": 1.3` only to force it (that turns the speed test off for this clip).

**premise**: the title shown at the top for the whole video: white bold text with a thick black outline, emojis allowed and encouraged (😭💀🧠🎈). Write one per **title style** so variants test styles against each other; the weekly review learns which style wins:
- `gotta`: "Gotta <challenge> to turn off my alarm 😭"
- `pov`: "POV: your alarm makes you <challenge> 💀"
- `crashing_out`: "crashing out because my alarm <situation> 😭"
- (new styles are fine — `me_when`, `nobody_warned_me`, … — give each a short snake_case name)

**Emojis are tested too:** for each style write the same title three ways — no emoji, one emoji, and a combo of 2–4 **different** emojis (e.g. "Gotta shake my phone 67 times to turn off my alarm", "… 📱", "… 😭📱💀"). Variants pick the style first, then the emoji count, both weighted by results.

**Vary the emojis (Chika, 2026-11-25).** Don't default to 😭. Pick ones that fit the challenge and the mood and mix them: 💀 😩 😵 🫠 🥲 😤 🙄 🤡 😮‍💨 ⏰ 📱 🧠 🎈 👟 🪞 📺 🚽 📸 🔥 💯 ‼️. Multiple emojis are fine anywhere in the title as long as it stays within 3 lines on screen. Don't repeat the same combo across a clip's titles.

**Lead with the challenge's numbers (Chika, 2026-11-25).** Titles should name the specific challenge parameter: "walk 100 steps", "shake 67 times", "memorize 6 colors", "tap 60 times", "find a TV". Use the frames to get the real number when it's easy to read, but you don't have to be exact: playful exaggeration is encouraged ("walk 1000 steps", "shake my phone 500 times") because it gets people commenting. Mix real and exaggerated numbers across the three styles. Keep exaggeration obviously playful and about the challenge itself; don't invent app features, and only use clock times the clip shows.

Keep titles short (≤ 12 words, max 3 lines on screen) so they don't cover the video. Leave `premise` out when the clip has speech you want captioned word by word.

**moods**: background-music moods (the `<mood>` of `sounds/music-<mood>/`) that fit the energy (`[]` for no music, e.g. a talking clip where music would distract).

**unusable**: true if nothing is worth posting (blurry, accidental recording, private content). The clip is then skipped forever.
