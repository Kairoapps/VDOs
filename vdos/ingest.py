"""Ingest raw clips and music into the ledger, applying naming conventions.

Raw clips: drop any file into media/raw/. Optional topic prefix: `gym__anything.mov`.
On ingest they are renamed to R<YYYYMMDD>-<seq>__<topic>.<ext>.
All audio lives in sounds/<category>/:
  background music: sounds/music-<mood>/<artist>__<title>__<source>.mp3
  everything else (alarms, whooshes, ...): sounds/<category>/<description>__<source>.mp3
(See docs/naming.md.)
"""
from __future__ import annotations

import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from . import config, db, media

VIDEO_EXT = {".mp4", ".mov", ".m4v"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac"}
CANON = re.compile(r"^R(\d{8})-(\d{3})__([a-z0-9-]+)$")
TOPIC_PREFIX = re.compile(r"^([A-Za-z0-9-]+)__")


NAME_DATE = re.compile(r"__(\d{8})(?=__|\.|$)")


def _capture_date(info: dict, path: Path) -> datetime:
    m = NAME_DATE.search(path.name)  # web uploads carry the date in the name: <topic>__<YYYYMMDD>__<id>.mp4
    if m and not CANON.match(path.stem):
        try:
            return datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            pass
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


def canonical_rename(raw: Path, retired: Path) -> list[dict]:
    """Rename new drop-ins to R<date>-<seq>__<topic> using only the files on disk (no database).
    The Mac does this before uploading, so names are final before the cloud ever sees them."""
    taken = {f.stem.split("__")[0] for d in (raw, retired) if d.exists() for f in d.iterdir() if CANON.match(f.stem)}
    out = []
    for f in sorted(raw.iterdir()):
        if not f.is_file() or f.suffix.lower() not in VIDEO_EXT or CANON.match(f.stem) or ".part" in f.name:
            continue
        if time.time() - f.stat().st_mtime < config.load().raw.get("compress", {}).get("min_age_seconds", 60):
            continue  # still being copied in
        try:
            info = media.probe(f)
        except Exception as e:
            out.append({"file": f.name, "result": "unreadable", "error": str(e)[:200]})
            continue
        m = TOPIC_PREFIX.match(f.name)
        topic = m.group(1).lower() if m else "misc"
        date_str = _capture_date(info, f).strftime("%Y%m%d")
        seq = 1
        while f"R{date_str}-{seq:03d}" in taken:
            seq += 1
        cid = f"R{date_str}-{seq:03d}"
        taken.add(cid)
        cc = config.load().raw.get("compress", {})
        if cc.get("enabled"):
            new_name = f"{cid}__{topic}.mp4"
            try:
                before = f.stat().st_size
                compress(f, raw / new_name, cc, info)
                _to_trash(f)
                out.append({"file": f.name, "name": new_name, "mb_before": round(before / 1e6, 1),
                            "mb_after": round((raw / new_name).stat().st_size / 1e6, 1)})
            except Exception as e:
                (raw / new_name).unlink(missing_ok=True)
                taken.discard(cid)
                out.append({"file": f.name, "result": "compress failed", "error": str(e)[-300:]})
            continue
        new_name = f"{cid}__{topic}{f.suffix.lower()}"
        f.rename(raw / new_name)
        out.append({"file": f.name, "name": new_name})
    return out


def compress(src: Path, dst: Path, cc: dict, info: dict) -> None:
    """Re-encode a raw clip to H.264 at the post's resolution. Keeps audio and the capture date."""
    tmp = dst.with_name(dst.stem + ".part.mp4")
    media.run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
               "-vf", f"scale='min({cc.get('width', 1080)},iw)':-2,fps={cc.get('fps', 30)}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", str(cc.get("crf", 23)), "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-map_metadata", "0", "-movflags", "+faststart", str(tmp)])
    got = media.probe(tmp).get("duration") or 0
    want = info.get("duration") or 0
    if want and abs(got - want) > 1.0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"duration mismatch {got} vs {want}")
    tmp.rename(dst)


def _to_trash(f: Path) -> None:
    """Move the original to the macOS Trash (recoverable) instead of deleting it."""
    trash = Path.home() / ".Trash"
    if trash.is_dir():
        dest = trash / f.name
        if dest.exists():
            dest = trash / f"{f.stem}-{int(time.time())}{f.suffix}"
        shutil.move(str(f), dest)
    else:
        f.unlink()


def ingest_clips() -> list[dict]:
    cfg = config.load()
    dirs = [cfg.path("raw")] + ([cfg.path("inbox")] if "inbox" in cfg.raw["paths"] else [])
    files = [f for d in dirs if d.exists() for f in sorted(d.iterdir())]
    results = []
    with db.tx() as con:
        for f in files:
            raw = f.parent
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
            cap = _capture_date(info, f)
            canon = CANON.match(f.stem)
            if canon and not con.execute("SELECT 1 FROM clips WHERE id=?", (f.stem.split("__")[0],)).fetchone():
                # already named (by the Mac): register as-is, no rename
                cid, topic, new_name = f.stem.split("__")[0], canon.group(3), f.name
            else:
                m = TOPIC_PREFIX.match(f.name)
                topic = m.group(1).lower() if m else "misc"
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
            folder = f.parent.name if f.parent != root else ""
            if not folder.startswith("music"):
                continue  # not background music (alarms etc. are catalogued by ingest_sfx)
            mood = folder[len("music-"):] if folder.startswith("music-") else "any"
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
    """Catalog sounds/<category>/<description>__<source>.mp3 except music-* folders (measures loudness)."""
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
            if category.startswith("music"):
                continue
            parts = f.stem.split("__")
            info = media.probe(f)
            con.execute("INSERT INTO sfx(id, category, description, source, duration_s, lufs, added_at) VALUES (?,?,?,?,?,?,?)",
                        (rel, category.lower(), parts[0], parts[1] if len(parts) > 1 else None, info["duration"],
                         media.loudness(f), db.now_iso()))
            added.append({"sfx": rel, "category": category})
        for gone in known - present:
            con.execute("DELETE FROM sfx WHERE id=?", (gone,))
    return added
