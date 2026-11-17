"""Weekly analysis: score posts, rank attributes, update weights, mark evergreen clips, write report."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import config, db, reuse

DIMENSIONS = ["topic_format", "topic", "format", "hook_type", "caption_style", "caption_text", "music_mood", "track",
              "sfx", "length_bucket", "time_slot", "hashtag_set"]


def _pct(values: list[float], v: float) -> float:
    if not values:
        return 50.0
    below = sum(1 for x in values if x < v)
    equal = sum(1 for x in values if x == v)
    return 100.0 * (below + 0.5 * equal) / len(values)


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
        """SELECT p.id, p.platform, p.slot_id, s.time_slot, s.hashtag_set, s.scheduled_at, s.variant_id,
                  v.clip_id, v.hook_type, v.caption_style, v.caption_text, v.sfx_ids, v.track_id, v.duration_s, c.topic, c.format, t.mood
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
        per_post[p["id"]] = dict(p) | {"views": views, "ss_rate": ss, "age": m["age_days"],
                                       "likes": m["likes"], "comments": m["comments"], "shares": m["shares"], "saves": m["saves"]}
    by_platform = defaultdict(list)
    for r in per_post.values():
        by_platform[r["platform"]].append(r)
    for plat, rows in by_platform.items():
        vs = [r["views"] for r in rows]
        sr = [r["ss_rate"] for r in rows]
        for r in rows:
            r["score"] = 0.7 * _pct(vs, r["views"]) + 0.3 * _pct(sr, r["ss_rate"])
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
            "topic": r0["topic"], "format": r0["format"], "topic_format": f"{r0['topic']}|{r0['format']}",
            "hook_type": r0["hook_type"], "caption_style": r0["caption_style"] or "none",
            "caption_text": r0["caption_text"] or "none", "sfx": r0["sfx_ids"] or "none",
            "music_mood": r0["mood"] or "none", "track": r0["track_id"] or "none",
            "length_bucket": _length_bucket(r0["duration_s"]), "time_slot": r0["time_slot"], "hashtag_set": r0["hashtag_set"],
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


def experiment_status(slots: list[dict]) -> dict:
    cfg = config.load()
    exp = cfg["experiments"]
    var = exp["active"]
    if var not in ("time_slot", "hashtag_set"):
        return {"active": "none"}
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
            "recommendation": (f"Enough data: lock in {leader['arm']} and switch the experiment to the next variable."
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
        posts_url = {r["buffer_post_id"]: r["external_url"] for r in con.execute("SELECT buffer_post_id, external_url FROM posts")}
    tf = [r for r in ranking["topic_format"] if r["enough"]]
    shot_list = [r["value"].replace("|", " × ") for r in tf[:3]] or [r["value"].replace("|", " × ") for r in ranking["topic_format"][:3]]
    result = {
        "generated_at": db.now_iso(), "n_scored_slots": len(slots), "ranking": ranking,
        "experiment": experiment_status(slots), "evergreen_new": evergreen, "retired_now": retired,
        "retired_this_week": retired_week, "inventory": inv, "clips": clips,
        "top5": recent[:5], "bottom5": recent[-5:][::-1] if len(recent) > 5 else [],
        "week_posts": [dict(r) for r in week_posts], "shot_list": shot_list,
    }
    if write:
        out = cfg.path("reports")
        stamp = datetime.now().strftime("%Y-%m-%d")
        (out / f"weekly-{stamp}.json").write_text(json.dumps(result, indent=1, default=str))
        (out / f"weekly-{stamp}.md").write_text(report_md(result))
    return result


def report_md(r: dict) -> str:
    inv = r["inventory"]
    L = [f"# Weekly report — {r['generated_at'][:10]}", "",
         f"**Inventory:** {inv['days']} days of posts left ({inv['level']}), {inv['active_clips']} active clips.",
         f"**Scored slots (30d):** {r['n_scored_slots']}", ""]
    if r["shot_list"]:
        L += ["## Record more like this", *[f"- {s}" for s in r["shot_list"]],
              f"- Need about {inv['clips_needed']} new clips" if inv["clips_needed"] else "", ""]
    L += ["## What's working (median score 0–100; * = not enough data yet)"]
    for dim in ["topic_format", "format", "hook_type", "caption_style", "music_mood", "length_bucket", "time_slot", "hashtag_set"]:
        rows = r["ranking"].get(dim, [])
        if rows:
            L.append(f"- **{dim}:** " + ", ".join(f"{x['value']} {x['median']}{'' if x['enough'] else '*'} (n={x['n']})" for x in rows[:6]))
    e = r["experiment"]
    L += ["", "## Experiment", f"- Testing **{e.get('active')}**. {e.get('recommendation', '')}"]
    for a in e.get("arms", []):
        L.append(f"  - {a['arm']}: median {a['median']} (n={a['n']})")
    L += ["", "## Top posts this week"]
    for s in r["top5"]:
        L.append(f"- {s['variant_id']} ({s['topic']} × {s['format']}, {s['hook_type']}, {s['caption_style']}, {s['music_mood']}) — score {s['score']:.0f}, views {s['views']}")
    if r["evergreen_new"]:
        L += ["", "## Promoted to evergreen", *[f"- {c}" for c in r["evergreen_new"]]]
    if r["retired_this_week"]:
        L += ["", "## Retired this week", *[f"- {x['clip']} ({x.get('topic')})" for x in r["retired_this_week"]]]
    return "\n".join(x for x in L if x is not None) + "\n"
