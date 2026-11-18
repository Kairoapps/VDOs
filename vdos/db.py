"""SQLite ledger: clips, variants, tracks, posts, metrics, weights."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY,               -- R20261111-003
    file_name TEXT NOT NULL,
    sha256 TEXT UNIQUE NOT NULL,
    duration_s REAL,
    width INTEGER, height INTEGER,
    has_audio INTEGER,
    captured_at TEXT,
    ingested_at TEXT NOT NULL,
    topic TEXT DEFAULT 'misc',
    format TEXT,                       -- pov, tutorial, storytime, montage, reaction, before_after
    status TEXT NOT NULL DEFAULT 'new',-- new, prepped, edited, retired, unusable
    reuse_cap INTEGER,                 -- NULL = config default; raised for evergreen
    evergreen INTEGER DEFAULT 0,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS variants (
    id TEXT PRIMARY KEY,               -- R20261111-003_v2
    clip_id TEXT NOT NULL REFERENCES clips(id),
    file_name TEXT NOT NULL,           -- R20261111-003_v2_k7f3q9.mp4
    hook_type TEXT, caption_style TEXT, track_id TEXT,
    overlay_text TEXT, speed REAL, start_s REAL, duration_s REAL,
    spec_json TEXT,
    created_at TEXT NOT NULL,
    active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,               -- relative path under sounds/, e.g. music-hype/lumen__drift__artlist.mp3
    mood TEXT, artist TEXT, title TEXT, source TEXT,
    duration_s REAL, lufs REAL, bpm REAL,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sfx (
    id TEXT PRIMARY KEY,               -- relative path under sounds/, e.g. alarm/scifi-alarm-02__epidemic.mp3
    category TEXT, description TEXT, source TEXT,
    duration_s REAL, lufs REAL,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS slots (       -- one daily slot = one "use" of a clip
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id TEXT NOT NULL REFERENCES variants(id),
    clip_id TEXT NOT NULL REFERENCES clips(id),
    scheduled_at TEXT NOT NULL,        -- ISO with offset
    time_slot TEXT, hashtag_set TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER NOT NULL REFERENCES slots(id),
    platform TEXT NOT NULL,            -- instagram, tiktok, youtube
    channel_id TEXT,
    buffer_post_id TEXT UNIQUE,
    caption TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled', -- scheduled, sent, error, deleted
    sent_at TEXT, error TEXT,
    external_url TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
    post_id INTEGER NOT NULL REFERENCES posts(id),
    pulled_at TEXT NOT NULL,
    age_days REAL,
    views REAL, reach REAL, likes REAL, comments REAL, shares REAL, saves REAL,
    raw_json TEXT,
    PRIMARY KEY (post_id, pulled_at)
);
CREATE TABLE IF NOT EXISTS weights (
    dimension TEXT NOT NULL,           -- music_mood, caption_style, hook_type, topic, format, time_slot, hashtag_set, topic_format
    value TEXT NOT NULL,
    weight REAL NOT NULL,
    median_score REAL, n INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (dimension, value)
);
CREATE TABLE IF NOT EXISTS events (       -- alerts/notifications log
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    cfg = config.load()
    con = sqlite3.connect(cfg.path("db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # TRUNCATE keeps the journal file instead of deleting it: works on mounted folders where
    # deletes aren't allowed, and avoids WAL shared memory across the Mac and Claude's Linux shell.
    con.execute("PRAGMA journal_mode = TRUNCATE")
    con.execute("PRAGMA busy_timeout = 15000")
    con.executescript(SCHEMA)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(variants)")}
    if "sfx_ids" not in cols:
        con.execute("ALTER TABLE variants ADD COLUMN sfx_ids TEXT")
    if "caption_text" not in cols:
        con.execute("ALTER TABLE variants ADD COLUMN caption_text TEXT")
    if "title_style" not in cols:
        con.execute("ALTER TABLE variants ADD COLUMN title_style TEXT")
    return con


@contextmanager
def tx():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def log_event(con: sqlite3.Connection, kind: str, payload: dict) -> None:
    con.execute("INSERT INTO events(at, kind, payload) VALUES (?,?,?)", (now_iso(), kind, json.dumps(payload)))
