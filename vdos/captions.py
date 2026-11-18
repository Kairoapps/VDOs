"""ASS subtitle generation: word-highlight captions + hook overlay, inside the safe zone.

Times are mapped from source time to output time (after cuts and speed change).
"""
from __future__ import annotations


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


# Colors are &HBBGGRR& in ASS
STYLES = {
    # big bold white, current word yellow, centered a bit above the bottom UI zone
    "pop": dict(font_size=88, primary="&H00FFFFFF", highlight="&H0000E5FF", outline=6, bold=-1, words=3, upper=True),
    # small, clean, whole phrase, no highlight
    "minimal": dict(font_size=62, primary="&H00FFFFFF", highlight=None, outline=3, bold=0, words=6, upper=False),
    # phrase with progressive karaoke fill
    "karaoke": dict(font_size=76, primary="&H00FFFFFF", highlight="&H0066FF66", outline=5, bold=-1, words=4, upper=False),
}
# One line stating the clip's premise, on screen for the whole video (the reference-clip style).
PREMISE_STYLES = {"premise": "outline"}  # white bold text, thick black outline (rendered by title.py)


def header(width: int, height: int, style_name: str) -> str:
    st = STYLES[style_name]
    # Safe zone: platforms overlay UI at the bottom ~22% and right edge; keep captions at ~62% height.
    margin_v = int(height * 0.30)
    side = int(width * 0.09)
    secondary = st["highlight"] or st["primary"]
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,{st['font_size']},{st['primary'] if style_name != 'karaoke' else secondary},{st['primary'] if style_name == 'karaoke' else secondary},&H00000000,&H64000000,{st['bold']},0,0,0,100,100,0,0,1,{st['outline']},2,2,{side},{side + int(width * 0.06)},{margin_v},1
Style: Hook,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,18,0,8,{side},{side},{int(height * 0.14)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def premise_ass(text: str, width: int, height: int, duration: float, look: str = "outline") -> str:
    """Big top-centre caption for the whole clip, below the platforms' top UI."""
    side = int(width * 0.08)
    top = int(height * 0.11)
    if look == "box":   # dark text on a white box
        style = f"Style: Premise,Arial,68,&H00111111,&H00111111,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,14,0,8,{side},{side},{top},1"
    else:               # white text, heavy black outline
        style = f"Style: Premise,Arial,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,8,{side},{side},{top},1"
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{_ts(0)},{_ts(duration + 0.5)},Premise,,0,0,0,,{_esc(text)}
"""


def build_ass(words_out: list[dict], width: int, height: int, style_name: str,
              hook_text: str | None = None, hook_dur: float = 2.2) -> str:
    """words_out: [{"w","s","e"}] already in OUTPUT time."""
    st = STYLES[style_name]
    lines = [header(width, height, style_name)]
    if hook_text:
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(hook_dur)},Hook,,0,0,0,,{_esc(hook_text)}")
    n = st["words"]
    chunks = [words_out[i:i + n] for i in range(0, len(words_out), n)]
    for ci, chunk in enumerate(chunks):
        if not chunk:
            continue
        start = chunk[0]["s"]
        nxt = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) and chunks[ci + 1] else None
        end = chunk[-1]["e"] + 0.15
        if nxt is not None:
            end = min(end, nxt)
        texts = [(_esc(w["w"]).upper() if st["upper"] else _esc(w["w"])) for w in chunk]
        if style_name == "minimal" or not st["highlight"]:
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{' '.join(texts)}")
        elif style_name == "karaoke":
            parts = []
            for w, t in zip(chunk, texts):
                cs = max(1, int(round((w["e"] - w["s"]) * 100)))
                parts.append(f"{{\\kf{cs}}}{t}")
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{' '.join(parts)}")
        else:  # pop: one event per word, active word highlighted
            for wi, w in enumerate(chunk):
                ws = w["s"] if wi else start
                we = chunk[wi + 1]["s"] if wi + 1 < len(chunk) else end
                if we <= ws:
                    continue
                txt = " ".join(
                    (f"{{\\c{st['highlight']}\\fscx110\\fscy110}}{t}{{\\r}}" if j == wi else t)
                    for j, t in enumerate(texts))
                lines.append(f"Dialogue: 0,{_ts(ws)},{_ts(we)},Cap,,0,0,0,,{txt}")
    return "\n".join(lines) + "\n"


def map_words(words: list[dict], segments: list[tuple[float, float]], speed: float) -> list[dict]:
    """Map source-time words onto output time given kept segments (source times) and speed."""
    out, offset = [], 0.0
    for a, b in segments:
        for w in words:
            if w["s"] >= a and w["e"] <= b + 0.05:
                out.append({"w": w["w"], "s": (offset + w["s"] - a) / speed, "e": (offset + min(w["e"], b) - a) / speed})
        offset += b - a
    return out
