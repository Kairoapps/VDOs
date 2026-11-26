"""Record ElevenLabs voice lines for every queued story that doesn't have them yet.

Usage (the key goes on the command only; never write it to a file):
    ELEVENLABS_API_KEY=... python3 anim/record_queue.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

root = Path(__file__).resolve().parent.parent / "work" / "anim" / "queue"
for d in sorted(p for p in root.iterdir() if (p / "spec.json").exists()):
    s = json.loads((d / "spec.json").read_text())
    lines = [b.get("line") or re.sub(r"[*\n]", " ", b.get("caption", "")) for b in s["beats"]] + [s.get("cta_line", "Download Unsnooze. Link in bio!")]
    have = len(list((d / "vo").glob("l*.mp3"))) if (d / "vo").exists() else 0
    if have >= len(lines):
        print(d.name, "already recorded"); continue
    ok = build.elevenlabs(lines, d / "vo")
    print(d.name, "recorded" if ok else "FAILED")
