"""Derived labels the weekly review ranks: emoji counts, sound type, speed bucket, angle."""
from __future__ import annotations

import re

_EMOJI_CH = r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿‼⁉]"
# one emoji = one cluster (ZWJ sequences like 😮‍💨, skin tones and variation selectors count once)
_EMOJI = re.compile(rf"{_EMOJI_CH}(?:[\uFE0F\U0001F3FB-\U0001F3FF]|\u200D{_EMOJI_CH})*")

# Keyword -> sound type, checked in order against the sound's file name (sounds/<category>/<description>__<source>.mp3).
SOUND_TYPES = [("siren", "siren"), ("beep", "beeping"), ("scifi", "sci-fi"), ("samsung", "ringtone"),
               ("ringtone", "ringtone"), ("voicemod", "ringtone"), ("loud", "loud-alarm"), ("loop", "alarm-loop")]


def emoji_count(text: str | None) -> int:
    return len(_EMOJI.findall(text or ""))


def emoji_bucket(text: str | None) -> str:
    n = emoji_count(text)
    return "0" if n == 0 else "1" if n == 1 else "2" if n == 2 else "3+"


def sound_type(sound_id: str | None) -> str:
    if not sound_id:
        return "none"
    if sound_id.startswith("music-"):
        return "music-" + sound_id.split("/")[0][len("music-"):]
    name = sound_id.lower()
    for key, label in SOUND_TYPES:
        if key in name:
            return label
    return "alarm-clock"


def speed_bucket(speed: float | None) -> str:
    if not speed:
        return "?"
    return f"{round(float(speed) * 10) / 10:.1f}x"


def angle_of(edit: dict) -> str:
    a = edit.get("angle")
    if a:
        return a
    return "sus" if edit.get("sus") else "challenge"
