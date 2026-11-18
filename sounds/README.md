# Sounds

All audio for the videos. One subfolder per category; files are `<description>__<source>.mp3` (see `docs/naming.md`).

| Folder | Used for | Picked automatically? |
|---|---|---|
| `alarm/` | the alarm that loops from the first frame until the challenge is done | yes (default bed) |
| `music-<mood>/` | background music, e.g. `music-hype/` | yes, when a clip's `edit.json` lists that mood |
| `unlicensed/` | sounds without a clear license for commercial social posts (phone-maker ringtones, Voicemod soundboard clips, the EAS emergency tone) | **no** — only if an `edit.json` names the category on purpose |

Only put sounds in an auto-used folder if you have the rights to use them in promotional posts (e.g. Epidemic Sound, Artlist, Mixkit, Pixabay). Short sounds are fine: they repeat with a crossfade.
