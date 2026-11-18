"""Host rendered videos for Buffer on the repo's `publish` branch (plain git files, no LFS).

Buffer downloads https://raw.githubusercontent.com/<owner>/<repo>/publish/<file>.
Each publish rebuilds the branch as a single commit holding only the videos still needed,
so the branch never accumulates history.
"""
from __future__ import annotations

import shutil
import subprocess
import urllib.request
from pathlib import Path

from . import config, db

BRANCH = "publish"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def needed_files(con) -> set[str]:
    """Videos of active variants, plus any variant with a post not yet sent."""
    keep = {r["file_name"] for r in con.execute("SELECT file_name FROM variants WHERE active=1")}
    keep |= {r["file_name"] for r in con.execute(
        """SELECT DISTINCT v.file_name FROM posts p JOIN slots s ON s.id=p.slot_id JOIN variants v ON v.id=s.variant_id
           WHERE p.status='scheduled'""")}
    return keep


def publish(remote: str) -> dict:
    """Make the publish branch hold exactly the needed videos. New renders come from media/edited."""
    cfg = config.load()
    work = cfg.path("work") / "publish-branch"
    if work.exists():
        shutil.rmtree(work)
    cloned = True
    try:
        subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", BRANCH, remote, str(work)], check=True,
                       capture_output=True, text=True)
    except subprocess.CalledProcessError:
        cloned = False
        work.mkdir(parents=True)
        _git(work, "init", "-q", "-b", BRANCH)
        _git(work, "remote", "add", "origin", remote)
    with db.tx() as con:
        keep = needed_files(con)
    edited = cfg.path("edited")
    added, missing = [], []
    for name in sorted(keep):
        dst = work / name
        src = edited / name
        if not dst.exists():
            if src.exists():
                shutil.copy2(src, dst)
                added.append(name)
            else:
                missing.append(name)
    removed = [f.name for f in work.glob("*.mp4") if f.name not in keep]
    for name in removed:
        (work / name).unlink()
    (work / "README.md").write_text("Rendered videos served to Buffer. Rebuilt by VDOs on every run; do not edit.\n")
    if cloned and not added and not removed:
        return {"added": [], "removed": [], "missing": missing, "pushed": False}
    _git(work, "checkout", "-q", "--orphan", "tmp-publish")
    _git(work, "add", "-A")
    _git(work, "-c", "user.name=VDOs", "-c", "user.email=noreply@kairoapps.com", "commit", "-q", "-m",
         f"publish: {len(keep) - len(missing)} videos")
    _git(work, "branch", "-M", BRANCH)
    _git(work, "push", "-q", "-f", "origin", BRANCH)
    return {"added": added, "removed": removed, "missing": missing, "pushed": True}


def check_url(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200 and int(r.headers.get("Content-Length", "0")) > 10_000
    except Exception:
        return False
