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
  "alarm_at": 6.0,                      # optional: source second the alarm starts ringing (silent before it)
  "angle": "challenge",                 # challenge | sus | multi_challenge (content angle, ranked weekly)
  "unusable": false
}
"""
from __future__ import annotations

import json
import random
import secrets
from datetime import datetime, timedelta, timezone

from . import config, db, labels, media, render, weights
from .captions import PREMISE_STYLES

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


def _speed_for(raw_len: float, vcfg: dict, override: float | None, level: str) -> float:
    """Longer cuts get faster (up to 1.5x); `level` (base/faster/fastest) picks within the cut's length tier.
    edit.json "speed" overrides."""
    lo, hi = vcfg.get("speed_min", 1.0), vcfg.get("speed_max", 1.5)
    if override:
        return round(min(hi, max(lo, float(override))), 2)
    levels = vcfg.get("speed_levels", ["base", "faster", "fastest"])
    tier = next((opts for limit, opts in vcfg.get("speed_tiers", [[9999, [1.0]]]) if raw_len <= limit), [1.0])
    i = min(levels.index(level) if level in levels else 0, len(tier) - 1)
    return round(min(hi, max(lo, float(tier[i]))), 2)


def _out_time(spans: list, speed: float, src_t: float | None) -> float:
    """Map a source time onto the edited video's timeline (end of video if None or cut out)."""
    total = sum(b - a for a, b in spans) / speed
    if src_t is None:
        return total
    acc = 0.0
    for a, b in spans:
        if a <= src_t <= b:
            return (acc + src_t - a) / speed
        if src_t < a:
            return acc / speed
        acc += b - a
    return total


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
    tr = json.loads((wd / "transcript.json").read_text()) if (wd / "transcript.json").exists() else {"words": [], "segments": []}

    made = []
    with db.tx() as con:
        clip = con.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
        if edit.get("unusable"):
            con.execute("UPDATE clips SET status='unusable' WHERE id=?", (clip_id,))
            return []
        con.execute("UPDATE clips SET topic=?, format=?, angle=? WHERE id=?",
                    (edit.get("topic") or clip["topic"], edit.get("format") or "pov", labels.angle_of(edit), clip_id))
        existing = con.execute("SELECT COUNT(*) c FROM variants WHERE clip_id=?", (clip_id,)).fetchone()["c"]
        siblings = con.execute("SELECT caption_style, track_id, hook_type FROM variants WHERE clip_id=? AND active=1",
                               (clip_id,)).fetchall()
        used_styles = {s["caption_style"] for s in siblings}
        used_tracks = {s["track_id"] for s in siblings}
        hooks = edit.get("hooks") or [{"type": "mid_action", "start": edit["keep"][0][0]}]
        if edit.get("alarm_at") is not None:  # never cut the alarm going off: no opening may start after it
            k0 = edit["keep"][0][0]
            hooks = [dict(h, start=k0) if float(h.get("start", k0)) > float(edit["alarm_at"]) else h for h in hooks]
        moods = edit.get("moods", ["any"])
        tracks = _eligible_tracks(con, moods, cfg["reuse"]["music_min_days_between"]) if moods else []
        used_hooks = {(v["hook_type"], v["start_s"]) for v in con.execute(
            "SELECT hook_type, start_s FROM variants WHERE clip_id=? AND active=1", (clip_id,))}
        # Premise captions (one line on screen the whole clip) for clips without useful speech.
        premises = edit.get("premise") or []
        if isinstance(premises, (str, dict)):
            premises = [premises]
        # each premise is {"style": "gotta"|"pov"|"crashing_out"|..., "text": "..."} (a bare string = style "plain")
        premises = [p if isinstance(p, dict) else {"style": "plain", "text": p} for p in premises]
        use_premise = bool(premises) and not tr["words"]
        caption_options = list(PREMISE_STYLES) if use_premise else vcfg["caption_styles"]
        used_texts = {s["caption_text"] for s in con.execute(
            "SELECT caption_text FROM variants WHERE clip_id=? AND active=1", (clip_id,))}
        bed_cat = (edit.get("bed") or {}).get("category", "alarm") if (edit.get("dismiss_at") or edit.get("bed")) else None
        bed_rows = con.execute("SELECT * FROM sfx WHERE category=? ORDER BY id", (bed_cat,)).fetchall() if bed_cat else []
        used_beds = {s["sfx_ids"].split(",")[0] for s in con.execute(
            "SELECT sfx_ids FROM variants WHERE clip_id=? AND active=1 AND sfx_ids IS NOT NULL", (clip_id,))}
        sib_more = con.execute("SELECT speed_level, cta_mode FROM variants WHERE clip_id=? AND active=1", (clip_id,)).fetchall()
        used_levels = {s["speed_level"] for s in sib_more if s["speed_level"]}
        used_ctas = {s["cta_mode"] for s in sib_more if s["cta_mode"]}
        ccfg = cfg.get("cta") or {}
        cta_modes = ccfg.get("modes", ["none"])
        speed_levels = vcfg.get("speed_levels", ["base", "faster", "fastest"])
        sfx_plan = edit.get("sfx") or []
        used_sfx: set[str] = set()
        src_path = cfg.clip_path(clip["file_name"])
        src_lufs = media.loudness(src_path) if clip["has_audio"] and not dry_run else None

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
            style = weights.choose(con, "caption_style", caption_options, exclude=used_styles, rng=rng)
            used_styles.add(style)
            if len(used_styles & set(caption_options)) >= len(caption_options):
                used_styles.clear()
            caption_text, title_style = None, None
            if use_premise:
                fresh_t = [p for p in premises if p["text"] not in used_texts]
                if fresh_t:  # weighted by how each title style (then emoji count) has performed
                    ts = weights.choose(con, "title_style", sorted({p["style"] for p in fresh_t}), rng=rng)
                    same = [p for p in fresh_t if p["style"] == ts]
                    eb = weights.choose(con, "title_emoji", sorted({labels.emoji_bucket(p["text"]) for p in same}), rng=rng)
                    pick_p = next(p for p in same if labels.emoji_bucket(p["text"]) == eb)
                else:
                    pick_p = premises[(existing + i) % len(premises)]
                caption_text, title_style = pick_p["text"], pick_p["style"]
                used_texts.add(caption_text)
            sfx_list, sfx_ids = [], []
            bed = None
            if bed_rows:
                pool = [x for x in bed_rows if x["id"] not in used_beds] or bed_rows
                # weighted by how each sound type, then each sound, has performed
                st = weights.choose(con, "sound_type", sorted({labels.sound_type(x["id"]) for x in pool}), rng=rng)
                pool = [x for x in pool if labels.sound_type(x["id"]) == st]
                bid = weights.choose(con, "sound", [x["id"] for x in pool], rng=rng)
                b = next(x for x in pool if x["id"] == bid)
                used_beds.add(b["id"])
                sfx_ids.append(b["id"])
                bed = {"path": str(cfg.path("sfx") / b["id"]), "lufs": b["lufs"], "dur": b["duration_s"],
                       "dismiss_src": edit.get("dismiss_at"), "alarm_src": edit.get("alarm_at")}
            for s in sfx_plan:
                rows = con.execute("SELECT * FROM sfx WHERE category=? ORDER BY id", (s.get("category", "alarm"),)).fetchall()
                if not rows:
                    continue
                pool = [x for x in rows if x["id"] not in used_sfx] or rows
                pick = rng.choice(pool)
                used_sfx.add(pick["id"])
                sfx_ids.append(pick["id"])
                sfx_list.append({"path": str(cfg.path("sfx") / pick["id"]), "lufs": pick["lufs"],
                                 "at": s.get("at", 0), "dur": min(float(s.get("dur", 3)), pick["duration_s"] or 3),
                                 "gain_db": s.get("gain_db", 0)})
            track = None
            if tracks:
                pool = [t for t in tracks if t["id"] not in used_tracks] or tracks
                mood = weights.choose(con, "music_mood", sorted({t["mood"] for t in pool}), rng=rng)
                tid = weights.choose(con, "track", [t["id"] for t in pool if t["mood"] == mood], rng=rng)
                track = next(t for t in pool if t["id"] == tid)
                used_tracks.add(track["id"])
            start = float(hook.get("start", 0))
            raw_len = sum(b - a for a, b in _spans_from(edit["keep"], start, 10_000))  # cut length at 1x
            level = weights.choose(con, "speed_level", speed_levels, exclude=used_levels, rng=rng)
            used_levels.add(level)
            if used_levels >= set(speed_levels):
                used_levels.clear()
            speed = _speed_for(raw_len, vcfg, edit.get("speed"), level)
            if edit.get("speed"):
                level = "fixed"
            cta_mode = weights.choose(con, "cta_mode", cta_modes, exclude=used_ctas, rng=rng)
            used_ctas.add(cta_mode)
            if used_ctas >= set(cta_modes):
                used_ctas.clear()
            cta_text = (weights.choose(con, "cta_text", ccfg.get("texts", []), rng=rng)
                        if cta_mode != "none" and ccfg.get("texts") else None)
            spans = _spans_from(edit["keep"], start, rcfg["max_len"] * speed)
            length = sum(b - a for a, b in spans) / speed
            if length < min(rcfg["min_len"], clip["duration_s"] * 0.8):
                raw_len = sum(b - a for a, b in _spans_from(edit["keep"], edit["keep"][0][0], 10_000))
                speed = _speed_for(raw_len, vcfg, edit.get("speed"), level if level != "fixed" else "base")
                spans = _spans_from(edit["keep"], edit["keep"][0][0], rcfg["max_len"] * speed)
                length = sum(b - a for a, b in spans) / speed
            overlay = hook.get("text") if hook["type"] in ("bold_claim", "question", "text_overlay") and not use_premise else None
            vid = f"{clip_id}__v{existing + i + 1}"
            fname = f"{clip_id}__v{existing + i + 1}__{secrets.token_hex(3)}.mp4"
            spec = {
                "src": str(src_path), "segments": spans, "speed": speed,
                "caption_style": style if (tr["words"] or use_premise) else None, "hook_text": overlay,
                "words": tr["words"], "caption_text": caption_text, "sfx": sfx_list, "src_lufs": src_lufs,
                "bed": dict(bed, end=_out_time(spans, speed, bed["dismiss_src"]),
                            start=_out_time(spans, speed, bed["alarm_src"]) if bed.get("alarm_src") is not None else 0.0) if bed else None,
                "has_audio": bool(clip["has_audio"]),
                "track": str(cfg.path("music") / track["id"]) if track else None,
                "track_lufs": track["lufs"] if track else None,
                "track_offset": round(rng.uniform(0, max(0, (track["duration_s"] or 0) - length - 2)), 1) if track else 0,
                "reframe": rcfg["reframe"],
                "cta": {"text": cta_text, "mode": cta_mode,
                        "start": (0.0 if cta_mode == "always" else
                                  max(0.0, min(_out_time(spans, speed, edit.get("dismiss_at")) if edit.get("dismiss_at") else length,
                                               length - float(ccfg.get("end_min_seconds", 3.0)))))}
                if cta_text else None,
            }
            info = {"id": vid, "file": fname, "hook_type": hook["type"], "caption_style": spec["caption_style"],
                    "caption_text": caption_text, "title_style": title_style, "sfx": sfx_ids,
                    "track": track["id"] if track else None, "speed": speed, "speed_level": level,
                    "cta": cta_mode, "cta_text": cta_text, "title_emoji": labels.emoji_bucket(caption_text) if caption_text else None,
                    "sound_type": labels.sound_type(sfx_ids[0]) if sfx_ids else None,
                    "length": round(length, 1), "overlay": overlay}
            if not dry_run:
                render.render(spec, cfg.path("edited") / fname)
                real = media.probe(cfg.path("edited") / fname)["duration"]
                con.execute(
                    """INSERT INTO variants(id, clip_id, file_name, hook_type, caption_style, track_id, overlay_text, speed,
                       start_s, duration_s, spec_json, created_at, sfx_ids, caption_text, title_style,
                       sound_id, sound_type, speed_level, cta_mode, cta_text, title_emoji)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (vid, clip_id, fname, hook["type"], spec["caption_style"], info["track"], overlay, speed,
                     spans[0][0], real, json.dumps({k: v for k, v in spec.items() if k != "words"}), db.now_iso(),
                     ",".join(sfx_ids) or None, caption_text, title_style,
                     sfx_ids[0] if sfx_ids else (info["track"] or None),
                     info["sound_type"] or (labels.sound_type(info["track"]) if info["track"] else None),
                     level, cta_mode, cta_text, info["title_emoji"]))
                info["length"] = round(real, 1)
            made.append(info)
        if not dry_run:
            con.execute("UPDATE clips SET status='edited' WHERE id=?", (clip_id,))
    return made
