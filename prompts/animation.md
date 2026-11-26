# Tonight's animation (part of the daily run)

Each day 1-2 of the 4 slots are animated videos. This step makes one new animation a night so the library never runs dry
(each animation is used at most 3 times, like a clip). Tool docs: `anim/README.md`. Don't stop to ask questions.

1. `python3 -m vdos anim-status` — `next_style`, `concepts_used`, `in_stock`, `uses_left`. Only `low_poly` is live.
   If `next_style` is anything else, use `low_poly` and say so in the summary.
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
4. **Check, build, check.** `python3 anim/build.py <spec> --snap` and Read the snaps image: every shot shows the character doing
   what the caption says. Then `python3 anim/build.py <spec>` (about a minute) and Read `<id>.sheet.jpg`: captions readable and
   not covering his face, cards/phones in the top third, counters right, download card last. Fix the spec and rebuild until it is right
   (at most 3 rebuilds; if it still isn't right, skip tonight's animation and say so — the plan reuses the ones in stock).
   Voice: the build always tries ElevenLabs (the key is a network secret on the cloud environment for `api.elevenlabs.io`, so there is no variable to check; an `ELEVENLABS_API_KEY` variable also works). If the call fails it prints why and makes a captions-only video; report which one in the summary.
5. **Add it:** `python3 -m vdos anim-add work/anim/<id>/<id>.mp4 --title "<the hook line>" --summary "<2 sentences: what happens>" --style low_poly --concept <slug> --voice <elevenlabs|none>`
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
