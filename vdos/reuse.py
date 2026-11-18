"""Usage tracking, clip status, retirement and inventory.

A "use" = one daily slot of a clip. It counts once any of the slot's platform posts is sent.
Scheduled-but-unsent slots still block the clip for planning (so it isn't double-booked).
"""
from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta, timezone

from . import config, db


def _d(iso: str) -> date:
    return datetime.fromisoformat(iso).date()


def clip_table(con) -> list[dict]:
    cfg = config.load()
    rc = cfg["reuse"]
    today = datetime.now(timezone.utc).date()
    rows = []
    for c in con.execute("SELECT * FROM clips ORDER BY id"):
        slots = con.execute(
            """SELECT s.id, s.scheduled_at,
                      SUM(p.status='sent') sent, SUM(p.status='scheduled') pending, COUNT(p.id) total
               FROM slots s LEFT JOIN posts p ON p.slot_id=s.id WHERE s.clip_id=? GROUP BY s.id""", (c["id"],)).fetchall()
        live = [s for s in slots if (s["sent"] or 0) > 0 or (s["pending"] or 0) > 0 or s["total"] == 0]
        uses = sum(1 for s in slots if (s["sent"] or 0) > 0)
        committed = len(live)
        cap = c["reuse_cap"] or (rc["evergreen_max_uses"] if c["evergreen"] else rc["max_uses"])
        last = max((_d(s["scheduled_at"]) for s in live), default=None)
        next_ok = last + timedelta(days=rc["min_days_between"]) if last else today
        variants = con.execute("SELECT COUNT(*) n FROM variants WHERE clip_id=? AND active=1", (c["id"],)).fetchone()["n"]
        if c["status"] in ("retired", "unusable"):
            status = c["status"]
        elif committed >= cap:
            status = "exhausted"
        elif next_ok > today:
            status = "cooling"
        elif c["status"] in ("new", "prepped") or variants == 0:
            status = "needs_edit"
        else:
            status = "available"
        rows.append({"id": c["id"], "topic": c["topic"], "format": c["format"], "uses": uses, "committed": committed,
                     "cap": cap, "evergreen": bool(c["evergreen"]), "last_used": last.isoformat() if last else None,
                     "next_eligible": next_ok.isoformat() if status not in ("exhausted", "retired", "unusable") else None,
                     "status": status, "variants": variants, "db_status": c["status"]})
    return rows


def retire_exhausted(con) -> list[str]:
    """Move clips whose final use has been SENT (no pending posts) to media/raw/_retired."""
    cfg = config.load()
    retired = []
    for row in clip_table(con):
        if row["status"] != "exhausted" or row["uses"] < row["cap"]:
            continue
        pending = con.execute(
            "SELECT COUNT(*) n FROM posts p JOIN slots s ON s.id=p.slot_id WHERE s.clip_id=? AND p.status='scheduled'",
            (row["id"],)).fetchone()["n"]
        if pending:
            continue
        c = con.execute("SELECT file_name FROM clips WHERE id=?", (row["id"],)).fetchone()
        src = cfg.clip_path(c["file_name"])
        if src.exists():
            if src.parent == cfg.path("raw"):
                shutil.move(str(src), cfg.path("retired") / c["file_name"])
            else:
                src.unlink()  # web upload: drop it from the repo (history keeps it)
        con.execute("UPDATE variants SET active=0 WHERE clip_id=?", (row["id"],))
        con.execute("UPDATE clips SET status='retired' WHERE id=?", (row["id"],))
        db.log_event(con, "retired", {"clip": row["id"], "topic": row["topic"], "format": row["format"]})
        retired.append(row["id"])
    return retired


def cleanup(con) -> list[str]:
    """Delete rendered files of inactive variants (run by the Mac worker, which may delete files)."""
    cfg = config.load()
    removed = []
    for v in con.execute("SELECT file_name FROM variants WHERE active=0"):
        p = cfg.path("edited") / v["file_name"]
        if p.exists():
            try:
                p.unlink()
                removed.append(v["file_name"])
            except OSError:
                pass
    return removed


def unretire(con, clip_id: str) -> None:
    cfg = config.load()
    c = con.execute("SELECT file_name FROM clips WHERE id=?", (clip_id,)).fetchone()
    src = cfg.path("retired") / c["file_name"]
    if src.exists():
        shutil.move(str(src), cfg.path("raw") / c["file_name"])
    used = con.execute("SELECT COUNT(*) n FROM slots WHERE clip_id=?", (clip_id,)).fetchone()["n"]
    con.execute("UPDATE clips SET status='new', reuse_cap=? WHERE id=?", (used + config.load()["reuse"]["max_uses"], clip_id))


def inventory(con, horizon: int = 60) -> dict:
    """Days of posting the current library covers, simulating the reuse rules day by day."""
    cfg = config.load()
    per_day = cfg["posting"]["posts_per_day"]
    gap = cfg["reuse"]["min_days_between"]
    today = datetime.now(timezone.utc).date()
    pool = {}
    for r in clip_table(con):
        if r["status"] in ("retired", "unusable", "exhausted"):
            continue
        last = date.fromisoformat(r["last_used"]) if r["last_used"] else None
        pool[r["id"]] = {"left": r["cap"] - r["committed"], "last": last}
    # days already covered by scheduled slots
    booked = {}
    for s in con.execute("SELECT scheduled_at FROM slots WHERE scheduled_at >= ?", (today.isoformat(),)):
        d = _d(s["scheduled_at"])
        booked[d] = booked.get(d, 0) + 1
    remaining_uses = sum(p["left"] for p in pool.values())
    days = 0
    first_gap = None
    for i in range(horizon):
        d = today + timedelta(days=i)
        need = per_day - booked.get(d, 0)
        elig = sorted((cid for cid, p in pool.items() if p["left"] > 0 and (p["last"] is None or (d - p["last"]).days >= gap)),
                      key=lambda cid: -pool[cid]["left"])
        if len(elig) < need:
            first_gap = d
            break
        for cid in elig[:need]:
            pool[cid]["left"] -= 1
            pool[cid]["last"] = d
        days += 1
    level = ("empty" if days == 0 else "urgent" if days < cfg["inventory"]["urgent_days"]
             else "heads_up" if days < cfg["inventory"]["heads_up_days"] else "healthy")
    clips_needed = 0
    if level != "healthy":
        # enough new clips to cover `heads_up_days` of posting
        short = per_day * cfg["inventory"]["heads_up_days"] - remaining_uses
        clips_needed = max(1, -(-short // cfg["reuse"]["max_uses"]))
    return {"days": days, "level": level, "remaining_uses": remaining_uses, "active_clips": len(pool),
            "clips_needed": clips_needed,
            "covered_through": (today + timedelta(days=days - 1)).isoformat() if days else None,
            "first_gap": first_gap.isoformat() if first_gap else None,
            "available_now": sum(1 for p in pool.values() if p["left"] > 0 and (p["last"] is None or (today - p["last"]).days >= gap))}
