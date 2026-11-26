# Slideshows

Photo-carousel posts (TikTok photo mode, Instagram carousel) built from illustrated art + the video title style.

```
python tools/slides/build.py              # every slideshow -> media/slides/<name>/<name>__01.jpg …
python tools/slides/build.py shake math   # only these
```

## Style (standing rules)

- **Art:** hand-drawn 2D webcomic look: ink lines, flat muted colours (dusty navy, terracotta, cream), light paper grain. Not glossy 3D, no talking mascot. Same recurring character: young man, short curly dark hair, brown skin, light blue tee, plaid pajama pants.
- **Size:** 1080×1920 (9:16). Art keeps its top third empty for text.
- **Text:** white Poppins Bold, thick black outline, colour emojis (`vdos/title.py`).
- **Length:** 6–8 slides (builder enforces it; platform max is 10).
- **Last slide:** always `assets/slides/cta-download.png`: "Download Unsnooze Today", app icon, App Store listing card, App Store badge, "link in bio".
- No "free" claims (Unsnooze needs a subscription after the trial).

## Files

| Path | What |
|---|---|
| `assets/slides/art/<scene>__<source>.png` | scene art; `<source>` = where it came from (`figma-ai` = Figma image AI, so label posts as AI-generated) |
| `assets/slides/cta-download.png` | fixed last slide |
| `assets/brand/unsnooze-icon.png` | app icon, 1024×1024 (from the App Store listing) |
| `media/slides/<name>/<name>__<nn>.jpg` | built slides, ready to post |
| `tools/slides/build.py` | slideshow scripts (`SLIDESHOWS`) + builder |

## Scenes available

`ring` (asleep, alarm ringing) · `reach` (reaching for snooze) · `shock` (staring at phone in disbelief) · `shake` (shaking phone) · `tired` (exhausted on bed edge) · `relief` (sigh, phone down) · `morning` (awake, coffee, sun) · `counting` (counting on fingers) · `solved` (eureka, pointing at phone) · `hallway` (walking the hall at night) · `pushup` · `collapse` (face down after push-ups) · `squat` · `memory` (colored tiles glowing) · `matching` (cards popping from phone) · `typing` · `sink` (photographing the sink) · `affirmation` (reading aloud, calm) · `tapping` (furious tapping)

Slideshows (15): shake, math, walk, pushups, squats, memory, matching, type, house_hunt, affirmation, tap, three_in_a_row, every_way, random_week, rate_them.

Shared scenes (`ring`, `reach`, `shock`, `tired`, `relief`, `morning`) fit any challenge; a new challenge usually needs 2–3 new scenes.

New art: generate in the same style (prompt template below), save as `assets/slides/art/<scene>__<source>.png`, add the slideshow to `SLIDESHOWS`.

> Hand-drawn 2D digital illustration in a modern editorial webcomic style: clean confident ink linework, flat colors with soft simple shading, subtle paper grain texture, muted warm palette of dusty navy, terracotta orange and cream, slightly imperfect hand-made feel. Not 3D, not glossy, not photorealistic. Scene: **…** a young man with short curly dark hair and brown skin, light blue t-shirt and plaid pajama pants **…** Vertical 9:16, top third is plain flat wall for text, no text, no letters
