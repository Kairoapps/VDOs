"""Render one variant with ffmpeg: cuts, speed, 9:16 reframe, captions, hook overlay, ducked music, loudnorm."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import captions, config, media


def render(spec: dict, out_path: Path) -> Path:
    """spec keys: src, segments [[a,b]], speed, caption_style, hook_text, words (source time),
    has_audio, track (path or None), track_lufs, track_offset, reframe."""
    cfg = config.load()
    r = cfg["render"]
    W, H, fps = r["width"], r["height"], r["fps"]
    speed = float(spec.get("speed", 1.0))
    segs = [(float(a), float(b)) for a, b in spec["segments"]]
    dur = sum(b - a for a, b in segs) / speed
    has_audio = bool(spec.get("has_audio", True))
    words_out = captions.map_words(spec.get("words", []), segs, speed) if spec.get("caption_style") else []

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ass = captions.build_ass(words_out, W, H, spec.get("caption_style") or "minimal", spec.get("hook_text"))
        (td / "subs.ass").write_text(ass)

        inputs = ["-i", str(Path(spec["src"]).resolve())]
        idx = 1
        music_idx = None
        if spec.get("track"):
            inputs += ["-stream_loop", "-1", "-i", str(Path(spec["track"]).resolve())]
            music_idx = idx
            idx += 1
        if not has_audio:
            inputs += ["-f", "lavfi", "-t", f"{dur + 1:.2f}", "-i", "anullsrc=r=48000:cl=stereo"]
            null_idx = idx
            idx += 1

        f = []
        for i, (a, b) in enumerate(segs):
            f.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
            if has_audio:
                f.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
        n = len(segs)
        if has_audio:
            f.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
        else:
            f.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]")

        v = f"[vc]setpts=PTS/{speed}"
        if spec.get("reframe", r["reframe"]) == "crop":
            f.append(f"{v},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},setsar=1[vr]")
        else:
            f.append(f"{v},fps={fps},split[bgs][fgs]")
            f.append(f"[bgs]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:2,eq=brightness=-0.08[bg]")
            f.append(f"[fgs]scale={W}:{H}:force_original_aspect_ratio=decrease[fg]")
            f.append("[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[vr]")
        f.append("[vr]ass=subs.ass,format=yuv420p[vout]")

        if has_audio:
            tempo = f",atempo={speed}" if abs(speed - 1) > 1e-3 else ""
            f.append(f"[ac]anull{tempo}[voice]")
        else:
            f.append(f"[{null_idx}:a]atrim=duration={dur:.3f}[voice]")

        if music_idx is not None:
            speechy = bool(words_out)
            target = r["music_bed_lufs"] if speechy else r["music_solo_lufs"]
            gain = target - (spec.get("track_lufs") if spec.get("track_lufs") is not None else -14)
            off = float(spec.get("track_offset", 0))
            fade_out = max(0.0, dur - 1.2)
            f.append(f"[{music_idx}:a]atrim=start={off:.2f}:duration={dur:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"volume={gain:.1f}dB,afade=t=in:d=0.4,afade=t=out:st={fade_out:.2f}:d=1.2[mus]")
            if speechy:
                f.append("[voice]asplit[vmain][vsc]")
                f.append("[mus][vsc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck]")
                f.append("[vmain][duck]amix=inputs=2:normalize=0:duration=first[mix]")
            else:
                f.append("[voice][mus]amix=inputs=2:normalize=0:duration=first[mix]")
        else:
            f.append("[voice]anull[mix]")
        f.append(f"[mix]loudnorm=I={r['target_lufs']}:TP=-1.5:LRA=11,aresample=48000[aout]")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
               "-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
               "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]),
               "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
               "-movflags", "+faststart", str(out_path.resolve())]
        media.run(cmd, cwd=td)
    return out_path
