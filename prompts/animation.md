# Tonight's animation (part of the daily run)

**Chika, 2026-11-28 ("all animations still look the exact same... the voice sounds too enthusiastic"). These override anything older below:**
- **Length: 30-50 seconds** (Chika, later on 2026-11-28; was 45-60), 10-16 beats. Check `seconds` in the build output; add or trim beats until it is in range.
- **Talk to the viewer (Chika, 2026-11-28, after studying a Renno video she likes).** Write to "you", not about "I" or "he": the viewer is the
  one who snoozes ("you slept four hours." "you get up anyway."). The structure that works:
  1. **One idea carried all the way through.** Open on a comparison or claim the viewer instantly recognises ("your dog has never let
     you snooze."), make the case with it, and END on a callback to it ("make your alarm as stubborn as your dog."). Not a story that
     switches topic to an app at the end.
  2. **Very short lines**: 3-7 words, one thought each ("it's six a.m." "you slept four hours." "you get up anyway."), one line per beat.
  3. **The app arrives at the midpoint** by name ("unsnooze fixes that."), then three quick lines on how it works, each with the real
     app screen shown large and centred above the character (`phone` overlay, `x` 540, `y` 370, `scale` 0.58-0.62, `rot` 0).
  4. Set `"voice_sep": " "` in the spec so the one-take voice runs the short lines together instead of pausing after each.
  Reference build: `work/anim/A20261128-006/spec.json` (33 s).
- **A real pain point.** Build the story on something heavy sleepers actually go through, shown specifically: phone across the room and
  back to bed anyway, five stacked alarms, "five more minutes" turning into forty, missing the bus, walking in late with everyone
  looking, the group chat asking where you are, a partner or roommate woken instead of you. Name the pain before the app appears.
- **Different places.** At most a third of the beats in the bedroom; at least 2 other places per video, and every night at least one
  place the last 3 videos didn't use. Sets so far: `bus_stop` (outdoors), classroom (`class_late`, `class_desk`), cafe (`cafe_late`, `cafe_work`, `cafe_talk`). Build a new set in
  `anim/lowpoly/index.html` when needed (kitchen, office, gym, train, shop, car...), the way those two are built, and list it in `anim/README.md`.
- **Different characters.** `build.py` now also picks body build (`tall`, `wide`, `headS`), short sleeves / shorts and an accessory.
  On the sheet the figure's silhouette must differ from the last video's, not just its colours. A non-human narrator (the alarm
  with a face, `alarm_*` shots) or classmates/extras count as variety too; don't use the alarm character two nights running.
- **Different graphics.** `build.py` picks a `theme` (caption colours/style, card and stamp style, font) that the last 3 videos didn't
  use. Mix overlay kinds too (`bubble` chat messages, cards, stamps, tiles, phone screens). The download card at the end never changes.
- **Calmer voice.** Same pinned voice, but dry and conversational: `elevenlabs_stability = 1.0` in `config.toml`, no `[excited]`,
  `[proud]` or other hype tags (`[deadpan]` at most twice), no exclamation marks. The ending line is now
  `"cta_line": "Download Unsnooze. Link in bio."` (no tag). Backup queue stories still have the old excited ending recorded.
- **One flowing voice take** (the line-by-line takes sounded "fast and choppy, the parts don't flow"): `build.py` now reads the whole
  script in one ElevenLabs take (`elevenlabs_continuous`, `elevenlabs_speed = 0.9`) and cuts it at the pauses. Write the lines as one
  continuous piece of talking: full sentences that lead into each other ("then...", "except...", "so...", "or..."), commas rather than
  clipped fragments ("Six. Six oh five. Six ten." was choppy), no tone tags. Read the script top to bottom before building.
- **No jump to the download card** ("don't just jump directly to download unsnooze"): the last story beat must hand over to it:
  it names the app for the first time in the character's own words ("i'm unsnooze, by the way.") on a calm close shot. The card then
  rises over that shot (automatic) and the ending line follows. Never cut from the middle of the story straight to the card.
- **Captions: no background box** ("we don't really need a white background, just make sure the text is easy to read"): captions
  are bold outlined text in every theme. On the sheet, check each caption reads clearly against its scene.
- **Soft look (sample made 2026-11-28, waiting for Chika's verdict; use it only if a later note here says she approved it):**
  `"render": "soft"` (smooth rounded shapes, soft shadows, round dot eyes, 720x1280) with `"theme": "serif"` (small italic serif
  captions, whole line at once; `"cap_pos": "top"` puts the hook big at the top; cards become bare text) and a per-video end card
  `"end": {"tagline": "...", "big": ["GET UP.", "FOR REAL."]}` whose tagline is the callback line. Details in `anim/README.md`.
- **Sound.** Music is louder (`music_gain` in `config.toml`). Every cut gets a whoosh and every card a pop automatically; add at
  least 4 story sound effects with a beat's `"sfx"` list (bus, steps, bell, scratch, sad, tick, flop, sparkle, ding... see `anim/README.md`).

Each day 2 of the 4 slots are animated videos (Chika, 2026-11-27; was 1-2). This step makes one new animation a night so the library never runs dry
(each animation is used at most 3 times, like a clip). Tool docs: `anim/README.md`. Don't stop to ask questions.

1. `python3 -m vdos anim-status` — `next_style`, `concepts_used`, `in_stock`, `uses_left`. Only `low_poly` is live.
   If `next_style` is anything else, use `low_poly` and say so in the summary.
1a. **One voice for every animation (Chika, 2026-11-27).** Always the fire-alarm video's voice: `config.toml` `[animation]`
   `elevenlabs_voice_id` (Jack John - Conversational and Upbeat) with `elevenlabs_model`. Never set `ELEVENLABS_VOICE_ID`, never
   change the voice, id or model, and don't give other characters a different voice: one narrator voices everything. Use tone
   tags lightly (at most 2 lines per video) so he still sounds like the same person. Backup queue stories are the same voice.
1b. **Fresh story, live voice (Chika, 2026-11-26).** Every night is a brand-new story (step 2) voiced live by ElevenLabs. The key is the
   `ELEVENLABS_API_KEY=` line in the scheduled task's own prompt; use it only as a prefix on the curl check and the build command.
   `work/anim/queue/` holds pre-voiced backup stories: use the lowest-numbered one **only if the live voice check fails** (`git mv` it to
   `work/anim/<id>/`, set its `"id"`, keep `"voice_dir": "vo"`, don't change any `line`), and say so in the notification.
1c. **New look every night (Chika, 2026-11-26).** Never reuse the same character and room. `build.py` picks a new `look` (character:
   skin, hair style/colour, glasses, beard, outfit; room: wall texture/colour, floor, bedding, lights, props) that differs from recent
   animations and saves it in the spec. Check on the sheet that tonight's character and room clearly differ from the last few videos'
   sheets; if not, delete `"look"` from the spec, or set fields by hand, and rebuild. Don't copy a previous spec's `look`.
2. **Story.** Write a new one, different from every entry in `concepts_used` (different hook AND different middle). 7-14 beats,
   18-44 s: **the finished video must be under 45 seconds** (Chika, 2026-11-27; check `seconds` in the build output and trim if not).
   **Change it up every night (Chika, 2026-11-27: "it keeps following the same familiar character and sequence... be creative,
   make different scenarios").** The old formula (asleep -> snooze slaps -> late sprint -> set alarm -> challenge -> stretch ->
   out the door) is retired as a template. Rules:
   - Before writing, read the last 4 specs in `work/anim/A*/spec.json` and list their shot sequences. Tonight's video may share
     **at most 2 shots** with any one of them, and must not open or close on the same shot as the last 3 (`out_the_door` and
     `stretch_win` endings and `phone_buzz_asleep`/`snooze_slaps`/`late_sprint` middles are overused: avoid them most nights).
   - **A new scenario each night**: a different situation, place or format, not just a new excuse in the same bedroom morning.
     Ideas: the alarm/phone narrates ("I've rung 7 times. he hasn't moved."); a sports commentator or nature documentary on a
     snoozer; the group chat/class/shift/gym/bus/exam he's missing, shown from there; a roommate, mom or sibling as a second
     character; a courtroom or job interview with his alarm; ranking challenges; a dream that the alarm keeps breaking into;
     a day told backwards; a nap gone wrong; a heavy sleeper's "setup tour"; two versions of him split-screen in time.
     The Unsnooze challenge still has to be shown working, but it can come early, late, or be the whole video.
   - **At least 2 brand-new shots per video**, written into `anim/lowpoly/index.html` (new poses, camera, props or a new place
     built from low-poly boxes: desk, bus stop, kitchen, hallway, lecture hall, gym...; a second character is `look` with other
     colours). Document each new shot in the table in `anim/README.md` so later nights can reuse it sparingly. Check new shots
     with `--snap` (snaps don't count toward the 3 rebuilds).
   - The character changes too: `build.py` picks the look (step 1c); vary age/role in the story (student, night-shift worker,
     new parent, athlete, roommate...) and who is talking (not always "I").
   - Still **low poly only**, voiced, with a strong hook.
   - **The ending never changes (Chika, 2026-11-27): every animation, whatever the scenario, ends with the same CTA** — the
     automatic download card (app icon, "Download Unsnooze Today", App Store listing, badge, "LINK IN BIO") with the same voice
     line, `"cta_line": "[excited] Download Unsnooze. Link in bio!"`. Don't reword, shorten, restyle or drop it, don't end on a
     story beat instead, and check on the sheet that the card is the last frame. The under-45 s limit includes the card.
   Shape (loose): hook -> a situation people recognise -> the turn to Unsnooze -> one or two challenges shown working -> payoff.
   Good angles: an everyday comparison (things nobody snoozes: a fire alarm, a flight, a kettle), "POV" of the snooze bargain,
   a countdown of excuses, the roommate/mom who used to wake him, first week with the app, one challenge in detail.
   **The hook decides the video (Chika, 2026-11-27).** Beat 1 is the hook: its caption and voice line must stop the scroll in the
   first 2 seconds, on their own, before anything is explained. A good hook is a full, specific claim a heavy sleeper instantly
   agrees with or wants to argue with ("you've never snoozed a fire alarm", "ten alarms. slept through all ten.", "night me and
   morning me are not the same person."), not a scene-setter ("6 AM.", "so this morning...", "night me sets the alarm"). Keep it
   <= 9 words, no app name, no greeting, and put the strongest visual of the first act under it (card or stamp on screen by 0.3 s).
   Write 3 candidate hooks, pick the one that would work as a caption with the sound off, and use it as the `--title` too.
   Don't reuse a hook shape from the last 3 animations (comparison, number, POV, confession, question...). If the hook is weak on
   the sheet, rewrite beat 1 before adding the video: a weak hook counts as "not right".
   Rules: first person, casual, lowercase captions (voice per `prompts/voice.md`); one idea per beat; captions <= 9 words;
   only real Unsnooze challenges and plausible numbers (push-ups, squats, walking steps, shake, memory, math, typing, matching,
   house hunt, affirmation; "15+ ways to wake up"); no claims about results the app can't promise; nothing about other apps.
3. **Spec.** `work/anim/<id>/spec.json` (`<id>` = `A<yyyymmdd>-<n>`, today's date in Eastern time), using the shots and overlays in
   `anim/README.md`. Put `"lift": true` on the turn. If the story needs a shot that doesn't exist, add it to
   `anim/lowpoly/index.html` (it is saved with `cloud-save`).
4. **Check, build, check.** First check the voice: `curl -s -o /dev/null -w '%{http_code}' -H "xi-api-key: $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/user`
   must print 200 (the scheduled task gives the key as `ELEVENLABS_API_KEY` on the build command only; never write it to a file, commit,
   log or summary: the repo is public). If it isn't 200, **skip tonight's animation** (403 = host blocked in claude.ai Settings > Capabilities >
   Allowed websites; 401 = key missing or wrong) and put "ANIMATION SKIPPED: no voice (<code>)" first in the push notification.
   Then `python3 anim/build.py <spec> --snap` and Read the snaps image: every shot shows the character doing
   what the caption says. Then `python3 anim/build.py <spec> --require-voice` (about a minute) and Read `<id>.sheet.jpg`: captions readable and
   not covering his face, cards/phones in the top third, counters right, download card last. Fix the spec and rebuild until it is right
   (at most 3 rebuilds; if it still isn't right, skip tonight's animation and say so — the plan reuses the ones in stock).
   **Never add a captions-only animation (Chika, 2026-11-26).** `--require-voice` stops the build when the voice fails; if it does,
   skip tonight's animation. After a good build add `"voice_dir": "vo"` to the spec so rebuilds reuse the recorded lines.

5. **Add it:** `python3 -m vdos anim-add work/anim/<id>/<id>.mp4 --title "<the hook line>" --summary "<2 sentences: what happens>" --style low_poly --concept <slug> --voice elevenlabs`
   Then continue with `vdos publish` (step 2 of the daily run), which uploads it for Buffer.

Posting an animation slot (`"kind": "animation"` in the plan) works like any other slot: same caption rules, hashtags and tests.
Write the caption from the slot's `summary` and `caption_text` (the hook). If Buffer's `create_post` offers an AI-generated-content
flag for a platform, set it on animation slots.

## App UI reference (optional)

When a video needs an app screen that isn't already in `anim/assets/`, you may look at Chika's Figma file through the Figma
connector (file key `3Ug3mROsgOOhGXoCAOpZvX`, starting node `80410:74`,
https://www.figma.com/design/3Ug3mROsgOOhGXoCAOpZvX/Unsnooze?node-id=80410-74) to match real screens, colours and wording.
It is a reference, not a requirement (Chika, 2026-11-25: "don't ALWAYS rely on this"): most videos should keep using the
overlays the builder already draws. Read only; never edit the Figma file. If the connector isn't available, carry on without it.
