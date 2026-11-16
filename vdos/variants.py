"""Turn an edit decision (work/<clip>/edit.json) into N distinct rendered variants.

edit.json (written by Claude after reading work/<clip>/context.md and frames, or by `auto_edit`):
{
  "topic": "gym",                       # overrides the file-name topic
  "format": "pov",                      # pov | tutorial | storytime | montage | reaction | before_after
  "summary": "one line on what happens",
  "keep": [[0.0, 7.4], [9.1, 31.0]],    # source-time spans to keep, in order (dead air removed)
  "hooks": [                            # candidate openings; variants rotate through them
    {"type": "bold_claim", "start": 9.1, "text": "5am gym is overrated"},
    {"type": "mid_action", "start": 0.0},
    {"type": "question", "start": 0.0, "text": "Would you train like this?"}
  ],
  "moods": ["hype", "chill"],           # music subfolders that fit; [] = no music
  "unusable": false
}
"""
from __future__ import annotations

import json
import random
import secrets
from datetime import datetime, timedelta, timezone

from . import config, db, media, render, weights

FORMATS = ["pov", "tutorial", "storytime", "montage", "reaction", "before_after"]


def auto_edit(clip_id: str) -> dict:
    """Fallback edit with no editorial judgment: drop silences, open mid-action."""
    cfg = config.load()
    with db.tx() as con:
        clip = con.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
    wd = cfg.path("work") / clip_id
    sil = json.loads((wd / "silences.json").read_text()) if (wd / "silences.json").exists() else []
    dur = clip["duration_s"]
    keep, t = [], 0.0
    for a, b in sil:
        b = min(b, dur)
        if a - t > 0.5:
            keep.append([round(max(0, t - 0.1), 2), round(min(dur, a + 0.15), 2)])
        t = b
    if dur - t > 0.5:
        keep.append([round(max(0, t - 0.1), 2), round(dur, 2)])
    if not keep:
        keep = [[0.0, round(dur, 2)]]
    hooks = [{"type": "mid_action", "start": keep[0][0]}]
    total = sum(b - a for a, b in keep)
    if total > 20:  # a second opening further in, so auto variants differ by more than music/speed
        acc, target = 0.0, total * 0.25
        for a, b in keep:
            if acc + (b - a) >= target:
                hooks.append({"type": "mid_action", "start": round(a + target - acc, 2)})
                break
            acc += b - a
    return {"topic": clip["topic"], "format": "pov", "summary": "", "keep": keep,
            "hooks": hooks, "moods": ["any"], "unusable": False}


def _spans_from(keep: list, start: float, max_len: float) -> list[list[float]]:
    out, total = [], 0.0
    for a, b in keep:
        if b <= start:
            continue
        a = max(a, start)
        take = min(b - a, max_len - total)
        if take <= 0.3:
            break
        out.append([round(a, 2), round(a + take, 2)])
        total += take
    return out


def _eligible_tracks(con, moods: list[str], days: int) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    recent = {r["track_id"] for r in con.execute(
        """SELECT v.track_id FROM slots s JOIN variants v ON v.id=s.variant_id WHERE s.scheduled_at >= ?""", (cutoff,))}
    rows = con.execute("SELECT * FROM tracks").fetchall()
    if moods and "any" not in moods:
        pref = [r for r in rows if r["mood"] in moods]
        rows = pref or rows
    fresh = [r for r in rows if r["id"] not in recent]
    return fresh or rows


