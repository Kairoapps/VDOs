"""vdos command line. Every command prints JSON (or a path) so Claude's scheduled runs can parse it."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import analysis, buffer_sync, config, dashboard, db, gitops, ingest, prep, publish, reuse, scheduler, server, variants


def out(obj) -> None:
    print(json.dumps(obj, indent=1, default=str))


def cmd_ingest(a):
    res = {"clips": ingest.ingest_clips(), "music": ingest.ingest_music(), "sfx": ingest.ingest_sfx()}
    if not a.no_git and (res["clips"] or res["music"]):
        res["git"] = gitops.sync(f"ingest: {len(res['clips'])} clip(s), {len(res['music'])} track(s)", push=not a.no_push)
    out(res)


def _targets(a, statuses):
    if a.clip:
        return [a.clip]
    with db.tx() as con:
        return [r["id"] for r in con.execute(
            f"SELECT id FROM clips WHERE status IN ({','.join('?' * len(statuses))}) ORDER BY id", statuses)]


def cmd_prep(a):
    out({cid: str(prep.prep_clip(cid, skip_transcribe=a.skip_transcribe)) for cid in _targets(a, ["new"])})


def cmd_variants(a):
    res = {}
    for cid in _targets(a, ["prepped"]):
        edit = config.load().path("work") / cid / "edit.json"
        if not edit.exists() and not a.auto:
            res[cid] = "skipped: no edit.json (write one, or pass --auto)"
            continue
        res[cid] = variants.generate(cid, n=a.n, seed=a.seed)
    out(res)


def cmd_status(a):
    with db.tx() as con:
        table = reuse.clip_table(con)
        out({"inventory": reuse.inventory(con), "clips": table if a.all else
             [r for r in table if r["status"] not in ("retired", "unusable")]})


def cmd_plan(a):
    out(scheduler.plan(a.date, seed=a.seed))


def cmd_record(a):
    out({"posts_recorded": scheduler.record(json.loads(Path(a.file).read_text()))})


def cmd_sync_buffer(a):
    res = buffer_sync.sync(json.loads(Path(a.file).read_text()))
    if a.deleted:
        res["marked_deleted"] = buffer_sync.mark_deleted(a.deleted.split(","))
    out(res)


def cmd_retire(a):
    with db.tx() as con:
        r = reuse.retire_exhausted(con)
    if r and not a.no_git:
        gitops.sync(f"retire: {', '.join(r)}", push=not a.no_push)
    out({"retired": r})


def cmd_unretire(a):
    with db.tx() as con:
        reuse.unretire(con, a.clip)
    out({"unretired": a.clip})


def cmd_alerts(a):
    """Everything worth a push notification since the last time alerts were acknowledged."""
    with db.tx() as con:
        last = con.execute("SELECT MAX(at) t FROM events WHERE kind='alerts_sent'").fetchone()["t"] or ""
        ev = [dict(kind=e["kind"], **json.loads(e["payload"])) for e in con.execute(
            "SELECT kind, payload FROM events WHERE at > ? AND kind IN ('retired','evergreen') ORDER BY at", (last,))]
        inv = reuse.inventory(con)
        failed = [dict(r) for r in con.execute(
            "SELECT p.platform, p.buffer_post_id, p.error, s.variant_id FROM posts p JOIN slots s ON s.id=p.slot_id "
            "WHERE p.status='error' AND s.scheduled_at > ?", (last or "0",))]
        weekly = analysis.scored_slots(con, days=14)
        ranking = analysis.rank(weekly)
        shot = [r["value"].replace("|", " × ") for r in ranking["topic_format"][:3]]
        if a.ack:
            db.log_event(con, "alerts_sent", {})
    out({"inventory": inv, "retired": [e for e in ev if e["kind"] == "retired"],
         "evergreen": [e for e in ev if e["kind"] == "evergreen"], "failed_posts": failed, "shot_list": shot,
         "notify": inv["level"] in ("urgent", "empty") or bool(failed) or bool(ev)})


def cmd_weekly(a):
    r = analysis.weekly()
    path = dashboard.build(r)
    if not a.no_git:
        gitops.sync("weekly report", push=not a.no_push)
    out({"dashboard": str(path), "report_md": analysis.report_md(r)})


def cmd_dashboard(a):
    print(dashboard.build())


def cmd_cleanup(a):
    with db.tx() as con:
        out({"removed": reuse.cleanup(con)})


def cmd_worker(a):
    """Mac step (launchd, every 15 min): name new raw clips and upload them (Git LFS) with references.
    Everything else (edits, renders, Buffer, the database) happens in Claude's cloud runs."""
    cfg = config.load()
    res = {"renamed": ingest.canonical_rename(cfg.path("raw"), cfg.path("retired"))}
    if not a.no_git:
        res["git"] = gitops.sync("mac: upload new clips", push=True)
    out(res)


