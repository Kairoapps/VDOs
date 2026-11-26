# Tonight's animation (part of the daily run)

Each day 1-2 of the 4 slots are animated videos. This step makes one new animation a night so the library never runs dry
(each animation is used at most 3 times, like a clip). Tool docs: `anim/README.md`. Don't stop to ask questions.

1. `python3 -m vdos anim-status` — `next_style`, `concepts_used`, `in_stock`, `uses_left`. Only `low_poly` is live.
   If `next_style` is anything else, use `low_poly` and say so in the summary.
1b. **Fresh story, live voice (Chika, 2026-11-26).** Every night is a brand-new story (step 2) voiced live by ElevenLabs. The key is the
   `ELEVENLABS_API_KEY=` line in the scheduled task's own prompt; use it only as a prefix on the curl check and the build command.
   `work/anim/queue/` holds pre-voiced backup stories: use the lowest-numbered one **only if the live voice check fails** (`git mv` it to
   `work/anim/<id>/`, set its `"id"`, keep `"voice_dir": "vo"`, don't change any `line`), and say so in the notification.
1c. **New look every night (Chika, 2026-11-26).** Never reuse the same character and room. `build.py` picks a new `look` (character:
   skin, hair style/colour, glasses, beard, outfit; room: wall texture/colour, floor, bedding, lights, props) that differs from recent
   animations and saves it in the spec. Check on the sheet that tonight's character and room clearly differ from the last few videos'
   sheets; if not, delete `"look"` from the spec, or set fields by hand, and rebuild. Don't copy a previous spec's `look`.
2. **Story.** Write a new one, different from every entry in `concepts_used` (different hook AND different middle). 7-12 beats, 18-35 s.
   Shape: a hook in the first line that names a feeling every heavy sleeper knows -> the snooze spiral or its cost ->
   the turn ("so I...") -> one or two Unsnooze challenges shown working -> the payoff -> (download card is automatic).
   Good angles: an everyday comparison (things nobody snoozes: a fire alarm, a flight, a kettle), "POV" of the snooze bargain,
   a countdown of excuses, the roommate/mom who used to wake him, first week with the app, one challenge in detail.
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