def generate(clip_id: str, n: int | None = None, seed: int | None = None, dry_run: bool = False) -> list[dict]:
    cfg = config.load()
    vcfg, rcfg = cfg["variants"], cfg["render"]
    n = n or vcfg["per_clip"]
    rng = random.Random(seed)
    wd = cfg.path("work") / clip_id
    edit_path = wd / "edit.json"
    edit = json.loads(edit_path.read_text()) if edit_path.exists() else auto_edit(clip_id)
    if not edit_path.exists():
        edit_path.write_text(json.dumps(edit, indent=2))
    tr = json.loads((wd / "transcript.json").read_text()) if (wd / "transcript.json").exists() else {"words": []}

    made = []
    with db.tx() as con:
        clip = con.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
        if edit.get("unusable"):
            con.execute("UPDATE clips SET status='unusable' WHERE id=?", (clip_id,))
            return []
        con.execute("UPDATE clips SET topic=?, format=? WHERE id=?",
                    (edit.get("topic") or clip["topic"], edit.get("format") or "pov", clip_id))
        existing = con.execute("SELECT COUNT(*) c FROM variants WHERE clip_id=?", (clip_id,)).fetchone()["c"]
        siblings = con.execute("SELECT caption_style, track_id, hook_type FROM variants WHERE clip_id=? AND active=1",
                               (clip_id,)).fetchall()
        used_styles = {s["caption_style"] for s in siblings}
        used_tracks = {s["track_id"] for s in siblings}
        hooks = edit.get("hooks") or [{"type": "mid_action", "start": edit["keep"][0][0]}]
        moods = edit.get("moods", ["any"])
        tracks = _eligible_tracks(con, moods, cfg["reuse"]["music_min_days_between"]) if moods else []
        used_hooks = {(v["hook_type"], v["start_s"]) for v in con.execute(
            "SELECT hook_type, start_s FROM variants WHERE clip_id=? AND active=1", (clip_id,))}

        for i in range(n):
            # hook: weighted by hook_type, rotate so variants differ
            types = [h["type"] for h in hooks]
            fresh = [h for h in hooks if (h["type"], h.get("start")) not in used_hooks]
            if not fresh:
                used_hooks.clear()
                fresh = hooks
            ht = weights.choose(con, "hook_type", [h["type"] for h in fresh], rng=rng)
            hook = rng.choice([h for h in fresh if h["type"] == ht])
            used_hooks.add((hook["type"], hook.get("start")))
            style = weights.choose(con, "caption_style", vcfg["caption_styles"], exclude=used_styles, rng=rng)
            used_styles.add(style)
            track = None
            if tracks:
                pool = [t for t in tracks if t["id"] not in used_tracks] or tracks
                mood = weights.choose(con, "music_mood", sorted({t["mood"] for t in pool}), rng=rng)
                track = rng.choice([t for t in pool if t["mood"] == mood])
                used_tracks.add(track["id"])
            speed = vcfg["speeds"][(existing + i) % len(vcfg["speeds"])]
            spans = _spans_from(edit["keep"], float(hook.get("start", 0)), rcfg["max_len"] * speed)
            length = sum(b - a for a, b in spans) / speed
            if length < min(rcfg["min_len"], clip["duration_s"] * 0.8):
                spans = _spans_from(edit["keep"], edit["keep"][0][0], rcfg["max_len"] * speed)
                length = sum(b - a for a, b in spans) / speed
            overlay = hook.get("text") if hook["type"] in ("bold_claim", "question", "text_overlay") else None
            vid = f"{clip_id}_v{existing + i + 1}"
            fname = f"{vid}_{secrets.token_hex(3)}.mp4"
            spec = {
                "src": str(cfg.path("raw") / clip["file_name"]), "segments": spans, "speed": speed,
                "caption_style": style if tr["words"] else None, "hook_text": overlay, "words": tr["words"],
                "has_audio": bool(clip["has_audio"]),
                "track": str(cfg.path("music") / track["id"]) if track else None,
                "track_lufs": track["lufs"] if track else None,
                "track_offset": round(rng.uniform(0, max(0, (track["duration_s"] or 0) - length - 2)), 1) if track else 0,
                "reframe": rcfg["reframe"],
            }
            info = {"id": vid, "file": fname, "hook_type": hook["type"], "caption_style": spec["caption_style"],
                    "track": track["id"] if track else None, "speed": speed, "length": round(length, 1), "overlay": overlay}
            if not dry_run:
                render.render(spec, cfg.path("edited") / fname)
                real = media.probe(cfg.path("edited") / fname)["duration"]
                con.execute(
                    """INSERT INTO variants(id, clip_id, file_name, hook_type, caption_style, track_id, overlay_text, speed,
                       start_s, duration_s, spec_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (vid, clip_id, fname, hook["type"], spec["caption_style"], info["track"], overlay, speed,
                     spans[0][0], real, json.dumps({k: v for k, v in spec.items() if k != "words"}), db.now_iso()))
                info["length"] = round(real, 1)
            made.append(info)
        if not dry_run:
            con.execute("UPDATE clips SET status='edited' WHERE id=?", (clip_id,))
    return made
