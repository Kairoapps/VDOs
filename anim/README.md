# Animations

Animated Unsnooze videos made entirely in code. Each day 2 of the 4 posting slots are animations (`config.toml` `[animation]`).
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
- **beats**: 7-14, in order; the finished video is 45-60 seconds (Chika, 2026-11-28; 14-18 beats). Each beat is one shot with one caption. The video ends with the download card (app icon, App Store
  listing, badge, "LINK IN BIO"), added automatically. This CTA is the same on every video (Chika, 2026-11-27):
  keep `cta_line` as "Download Unsnooze. Link in bio." (no tone tag since 2026-11-28: calmer voice) and never remove or restyle the card.
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
| `across_room_go` | the alarm is on the window sill "across the room": eyes shut, he shuffles over and taps it off (78% of the shot) | added 2026-11-28; needs >= 3.2 s |
| `back_to_bed` | ...then shuffles straight back and face-plants into bed (62%) | added 2026-11-28; needs >= 3.2 s |
| `bus_stop` | PLACE: a street with a bus stop. `p.mode` `miss` (default): he sprints after the bus as it pulls away, turns back, sags; `catch`: he waits with his backpack and waves as the bus pulls in | added 2026-11-28; needs >= 2.8 s |
| `class_late` | PLACE: a classroom. He tiptoes in through the back door and every classmate turns to look | added 2026-11-28 |
| `class_desk` | classroom, at his desk with the alarm standing on it. `p.mode` `slump` (default): asleep on the desk; `early`: awake, smiling, empty room. `p.face` = the alarm's face | added 2026-11-28 |
| `cafe_late` | PLACE: a cafe (his job). He bursts in through the door, late; the boss behind the counter turns to look | added 2026-11-28; needs >= 3 s |
| `cafe_work` | behind the cafe counter in an apron. `p.mode` `tired` (default): nodding off next to the boss; `early`: alone, awake, wiping the counter | added 2026-11-28 |
| `cafe_talk` | in front of the counter, talking to the camera. `p.phone` holds his phone up, `p.boss` the boss stares, `p.view` `close` | added 2026-11-28 |
| `bed_top` | bedroom from the ceiling: starfished asleep, phone lit up by his head. `p.slap`: his hand flops onto it (0.7, 1.6 s); with `p.once` one tap at 0.6 s and the phone stays dark; `p.quiet`: phone dark | added 2026-11-28; good under `bubble` texts |
| `dog_wake` | a dog on the bed while he sleeps. `p.mode` `stare` (default): sits staring at the camera, head tilting; `paw`: leans over and noses his face | added 2026-11-28 |
| `dog_up` | he sits up in bed yawning while the dog bounces beside the bed. `p.ring`: no dog, the phone keeps ringing and he stares at it | added 2026-11-28 |
| `dog_door` | the dog waits at the bedroom door, leash in its mouth; he shuffles over. `p.close`: close on the dog | added 2026-11-28 |
| `dog_walk` | PLACE: the street at sunrise; he walks the dog on a leash | added 2026-11-28; needs >= 2 s |
| `dog_end` | street at sunrise, low and close on the dog sitting, looking up; he stands behind | added 2026-11-28 |
| `store_art` | the real "15+ ways to wake up" App Store screenshot, full screen | no overlays |
| `alarm_slapped` | the alarm itself (a phone with a face) rears up ringing on the nightstand and gets slapped flat at 0.75 / 1.5 / 2.25 s; he sleeps on | added 2026-11-28; needs >= 3 s; stamp at 0.75 |
| `alarm_talk` | the alarm talks to the camera from the nightstand | added 2026-11-28; `p`: `face` annoyed/dead/determined/happy, `bg` asleep/gone/made, `view` 0 close / 1 wide with the bed / 2 low hero, plus `mood`, `clock` |
| `alarm_thrown` | he throws the alarm across the room; it lands on the rug (0.8 s), lies there, then rings again (1.6 s) | added 2026-11-28; needs >= 2.4 s |
| `alarm_held` | up and smiling, he holds the happy alarm up to the camera | added 2026-11-28; day |

Every new video needs at least 2 new shots and a new scenario (Chika, 2026-11-27; `prompts/animation.md` step 2): don't rebuild the
same wake/snooze/late/win sequence from this table. A story may need a shot that isn't here. Add `S.<name> = (u, d, k, t) => {...}` to `anim/lowpoly/index.html` by copying the closest
one (`pose({...})` sets every joint, `cam(...)` the camera, `mood(...)` the light), add it to `TILTS` if cards sit above his head,
and check it with `--snap` before building. Shots must depend only on the time arguments.

