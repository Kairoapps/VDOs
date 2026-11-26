"""Slideshow (photo carousel) inventory, picking and stats.

Built slideshows live in media/slides/<name>/ (see tools/slides/build.py):
  <name>__NN.jpg      1080x1920 (9:16)  -> TikTok photo post
  4x5/<name>__NN.jpg  1080x1350 (4:5)   -> Instagram carousel, Facebook multi-photo post
Posts are recorded in the `slide_posts` table (separate from video slots so the video analysis stays clean).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from . import config, db, weights

PLATFORM_RATIO = {"tiktok": "9x16", "instagram": "4x5", "facebook": "4x5"}


def _cfg() -> dict:
    return config.load().raw.get("slideshows") or {}


def catalog() -> dict[str, dict[str, list[str]]]:
    """{name: {"9x16": [file names...], "4x5": [...]}} for every built slideshow with both versions."""
    root = config.ROOT / _cfg().get("dir", "media/slides")
    out = {}
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        tall = sorted(f.name for f in d.glob(f"{d.name}__*.jpg"))
        four = sorted(f.name for f in (d / "4x5").glob(f"{d.name}__*.jpg")) if (d / "4x5").exists() else []
        if tall and len(tall) == len(four):
            out[d.name] = {"9x16": tall, "4x5": four}
    return out


def urls(name: str, files: dict[str, list[str]], platform: str) -> list[str]:
    base = _cfg().get("base_url", "").rstrip("/")
    ratio = PLATFORM_RATIO.get(platform, "9x16")
    sub = "" if ratio == "9x16" else "4x5/"
    return [f"{base}/{name}/{sub}{f}" for f in files[ratio]]


def usage(con) -> dict[str, dict]:
    """{name: {"uses": n distinct scheduled times, "last": date|None}} (errors/deletions don't count)."""
    rows = con.execute("""SELECT slideshow, COUNT(DISTINCT scheduled_at) n, MAX(substr(scheduled_at,1,10)) last
                          FROM slide_posts WHERE status NOT IN ('error','deleted') GROUP BY slideshow""").fetchall()
    return {r["slideshow"]: {"uses": r["n"], "last": date.fromisoformat(r["last"]) if r["last"] else None} for r in rows}


def scheduled_on(con, d: date) -> int:
    return con.execute("""SELECT COUNT(DISTINCT scheduled_at) c FROM slide_posts
                          WHERE substr(scheduled_at,1,10)=? AND status NOT IN ('error','deleted')""",
                       (d.isoformat(),)).fetchone()["c"]


def pick(con, d: date, rng) -> tuple[str | None, str]:
    """Choose today's slideshow. Returns (name, note). Never returns None if any slideshow exists."""
    c = _cfg()
    cat = catalog()
    if not cat:
        return None, "no built slideshows in media/slides"
    use = usage(con)
    gap = timedelta(days=int(c.get("min_days_between_uses", 7)))
    cap = int(c.get("max_uses", 3))

    def eligible(n):
        u = use.get(n, {"uses": 0, "last": None})
        return u["uses"] < cap and (u["last"] is None or d - u["last"] >= gap)

    pool = [n for n in cat if eligible(n)]
    note = ""
    if not pool:  # a slideshow is required every day: reuse the least recently used one
        pool = sorted(cat, key=lambda n: (use.get(n, {}).get("last") or date.min, use.get(n, {}).get("uses", 0)))[:1]
        note = "no fresh slideshow left: reused the least recently used one; build more"
    fewest = min(use.get(n, {"uses": 0})["uses"] for n in pool)
    pool = [n for n in pool if use.get(n, {"uses": 0})["uses"] == fewest]  # never-posted first
    if fewest == 0:
        return rng.choice(pool), note
    # reruns: favor slideshows that scored well (weekly review writes the "slide_slideshow" weights)
    w = weights.get(con, "slide_slideshow")
    mean = sum(w.values()) / len(w) if w else 1.0
    return rng.choices(pool, weights=[max(0.05, w.get(n, mean)) for n in pool], k=1)[0], note


def inventory(con, d: date | None = None) -> dict:
    d = d or datetime.now().date()
    c = _cfg()
    cat, use = catalog(), usage(con)
    cap = int(c.get("max_uses", 3))
    fresh = [n for n in cat if use.get(n, {"uses": 0})["uses"] == 0]
    left = sum(max(0, cap - use.get(n, {"uses": 0})["uses"]) for n in cat)
    return {"slideshows": len(cat), "never_posted": len(fresh), "uses_left": left,
            "days_left_fresh": len(fresh) // max(1, int(c.get("per_day", 1)))}


def plan_entry(con, d: date, local: datetime, time_slot: str, rng, hashtag_set: str, hashtags: list[str],
               caption_style: str, emoji: str) -> dict | None:
    name, note = pick(con, d, rng)
    if not name:
        return None
    files = catalog()[name]
    plats = list(_cfg().get("platforms", ["tiktok", "instagram", "facebook"]))
    return {
        "kind": "slideshow", "slideshow": name, "slides": len(files["9x16"]),
        "image_urls": {p: urls(name, files, p) for p in plats},
        "scheduled_at": local.isoformat(), "time_slot": time_slot,
        "hashtag_set": hashtag_set, "hashtags": hashtags,
        "post_caption_style": caption_style, "post_emoji": emoji,
        "platforms": plats, "use_number": usage(con).get(name, {"uses": 0})["uses"] + 1,
        "tiktok_notify_for_music": bool(_cfg().get("tiktok_notify_for_music", False)),
        "note": note,
    }


def record_slot(con, s: dict) -> int:
    n = 0
    for p in s.get("posts", []):
        con.execute("""INSERT INTO slide_posts(slideshow, scheduled_at, time_slot, hashtag_set, post_caption_style, post_emoji,
                       platform, channel_id, buffer_post_id, caption, status, error, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (s["slideshow"], s["scheduled_at"], s.get("time_slot"), s.get("hashtag_set"), s.get("post_caption_style"),
                     s.get("post_emoji"), p["platform"], p.get("channel_id"), p.get("buffer_post_id"), p.get("caption"),
                     p.get("status", "scheduled"), p.get("error"), db.now_iso()))
        n += 1
    return n


def stats(con, days: int = 28) -> dict:
    """Slideshow vs video, per platform: posts and average views/likes/comments/shares/saves (latest snapshot)."""
    since = (datetime.now() - timedelta(days=days)).date().isoformat()
    out = {"slideshow": {}, "video": {}}
    for r in con.execute("""SELECT platform, COUNT(*) n, AVG(views) views, AVG(likes) likes, AVG(comments) comments,
                                   AVG(shares) shares, AVG(saves) saves
                            FROM slide_posts WHERE status='sent' AND substr(scheduled_at,1,10)>=? GROUP BY platform""", (since,)):
        out["slideshow"][r["platform"]] = {k: (round(r[k], 1) if isinstance(r[k], float) else r[k])
                                          for k in ("n", "views", "likes", "comments", "shares", "saves")}
    for r in con.execute("""SELECT p.platform, COUNT(*) n, AVG(m.views) views, AVG(m.likes) likes, AVG(m.comments) comments,
                                   AVG(m.shares) shares, AVG(m.saves) saves
                            FROM posts p JOIN slots s ON s.id=p.slot_id
                            JOIN metrics m ON m.post_id=p.id AND m.pulled_at=(SELECT MAX(pulled_at) FROM metrics WHERE post_id=p.id)
                            WHERE p.status='sent' AND substr(s.scheduled_at,1,10)>=? GROUP BY p.platform""", (since,)):
        out["video"][r["platform"]] = {k: (round(r[k], 1) if isinstance(r[k], float) else r[k])
                                      for k in ("n", "views", "likes", "comments", "shares", "saves")}
    by_show = con.execute("""SELECT slideshow, COUNT(*) n, AVG(views) views FROM slide_posts WHERE status='sent'
                             GROUP BY slideshow ORDER BY views DESC""").fetchall()
    out["by_slideshow"] = [{"slideshow": r["slideshow"], "posts": r["n"], "avg_views": round(r["views"] or 0, 1)} for r in by_show]
    return out


# ---------------------------------------------------------------- weekly review

SLIDE_DIMS = ["slideshow", "kind", "slides", "time_slot", "hashtag_set", "post_caption_style", "post_emoji"]
SLIDE_SCORE = {"views": 0.55, "shares_saves": 0.25, "comments": 0.2}  # no watch time for photo posts


def _pct(values, v):
    if not values:
        return 50.0
    return 100.0 * (sum(1 for x in values if x < v) + 0.5 * sum(1 for x in values if x == v)) / len(values)


def kind(name: str) -> str:
    return "multi_challenge" if name in set(_cfg().get("multi_challenge", [])) else "single_challenge"


def scored(con, days: int = 30) -> list[dict]:
    """One row per slideshow post time (all its platforms), score 0-100 ranked within platform among slideshow posts."""
    cfg = config.load()
    early = cfg["analysis"]["early_age_days"]
    now = datetime.now(timezone.utc)
    lo = (now - timedelta(days=days + cfg["analysis"]["score_age_days"])).isoformat()
    hi = (now - timedelta(days=early)).isoformat()
    rows = [dict(r) for r in con.execute("""SELECT * FROM slide_posts WHERE status='sent' AND views IS NOT NULL
                                            AND scheduled_at >= ? AND scheduled_at <= ?""", (lo, hi))]
    cat = catalog()
    by_plat = defaultdict(list)
    for r in rows:
        v = r["views"] or 0
        r["ss_rate"] = ((r["shares"] or 0) + (r["saves"] or 0)) / v if v else 0
        r["c_rate"] = (r["comments"] or 0) / v if v else 0
        by_plat[r["platform"]].append(r)
    for rs in by_plat.values():
        vs, ss, cs = [r["views"] for r in rs], [r["ss_rate"] for r in rs], [r["c_rate"] for r in rs]
        for r in rs:
            r["score"] = (SLIDE_SCORE["views"] * _pct(vs, r["views"]) + SLIDE_SCORE["shares_saves"] * _pct(ss, r["ss_rate"])
                          + SLIDE_SCORE["comments"] * _pct(cs, r["c_rate"]))
    groups = defaultdict(list)
    for r in rows:
        groups[(r["slideshow"], r["scheduled_at"])].append(r)
    out = []
    for (name, at), rs in groups.items():
        r0 = rs[0]
        out.append({"slideshow": name, "scheduled_at": at, "score": statistics.mean(r["score"] for r in rs),
                    "kind": kind(name), "slides": f"{len(cat.get(name, {}).get('9x16', []))} slides",
                    "time_slot": r0["time_slot"] or "none", "hashtag_set": r0["hashtag_set"] or "none",
                    "post_caption_style": r0["post_caption_style"] or "none", "post_emoji": r0["post_emoji"] or "none",
                    "views": {r["platform"]: r["views"] for r in rs}, "total_views": sum(r["views"] or 0 for r in rs),
                    "comments": sum(r["comments"] or 0 for r in rs), "likes": sum(r["likes"] or 0 for r in rs),
                    "shares_saves": sum((r["shares"] or 0) + (r["saves"] or 0) for r in rs),
                    "urls": {r["platform"]: r["external_url"] for r in rs if r.get("external_url")}})
    return out


def rank(items: list[dict]) -> dict[str, list[dict]]:
    min_n = config.load()["analysis"]["min_posts_per_value"]
    res = {}
    for dim in SLIDE_DIMS:
        g = defaultdict(list)
        for s in items:
            g[s[dim]].append(s["score"])
        rows = [{"value": k, "n": len(v), "median": round(statistics.median(v), 1), "enough": len(v) >= min_n} for k, v in g.items()]
        rows.sort(key=lambda r: (not r["enough"], -r["median"]))
        res[dim] = rows
    return res


def vs_video(con, days: int = 7) -> dict:
    """Per platform: slideshow vs video posts from the last `days` days that are at least early_age_days old.
    Medians of latest views / likes / comments / shares+saves, plus engagement per 1k views."""
    cfg = config.load()
    now = datetime.now(timezone.utc)
    lo = (now - timedelta(days=days)).isoformat()
    hi = (now - timedelta(days=cfg["analysis"]["early_age_days"])).isoformat()
    srows = con.execute("""SELECT platform, views, likes, comments, COALESCE(shares,0)+COALESCE(saves,0) ss FROM slide_posts
                           WHERE status='sent' AND views IS NOT NULL AND scheduled_at BETWEEN ? AND ?""", (lo, hi)).fetchall()
    vrows = con.execute("""SELECT p.platform, m.views, m.likes, m.comments, COALESCE(m.shares,0)+COALESCE(m.saves,0) ss
                           FROM posts p JOIN slots s ON s.id=p.slot_id
                           JOIN metrics m ON m.post_id=p.id AND m.pulled_at=(SELECT MAX(pulled_at) FROM metrics WHERE post_id=p.id)
                           WHERE p.status='sent' AND p.platform IN ('tiktok','instagram','facebook')
                             AND s.scheduled_at BETWEEN ? AND ?""", (lo, hi)).fetchall()

    def summ(rows):
        if not rows:
            return None
        v = [r["views"] or 0 for r in rows]
        eng = sum((r["likes"] or 0) + (r["comments"] or 0) + r["ss"] for r in rows)
        return {"posts": len(rows), "median_views": round(statistics.median(v)), "avg_views": round(statistics.mean(v)),
                "median_likes": statistics.median([r["likes"] or 0 for r in rows]),
                "comments": sum(r["comments"] or 0 for r in rows), "shares_saves": sum(r["ss"] for r in rows),
                "eng_per_1k": round(1000 * eng / sum(v), 1) if sum(v) else 0}

    out = {}
    for plat in ("tiktok", "instagram", "facebook"):
        s = summ([r for r in srows if r["platform"] == plat])
        v = summ([r for r in vrows if r["platform"] == plat])
        verdict = None
        if s and v and s["posts"] >= 3 and v["posts"] >= 3:
            ratio = s["median_views"] / v["median_views"] if v["median_views"] else None
            if ratio is not None:
                verdict = ("slideshows ahead" if ratio >= 1.15 else "videos ahead" if ratio <= 0.87 else "about even") + f" ({ratio:.2f}x views)"
        out[plat] = {"slideshow": s, "video": v, "verdict": verdict or "not enough posts yet (3+ of each)"}
    return out


def update_weights(con, ranking: dict) -> None:
    """Store slideshow rankings as weights with a slide_ prefix so they never mix with the video tests."""
    cfg = config.load()
    exploit = cfg["analysis"]["exploit_share"]
    now = db.now_iso()
    for dim, rows in ranking.items():
        if not rows:
            continue
        qual = [r for r in rows if r["enough"]]
        denom = sum(max(1.0, r["median"]) ** 2 for r in qual)
        for r in rows:
            w = (1 - exploit) / len(rows) if qual else 1.0 / len(rows)
            if qual and r["enough"]:
                w += exploit * max(1.0, r["median"]) ** 2 / denom
            con.execute("""INSERT INTO weights(dimension, value, weight, median_score, n, updated_at) VALUES (?,?,?,?,?,?)
                           ON CONFLICT(dimension, value) DO UPDATE SET weight=excluded.weight, median_score=excluded.median_score,
                           n=excluded.n, updated_at=excluded.updated_at""",
                        (f"slide_{dim}", str(r["value"]), round(w, 4), r["median"], r["n"], now))


def weekly(con) -> dict:
    """Everything the weekly report says about slideshows."""
    items = scored(con)
    ranking = rank(items)
    update_weights(con, ranking)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    week = sorted([s for s in items if s["scheduled_at"] >= week_ago], key=lambda s: -s["score"])
    posted = con.execute("""SELECT platform, status, COUNT(*) n FROM slide_posts WHERE scheduled_at >= ?
                            GROUP BY platform, status""", (week_ago,)).fetchall()
    inv = inventory(con)
    use = usage(con)
    never = [n for n in catalog() if n not in use]
    return {"n_scored": len(items), "ranking": ranking, "vs_video": vs_video(con, 7), "vs_video_30d": vs_video(con, 30),
            "best_week": week[:3], "worst_week": week[-3:][::-1] if len(week) > 3 else [],
            "posted_week": [dict(r) for r in posted], "inventory": inv, "never_posted": never,
            "build_more": inv["days_left_fresh"] < 7}
