"""Slideshow (photo carousel) inventory, picking and stats.

Built slideshows live in media/slides/<name>/ (see tools/slides/build.py):
  <name>__NN.jpg      1080x1920 (9:16)  -> TikTok photo post
  4x5/<name>__NN.jpg  1080x1350 (4:5)   -> Instagram carousel, Facebook multi-photo post
Posts are recorded in the `slide_posts` table (separate from video slots so the video analysis stays clean).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import config, db

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
    pool = [n for n in pool if use.get(n, {"uses": 0})["uses"] == fewest]  # unused first
    return rng.choice(pool), note


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
