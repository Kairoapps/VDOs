"""Daily planning: choose clips/variants, times and hashtag sets for the day's slots.

`plan()` returns a JSON-able plan that Claude turns into Buffer posts (writing the captions),
then `record()` stores what was actually created.
"""
from __future__ import annotations

import itertools
import json
import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import config, db, reuse, weights


def _exposure(con, column: str) -> dict[str, int]:
    return {r[column]: r["n"] for r in con.execute(f"SELECT {column}, COUNT(*) n FROM slots GROUP BY {column}")}


def active_experiments(cfg=None) -> list[str]:
    a = (cfg or config.load())["experiments"].get("active", [])
    if isinstance(a, str):
        a = [] if a == "none" else [a]
    return list(a)


def _mins(a: str) -> int:
    return int(a[:2]) * 60 + int(a[3:])


def _pick_times(con, n: int, rng) -> list[str]:
    cfg = config.load()
    exp = cfg["experiments"]
    min_gap = cfg["posting"]["min_gap_hours"] * 60
    if "time_slot" in active_experiments(cfg):
        # every set of n arms that are min_gap apart; take the least-exposed set (random tie-break)
        arms = sorted(exp["time_slot"]["arms"], key=_mins)
        seen = _exposure(con, "time_slot")
        combos = [c for c in itertools.combinations(arms, n)
                  if all(_mins(b) - _mins(a) >= min_gap for a, b in zip(c, c[1:]))]
        if combos:
            best = min(combos, key=lambda c: (sum(seen.get(a, 0) for a in c), max(seen.get(a, 0) for a in c), rng.random()))
            return list(best)
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


def _pick_hashtags(con, rng, today: dict[str, int] | None = None) -> str:
    cfg = config.load()
    exp = cfg["experiments"]
    sets = list(exp["hashtag_set"]["arms"])
    if "hashtag_set" in active_experiments(cfg):
        seen = _exposure(con, "hashtag_set")
        today = today or {}
        rng.shuffle(sets)
        return min(sets, key=lambda s: seen.get(s, 0) + today.get(s, 0))
    w = weights.get(con, "hashtag_set")
    return max(w, key=w.get) if w else exp["hashtag_set"]["default"]


def _youtube_slots(d: date, times: list[str], cap: int) -> set[str]:
    """Which of the day's slots also go to YouTube (Buffer allows 2/day). Rotates daily so every
    time of day gets YouTube posts."""
    if cap >= len(times):
        return set(times)
    patterns = [p for p in itertools.combinations(range(len(times)), cap)]
    spread = [p for p in patterns if all(b - a >= 2 for a, b in zip(p, p[1:]))] or patterns
    return {times[i] for i in spread[d.toordinal() % len(spread)]}


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
        pl = cfg["posting"]["platforms"]
        cap = cfg["posting"].get("platform_daily_max", {})
        yt_today = con.execute("""SELECT COUNT(*) c FROM posts p JOIN slots s ON s.id=p.slot_id
                                  WHERE p.platform='youtube' AND substr(s.scheduled_at,1,10)=?""", (d.isoformat(),)).fetchone()["c"]
        yt_times = _youtube_slots(d, times, max(0, cap.get("youtube", 99) - yt_today)) if "youtube" in pl else set()
        tags_today: dict[str, int] = {}
        pcfg = cfg.get("post_captions") or {}
        for t in times:
            pool = [r for r in avail if r["id"] not in used]
            if not pool:
                break
            # weight: topic x format performance, evergreen boost, fresher clips slightly favored
            tf = weights.get(con, "topic_format")
            mean = sum(tf.values()) / len(tf) if tf else 1.0
            aw = weights.get(con, "angle")
            amean = sum(aw.values()) / len(aw) if aw else 1.0
            ws = [max(0.05, tf.get(f"{r['topic']}|{r['format']}", mean)) * (1.5 if r["evergreen"] else 1.0)
                  * (1.2 if r["committed"] == 0 else 1.0) * max(0.2, aw.get(r.get("angle") or "challenge", amean) / amean)
                  for r in pool]
            clip = rng.choices(pool, weights=ws, k=1)[0]
            used.add(clip["id"])
            v = con.execute(
                """SELECT v.*, (SELECT COUNT(*) FROM slots s WHERE s.variant_id=v.id) n FROM variants v
                   WHERE v.clip_id=? AND v.active=1 ORDER BY n, v.id""", (clip["id"],)).fetchone()
            hs = _pick_hashtags(con, rng, tags_today)
            tags_today[hs] = tags_today.get(hs, 0) + 1
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
                "angle": clip.get("angle") or "challenge",
                "platforms": [p for p in pl if p != "youtube" or t in yt_times],
                "post_caption_style": weights.choose(con, "post_caption_style", pcfg.get("styles", ["hook_cta"]), rng=rng),
                "post_emoji": weights.choose(con, "post_emoji", pcfg.get("emojis", ["1"]), rng=rng),
                "cta": v["cta_mode"], "cta_text": v["cta_text"],
            })
        inv = reuse.inventory(con)
    return {"date": d.isoformat(), "slots": picks, "shortfall": n - len(picks), "inventory": inv,
            "platforms": cfg["posting"]["platforms"]}


def record(payload: dict) -> int:
    """payload: {"slots":[{"variant_id","scheduled_at","time_slot","hashtag_set","post_caption_style","post_emoji",
                 "posts":[{"platform","channel_id","buffer_post_id","caption","status"}]}]}"""
    n = 0
    with db.tx() as con:
        for s in payload["slots"]:
            v = con.execute("SELECT clip_id FROM variants WHERE id=?", (s["variant_id"],)).fetchone()
            cur = con.execute("""INSERT INTO slots(variant_id, clip_id, scheduled_at, time_slot, hashtag_set, created_at,
                                 post_caption_style, post_emoji, platforms) VALUES (?,?,?,?,?,?,?,?,?)""",
                              (s["variant_id"], v["clip_id"], s["scheduled_at"], s.get("time_slot"), s.get("hashtag_set"), db.now_iso(),
                               s.get("post_caption_style"), s.get("post_emoji"),
                               ",".join(p["platform"] for p in s.get("posts", [])) or None))
            for p in s.get("posts", []):
                con.execute("INSERT INTO posts(slot_id, platform, channel_id, buffer_post_id, caption, status, error) VALUES (?,?,?,?,?,?,?)",
                            (cur.lastrowid, p["platform"], p.get("channel_id"), p.get("buffer_post_id"), p.get("caption"),
                             p.get("status", "scheduled"), p.get("error")))
                n += 1
    return n
