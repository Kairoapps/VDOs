"""Prepare a clip for editorial decisions: transcript (word timestamps), sampled frames, silences.

Outputs work/<clip_id>/:
  transcript.json   {"language", "words": [{"w","s","e"}], "segments": [{"s","e","text"}]}
  frames/f_0001.jpg one frame every N seconds (for Claude to look at)
  silences.json     [[start, end], ...]
  context.md        a compact summary Claude reads before writing edit.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import config, db, media


def transcribe(path: Path) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise SystemExit("faster-whisper not installed: pip install faster-whisper") from e
    model_name = os.environ.get("WHISPER_MODEL", "small")
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments, info = model.transcribe(str(path), word_timestamps=True, vad_filter=True)
    words, segs = [], []
    for s in segments:
        segs.append({"s": round(s.start, 2), "e": round(s.end, 2), "text": s.text.strip()})
        for w in s.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)})
    return {"language": info.language, "words": words, "segments": segs}


def prep_clip(clip_id: str, frame_every: float = 2.0, skip_transcribe: bool = False) -> Path:
    cfg = config.load()
    with db.tx() as con:
        clip = con.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
        if not clip:
            raise SystemExit(f"unknown clip {clip_id}")
        src = cfg.clip_path(clip["file_name"])
        out = cfg.path("work") / clip_id
        out.mkdir(parents=True, exist_ok=True)

        tpath = out / "transcript.json"
        if not tpath.exists():
            if skip_transcribe or not clip["has_audio"]:
                tr = {"language": None, "words": [], "segments": []}
            else:
                try:
                    tr = transcribe(src)
                except (SystemExit, Exception) as e:  # no whisper / model download blocked (cloud): no captions
                    tr = {"language": None, "words": [], "segments": [], "note": f"transcription unavailable: {str(e)[:120]}"}
            tpath.write_text(json.dumps(tr, indent=1))
        tr = json.loads(tpath.read_text())

        frames = media.sample_frames(src, out / "frames", every_s=frame_every)
        sil = media.silences(src) if clip["has_audio"] else []
        (out / "silences.json").write_text(json.dumps(sil))

        lines = [f"# {clip_id} ({clip['topic']})",
                 f"duration {clip['duration_s']:.1f}s, {clip['width']}x{clip['height']}, audio={bool(clip['has_audio'])}",
                 f"frames: {len(frames)} in frames/ (one every {frame_every}s; f_0001 = t=0)",
                 "", "## Transcript (segments)"]
        lines += [f"[{s['s']:.1f}-{s['e']:.1f}] {s['text']}" for s in tr["segments"]] or ["(no speech)"]
        lines += ["", "## Silences", *[f"{a:.1f}-{b:.1f}" for a, b in sil[:50]]]
        (out / "context.md").write_text("\n".join(lines))
        con.execute("UPDATE clips SET status='prepped' WHERE id=? AND status='new'", (clip_id,))
    return out