def cmd_pending_raw(a):
    """Raw clips on disk/in git that the database doesn't know yet (the cloud run pulls these from LFS)."""
    cfg = config.load()
    with db.tx() as con:
        known = {r["file_name"] for r in con.execute("SELECT file_name FROM clips")}
    files = [str(f.relative_to(config.ROOT)) for key in ("raw", "inbox") if key in cfg.raw["paths"] and cfg.path(key).exists()
             for f in sorted(cfg.path(key).iterdir())
             if f.is_file() and f.suffix.lower() in ingest.VIDEO_EXT and f.name not in known]
    out(files)


def cmd_publish(a):
    import os
    remote = a.remote or os.environ.get("VDOS_REMOTE") or gitops._git("remote", "get-url", "origin")
    out(publish.publish(remote))


def cmd_cloud_save(a):
    out({"git": gitops.sync(a.message, push=True, paths=gitops.CLOUD_PATHS)})


def cmd_serve(a):
    server.serve(a.port)


def main(argv=None):
    p = argparse.ArgumentParser(prog="vdos")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="register new raw clips + music (renames, dedupes, commits)")
    s.add_argument("--no-git", action="store_true"); s.add_argument("--no-push", action="store_true"); s.set_defaults(f=cmd_ingest)
    s = sub.add_parser("prep", help="transcribe + sample frames for new clips")
    s.add_argument("clip", nargs="?"); s.add_argument("--skip-transcribe", action="store_true"); s.set_defaults(f=cmd_prep)
    s = sub.add_parser("variants", help="render variants for prepped clips that have edit.json")
    s.add_argument("clip", nargs="?"); s.add_argument("-n", type=int); s.add_argument("--seed", type=int)
    s.add_argument("--auto", action="store_true", help="use automatic edit when edit.json is missing"); s.set_defaults(f=cmd_variants)
    s = sub.add_parser("status", help="clip table + inventory")
    s.add_argument("--all", action="store_true"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("plan", help="plan today's slots (JSON for the posting run)")
    s.add_argument("--date"); s.add_argument("--seed", type=int); s.set_defaults(f=cmd_plan)
    s = sub.add_parser("record", help="record posts created in Buffer"); s.add_argument("file"); s.set_defaults(f=cmd_record)
    s = sub.add_parser("sync-buffer", help="update post status + metrics from saved Buffer list_posts JSON")
    s.add_argument("file"); s.add_argument("--deleted", help="comma-separated Buffer post ids deleted in Buffer"); s.set_defaults(f=cmd_sync_buffer)
    s = sub.add_parser("retire", help="retire clips whose final use was sent")
    s.add_argument("--no-git", action="store_true"); s.add_argument("--no-push", action="store_true"); s.set_defaults(f=cmd_retire)
    s = sub.add_parser("unretire"); s.add_argument("clip"); s.set_defaults(f=cmd_unretire)
    s = sub.add_parser("alerts", help="what to notify about"); s.add_argument("--ack", action="store_true"); s.set_defaults(f=cmd_alerts)
    s = sub.add_parser("weekly", help="analysis, weights, evergreen, report, dashboard")
    s.add_argument("--no-git", action="store_true"); s.add_argument("--no-push", action="store_true"); s.set_defaults(f=cmd_weekly)
    s = sub.add_parser("dashboard"); s.set_defaults(f=cmd_dashboard)
    s = sub.add_parser("cleanup", help="delete rendered files of retired variants"); s.set_defaults(f=cmd_cleanup)
    s = sub.add_parser("worker", help="Mac step: name new raw clips, upload them to GitHub")
    s.add_argument("--no-git", action="store_true"); s.set_defaults(f=cmd_worker)
    s = sub.add_parser("pending-raw", help="raw clips not yet in the database"); s.set_defaults(f=cmd_pending_raw)
    s = sub.add_parser("publish", help="put the videos Buffer needs on the publish branch")
    s.add_argument("--remote"); s.set_defaults(f=cmd_publish)
    s = sub.add_parser("cloud-save", help="commit + push the database, edits and reports (cloud run)")
    s.add_argument("-m", "--message", default="cloud run: ledger + edits"); s.set_defaults(f=cmd_cloud_save)
    s = sub.add_parser("serve"); s.add_argument("--port", type=int); s.set_defaults(f=cmd_serve)

    a = p.parse_args(argv)
    config.load()
    a.f(a)


if __name__ == "__main__":
    sys.exit(main())
