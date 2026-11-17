"""Commit and push raw clips, music, retirements and reports (media via Git LFS)."""
from __future__ import annotations

import subprocess

from . import config


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.ROOT, check=True, capture_output=True, text=True).stdout.strip()


def sync(message: str, push: bool = True) -> str:
    _git("add", "-A", "media/raw", "media/music", "media/sfx", "references", "data", "work", "reports", "config.toml")
    if not _git("status", "--porcelain", "--", "media/raw", "media/music", "media/sfx", "references", "data", "work", "reports", "config.toml"):
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
