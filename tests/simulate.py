"""End-to-end simulation against a throwaway ledger: fake 3 weeks of posting + Buffer metrics.

Run: VDOS_ROOT=$(pwd) python3 tests/simulate.py   (uses whatever clips/variants exist in the ledger)
"""
import json
import random
from datetime import datetime, timedelta, timezone

from vdos import analysis, buffer_sync, dashboard, db, reuse, scheduler

rng = random.Random(7)
now = datetime.now(timezone.utc)
with db.tx() as con:
    variants = [dict(r) for r in con.execute("SELECT v.id, v.clip_id, v.hook_type, v.caption_style, c.topic FROM variants v JOIN clips c ON c.id=v.clip_id WHERE v.active=1")]
    con.execute("DELETE FROM metrics"); con.execute("DELETE FROM posts"); con.execute("DELETE FROM slots")

buffer_posts = []
pid = 0
slots_payload = []
for day in range(21, 0, -1):
    for t in ["08:30", "12:30", "19:00"]:
        v = rng.choice(variants)
        when = (now - timedelta(days=day)).replace(hour=int(t[:2]), minute=int(t[3:]), second=0, microsecond=0)
        posts = []
        for plat in ["instagram", "tiktok", "youtube"]:
            pid += 1
            bid = f"{pid:024x}"
            posts.append({"platform": plat, "channel_id": "c" * 24, "buffer_post_id": bid, "caption": "test", "status": "scheduled"})
            # performance model: gym and evening + pop captions do better
            base = 800 * (2.0 if v["topic"] == "gym" else 1.0) * (1.6 if t == "19:00" else 1.0) * (1.3 if v["caption_style"] == "pop" else 1.0)
            views = int(base * rng.uniform(0.5, 1.5)) * (3 if plat == "tiktok" else 1)
            buffer_posts.append({"id": bid, "status": "sent", "sentAt": when.isoformat(), "dueAt": when.isoformat(),
                                 "metrics": [{"type": "views", "value": views}, {"type": "likes", "value": views // 20},
                                             {"type": "comments", "value": views // 200}, {"type": "shares", "value": views // 150},
                                             {"type": "saves", "value": views // 120}]})
        slots_payload.append({"variant_id": v["id"], "scheduled_at": when.isoformat(), "time_slot": t, "hashtag_set": rng.choice(["tags-1", "tags-2"]), "posts": posts})

print("recorded", scheduler.record({"slots": slots_payload}))
print("sync", buffer_sync.sync({"data": {"posts": {"edges": [{"node": p} for p in buffer_posts]}}}))
r = analysis.weekly(write=True)
print("scored slots", r["n_scored_slots"])
print(analysis.report_md(r))
print("dashboard", dashboard.build(r))
with db.tx() as con:
    print("inventory", reuse.inventory(con))
print(json.dumps(scheduler.plan(seed=1), indent=1, default=str)[:1500])
