"""Animated videos (made in code by the nightly run, see anim/ and prompts/animation.md).

An animation is stored like any other video: one row in `clips` (id A<yyyymmdd>-<nnn>, topic and format
"animation", angle "animation") and one row in `variants` (the finished mp4 in media/edited). So reuse caps,
publishing, Buffer sync and the weekly ranking all work unchanged. The style (low_poly / zach_3d) is stored
as the variant's title_style ("anim_low_poly"), which the weekly review already ranks.
"""
from __future__ import annotations

import hashlib
import json
import random
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, db, media, reuse

TOPIC = FORMAT = ANGLE = "animation"


def is_animation(row) -> bool:
    return (row["topic"] if "topic" in row.keys() else None) == TOPIC or str(row["id"]).startswith("A")


def register(mp4: Path, title: str, summary: str, style: str = "low_poly", concept: str = "", voice: str = "none",
             day: str | None = None) -> dict:
    """Add a finished animation (1080x1920 mp4) to the library so `plan` can schedule it."""
    cfg = config.load()
    mp4 = Path(mp4)
    sha = hashlib.sha256(mp4.read_bytes()).hexdigest()
    info = media.probe(mp4)
    tz = ZoneInfo(cfg["posting"]["timezone"])
    d = (day or datetime.now(tz).date().isoformat()).replace("-", "")
    with db.tx() as con:
        dup = con.execute("SELECT id FROM clips WHERE sha256=?", (sha,)).fetchone()
        if dup:
            return {"clip_id": dup["id"], "duplicate": True}
        n = con.execute("SELECT COUNT(*) c FROM clips WHERE id LIKE ?", (f"A{d}-%",)).fetchone()["c"] + 1
        cid = f"A{d}-{n:03d}"
        vid = f"{cid}_v1"
        fname = f"{vid}_{secrets.token_hex(3)}.mp4"
        shutil.copy2(mp4, cfg.path("edited") / fname)
        con.execute("""INSERT INTO clips(id, file_name, sha256, duration_s, width, height, has_audio, captured_at, ingested_at,
                       topic, format, status, notes, angle) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cid, mp4.name, sha, info.get("duration"), info.get("width"), info.get("height"), 1, db.now_iso(), db.now_iso(),
                     TOPIC, FORMAT, "edited", f"animation:{style}:{concept}", ANGLE))
        spec = {"kind": "animation", "style": style, "concept": concept, "voice": voice, "summary": summary}
        con.execute("""INSERT INTO variants(id, clip_id, file_name, hook_type, caption_style, overlay_text, speed, start_s, duration_s,
                       spec_json, created_at, active, caption_text, title_style, sound_id, sound_type, speed_level, cta_mode, title_emoji)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (vid, cid, fname, "story", "animation", title, 1.0, 0.0, info.get("duration"), json.dumps(spec), db.now_iso(), 1,
                     title, f"anim_{style}", f"anim-voice-{voice}", "animation", "base", "none", "none"))
        db.log_event(con, "animation", {"clip": cid, "style": style, "concept": concept})
    wd = cfg.path("work") / cid
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "edit.json").write_text(json.dumps({"topic": TOPIC, "format": FORMAT, "angle": ANGLE, "summary": summary,
                                              "style": style, "concept": concept, "title": title, "voice": voice}, indent=2))
    return {"clip_id": cid, "variant_id": vid, "file": fname, "duration_s": info.get("duration")}


def status() -> dict:
    """What the nightly run needs to know: animations in stock, concepts already used, and the style to make next."""
    cfg = config.load()
    acfg = cfg.get("animation") or {}
    with db.tx() as con:
        rows = [r for r in reuse.clip_table(con) if r["topic"] == TOPIC]
        used = []
        for r in con.execute("SELECT id, notes FROM clips WHERE topic=? ORDER BY id", (TOPIC,)):
            parts = (r["notes"] or "").split(":", 2)
            used.append({"clip": r["id"], "style": parts[1] if len(parts) > 1 else "", "concept": parts[2] if len(parts) > 2 else ""})
        w = {r["value"]: r["weight"] for r in con.execute("SELECT value, weight FROM weights WHERE dimension='title_style'")}
    live = [r for r in rows if r["status"] in ("available", "cooling")]
    styles = dict(acfg.get("styles") or {"low_poly": 1.0})
    # lean on the configured mix, nudged by how each style has scored once the weekly review has data
    ws = {s: float(v) * (w.get(f"anim_{s}", 1.0) if w else 1.0) for s, v in styles.items() if float(v) > 0}
    rng = random.Random(datetime.now().toordinal())
    nxt = rng.choices(list(ws), weights=list(ws.values()), k=1)[0] if ws else "low_poly"
    return {"in_stock": len(live), "uses_left": sum(r["cap"] - r["committed"] for r in live),
            "available_today": sum(1 for r in rows if r["status"] == "available"),
            "make_tonight": int(acfg.get("new_per_night", 1)), "next_style": nxt, "styles": styles,
            "per_day": [int(acfg.get("min_per_day", 1)), int(acfg.get("max_per_day", 2))],
            "voice": acfg.get("voice", "elevenlabs"), "concepts_used": used[-30:]}
