"""Daily planning: choose clips/variants, times and hashtag sets for the day's slots.

`plan()` returns a JSON-able plan that Claude turns into Buffer posts (writing the captions),
then `record()` stores what was actually created.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import config, db, reuse, weights


def _exposure(con, column: str) -> dict[str, int]:
    return {r[column]: r["n"] for r in con.execute(f"SELECT {column}, COUNT(*) n FROM slots GROUP BY {column}")}


def _pick_times(con, n: int, rng) -> list[str]:
    cfg = config.load()
    exp = cfg["experiments"]
    min_gap = cfg["posting"]["min_gap_hours"] * 60
    if exp["active"] == "time_slot":
        arms = list(exp["time_slot"]["arms"])
        seen = _exposure(con, "time_slot")
        rng.shuffle(arms)
        arms.sort(key=lambda a: seen.get(a, 0))  # least-exposed first
        chosen = []
        for a in arms:
            m = int(a[:2]) * 60 + int(a[3:])
            if all(abs(m - (int(c[:2]) * 60 + int(c[3:]))) >= min_gap for c in chosen):
                chosen.append(a)
            if len(chosen) == n:
                break
        if len(chosen) == n:
            return sorted(chosen)
    # no experiment (or not enough spaced arms): exploit the weighted best slots, else defaults
    w = weights.get(con, "time_slot")
    if w:
        ranked = sorted(w, key=lambda k: -w[k])
        chosen = []
        for a in ranked + cfg["posting"]["default_slots"]:
            m = int(a[:2]) * 60 + int(a[3:])
            if a not in chosen and all(abs(m - (int(c[:2]) * 60 + int(c[3:]))) >= min_gap for c in chosen):
                chosen.append(a)
            if len(chosen) == n:
                return sorted(chosen)
    return cfg["posting"]["default_slots"][:n]


def _pick_hashtags(con, rng) -> str:
    cfg = config.load()
    exp = cfg["experiments"]
    sets = list(exp["hashtag_set"]["arms"])
    if exp["active"] == "hashtag_set":
        seen = _exposure(con, "hashtag_set")
        rng.shuffle(sets)
        return min(sets, key=lambda s: seen.get(s, 0))
    w = weights.get(con, "hashtag_set")
    return max(w, key=w.get) if w else exp["hashtag_set"]["default"]


def plan(day: str | None = None, seed: int | None = None) -> dict:
    cfg = config.load()
    tz = ZoneInfo(cfg["posting"]["timezone"])
    rng = random.Random(seed)
    d = date.fromisoformat(day) if day else datetime.now(tz).date()
    n = cfg["posting"]["posts_per_day"]
    base = cfg.public_base_url
    with db.tx() as con:
        already = con.execute("SELECT COUNT(*) c FROM slots WHERE substr(scheduled_at,1,10)=?", (d.isoformat(),)).fetchone()["c"]
        n = max(0, n - already)
        table = {r["id"]: r for r in reuse.clip_table(con)}
        avail = [r for r in table.values() if r["status"] == "available"]
        times = _pick_times(con, cfg["posting"]["posts_per_day"], rng)[-n:] if n else []
        picks, used = [], set()
        for t in times:
            pool = [r for r in avail if r["id"] not in used]
            if not pool:
                break
            # weight: topic x format performance, evergreen boost, fresher clips slightly favored
            tf = weights.get(con, "topic_format")
            mean = sum(tf.values()) / len(tf) if tf else 1.0
            ws = [max(0.05, tf.get(f"{r['topic']}|{r['format']}", mean)) * (1.5 if r["evergreen"] else 1.0)
                  * (1.2 if r["committed"] == 0 else 1.0) for r in pool]
            clip = rng.choices(pool, weights=ws, k=1)[0]
            used.add(clip["id"])
            v = con.execute(
                """SELECT v.*, (SELECT COUNT(*) FROM slots s WHERE s.variant_id=v.id) n FROM variants v
                   WHERE v.clip_id=? AND v.active=1 ORDER BY n, v.id""", (clip["id"],)).fetchone()
            hs = _pick_hashtags(con, rng)
            local = datetime.combine(d, time(int(t[:2]), int(t[3:])), tzinfo=tz)
            if local < datetime.now(tz) + timedelta(minutes=15):
                used.discard(clip["id"])
                continue  # slot already passed today
            spec = json.loads(v["spec_json"] or "{}")
            wd = cfg.path("work") / clip["id"]
            edit = json.loads((wd / "edit.json").read_text()) if (wd / "edit.json").exists() else {}
            transcript = ""
            if (wd / "transcript.json").exists():
                segs = json.loads((wd / "transcript.json").read_text())["segments"]
                transcript = " ".join(s["text"] for s in segs)[:600]
            picks.append({
                "variant_id": v["id"], "clip_id": clip["id"],
                "video_url": f"{base}/{v['file_name']}" if base else None, "file": v["file_name"],
                "scheduled_at": local.isoformat(), "time_slot": t,
                "hashtag_set": hs, "hashtags": cfg["experiments"]["hashtag_set"]["arms"][hs],
                "topic": clip["topic"], "format": clip["format"], "hook_type": v["hook_type"],
                "overlay_text": v["overlay_text"], "caption_text": v["caption_text"], "duration_s": v["duration_s"],
                "summary": edit.get("summary", ""), "transcript": transcript,
                "use_number": clip["committed"] + 1, "cap": clip["cap"],
            })
        inv = reuse.inventory(con)
    return {"date": d.isoformat(), "slots": picks, "shortfall": n - len(picks), "inventory": inv,
            "platforms": cfg["posting"]["platforms"]}


def record(payload: dict) -> int:
    """payload: {"slots":[{"variant_id","scheduled_at","time_slot","hashtag_set",
                 "posts":[{"platform","channel_id","buffer_post_id","caption","status"}]}]}"""
    n = 0
    with db.tx() as con:
        for s in payload["slots"]:
            v = con.execute("SELECT clip_id FROM variants WHERE id=?", (s["variant_id"],)).fetchone()
            cur = con.execute("INSERT INTO slots(variant_id, clip_id, scheduled_at, time_slot, hashtag_set, created_at) VALUES (?,?,?,?,?,?)",
                              (s["variant_id"], v["clip_id"], s["scheduled_at"], s.get("time_slot"), s.get("hashtag_set"), db.now_iso()))
            for p in s.get("posts", []):
                con.execute("INSERT INTO posts(slot_id, platform, channel_id, buffer_post_id, caption, status, error) VALUES (?,?,?,?,?,?,?)",
                            (cur.lastrowid, p["platform"], p.get("channel_id"), p.get("buffer_post_id"), p.get("caption"),
                             p.get("status", "scheduled"), p.get("error")))
                n += 1
    return n
