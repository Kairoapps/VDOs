"""Ingest raw clips and music into the ledger, applying naming conventions.

Raw clips: drop any file into media/raw/. Optional topic prefix: `gym__anything.mov`.
On ingest they are renamed to R<YYYYMMDD>-<seq>__<topic>.<ext>.
Music: media/music/<mood>/<artist>__<title>__<source>.mp3
Sound effects: media/sfx/<category>/<description>__<source>.mp3
(See docs/naming.md.)
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import config, db, media

VIDEO_EXT = {".mp4", ".mov", ".m4v"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac"}
CANON = re.compile(r"^R(\d{8})-(\d{3})__([a-z0-9-]+)$")
TOPIC_PREFIX = re.compile(r"^([A-Za-z0-9-]+)__")


def _capture_date(info: dict, path: Path) -> datetime:
    ct = info.get("creation_time")
    if ct:
        try:
            return datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def _next_seq(con, date_str: str) -> int:
    row = con.execute("SELECT id FROM clips WHERE id LIKE ? ORDER BY id DESC LIMIT 1", (f"R{date_str}-%",)).fetchone()
    return int(row["id"].split("-")[1]) + 1 if row else 1


def ingest_clips() -> list[dict]:
    cfg = config.load()
    raw = cfg.path("raw")
    results = []
    with db.tx() as con:
        for f in sorted(raw.iterdir()):
            if not f.is_file() or f.suffix.lower() not in VIDEO_EXT:
                continue
            if CANON.match(f.stem) and con.execute("SELECT 1 FROM clips WHERE file_name=?", (f.name,)).fetchone():
                continue
            digest = media.sha256(f)
            dup = con.execute("SELECT id FROM clips WHERE sha256=?", (digest,)).fetchone()
            if dup:
                results.append({"file": f.name, "result": "duplicate", "of": dup["id"]})
                f.unlink()
                continue
            try:
                info = media.probe(f)
            except Exception as e:  # corrupt
                results.append({"file": f.name, "result": "unreadable", "error": str(e)[:200]})
                continue
            m = TOPIC_PREFIX.match(f.name)
            topic = m.group(1).lower() if m else "misc"
            cap = _capture_date(info, f)
            date_str = cap.strftime("%Y%m%d")
            seq = _next_seq(con, date_str)
            cid = f"R{date_str}-{seq:03d}"
            new_name = f"{cid}__{topic}{f.suffix.lower()}"
            f.rename(raw / new_name)
            status = "new"
            if info["duration"] < 4 or info["width"] == 0:
                status = "unusable"
            con.execute(
                """INSERT INTO clips(id, file_name, sha256, duration_s, width, height, has_audio,
                   captured_at, ingested_at, topic, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, new_name, digest, info["duration"], info["width"], info["height"], int(info["has_audio"]),
                 cap.isoformat(), db.now_iso(), topic, status))
            results.append({"file": f.name, "result": "ingested" if status == "new" else "unusable", "id": cid,
                            "name": new_name, "duration": round(info["duration"], 1)})
    return results




def ingest_music() -> list[dict]:
    cfg = config.load()
    root = cfg.path("music")
    added = []
    with db.tx() as con:
        known = {r["id"] for r in con.execute("SELECT id FROM tracks")}
        present = set()
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in AUDIO_EXT:
                continue
            rel = str(f.relative_to(root))
            present.add(rel)
            if rel in known:
                continue
            mood = f.parent.name if f.parent != root else "any"
            parts = f.stem.split("__")
            artist, title, source = (parts + [None, None])[:3] if len(parts) >= 3 else ("", parts[0], parts[1] if len(parts) > 1 else None)
            info = media.probe(f)
            lufs = media.loudness(f)
            con.execute("INSERT INTO tracks(id, mood, artist, title, source, duration_s, lufs, added_at) VALUES (?,?,?,?,?,?,?,?)",
                        (rel, mood.lower(), artist, title, source, info["duration"], lufs, db.now_iso()))
            added.append({"track": rel, "mood": mood, "lufs": lufs, "source": source})
        for gone in known - present:
            con.execute("DELETE FROM tracks WHERE id=?", (gone,))
    return added


def ingest_sfx() -> list[dict]:
    """Catalog media/sfx/<category>/<description>__<source>.mp3 (measures loudness)."""
    cfg = config.load()
    root = cfg.path("sfx")
    added = []
    with db.tx() as con:
        known = {r["id"] for r in con.execute("SELECT id FROM sfx")}
        present = set()
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in AUDIO_EXT:
                continue
            rel = str(f.relative_to(root))
            present.add(rel)
            if rel in known:
                continue
            category = f.parent.name if f.parent != root else "misc"
            parts = f.stem.split("__")
            info = media.probe(f)
            con.execute("INSERT INTO sfx(id, category, description, source, duration_s, lufs, added_at) VALUES (?,?,?,?,?,?,?)",
                        (rel, category.lower(), parts[0], parts[1] if len(parts) > 1 else None, info["duration"],
                         media.loudness(f), db.now_iso()))
            added.append({"sfx": rel, "category": category})
        for gone in known - present:
            con.execute("DELETE FROM sfx WHERE id=?", (gone,))
    return added
