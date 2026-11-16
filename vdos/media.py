"""ffprobe/ffmpeg helpers."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]).stdout
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    w, h = (int(v["width"]), int(v["height"])) if v else (0, 0)
    # Respect rotation metadata (phones/glasses often store rotated frames)
    rot = 0
    if v:
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        rot = int(v.get("tags", {}).get("rotate", rot))
    if abs(rot) in (90, 270):
        w, h = h, w
    tags = info["format"].get("tags", {})
    return {
        "duration": float(info["format"].get("duration", 0) or 0),
        "width": w,
        "height": h,
        "has_audio": a is not None,
        "creation_time": tags.get("creation_time") or (v or {}).get("tags", {}).get("creation_time"),
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def loudness(path: Path) -> float | None:
    """Integrated loudness (LUFS) via ebur128."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-filter_complex", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    return float(m[-1]) if m else None


def silences(path: Path, noise_db: int = -35, min_dur: float = 0.6) -> list[tuple[float, float]]:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", p.stderr)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        out.append((max(0.0, s), e if e is not None else float("inf")))
    return out


def sample_frames(path: Path, out_dir: Path, every_s: float = 2.0, width: int = 384) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("f_*.jpg"):
        old.unlink()
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vf",
         f"fps=1/{every_s},scale={width}:-2", "-q:v", "4", str(out_dir / "f_%04d.jpg")])
    return sorted(out_dir.glob("f_*.jpg"))
