"""Weekly analysis: score posts, rank attributes, update weights, mark evergreen clips, write report."""
from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import config, db, labels, reuse, slides
from .scheduler import active_experiments

DIMENSIONS = ["topic_format", "topic", "format", "angle", "hook_type", "caption_style", "title_style", "title_emoji", "caption_text",
              "cta_mode", "cta_text", "cta_color", "music_mood", "track", "sound", "sound_type", "speed_level", "speed", "length_bucket",
              "time_slot", "hashtag_set", "hashtag_count", "post_caption_style", "post_emoji"]
# What the weekly report / push summary lead with.
REPORT_DIMS = ["topic_format", "angle", "title_style", "title_emoji", "cta_mode", "cta_color", "cta_text", "sound_type", "sound", "speed_level", "speed",
               "length_bucket", "time_slot", "hashtag_set", "hashtag_count", "post_caption_style", "post_emoji", "music_mood"]


def _pct(values: list[float], v: float) -> float:
    if not values:
        return 50.0
    below = sum(1 for x in values if x < v)
    equal = sum(1 for x in values if x == v)
    return 100.0 * (below + 0.5 * equal) / len(values)


# Post score (0-100, ranked within its platform): reach, how long people watch, sharing/saving, commenting.
SCORE_WEIGHTS = {"views": 0.4, "watch": 0.3, "shares_saves": 0.15, "comments": 0.15}


def _watch_pct(raw_json: str | None, duration: float | None) -> float | None:
    """Average watch time as a share of the video's length (Buffer: averageTimeWatched, seconds; IG + TikTok only)."""
    if not raw_json or not duration:
        return None
    try:
        for x in json.loads(raw_json) or []:
            if x.get("type") == "averageTimeWatched" and x.get("value") is not None:
                return min(1.5, float(x["value"]) / float(duration))
    except (ValueError, TypeError, AttributeError):
        return None
    return None


