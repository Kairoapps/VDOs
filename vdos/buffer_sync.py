"""Reconcile ledger posts with Buffer and ingest per-post metrics.

Input is the JSON Claude saved from the Buffer connector's `list_posts` (with `includeMetrics: true`
for metrics). The parser is tolerant of shape: it finds post objects anywhere in the payload and
reads common metric names.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import db

STATUS_MAP = {"sent": "sent", "published": "sent", "error": "error", "failed": "error",
              "scheduled": "scheduled", "sending": "scheduled", "draft": "scheduled", "needs_approval": "scheduled"}

METRIC_ALIASES = {
    "views": ["views", "videoViews", "video_views", "plays", "videoPlays", "impressions"],
    "reach": ["reach", "uniqueViews"],
    "likes": ["likes", "reactions", "favorites"],
    "comments": ["comments", "replies"],
    "shares": ["shares", "reposts", "retweets", "sends"],
    "saves": ["saves", "saved", "bookmarks"],
}


def _iter_posts(obj):
    if isinstance(obj, dict):
        if "id" in obj and ("status" in obj or "dueAt" in obj or "sentAt" in obj):
            yield obj
        for v in obj.values():
            yield from _iter_posts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_posts(v)


def _metric_values(post: dict) -> dict:
    found = {}

    def walk(o):
        if isinstance(o, dict):
            # {"type": "likes", "value": 3} style
            t = o.get("type") or o.get("name") or o.get("metric")
            if isinstance(t, str) and isinstance(o.get("value"), (int, float)):
                found.setdefault(t, o["value"])
            for k, v in o.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    found.setdefault(k, v)
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(post.get("metrics") or post.get("statistics") or post.get("analytics") or {})
    lower = {k.lower(): v for k, v in found.items()}
    out = {}
    for field, names in METRIC_ALIASES.items():
        for n in names:
            if n.lower() in lower:
                out[field] = float(lower[n.lower()])
                break
    return out


def sync(payload: dict) -> dict:
    now = datetime.now(timezone.utc)
    updated, metrics, unknown = 0, 0, 0
    with db.tx() as con:
        for p in _iter_posts(payload):
            row = con.execute("SELECT id, status FROM posts WHERE buffer_post_id=?", (str(p["id"]),)).fetchone()
            if not row:
                unknown += 1
                continue
            status = STATUS_MAP.get(str(p.get("status", "")).lower(), row["status"])
            sent_at = p.get("sentAt") or p.get("publishedAt") or p.get("sent_at")
            err = p.get("error") or (p.get("errors") and json.dumps(p["errors"])[:500]) or None
            if isinstance(err, dict):  # Buffer now returns {"message": ...}
                err = err.get("message") or json.dumps(err)[:500]
            elif err is not None and not isinstance(err, str):
                err = json.dumps(err)[:500]
            link = p.get("externalLink") or p.get("serviceLink") or p.get("link")
            con.execute("""UPDATE posts SET status=?, sent_at=COALESCE(?, sent_at), error=COALESCE(?, error),
                           external_url=COALESCE(?, external_url) WHERE id=?""",
                        (status, sent_at, err if status == "error" else None, link if isinstance(link, str) else None, row["id"]))
            updated += 1
            m = _metric_values(p)
            if m and (sent_at or status == "sent"):
                sent = datetime.fromisoformat((sent_at or now.isoformat()).replace("Z", "+00:00"))
                age = (now - sent).total_seconds() / 86400
                con.execute("""INSERT OR REPLACE INTO metrics(post_id, pulled_at, age_days, views, reach, likes, comments, shares, saves, raw_json)
                               VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (row["id"], now.isoformat(timespec="seconds"), round(age, 2), m.get("views"), m.get("reach"),
                             m.get("likes"), m.get("comments"), m.get("shares"), m.get("saves"),
                             json.dumps(p.get("metrics"))[:4000]))
                metrics += 1
    return {"posts_updated": updated, "metric_snapshots": metrics, "unknown_buffer_posts": unknown}


def mark_deleted(buffer_post_ids: list[str]) -> int:
    with db.tx() as con:
        cur = con.executemany("UPDATE posts SET status='deleted' WHERE buffer_post_id=? AND status='scheduled'",
                              [(i,) for i in buffer_post_ids])
        return cur.rowcount
