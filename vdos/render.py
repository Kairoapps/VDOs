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
    # mute_original: drop the camera audio entirely; the soundtrack is the alarm bed + effects (+ music)
    has_audio = bool(spec.get("has_audio", True)) and not r.get("mute_original", False)
    style = spec.get("caption_style")
    premise = style in captions.PREMISE_STYLES
    words_out = captions.map_words(spec.get("words", []), segs, speed) if style and not premise else []

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        title_png, title_h = None, 0
        cta = spec.get("cta") or None
        cta_png = None
        if premise or (cta and cta.get("text")):
            from . import title  # Pillow; only needed for titles
        if premise:
            title_png = td / "title.png"
            _, title_h = title.render_png(spec.get("caption_text") or "", title_png, W, size=r.get("title_size", 64))
        if cta and cta.get("text"):
            ccfg = cfg.get("cta") or {}
            cta_png = td / "cta.png"
            title.render_png(cta["text"], cta_png, W, size=int(ccfg.get("size", 46)), stroke=6, max_lines=2,
                             fill=title.hex_rgba(cta.get("color") or ccfg.get("color", "#2BFF4F")))
        if premise:
            ass = captions.build_ass([], W, H, "minimal")  # empty: the title is an image overlay
        else:
            ass = captions.build_ass(words_out, W, H, style or "minimal", spec.get("hook_text"))
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
        title_idx = cta_idx = None
        if title_png:
            inputs += ["-i", str(title_png)]
            title_idx = idx
            idx += 1
        if cta_png:
            inputs += ["-i", str(cta_png)]
            cta_idx = idx
            idx += 1
        bed = spec.get("bed")  # looping sound (the alarm) from bed["start"] (default 0) until bed["end"] (output seconds)
        bed_idx, bed_n, bed_xf = [], 1, 0.0
        if bed:
            import math
            bed_end = min(dur, max(0.3, float(bed["end"])))
            bed_start = max(0.0, min(float(bed.get("start") or 0), bed_end - 0.3))
            bed_len = bed_end - bed_start
            sd = float(bed.get("dur") or 0)
            if sd and sd < bed_len + 0.05:
                # Too short: play it again, crossfading each repeat into the next so seams blend.
                bed_xf = round(min(0.5, sd / 4), 3)
                bed_n = min(40, math.ceil((bed_len - bed_xf) / max(0.2, sd - bed_xf)) + 1)
            for _ in range(bed_n):  # separate inputs (asplit + acrossfade stalls on one stream)
                inputs += ["-i", str(Path(bed["path"]).resolve())]
                bed_idx.append(idx)
                idx += 1
        sfx_idx = []
        for s in spec.get("sfx", []):
            inputs += ["-i", str(Path(s["path"]).resolve())]
            sfx_idx.append((idx, s))
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
        ty = int(H * r.get("title_top", 0.17))
        if title_idx is not None:
            f.append(f"[vr][{title_idx}:v]overlay=(W-w)/2:{ty}[vt]")
        else:
            f.append("[vr]ass=subs.ass[vt]")
        if cta_idx is not None:  # green call to action right under the title (or where the title would be)
            cy = ty + title_h + 6 if title_h else ty
            st = float(cta.get("start") or 0)
            en = f":enable='gte(t,{st:.2f})'" if st > 0.05 else ""
            f.append(f"[vt][{cta_idx}:v]overlay=(W-w)/2:{cy}{en},format=yuv420p[vout]")
        else:
            f.append("[vt]format=yuv420p[vout]")

        speechy = bool(words_out) or (bool(spec.get("words")) and not premise)
        if has_audio:
            tempo = f",atempo={speed}" if abs(speed - 1) > 1e-3 else ""
            boost = ""
            if not speechy and spec.get("src_lufs") is not None:
                # quiet camera audio: lift it toward the target, but not so far that hiss takes over
                gain = max(0.0, min(r["max_voice_boost_db"], r["target_lufs"] - 6 - spec["src_lufs"]))
                boost = f",volume={gain:.1f}dB"
            f.append(f"[ac]anull{tempo}{boost},aresample=48000,aformat=channel_layouts=stereo[voice]")
        else:
            f.append(f"[{null_idx}:a]atrim=duration={dur:.3f}[voice]")
        if bed_idx:
            end = bed_len
            g = r["sfx_lufs"] - (bed.get("lufs") if bed.get("lufs") is not None else -14)
            for k, i in enumerate(bed_idx):
                f.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[bp{k}]")
            prev = "bp0"
            for k in range(1, len(bed_idx)):
                f.append(f"[{prev}][bp{k}]acrossfade=d={bed_xf}:c1=qsin:c2=qsin[bx{k}]")
                prev = f"bx{k}"
            src = f"[{prev}]anull"
            f.append(f"{src},atrim=duration={end:.3f},asetpts=PTS-STARTPTS,"
                     f"volume={g:.1f}dB,afade=t=out:st={max(0, end - 0.06):.3f}:d=0.06"
                     + (f",adelay={int(bed_start * 1000)}:all=1" if bed_start > 0 else "")
                     + f",apad=whole_dur={dur:.3f}[bed]")
            f.append("[voice][bed]amix=inputs=2:normalize=0:duration=first[voicebed]")
            bed_label = "voicebed"
        else:
            bed_label = "voice"
        if sfx_idx:
            names = []
            for k, (i, s) in enumerate(sfx_idx):
                g = r["sfx_lufs"] - (s.get("lufs") if s.get("lufs") is not None else -14) + float(s.get("gain_db", 0))
                at = max(0.0, float(s.get("at", 0)))
                d = float(s.get("dur", 3))
                fade = min(0.6, d / 3)
                f.append(f"[{i}:a]atrim=duration={d:.2f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
                         f"volume={g:.1f}dB,afade=t=out:st={max(0, d - fade):.2f}:d={fade:.2f},adelay={int(at * 1000)}:all=1[fx{k}]")
                names.append(f"[fx{k}]")
            f.append(f"[{bed_label}]{''.join(names)}amix=inputs={1 + len(names)}:normalize=0:duration=first[voicefx]")
            voice_label = "voicefx"
        else:
            voice_label = bed_label

        if music_idx is not None:
            target = r["music_bed_lufs"] if speechy else r["music_solo_lufs"]
            gain = target - (spec.get("track_lufs") if spec.get("track_lufs") is not None else -14)
            off = float(spec.get("track_offset", 0))
            fade_out = max(0.0, dur - 1.2)
            f.append(f"[{music_idx}:a]atrim=start={off:.2f}:duration={dur:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"volume={gain:.1f}dB,afade=t=in:d=0.4,afade=t=out:st={fade_out:.2f}:d=1.2[mus]")
            if speechy:
                f.append(f"[{voice_label}]asplit[vmain][vsc]")
                f.append("[mus][vsc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck]")
                f.append("[vmain][duck]amix=inputs=2:normalize=0:duration=first[mix]")
            else:
                f.append(f"[{voice_label}][mus]amix=inputs=2:normalize=0:duration=first[mix]")
        else:
            f.append(f"[{voice_label}]anull[mix]")
        if speechy:
            f.append(f"[mix]loudnorm=I={r['target_lufs']}:TP=-1.5:LRA=11,aresample=48000[aout]")
        else:  # no speech: levels were set per source above; just keep peaks safe
            f.append("[mix]alimiter=limit=0.84:level=false,aresample=48000[aout]")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
               "-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
               "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]),
               "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
               "-movflags", "+faststart", str(out_path.resolve())]
        media.run(cmd, cwd=td)
    return out_path
