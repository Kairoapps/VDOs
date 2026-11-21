"""Render the on-screen title (white bold text, thick black outline, colour emojis) as a transparent PNG.

libass can't draw colour emojis, so the title is drawn with Pillow and overlaid by ffmpeg.
Fonts live in assets/fonts (both SIL Open Font License): Poppins-Bold.ttf, NotoColorEmoji.ttf.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

FONT_DIR = config.ROOT / "assets" / "fonts"
TEXT_FONT = FONT_DIR / "Poppins-Bold.ttf"
EMOJI_FONT = FONT_DIR / "NotoColorEmoji.ttf"
EMOJI_NATIVE = 109  # Noto Color Emoji is a bitmap font with one size

# An emoji cluster: a pictograph plus any variation selectors / skin tones / ZWJ-joined parts.
_EMOJI = r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿]"
_CLUSTER = re.compile(rf"{_EMOJI}(?:[️\U0001F3FB-\U0001F3FF]|‍{_EMOJI})*")


@lru_cache(maxsize=4)
def _text_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(TEXT_FONT), size)


@lru_cache(maxsize=1)
def _emoji_font() -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(EMOJI_FONT), EMOJI_NATIVE)


@lru_cache(maxsize=64)
def _emoji_image(cluster: str, size: int) -> Image.Image:
    f = _emoji_font()
    box = f.getbbox(cluster)
    img = Image.new("RGBA", (max(1, box[2]) + 8, max(1, box[3]) + 8), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((4, 4), cluster, font=f, embedded_color=True)
    img = img.crop(img.getbbox() or (0, 0, 1, 1))
    scale = size / max(img.height, 1)
    return img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)


def _runs(word: str) -> list[tuple[str, bool]]:
    """Split a word into (text, is_emoji) runs."""
    out, pos = [], 0
    for m in _CLUSTER.finditer(word):
        if m.start() > pos:
            out.append((word[pos:m.start()], False))
        out.append((m.group(0), True))
        pos = m.end()
    if pos < len(word):
        out.append((word[pos:], False))
    return out


def _word_width(word: str, size: int, gap: int) -> int:
    font = _text_font(size)
    w = 0
    for text, emoji in _runs(word):
        w += (_emoji_image(text, int(size * 1.05)).width + gap // 2) if emoji else round(font.getlength(text))
    return w


def render_png(text: str, out: Path, video_width: int, size: int = 58, stroke: int = 7,
               max_width_frac: float = 0.86, max_lines: int = 3,
               fill: tuple[int, int, int, int] = (255, 255, 255, 255)) -> tuple[int, int]:
    """Draw `text` centred and wrapped; returns (width, height) of the PNG."""
    font = _text_font(size)
    space = round(font.getlength(" "))
    max_w = int(video_width * max_width_frac)
    words = text.split()
    while True:  # shrink until it fits in max_lines
        lines, cur, cur_w = [], [], 0
        for wd in words:
            ww = _word_width(wd, size, space)
            if cur and cur_w + space + ww > max_w:
                lines.append(cur)
                cur, cur_w = [], 0
            cur.append(wd)
            cur_w += (space if cur_w else 0) + ww
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines or size <= 36:
            break
        size -= 4
        font = _text_font(size)
        space = round(font.getlength(" "))

    asc, desc = font.getmetrics()
    line_h = asc + desc
    pad = stroke + 4
    widths = [sum(_word_width(w, size, space) for w in ln) + space * (len(ln) - 1) for ln in lines]
    W = max(widths) + 2 * pad
    H = line_h * len(lines) + 2 * pad
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = pad
    for ln, lw in zip(lines, widths):
        x = (W - lw) // 2
        for wi, word in enumerate(ln):
            if wi:
                x += space
            for run, emoji in _runs(word):
                if emoji:
                    em = _emoji_image(run, int(size * 1.05))
                    img.alpha_composite(em, (x, y + (line_h - em.height) // 2 + desc // 3))
                    x += em.width + space // 2
                else:
                    draw.text((x, y), run, font=font, fill=fill,
                              stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                    x += round(font.getlength(run))
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return W, H


def hex_rgba(color: str) -> tuple[int, int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255
