# Animations

Animated Unsnooze videos made entirely in code. Each day 1-2 of the 4 posting slots are animations (`config.toml` `[animation]`).
The nightly run writes a story spec, builds it here, checks the contact sheet and adds it to the library with `vdos anim-add`.
The procedure for the run is in `prompts/animation.md`; this file documents the tool.

## Styles
- **low_poly** (live): `anim/lowpoly/` — a PS1-style bedroom and character in three.js (360x640, vertex snapping, dither, pixel textures
  drawn in code), rendered in headless Chrome. The technique comes from the `/low-poly` skill in
  https://github.com/artemnovitckii/claude-animation-skills (MIT), rebuilt as an Unsnooze scene with a shot library.
- **zach_3d** (off until tested, weight 0 in `config.toml`): the `/zach-3d-films` skill from the same repo. Its engine ships one
  armour short; an Unsnooze version needs its own shots and props and one supervised build before it runs unattended.

## Build
```
python3 anim/build.py work/anim/<id>/spec.json --snap    # quick: one 3D still per shot -> <id>.snaps.jpg (look at it first)
python3 anim/build.py work/anim/<id>/spec.json           # ~1 minute -> <id>.mp4 + <id>.sheet.jpg (look at it before adding)
python3 -m vdos anim-add work/anim/<id>/<id>.mp4 --title "<hook line>" --summary "<what happens>" --style low_poly --concept <slug> --voice elevenlabs|none
```
Needs Node, ffmpeg, Pillow, numpy and Chrome (`/usr/bin/google-chrome`, or set `CHROME`). The first build runs `npm install` in `anim/lowpoly`.

## Spec
```json
{"id": "A20261127-001", "style": "low_poly", "concept": "five-more-minutes", "title": "five more minutes",
 "summary": "one or two sentences: what happens (used for the post captions)",
 "beats": [
  {"shot": "snooze_slaps", "line": "[groggy] Snoozed. Seven times.", "caption": "snoozed. *seven* times.",
   "overlay": [{"type": "card", "label": "ALARM", "big": "6:00 AM", "at": 0.1}, {"type": "stamp", "text": "SNOOZED ×7", "at": 1.75}]},
  {"shot": "pushups", "lift": true, "caption": "now it wants *10 push-ups.*",
   "overlay": [{"type": "phone", "screen": "pushups", "from": 7, "to": 10, "total": 10}]}
 ],
 "cta_line": "Download Unsnooze. Link in bio!"}
```
- **beats**: 7-14, in order. Each beat is one shot with one caption. The video ends with the download card (app icon, App Store
  listing, badge, "LINK IN BIO"), added automatically.
- **caption**: lowercase, short; `*stars*` mark the 1-3 words shown in white (the rest is yellow). `\n` breaks lines, otherwise it wraps at ~24 characters.
- **line**: what the voice says (defaults to the caption). ElevenLabs tone tags like `[groggy]` are allowed.
- **dur** / **min**: fixed or minimum seconds for the beat. Without them a beat lasts as long as its voice line (or reading time).
- **lift**: put it on the beat where the story turns to Unsnooze; the drums come in there.
- **p**: shot options: `{"clock": "6:45", "mood": "night"|"dawn"|"day", "tilt": 12}`.
- **then**: cut to a second shot inside one beat: `{"shot": "thinking", "then": {"shot": "shake_phone", "at": 1.6}}`.
- **voice**: `false` forces captions only. `voice_dir` points at ready-made lines (`l01.mp3` ... one per beat, plus one for the CTA).

### Shots
| Shot | What happens | Notes |
|---|---|---|
| `asleep_smoke_alarm` | asleep, smoke alarm flashing red, Zzz | night |
| `bolt_upright` | bolts upright in bed, hands over ears, "!" | needs >= 1.2 s |
| `smoke_alarm_swat` | alarm from below, then he swats at it | best >= 2.5 s |
| `phone_buzz_asleep` | phone buzzing on the nightstand at 6:00, he sleeps on | |
| `snooze_slaps` | slaps snooze three times (0.4, 1.05, 1.6 s), clock jumps to 7:30 | needs >= 2.4 s; stamp at 1.75 |
| `late_sprint` | wakes at 8:47 and sprints for the door | needs >= 1.4 s |
| `facepalm` | hand over his face | |
| `set_alarm_in_bed` | at night, sitting in bed setting the alarm | good for `phone` `grid` overlay |
| `pushups` / `squats` | does the challenge next to the ringing phone | `phone` overlay with a counter |
| `walk_steps` | walks toward the camera holding the phone | `phone` `walk` |
| `shake_phone` | shakes the phone hard | `phone` `shake` |
| `thinking` | chin in hand | `tiles` overlay (math, memory...) |
| `floor_ping` | collapsed on the rug, the phone pings again | |
| `stretch_win` | alarm off: stretch, then fist pump at the sunny window | pump at 0.9 s; `DISMISSED` stamp at 0.9 |
| `talk` | talks to the camera with his hands | any line |
| `out_the_door` | walks out with his backpack, smiling | |
| `store_art` | the real "15+ ways to wake up" App Store screenshot, full screen | no overlays |

A story may need a shot that isn't here. Add `S.<name> = (u, d, k, t) => {...}` to `anim/lowpoly/index.html` by copying the closest
one (`pose({...})` sets every joint, `cam(...)` the camera, `mood(...)` the light), add it to `TILTS` if cards sit above his head,
and check it with `--snap` before building. Shots must depend only on the time arguments.

### Overlays (2D, on top of the 3D)
- `card`: `{"type": "card", "label": "ALARM", "big": "6:00 AM", "accent": "orange|red|green", "at": 0.1, "x": 500, "y": 320}` — dark app-style card.
- `stamp`: `{"type": "stamp", "text": "LATE", "color": "red|green", "at": 0.8, "x": 650, "y": 470}` — slams on with a thud.
- `phone`: `{"type": "phone", "screen": "pushups|walk|shake|squats|grid", "from": 7, "to": 10, "total": 10, "x": 835, "y": 440, "scale": 0.6}` —
  `pushups` and `grid` are the real app screens (from the App Store screenshots); the others are drawn in the app's style.
- `tiles`: `{"type": "tiles", "names": ["math", "memory"], "ats": [0.1, 0.8]}` — real challenge tiles: memory, walking, matching, math, house_hunt, affirmation.
Keep overlays in the top third; the character is framed below them. Only show challenges and numbers the app really has.

## Voice and sound
- Voice: ElevenLabs, voice and model from `config.toml` `[animation]`. It needs `ELEVENLABS_API_KEY` in the run's environment and
  `api.elevenlabs.io` reachable. Without them the build makes a captions-only video (music + sound effects), which is the usual
  low-poly-shorts format. (This path could not be tested from the cloud yet; the first night with a key should check the log line `voice:`.)
- Music: an original lo-fi bed generated in `build.py` (no licence needed), ducked under the voice.
- Sound effects: smoke-alarm chirps, the phone alarm from `sounds/alarm/`, thuds on stamps, chimes on the win and the download card.