def cta_comments(con, days: int = 30) -> list[dict]:
    """Comments per CTA mode / colour / wording (latest metrics of every sent post, scored or not)."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = con.execute(
        """SELECT v.cta_mode, v.cta_color, v.cta_text, p.platform,
                  (SELECT m.comments FROM metrics m WHERE m.post_id=p.id ORDER BY m.pulled_at DESC LIMIT 1) comments,
                  (SELECT m.views FROM metrics m WHERE m.post_id=p.id ORDER BY m.pulled_at DESC LIMIT 1) views
           FROM posts p JOIN slots s ON s.id=p.slot_id JOIN variants v ON v.id=s.variant_id
           WHERE p.status='sent' AND s.scheduled_at >= ?""", (since,)).fetchall()
    out = []
    for key in ("cta_mode", "cta_color", "cta_text"):
        g = defaultdict(lambda: {"posts": 0, "comments": 0.0, "views": 0.0})
        for r in rows:
            k = r[key] or "none"
            g[k]["posts"] += 1
            g[k]["comments"] += r["comments"] or 0
            g[k]["views"] += r["views"] or 0
        for k, v in g.items():
            out.append({"dim": key, "value": k, "posts": v["posts"], "comments": int(v["comments"]),
                        "per_post": round(v["comments"] / v["posts"], 2) if v["posts"] else 0,
                        "per_1k_views": round(1000 * v["comments"] / v["views"], 2) if v["views"] else 0})
    return sorted(out, key=lambda x: (x["dim"], -x["per_1k_views"]))


def hashtag_stats(days: int = 40) -> dict:
    """Every hashtag used in the last ~40 days of Buffer posts (work/buffer/posts-*.json, saved by the sync), scored by
    views percentile within the platform (posts at least 2 days old). Covers posts made before the ledger existed too."""
    cfg = config.load()
    files = sorted((cfg.path("work") / "buffer").glob("posts-*.json"))
    posts = []
    for f in files:
        try:
            d = json.loads(f.read_text())
        except ValueError:
            continue
        posts += [e.get("node", e) for e in d.get("edges", [])]
    now = datetime.now(timezone.utc)
    rows = []
    for p in posts:
        if p.get("status") != "sent" or not p.get("sentAt"):
            continue
        m = {x.get("type"): x.get("value") for x in (p.get("metrics") or []) if isinstance(x, dict)}
        sent = datetime.fromisoformat(p["sentAt"].replace("Z", "+00:00"))
        if (now - sent).days < 2 or m.get("views") is None:
            continue
        tags = sorted({t.lower() for t in re.findall(r"#\w+", p.get("text") or "")})
        rows.append({"platform": p.get("channelService"), "views": float(m["views"]), "comments": m.get("comments") or 0,
                     "tags": tags})
    by = defaultdict(list)
    for r in rows:
        by[r["platform"]].append(r["views"])
    tag_scores, set_scores = defaultdict(list), defaultdict(list)
    for r in rows:
        sc = _pct(by[r["platform"]], r["views"])
        set_scores[" ".join(r["tags"]) or "(no hashtags)"].append((sc, r["views"]))
        for t in r["tags"]:
            tag_scores[t].append((sc, r["views"]))

    def summ(g, min_n):
        out = [{"value": k, "n": len(v), "median": round(statistics.median(x for x, _ in v), 1),
                "avg_views": round(statistics.mean(y for _, y in v)), "enough": len(v) >= 6}
               for k, v in g.items() if len(v) >= min_n]
        return sorted(out, key=lambda r: -r["median"])
    return {"posts": len(rows), "tags": summ(tag_scores, 3), "sets": summ(set_scores, 3)}


def _length_bucket(s: float | None) -> str:
    if s is None:
        return "?"
    return "<15s" if s < 15 else "15-25s" if s < 25 else "25-35s" if s < 35 else "35s+"


def scored_slots(con, days: int = 30) -> list[dict]:
    cfg = config.load()
    target = cfg["analysis"]["score_age_days"]
    early = cfg["analysis"]["early_age_days"]
    since = (datetime.now(timezone.utc) - timedelta(days=days + target)).isoformat()
    posts = con.execute(
        """SELECT p.id, p.platform, p.slot_id, p.external_url, s.time_slot, s.hashtag_set, s.scheduled_at, s.variant_id,
                  s.post_caption_style, s.post_emoji, v.sound_id, v.sound_type, v.speed, v.speed_level, v.cta_mode, v.cta_text, v.cta_color,
                  v.title_emoji, c.angle,
                  v.clip_id, v.hook_type, v.caption_style, v.title_style, v.caption_text, v.sfx_ids, v.track_id, v.duration_s, c.topic, c.format, t.mood
           FROM posts p JOIN slots s ON s.id=p.slot_id JOIN variants v ON v.id=s.variant_id
           JOIN clips c ON c.id=v.clip_id LEFT JOIN tracks t ON t.id=v.track_id
           WHERE p.status='sent' AND s.scheduled_at >= ?""", (since,)).fetchall()
    per_post = {}
    for p in posts:
        snaps = con.execute("SELECT * FROM metrics WHERE post_id=? AND age_days >= ? ORDER BY ABS(age_days - ?) LIMIT 1",
                            (p["id"], early * 0.8, target), ).fetchall()
        if not snaps:
            continue
        m = snaps[0]
        views = m["views"] or 0
        ss = ((m["shares"] or 0) + (m["saves"] or 0)) / views if views else 0
        cr = (m["comments"] or 0) / views if views else 0
        per_post[p["id"]] = dict(p) | {"views": views, "ss_rate": ss, "c_rate": cr, "watch": _watch_pct(m["raw_json"], p["duration_s"]),
                                       "age": m["age_days"], "likes": m["likes"], "comments": m["comments"], "shares": m["shares"],
                                       "saves": m["saves"]}
    by_platform = defaultdict(list)
    for r in per_post.values():
        by_platform[r["platform"]].append(r)
    for plat, rows in by_platform.items():
        vs = [r["views"] for r in rows]
        sr = [r["ss_rate"] for r in rows]
        cr = [r["c_rate"] for r in rows]
        wr = [r["watch"] for r in rows if r["watch"] is not None]
        for r in rows:
            parts = [(SCORE_WEIGHTS["views"], _pct(vs, r["views"])), (SCORE_WEIGHTS["shares_saves"], _pct(sr, r["ss_rate"])),
                     (SCORE_WEIGHTS["comments"], _pct(cr, r["c_rate"]))]
            if r["watch"] is not None and len(wr) > 1:
                parts.append((SCORE_WEIGHTS["watch"], _pct(wr, r["watch"])))
            r["score"] = sum(w * x for w, x in parts) / sum(w for w, _ in parts)
    slots = defaultdict(list)
    for r in per_post.values():
        slots[r["slot_id"]].append(r)
    out = []
    for sid, rows in slots.items():
        r0 = rows[0]
        out.append({
            "slot_id": sid, "variant_id": r0["variant_id"], "clip_id": r0["clip_id"], "scheduled_at": r0["scheduled_at"],
            "score": statistics.mean(r["score"] for r in rows),
            "platform_scores": {r["platform"]: round(r["score"], 1) for r in rows},
            "views": {r["platform"]: r["views"] for r in rows},
            "total_views": sum(r["views"] for r in rows), "comments": sum(r["comments"] or 0 for r in rows),
            "likes": sum(r["likes"] or 0 for r in rows), "shares": sum((r["shares"] or 0) + (r["saves"] or 0) for r in rows),
            "watch": (round(100 * statistics.mean(w), 0) if (w := [r["watch"] for r in rows if r["watch"] is not None]) else None),
            "urls": {r["platform"]: r["external_url"] for r in rows if r.get("external_url")},
            "cta_color": r0["cta_color"] or "none",
            "topic": r0["topic"], "format": r0["format"], "topic_format": f"{r0['topic']}|{r0['format']}",
            "hook_type": r0["hook_type"], "caption_style": r0["caption_style"] or "none",
            "caption_text": r0["caption_text"] or "none", "title_style": r0["title_style"] or "none", "sfx": r0["sfx_ids"] or "none",
            "music_mood": r0["mood"] or "none", "track": r0["track_id"] or "none",
            "length_bucket": _length_bucket(r0["duration_s"]), "time_slot": r0["time_slot"], "hashtag_set": r0["hashtag_set"],
            "hashtag_count": str(len(cfg["experiments"]["hashtag_set"]["arms"].get(r0["hashtag_set"] or "", []))) + " tags",
            "angle": r0["angle"] or "challenge", "title_emoji": r0["title_emoji"] or "none",
            "cta_mode": r0["cta_mode"] or "none", "cta_text": r0["cta_text"] or "none",
            "sound": r0["sound_id"] or "none", "sound_type": r0["sound_type"] or labels.sound_type(r0["sound_id"]),
            "speed_level": r0["speed_level"] or "legacy", "speed": labels.speed_bucket(r0["speed"]),
            "post_caption_style": r0["post_caption_style"] or "legacy", "post_emoji": r0["post_emoji"] or "legacy",
        })
    return out


def rank(slots: list[dict]) -> dict[str, list[dict]]:
    cfg = config.load()
    min_n = cfg["analysis"]["min_posts_per_value"]
    res = {}
    for dim in DIMENSIONS:
        groups = defaultdict(list)
        for s in slots:
            groups[s[dim]].append(s["score"])
        rows = [{"value": k, "n": len(v), "median": round(statistics.median(v), 1),
                 "enough": len(v) >= min_n} for k, v in groups.items()]
        rows.sort(key=lambda r: (not r["enough"], -r["median"]))
        res[dim] = rows
    return res


def update_weights(con, ranking: dict) -> None:
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
            elif qual:
                pass
            con.execute("""INSERT INTO weights(dimension, value, weight, median_score, n, updated_at) VALUES (?,?,?,?,?,?)
                           ON CONFLICT(dimension, value) DO UPDATE SET weight=excluded.weight, median_score=excluded.median_score,
                           n=excluded.n, updated_at=excluded.updated_at""",
                        (dim, r["value"], round(w, 4), r["median"], r["n"], now))
    # map hook/caption/music weights onto the names variants.py uses (same dimension names already)


def mark_evergreen(con, slots: list[dict]) -> list[str]:
    cfg = config.load()
    if len(slots) < 10:
        return []
    by_clip = defaultdict(list)
    for s in slots:
        by_clip[s["clip_id"]].append(s["score"])
    cutoff = sorted((statistics.mean(v) for v in by_clip.values()), reverse=True)[max(0, len(by_clip) // 10 - 1)]
    table = {r["id"]: r for r in reuse.clip_table(con)}
    out = []
    for cid, scores in by_clip.items():
        t = table.get(cid)
        if not t or t["evergreen"] or t["status"] in ("retired", "unusable"):
            continue
        if statistics.mean(scores) >= cutoff and t["committed"] >= t["cap"] - 1:
            con.execute("UPDATE clips SET evergreen=1, reuse_cap=? WHERE id=?", (cfg["reuse"]["evergreen_max_uses"], cid))
            db.log_event(con, "evergreen", {"clip": cid, "score": round(statistics.mean(scores), 1)})
            out.append(cid)
    return out


def experiment_status(slots: list[dict]) -> list[dict]:
    """Status of every rotating experiment (several can run at once)."""
    return [_one_experiment(slots, v) for v in active_experiments() if v in ("time_slot", "hashtag_set")]


def _one_experiment(slots: list[dict], var: str) -> dict:
    cfg = config.load()
    exp = cfg["experiments"]
    arms = exp[var]["arms"]
    arms = list(arms) if isinstance(arms, dict) else arms
    groups = defaultdict(list)
    for s in slots:
        groups[s[var]].append(s["score"])
    min_n = cfg["analysis"]["min_posts_per_value"]
    rows = [{"arm": a, "n": len(groups.get(a, [])),
             "median": round(statistics.median(groups[a]), 1) if groups.get(a) else None} for a in arms]
    ready = all(r["n"] >= min_n for r in rows)
    leader = max((r for r in rows if r["median"] is not None), key=lambda r: r["median"], default=None)
    return {"active": var, "arms": rows, "ready": ready, "leader": leader["arm"] if leader else None,
            "recommendation": (f"Enough data: lock in the winner(s) (leader {leader['arm']}) and take {var} out of experiments.active."
                               if ready and leader else "Keep rotating; not every arm has enough posts yet.")}


def weekly(write: bool = True) -> dict:
    cfg = config.load()
    with db.tx() as con:
        slots = scored_slots(con)
        ranking = rank(slots)
        update_weights(con, ranking)
        evergreen = mark_evergreen(con, slots)
        retired = reuse.retire_exhausted(con)
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        retired_week = [json.loads(e["payload"]) for e in con.execute(
            "SELECT payload FROM events WHERE kind='retired' AND at >= ?", (week_ago,))]
        inv = reuse.inventory(con)
        clips = reuse.clip_table(con)
        recent = sorted([s for s in slots if s["scheduled_at"] >= week_ago], key=lambda s: -s["score"])
        week_posts = con.execute(
            """SELECT p.platform, p.status, COUNT(*) n FROM posts p JOIN slots s ON s.id=p.slot_id
               WHERE s.scheduled_at >= ? GROUP BY p.platform, p.status""", (week_ago,)).fetchall()
        cta_comments_rows = cta_comments(con)
        week_totals = dict(con.execute(
            """SELECT COALESCE(SUM(m.views),0) views, COALESCE(SUM(m.comments),0) comments FROM posts p JOIN slots s ON s.id=p.slot_id
               JOIN metrics m ON m.post_id=p.id AND m.pulled_at=(SELECT MAX(pulled_at) FROM metrics WHERE post_id=p.id)
               WHERE p.status='sent' AND s.scheduled_at >= ?""", (week_ago,)).fetchone())
        posts_url = {r["buffer_post_id"]: r["external_url"] for r in con.execute("SELECT buffer_post_id, external_url FROM posts")}
        slideshow = slides.weekly(con)
    tf = [r for r in ranking["topic_format"] if r["enough"]]
    shot_list = [r["value"].replace("|", " × ") for r in tf[:3]] or [r["value"].replace("|", " × ") for r in ranking["topic_format"][:3]]
    result = {
        "generated_at": db.now_iso(), "n_scored_slots": len(slots), "ranking": ranking,
        "experiment": experiment_status(slots), "evergreen_new": evergreen, "retired_now": retired,
        "retired_this_week": retired_week, "inventory": inv, "clips": clips,
        "top5": recent[:5], "top_week": recent[:6], "bottom5": recent[-5:][::-1] if len(recent) > 5 else [],
        "week_posts": [dict(r) for r in week_posts], "shot_list": shot_list,
        "cta_comments": cta_comments_rows, "hashtags": hashtag_stats(), "score_weights": SCORE_WEIGHTS,
        "week_totals": week_totals, "slideshows": slideshow,
    }
    if write:
        out = cfg.path("reports")
        stamp = datetime.now().strftime("%Y-%m-%d")
        (out / f"weekly-{stamp}.json").write_text(json.dumps(result, indent=1, default=str))
        (out / f"weekly-{stamp}.md").write_text(report_md(result))
    return result


def slides_md(sl: dict | None) -> list[str]:
    """'Slideshows' section of the weekly report: slideshow vs video per platform, what wins among slideshows, inventory."""
    if not sl:
        return []
    L = ["", "## Slideshows (TikTok photo posts, Instagram carousels, Facebook photos)"]
    for label, key in (("Last 7 days", "vs_video"), ("Last 30 days", "vs_video_30d")):
        L.append(f"**Slideshow vs video, {label.lower()}** (posts ≥ 3 days old; median views · engagement per 1k views):")
        for plat, x in sl[key].items():
            s, v = x["slideshow"], x["video"]
            fmt = lambda d: f"{d['median_views']} views · {d['eng_per_1k']}/1k (n={d['posts']})" if d else "no data"
            L.append(f"- {plat}: slideshows {fmt(s)} vs videos {fmt(v)} → **{x['verdict']}**")
    L.append(f"**What wins among slideshows** ({sl['n_scored']} scored; median score 0–100, * = fewer than enough posts):")
    for dim in slides.SLIDE_DIMS:
        rows = sl["ranking"].get(dim, [])
        if rows:
            L.append(f"- **{dim}:** " + ", ".join(f"{x['value']} {x['median']}{'' if x['enough'] else '*'} (n={x['n']})" for x in rows[:6]))
    if sl["best_week"]:
        L.append("**Best this week:** " + "; ".join(f"{x['slideshow']} ({x['time_slot']}) score {x['score']:.0f}, views {x['views']}" for x in sl["best_week"]))
    if sl["worst_week"]:
        L.append("**Worst this week:** " + "; ".join(f"{x['slideshow']} score {x['score']:.0f}, views {x['views']}" for x in sl["worst_week"]))
    fails = sum(x["n"] for x in sl["posted_week"] if x["status"] == "error")
    sent = sum(x["n"] for x in sl["posted_week"] if x["status"] == "sent")
    inv = sl["inventory"]
    L.append(f"**Posted this week:** {sent} slideshow posts sent, {fails} failed.")
    L.append(f"**Inventory:** {inv['slideshows']} slideshows, {inv['never_posted']} never posted (~{inv['days_left_fresh']} days of fresh ones), "
             f"{inv['uses_left']} uses left." + (" **Build more slideshows.**" if sl["build_more"] else ""))
    return L


def report_md(r: dict) -> str:
    inv = r["inventory"]
    L = [f"# Weekly report — {r['generated_at'][:10]}", "",
         f"**Inventory:** {inv['days']} days of posts left ({inv['level']}), {inv['active_clips']} active clips.",
         f"**Scored slots (30d):** {r['n_scored_slots']}", ""]
    if r["shot_list"]:
        L += ["## Record more like this", *[f"- {s}" for s in r["shot_list"]],
              f"- Need about {inv['clips_needed']} new clips" if inv["clips_needed"] else "", ""]
    L += ["## What's working (median score 0–100; * = not enough data yet)"]
    for dim in REPORT_DIMS:
        rows = r["ranking"].get(dim, [])
        if rows:
            L.append(f"- **{dim}:** " + ", ".join(f"{x['value']} {x['median']}{'' if x['enough'] else '*'} (n={x['n']})" for x in rows[:6]))
    L += ["", "## Experiments"]
    for e in r["experiment"] or [{"active": "none"}]:
        L.append(f"- Testing **{e.get('active')}**. {e.get('recommendation', '')}")
        for a in e.get("arms", []):
            L.append(f"  - {a['arm']}: median {a['median']} (n={a['n']})")
    hs = r.get("hashtags") or {}
    if hs.get("tags"):
        L += ["", "## Best hashtags (last 40 days, all Buffer posts)",
              "- Tags: " + ", ".join(f"{x['value']} {x['median']:.0f} (n={x['n']})" for x in hs["tags"][:8]),
              "- Combos: " + "; ".join(f"{x['value']} {x['median']:.0f} (n={x['n']})" for x in hs.get("sets", [])[:4])]
    cc = [x for x in r.get("cta_comments", []) if x["dim"] in ("cta_mode", "cta_color")]
    if cc:
        L += ["", "## CTA comments (30 days)", *[f"- {x['dim']} {x['value']}: {x['comments']} comments on {x['posts']} posts "
                                                 f"({x['per_post']}/post, {x['per_1k_views']}/1k views)" for x in cc]]
    L += slides_md(r.get("slideshows"))
    L += ["", "## Top posts this week"]
    for s in r["top5"]:
        L.append(f"- {s['variant_id']} ({s['topic']} × {s['angle']}, {s['title_style']}, {s['sound_type']}, {s['speed']}, cta {s['cta_mode']}) — score {s['score']:.0f}, views {s['views']}")
    if r["evergreen_new"]:
        L += ["", "## Promoted to evergreen", *[f"- {c}" for c in r["evergreen_new"]]]
    if r["retired_this_week"]:
        L += ["", "## Retired this week", *[f"- {x['clip']} ({x.get('topic')})" for x in r["retired_this_week"]]]
    return "\n".join(x for x in L if x is not None) + "\n"
