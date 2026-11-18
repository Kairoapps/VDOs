"""Commit and push raw clips, music, retirements and reports (media via Git LFS)."""
from __future__ import annotations

import subprocess

from . import config


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.ROOT, check=True, capture_output=True, text=True).stdout.strip()


MAC_PATHS = ("media/raw", "references")                       # what the Mac uploads (Git LFS)
CLOUD_PATHS = ("data", "work", "reports", "sounds", "config.toml", "media/inbox")  # what the cloud run saves (plain git)


def sync(message: str, push: bool = True, paths: tuple[str, ...] = MAC_PATHS) -> str:
    paths = tuple(p for p in paths if (config.ROOT / p).exists())
    if not paths:
        return "nothing to commit"
    _git("add", "-A", *paths)
    if not _git("status", "--porcelain", "--", *paths):
        return "nothing to commit"
    staged = _git("diff", "--cached", "--name-only")
    if not staged:
        return "nothing to commit"
    _git("commit", "-m", message)
    if push:
        try:
            _git("pull", "--rebase", "--autostash")
        except subprocess.CalledProcessError:
            pass
        _git("push")
    return f"committed {len(staged.splitlines())} file(s)"
