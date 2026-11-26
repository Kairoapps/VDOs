"""Build photo-carousel slideshows (TikTok photo mode / Instagram carousel) for Unsnooze.

Style: hand-drawn 2D webcomic art (assets/slides/art/<scene>__<source>.png, 9:16, top third left empty for text)
+ the video title style (white Poppins Bold, thick black outline, colour emojis; see vdos/title.py)
+ the fixed last slide assets/slides/cta-download.png ("Download Unsnooze Today", icon, store listing, App Store badge).

Rules: 6-8 slides per slideshow (hard max 10), last slide is always the CTA.
Output: media/slides/<name>/<name>__NN.jpg (1080x1920, TikTok) + media/slides/<name>/4x5/<name>__NN.jpg (1080x1350,
Instagram carousel + Facebook; Instagram won't auto-publish 9:16 feed images).

    python tools/slides/build.py              # build every slideshow into media/slides/<name>/
    python tools/slides/build.py shake math   # only these
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vdos import title  # noqa: E402

W, H = 1080, 1920
ART = ROOT / "assets" / "slides" / "art"
CTA = ROOT / "assets" / "slides" / "cta-download.png"
OUT = ROOT / "media" / "slides"
MIN_SLIDES, MAX_SLIDES = 6, 10

# Each entry: (scene, on-slide text). Scene = art file stem before "__". The CTA slide is appended automatically.
SLIDESHOWS: dict[str, list[tuple[str, str]]] = {
    "shake": [
        ("ring", "my alarm won't stop until i shake my phone 67 times 😭"),
        ("reach", "6:30am. i just wanted 5 more minutes 😴"),
        ("shock", "wait… it won't turn off unless i SHAKE it??"),
        ("shake", "shake. shake. SHAKE 📱💥"),
        ("tired", "41 of 67… my arm is gone 😩"),
        ("relief", "67. silence. finally 😮‍💨"),
        ("morning", "and now i'm actually awake ☀️"),
    ],
    "math": [
        ("ring", "my alarm won't stop until i solve a math problem 🧮"),
        ("reach", "6:30am. reaching for snooze like always 😴"),
        ("shock", "37 × 8??? at 6am??? 😭"),
        ("counting", "my brain is NOT on yet 🧠💤"),
        ("solved", "wait… 296!! 💡"),
        ("relief", "correct. alarm off. 😮‍💨"),
        ("morning", "brain: fully on ☀️"),
    ],
}


def art_path(scene: str) -> Path:
    hits = sorted(ART.glob(f"{scene}__*.png"))
    if not hits:
        raise FileNotFoundError(f"no art for scene '{scene}' in {ART}")
    return hits[0]


def cover(img: Image.Image) -> Image.Image:
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


H45 = 1350          # 4:5 for Instagram carousels / Facebook (Instagram rejects 9:16 feed images)
CROP45_TOP = 130    # 4:5 window into the 9:16 art: keeps the empty text band and most of the scene


def _text(img: Image.Image, text: str, hook: bool, y: int, tmp: Path = Path("/tmp/vdos_slide_title.png")) -> Image.Image:
    size = 92 if hook else 86
    title.render_png(text, tmp, W, size=size, stroke=size // 7, max_lines=4, max_width_frac=0.88)
    t = Image.open(tmp)
    img.alpha_composite(t, ((W - t.width) // 2, y))
    return img


def slide(scene: str, text: str, hook: bool) -> Image.Image:
    img = cover(Image.open(art_path(scene)).convert("RGB")).convert("RGBA")
    return _text(img, text, hook, 150 if hook else 170).convert("RGB")


def slide45(scene: str, text: str, hook: bool) -> Image.Image:
    art = cover(Image.open(art_path(scene)).convert("RGB")).crop((0, CROP45_TOP, W, CROP45_TOP + H45)).convert("RGBA")
    return _text(art, text, hook, 60 if hook else 70).convert("RGB")


def cta45() -> Image.Image:
    """The 9:16 CTA scaled into a 4:5 frame; the sides continue its vertical gradient."""
    cta = Image.open(CTA).convert("RGB")
    s = H45 / cta.height
    small = cta.resize((round(cta.width * s), H45), Image.LANCZOS)
    bg = cta.crop((0, 0, 4, cta.height)).resize((W, H45), Image.LANCZOS)
    bg.paste(small, ((W - small.width) // 2, 0))
    return bg


def build(name: str, out_root: Path = OUT) -> list[Path]:
    specs = SLIDESHOWS[name]
    n = len(specs) + 1
    if not MIN_SLIDES <= n <= MAX_SLIDES:
        raise ValueError(f"{name}: {n} slides (want {MIN_SLIDES}-{MAX_SLIDES})")
    d = out_root / name
    (d / "4x5").mkdir(parents=True, exist_ok=True)
    for old in list(d.glob("*.jpg")) + list((d / "4x5").glob("*.jpg")):
        old.unlink()
    tall = [slide(sc, tx, i == 0) for i, (sc, tx) in enumerate(specs)] + [Image.open(CTA).convert("RGB")]
    four = [slide45(sc, tx, i == 0) for i, (sc, tx) in enumerate(specs)] + [cta45()]
    files = []
    for i, (a, b) in enumerate(zip(tall, four), 1):
        f = d / f"{name}__{i:02d}.jpg"
        a.save(f, quality=90)
        b.save(d / "4x5" / f.name, quality=90)
        files.append(f)
    return files


if __name__ == "__main__":
    names = sys.argv[1:] or list(SLIDESHOWS)
    for nm in names:
        print(nm, len(build(nm)), "slides")