### Overlays (2D, on top of the 3D)
- `bubble`: `{"type": "bubble", "from": "group chat", "text": "where are you??", "side": "left|right", "at": 0.9, "x": 640, "y": 520}` — a chat message (added 2026-11-28).
- `card`: `{"type": "card", "label": "ALARM", "big": "6:00 AM", "accent": "orange|red|green", "at": 0.1, "x": 500, "y": 320}` — dark app-style card.
- `stamp`: `{"type": "stamp", "text": "LATE", "color": "red|green", "at": 0.8, "x": 650, "y": 470}` — slams on with a thud.
- `phone`: `{"type": "phone", "screen": "pushups|walk|shake|squats|grid", "from": 7, "to": 10, "total": 10, "x": 835, "y": 440, "scale": 0.6}` —
  `pushups` and `grid` are the real app screens (from the App Store screenshots); the others are drawn in the app's style.
- `tiles`: `{"type": "tiles", "names": ["math", "memory"], "ats": [0.1, 0.8]}` — real challenge tiles: memory, walking, matching, math, house_hunt, affirmation.
Keep overlays in the top third; the character is framed below them. Only show challenges and numbers the app really has.

## Voice and sound
- Voice: ElevenLabs, always the same voice (Chika, 2026-11-27): `elevenlabs_voice_id` and model pinned in `config.toml` `[animation]`. The key comes from `ELEVENLABS_API_KEY`, which the nightly
  scheduled task sets on the build command only (never commit it: this repo is public). `api.elevenlabs.io` must be allowed in
  claude.ai Settings > Capabilities > Allowed websites (Cowork sessions; the Claude Code environment's network secret does not reach
  them — found 2026-11-26). Without a voice the build makes a captions-only video, unless `--require-voice` is passed (the nightly
  run always passes it: captions-only animations are not posted).
- Music: an original lo-fi bed generated in `build.py` (no licence needed), ducked under the voice.
- Sound effects: smoke-alarm chirps, the phone alarm from `sounds/alarm/`, thuds on stamps, chimes on the win and the download card.

## Background music

The build writes its own music; there is no music file. `anim/build.py` has five original lo-fi tracks (`sunday`,
`slow_morning`, `get_up`, `late_night`, `bright`: same instruments, different key, tempo and chords). By default the
track is picked from the video's id, so it changes from video to video but repeats now and then. To choose one, add
`"music": "<name>"` to the spec. The build prints which track it used.

## Themes, builds and sound effects (2026-11-28)

- **Theme**: `"theme"` in the spec (`classic`, `paper`, `clean`, `pop`): caption colours, card and stamp style, font. Captions are always outlined text with no background box (Chika, 2026-11-28).
  `build.py` picks one the last 3 videos didn't use and saves it; the download card is never themed.
- **Build**: `look` also has `tall` (0.9-1.08), `wide` (0.86-1.24), `headS` (0.9-1.2), `sleeves` long/short, `shorts`, `acc` none/headphones/scarf.
- **Places**: other sets stand far from the bedroom in the same scene (`BX` bus stop, `CX` classroom, `FZ` cafe); a shot poses him there, moves
  the camera and calls `setSky(...)`. Copy that pattern for a new place.
- **Sound effects**: a beat's `"sfx": [{"name": "bus", "at": 0.0, "dur": 2.8, "vol": 1}]`. Names: `whoosh`, `pop`, `ding`, `bell`, `bus`,
  `steps`, `scratch`, `sad`, `tick`, `flop`, `sparkle`, `thud` (all synthesised in `build.py`). Cuts get a whoosh and cards a pop automatically.
- **Music level**: `music_gain` in `config.toml` `[animation]` (0.48; ducked to half under the voice).
- **Voice**: `elevenlabs_stability` in `config.toml` (1.0 = steadiest, calmest).

## Soft look and quiet captions (2026-11-28, modelled on a Renno video Chika likes; approved, now the default for new videos)

- `"render": "soft"` in the spec: every box gets rounded edges and smooth shading, textures are drawn clean (no pixel noise), faces are
  round dot eyes and simple mouths, the key light casts soft shadows, frames render at 720x1280 and get a gentle vignette. Without it
  the build is the pixelated PS1 look, unchanged. All shots work in both.
- `"theme": "serif"` (picked automatically with `render: soft`): captions in small italic serif, white with one accent word, the whole
  line at once; `"cap_pos": "top"` on a beat draws it large at the top (the hook). `card` overlays become bare text (small label + big value).
- The ending is always the original download card. A per-video end card was tried once and Chika rejected it (2026-11-28); `"end"` in a spec is ignored.
- `"voice_sep": " "`: the one-take voice read joins the lines with a space (flowing short lines) instead of a pause after each.
