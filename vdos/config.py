"""Config loading. Reads config.toml and .env from the repo root."""
from __future__ import annotations

import os
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.10 (Claude's Linux shell): pip install tomli
    import tomli as tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("VDOS_ROOT", Path(__file__).resolve().parent.parent))


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Config:
    raw: dict

    def __getitem__(self, k):
        return self.raw[k]

    def path(self, key: str) -> Path:
        if key in ("music", "sfx"):  # one folder for all audio
            key = "sounds"
        p = Path(self.raw["paths"][key])
        return p if p.is_absolute() else ROOT / p

    def clip_path(self, file_name: str) -> Path:
        """Where a raw clip lives: media/raw (Mac uploads, LFS) or media/inbox (web uploads)."""
        for key in ("raw", "inbox"):
            if key in self.raw["paths"]:
                p = self.path(key) / file_name
                if p.exists():
                    return p
        return self.path("raw") / file_name

    @property
    def public_base_url(self) -> str:
        url = os.environ.get("PUBLIC_BASE_URL") or self.raw["server"].get("public_base_url", "")
        return url.rstrip("/")


_cfg: Config | None = None


def load(path: Path | None = None) -> Config:
    global _cfg
    if _cfg is not None and path is None:
        return _cfg
    _load_env(ROOT / ".env")
    p = path or Path(os.environ.get("VDOS_CONFIG", ROOT / "config.toml"))
    with open(p, "rb") as f:
        _cfg = Config(tomllib.load(f))
    for key in ("raw", "retired", "sounds", "edited", "work", "reports"):
        _cfg.path(key).mkdir(parents=True, exist_ok=True)
    _cfg.path("db").parent.mkdir(parents=True, exist_ok=True)
    return _cfg
