# Pre-voiced animation queue

Stories whose ElevenLabs voice lines are already recorded (`vo/l01.mp3` ... one per beat, then the CTA line). Backup only: the nightly run writes a fresh story with a live ElevenLabs voice and uses one of these only when the voice check
fails (see `prompts/animation.md` step 1b). Don't edit a story's `line` text or `cta_line`: the audio wouldn't match.

To refill: in a session that has the key (ELEVENLABS_API_KEY set on the command only, never written to a file — this repo
is public), add new `NN-<concept>/spec.json` folders and record them with `anim/record_queue.py`.
