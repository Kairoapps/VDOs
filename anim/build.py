#!/usr/bin/env python3
"""Build one low-poly Unsnooze animation from a spec:  python3 anim/build.py work/anim/<id>/spec.json [--snap]

spec.json -> <id>.mp4 (1080x1920, 30 fps) + <id>.sheet.jpg next to the spec. See anim/README.md for the spec.
Steps: voice (ElevenLabs if a key is set, else captions only) -> timeline -> 3D frames (anim/lowpoly, headless Chrome)
-> UI overlays, captions, CTA card -> music + sound effects -> mp4.
"""
import base64, glob, json, math, os, re, subprocess, sys, urllib.request, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = HERE / "assets"
W, H, FPS, SR = 1080, 1920, 30, 44100
TAU = math.tau
BOLD = str(ROOT / "assets/fonts/Poppins-Bold.ttf")
MED = str(ASSETS / "fonts/Poppins-Medium.ttf")
EMOJI = str(ROOT / "assets/fonts/NotoColorEmoji.ttf")
STARS = next((p for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"] if os.path.exists(p)), BOLD)
ORANGE, RED, GREEN, DARK = (240, 106, 57), (232, 48, 42), (52, 199, 120), (19, 19, 19)
COL = {"orange": ORANGE, "red": RED, "green": GREEN}
ALIAS = {"asleep_smoke_alarm": "s01", "bolt_upright": "s02", "smoke_alarm_swat": "s03", "phone_buzz_asleep": "s04", "snooze_slaps": "s05",
         "late_sprint": "s06", "set_alarm_in_bed": "s07", "pushups": "s08", "walk_steps": "s09", "stretch_win": "s10", "floor_ping": "s11",
         "thinking": "s12a", "shake_phone": "s12b", "out_the_door": "s14", "store_art": "ways"}
SHOTS = set(ALIAS) | {"squats", "talk", "facepalm"}
SMOKE = {"asleep_smoke_alarm", "bolt_upright", "smoke_alarm_swat"}
RINGING = {"phone_buzz_asleep", "pushups", "walk_steps", "shake_phone", "squats"}


def F(p, s):
    return ImageFont.truetype(p, s)


def eo(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3


def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, "<i2").astype(np.float64) / 32768


# ------------------------------------------------------------------ voice
def _cfg():
    try:
        import tomllib
        return tomllib.load(open(ROOT / "config.toml", "rb")).get("animation", {})
    except Exception:
        return {}


SEP = None      # spec["voice_sep"]: what joins the lines in the one-take read ("\n\n" = a pause after every line, " " = run on)


def elevenlabs(lines, out_dir):
    """One mp3 per line with the ElevenLabs API. Returns True when every line was made; any failure -> False (captions only)."""
    # The key comes from the ELEVENLABS_API_KEY variable, which the nightly scheduled task sets for the build command only
    # (never write it to a file or commit it: the repo is public). A proxy-injected xi-api-key header also works.
    key = os.environ.get("ELEVENLABS_API_KEY")
    cfg = _cfg()

    def call(url, body=None):
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                     headers={**({"xi-api-key": key} if key else {}), "content-type": "application/json", "accept": "application/json" if body is None else "audio/mpeg"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    try:
        vid = os.environ.get("ELEVENLABS_VOICE_ID") or cfg.get("elevenlabs_voice_id")
        if not vid:
            name = cfg.get("elevenlabs_voice", "")
            for url in (f"https://api.elevenlabs.io/v2/voices?search={urllib.request.quote(name.split(' - ')[0])}", "https://api.elevenlabs.io/v1/voices"):
                vs = json.loads(call(url)).get("voices", [])
                hit = [v for v in vs if name.split(" - ")[0].lower() in v.get("name", "").lower()]   # never another voice (Chika, 2026-11-27)
                if hit:
                    vid = hit[0]["voice_id"]; break
        if not vid:
            print("voice: no ElevenLabs voice found -> captions only"); return False
        out_dir.mkdir(parents=True, exist_ok=True)
        models = [m for m in (cfg.get("elevenlabs_model"), "eleven_multilingual_v2") if m]
        if cfg.get("elevenlabs_continuous", True):
            # Chika, 2026-11-28: line-by-line takes sounded fast and choppy. Read the whole script in ONE take so the voice flows,
            # then cut it into beats at the pauses, using the character timestamps the API returns.
            try:
                import base64, wave as _w
                sep = cfg.get("elevenlabs_line_sep", "\n\n") if SEP is None else SEP
                m = models[0]; full = sep.join(lines); spans = []; pos = 0
                for l in lines:
                    spans.append((pos, pos + len(l))); pos += len(l) + len(sep)
                vs = {k: float(v) for k, v in (("stability", cfg.get("elevenlabs_stability")), ("speed", cfg.get("elevenlabs_speed"))) if v is not None}
                d = json.loads(call(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128",
                                    {"text": full, "model_id": m, **({"voice_settings": vs} if vs else {})}))
                al = d["alignment"]; st, en = al["character_start_times_seconds"], al["character_end_times_seconds"]
                if len(al["characters"]) != len(full):
                    raise ValueError("alignment length differs from the text")
                tmp = out_dir / "_full.mp3"; tmp.write_bytes(base64.b64decode(d["audio_base64"])); x = load_audio(tmp); tmp.unlink()

                def first(a, b):      # first spoken character of a line (skips a leading [tone tag])
                    k = a
                    while k < b and (full[k] == "[" or full[k].isspace()):
                        k = full.index("]", k) + 1 if full[k] == "[" else k + 1
                    return min(k, b - 1)
                cuts = [0.0] + [(en[spans[i][1] - 1] + st[first(*spans[i + 1])]) / 2 for i in range(len(lines) - 1)] + [len(x) / SR]
                for f in glob.glob(str(out_dir / "l[0-9][0-9].*")):
                    os.remove(f)
                for i in range(len(lines)):
                    seg = x[int(cuts[i] * SR):int(cuts[i + 1] * SR)]
                    with _w.open(str(out_dir / f"l{i + 1:02d}.wav"), "wb") as w:
                        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(seg, -1, 1) * 32767).astype("<i2").tobytes())
                (out_dir / "continuous.json").write_text(json.dumps({"continuous": True, "model": m, "seconds": round(len(x) / SR, 2)}))
                return True
            except Exception as e:
                print(f"voice: one-take read failed ({str(e)[:140]}) -> line by line")
        for i, text in enumerate(lines):
            for m in models:
                try:
                    t = text if "v3" in m or "v4" in m else re.sub(r"\[[a-z ]+\]\s*", "", text)   # tone tags only on the newest model
                    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128"
                    stab = cfg.get("elevenlabs_stability")      # same voice, calmer delivery (Chika, 2026-11-28): 1.0 = steadiest
                    try:
                        mp3 = call(url, {"text": t, "model_id": m, **({"voice_settings": {"stability": float(stab)}} if stab is not None else {})})
                    except Exception:
                        if stab is None:
                            raise
                        mp3 = call(url, {"text": t, "model_id": m})
                    (out_dir / f"l{i + 1:02d}.mp3").write_bytes(mp3); break
                except Exception as e:
                    err = e
            else:
                raise err
        return True
    except Exception as e:
        print(f"voice: ElevenLabs not available ({str(e)[:160]}) -> captions only"); return False


def trim(x, th=0.012):
    idx = np.where(np.abs(x) > th)[0]
    return x[max(0, idx[0] - int(.02 * SR)):idx[-1] + int(.06 * SR)] if len(idx) else x


# ------------------------------------------------------------------ captions
def parse_caption(text):
    """'you *never* snooze' -> lines of (word, highlighted). Wraps at ~24 characters when no line breaks are given."""
    lines, cur, n, hl = [], [], 0, False
    for raw in text.replace("\n", " \n ").split(" "):
        if raw == "\n":
            lines.append(cur); cur, n = [], 0; continue
        if not raw:
            continue
        w = raw
        if w.startswith("*"):
            hl = True; w = w[1:]
        end = w.endswith("*") or re.search(r"\*[.,!?…]*$", w)
        w2 = w.replace("*", "")
        if "\n" not in text and n + len(w2) > 24 and cur:
            lines.append(cur); cur, n = [], 0
        cur.append((w2, hl)); n += len(w2) + 1
        if end:
            hl = False
    lines.append(cur)
    return [l for l in lines if l]


# ------------------------------------------------------------------ UI pieces
def rr(size, rad, fill):
    c = Image.new("RGBA", size, (0, 0, 0, 0)); ImageDraw.Draw(c).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), rad, fill=fill); return c


def shadowed(layer, blur=22, off=14, alpha=120):
    pad = blur * 3
    c = Image.new("RGBA", (layer.width + pad * 2, layer.height + pad * 2), (0, 0, 0, 0))
    s = Image.new("RGBA", c.size, (0, 0, 0, 0)); s.paste((0, 0, 0, alpha), (pad, pad + off), layer.getchannel("A"))
    c.alpha_composite(s.filter(ImageFilter.GaussianBlur(blur))); c.alpha_composite(layer, (pad, pad)); return c


def rounded_img(im, rad):
    im = im.convert("RGBA"); m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), rad, fill=255); im.putalpha(m); return im


# Captions never sit on a white (or any) background box (Chika, 2026-11-28: "we don't really need a white background, just make
# sure the text is easy to read"): every theme draws them as bold text with a thick dark outline and a soft shadow.
# Graphics themes (Chika, 2026-11-28: the videos must not all look alike): caption colours and style, card and stamp style, font.
# build.py picks one that differs from the last 3 videos and saves it in the spec ("theme"); the download card never changes.
SOFTR = False      # spec["render"] == "soft": smooth 720x1280 3D frames (see anim/lowpoly/index.html)
CTA_IN = 0.55      # seconds the download card takes to rise over the last shot
INTER = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
THEMES = {
    "classic": dict(cap=((255, 242, 26), (255, 255, 255)), cap_style="outline", card="dark", stamp="outline", font=BOLD),
    "paper": dict(cap=((255, 255, 255), (255, 176, 64)), cap_style="outline", card="paper", stamp="solid", font=INTER),
    "clean": dict(cap=((255, 255, 255), (120, 235, 165)), cap_style="outline", card="light", stamp="solid", font=INTER),
    "pop": dict(cap=((255, 255, 255), (255, 150, 90)), cap_style="outline", card="accent", stamp="outline", font=BOLD),
    # the quiet look that goes with "render": "soft": small italic serif captions (one accent word), cards as bare text
    "serif": dict(cap=((255, 255, 255), (255, 104, 72)), cap_style="quiet", card="bare", stamp="outline", font=BOLD),
}
LORA = "/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf"
_qf = {}


def QF(size):
    if size not in _qf:
        try:
            f = ImageFont.truetype(LORA, size)
            try:
                f.set_variation_by_name("SemiBold Italic")
            except Exception:
                pass
        except Exception:
            f = F(MED, size)
        _qf[size] = f
    return _qf[size]
THEME = THEMES["classic"]


def TF():
    f = THEME.get("font", BOLD)
    return f if os.path.exists(f) else BOLD


def pick_theme(spec, spec_path, name):
    import zlib, random
    if spec.get("theme") in THEMES:
        return spec["theme"]
    if spec.get("render") == "soft":
        spec["theme"] = "serif"
        if spec_path.name == "spec.json":
            spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False))
        return "serif"
    used = []
    for f in sorted((HERE.parent / "work" / "anim").glob("A*/spec.json"), key=lambda q: q.stat().st_mtime)[-3:]:
        try:
            if f.resolve() != spec_path.resolve():
                used.append(json.loads(f.read_text()).get("theme") or "classic")
        except Exception:
            pass
    rng = random.Random(zlib.crc32(("theme" + name).encode()))
    th = next((t for t in rng.sample(sorted(k for k in THEMES if k != "serif"), len(THEMES) - 1) if t not in used), "classic")
    spec["theme"] = th
    if spec_path.name == "spec.json":
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    return th


def app_card(label, big, accent=ORANGE, w=None):
    st = THEME["card"]
    if st == "bare":      # just a small label and a big value, no box
        fb = F(BOLD, 92); d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); tw = int(max(d0.textlength(big, font=fb), d0.textlength(label, font=F(BOLD, 30)))) + 40
        c = Image.new("RGBA", (tw, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
        d.text((14, 8), label, font=F(BOLD, 30), fill=(*accent, 255), stroke_width=3, stroke_fill=(0, 0, 0, 170))
        d.text((12, 46), big, font=fb, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 170))
        return c
    f = F(TF(), 98); tw = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(big, font=f))
    w = w or max(520, tw + 110)
    fill, lab, txt, rad = {"dark": ((28, 28, 30, 250), accent, (255, 255, 255), 46), "light": ((250, 250, 246, 252), accent, (24, 24, 28), 46),
                           "accent": ((*accent, 252), (255, 255, 255), (255, 255, 255), 60), "paper": ((255, 232, 130, 255), (130, 96, 20), (30, 26, 20), 10)}[st]
    c = rr((w, 250), rad, fill); d = ImageDraw.Draw(c)
    if st == "paper":
        d.rectangle((w // 2 - 70, 0, w // 2 + 70, 26), fill=(255, 255, 255, 150))
    d.text((50, 36), label, font=F(BOLD, 32), fill=(*lab, 255)); d.text((50, 78), big, font=f, fill=(*txt, 255))
    c = shadowed(c)
    return c.rotate(-4, expand=True, resample=Image.BICUBIC) if st == "paper" else c


def stamp(text, color=RED):
    f = F(TF(), 96); tw = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=f))
    s = Image.new("RGBA", (tw + 96, 176), (0, 0, 0, 0)); d = ImageDraw.Draw(s)
    if THEME["stamp"] == "solid":
        d.rounded_rectangle((6, 6, tw + 89, 169), 88, fill=(*color, 255)); d.text((48, 22), text, font=f, fill=(255, 255, 255, 255))
    else:
        d.rounded_rectangle((6, 6, tw + 89, 169), 22, outline=(*color, 255), width=12, fill=(255, 255, 255, 235)); d.text((48, 22), text, font=f, fill=(*color, 255))
    return s


def bubble(text, sender="", side="left"):
    """A chat message: {"type": "bubble", "from": "mom", "text": "are you up??", "side": "left|right"}."""
    f = F(MED, 50); d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); words, lines, cur = text.split(), [], ""
    for wd in words:
        if cur and len(cur) + len(wd) > 20:
            lines.append(cur); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    tw = int(max(d0.textlength(l, font=f) for l in lines)); top = 46 if sender else 0
    c = Image.new("RGBA", (tw + 90, top + 56 + 64 * len(lines)), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    if sender:
        d.text((26, 0), sender, font=F(BOLD, 30), fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 200))
    d.rounded_rectangle((0, top, c.width - 1, c.height - 1), 44, fill=(40, 134, 255, 255) if side == "right" else (236, 236, 240, 255))
    for i, l in enumerate(lines):
        d.text((45, top + 24 + 64 * i), l, font=f, fill=(255, 255, 255, 255) if side == "right" else (20, 20, 24, 255))
    return shadowed(c, 14, 8, 110)


PBOX = (78, 320, 582, 1384)   # the phone inside a 660x1434 App Store screenshot
_img = {}


def asset(name):
    if name not in _img:
        _img[name] = Image.open(ASSETS / name).convert("RGBA")
    return _img[name]


def phone_cut(name):
    ph = asset(name).crop(PBOX); m = Image.new("L", ph.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((2, 2, ph.width - 3, ph.height - 3), 74, fill=255); ph.putalpha(m); return ph


def phone_screen(kind, n, total):
    ox, oy = PBOX[0], PBOX[1]
    if kind == "grid":
        return phone_cut("shot3.png")
    p = phone_cut("shot1.png"); d = ImageDraw.Draw(p)
    if kind == "pushups":     # the real push-up screen, with the counter redrawn
        d.rounded_rectangle((136 - ox, 1238 - oy, 524 - ox, 1310 - oy), 14, fill=(58, 54, 50, 255))
        d.text((330 - ox, 1266 - oy), f"{n} / {total}", font=F(MED, 28), fill=(255, 255, 255, 255), anchor="mm")
        d.rounded_rectangle((164 - ox, 1289 - oy, 496 - ox, 1299 - oy), 5, fill=(84, 80, 76, 255))
        d.rounded_rectangle((164 - ox, 1289 - oy, 164 - ox + int(332 * n / max(1, total)), 1299 - oy), 5, fill=(*ORANGE, 255))
        return p
    title, unit, foot = {"walk": (f"Walk {total} steps", "steps", "Keep walking to turn off your alarm"), "shake": ("Shake device", "", "Shake to turn off your alarm"),
                         "squats": (f"Do {total} squats", "squats", "Keep going to turn off your alarm")}.get(kind, (kind, "", ""))
    d.rounded_rectangle((92 - ox, 404 - oy, 568 - ox, 1366 - oy), 40, fill=(*DARK, 255)); d.rectangle((92 - ox, 404 - oy, 568 - ox, 460 - oy), fill=(*DARK, 255))
    d.text((330 - ox, 470 - oy), title, font=F(MED, 34), fill=(255, 255, 255, 255), anchor="mm")
    cx, cy, r = 330 - ox, 800 - oy, 150
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(48, 48, 50, 255), width=38)
    d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * n / max(1, total), fill=(*ORANGE, 255), width=38)
    d.text((cx, cy - (6 if unit else 0)), str(n), font=F(BOLD, 84), fill=(*ORANGE, 255), anchor="mm")
    if unit:
        d.text((cx, cy + 62), unit, font=F(MED, 26), fill=(255, 255, 255, 140), anchor="mm")
    d.text((cx, 1160 - oy), foot, font=F(MED, 22), fill=(255, 255, 255, 130), anchor="mm")
    return p


TILE = {"memory": (178, 776, 526, 1123), "walking": (554, 776, 902, 1123), "matching": (178, 1138, 526, 1485), "math": (554, 1138, 902, 1485),
        "house_hunt": (178, 1500, 526, 1847), "affirmation": (554, 1500, 902, 1847)}


def tile(name):
    return shadowed(rounded_img(asset("shot3_hi.png").crop(TILE[name]), 34))


def pop(im, layer, cx, cy, t, t0, dur=0.28, rot=0.0, slam=False, scale=1.0):
    if t < t0:
        return
    p = eo((t - t0) / dur)
    sc = ((2.6 - 1.6 * p) if slam else (0.55 + 0.45 * p + 0.07 * math.sin(min(1, (t - t0) / (dur * 1.7)) * math.pi))) * scale
    l = layer.rotate(rot, expand=True, resample=Image.BICUBIC) if rot else layer
    l = l.resize((max(2, int(l.width * sc)), max(2, int(l.height * sc))), Image.LANCZOS)
    if p < 1:
        l.putalpha(l.getchannel("A").point(lambda v: int(v * p)))
    im.alpha_composite(l, (int(cx - l.width / 2), int(cy - l.height / 2)))


_cache = {}


def C(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def draw_overlays(im, beat, t):
    a, b = beat["t0"], beat["t1"]
    for j, o in enumerate(beat.get("overlay", [])):
        at = a + float(o.get("at", 0.1)); kind = o["type"]; key = (beat["i"], j)
        if kind == "card":
            pop(im, C(key, lambda: app_card(o.get("label", "ALARM"), o["big"], COL.get(o.get("accent", "orange"), ORANGE))), o.get("x", W / 2 - 40), o.get("y", 320), t, at)
        elif kind == "stamp":
            pop(im, C(key, lambda: stamp(o["text"], COL.get(o.get("color", "red"), RED))), o.get("x", W / 2 + 110), o.get("y", 470), t, at, 0.14, rot=o.get("rot", -9), slam=True)
        elif kind == "phone":
            lo, hi, total = o.get("from", 0), o.get("to", 0), o.get("total", o.get("to", 10))
            n = int(round(lo + (hi - lo) * min(1, max(0, (t - at) / max(0.3, (b - at) * 0.9)))))
            jit = 10 * math.sin((t - a) * 40) if o["screen"] == "shake" else 0
            pop(im, shadowed(phone_screen(o["screen"], n, total)), o.get("x", W / 2 + 295) + jit, o.get("y", 440) + 8 * math.sin((t - a) * 2.2), t, at, 0.3, rot=o.get("rot", -5) + jit * 0.4, scale=o.get("scale", 0.6))
        elif kind == "bubble":
            pop(im, C(key, lambda: bubble(o["text"], o.get("from", ""), o.get("side", "left"))), o.get("x", W / 2 - 60), o.get("y", 330), t, at, 0.2, rot=o.get("rot", 0))
        elif kind == "tiles":
            for q, name in enumerate(o["names"][:3]):
                x, y, r = [(290, 330, 7), (780, 360, -6), (540, 520, 3)][q]
                pop(im, C((key, q), lambda: tile(name)), x, y, t, a + float(o.get("ats", [0.08, 0.78, 1.4])[q]), 0.2, rot=r, scale=0.9)


def draw_caption(im, beat, t):
    if not beat.get("caption"):
        return
    lines = C(("cap", beat["i"]), lambda: parse_caption(beat["caption"]))
    if THEME["cap_style"] == "quiet":      # small italic serif, the whole line at once; "cap_pos": "top" = the big hook line at the top
        top = beat.get("cap_pos") == "top"; font = QF(92 if top else 62); d = ImageDraw.Draw(im); sp = d.textlength(" ", font=font)
        if t < beat["line_at"]:
            return
        y = int(H * (0.085 if top else 0.655)); main, hlc = THEME["cap"]
        for ln in lines:
            x = (W - (sum(d.textlength(w, font=font) for w, _ in ln) + sp * (len(ln) - 1))) / 2
            for w, hl in ln:
                d.text((x + 2, y + 4), w, font=font, fill=(0, 0, 0, 150), stroke_width=5, stroke_fill=(0, 0, 0, 150))
                d.text((x, y), w, font=font, fill=(*(hlc if hl else main), 255), stroke_width=3, stroke_fill=(14, 14, 22, 235))
                x += d.textlength(w, font=font) + sp
            y += 112 if top else 80
        return
    font = F(TF(), 60); d = ImageDraw.Draw(im); sp = d.textlength(" ", font=font)
    main, hlc = THEME["cap"]; style = THEME["cap_style"]
    nchar = sum(len(w) for ln in lines for w, _ in ln) or 1
    y = int(H * (0.80 if beat["shot"] == "store_art" else 0.68)) - (40 if len(lines) > 2 else 0); acc = 0
    a, dur = beat["line_at"], beat["line_dur"]
    for ln in lines:
        lw = sum(d.textlength(w, font=font) for w, _ in ln) + sp * (len(ln) - 1); x = (W - lw) / 2
        if style != "outline" and t >= a + acc / nchar * dur * 0.85:
            box = Image.new("RGBA", (int(lw) + 56, 84), (0, 0, 0, 0))
            ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, 83), 20 if style == "box" else 42, fill=(16, 16, 20, 205) if style == "box" else (255, 255, 255, 240))
            im.alpha_composite(box, (int(x) - 28, y - 2)); d = ImageDraw.Draw(im)
        for w, hl in ln:
            if t >= a + acc / nchar * dur * 0.85:
                if style == "outline":
                    d.text((x + 3, y + 5), w, font=font, fill=(0, 0, 0, 150), stroke_width=9, stroke_fill=(0, 0, 0, 150))      # soft shadow: readable on bright scenes too
                    d.text((x, y), w, font=font, fill=(*(hlc if hl else main), 255), stroke_width=8, stroke_fill=(0, 0, 0, 255))
                else:
                    d.text((x, y), w, font=font, fill=(*(hlc if hl else main), 255))
            acc += len(w); x += d.textlength(w, font=font) + sp
        y += 80 if style == "outline" else 90


# ------------------------------------------------------------------ CTA card
def emoji(ch, size):
    try:
        e = Image.new("RGBA", (140, 140), (0, 0, 0, 0)); ImageDraw.Draw(e).text((0, 0), ch, font=ImageFont.truetype(EMOJI, 109), embedded_color=True)
        return e.crop(e.getbbox()).resize((size, size), Image.LANCZOS)
    except Exception:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def cta_layers():
    icon = Image.open(ASSETS / "icon.png"); L = {}
    g = np.linspace(0, 1, H)[:, None]; top, bot = np.array([244, 170, 128]), np.array([206, 100, 62])
    arr = (top * (1 - g) + bot * g)[:, None, :].repeat(W, 1).reshape(H, W, 3)
    yy, xx = np.mgrid[0:H, 0:W]; glow = np.exp(-(((xx - W / 2) / 620) ** 2 + ((yy - 330) / 520) ** 2))[..., None] * 22
    L["bg"] = Image.fromarray(np.clip(arr + glow, 0, 255).astype("uint8")).convert("RGBA")
    L["icon"] = shadowed(rounded_img(icon.resize((280, 280), Image.LANCZOS), 64), 26, 18, 90)
    t = Image.new("RGBA", (W, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    for i, s in enumerate(("Download", "Unsnooze Today")):
        d.text((W / 2 + 2, 70 + i * 128 + 5), s, font=F(BOLD, 112), fill=(120, 50, 20, 70), anchor="mm"); d.text((W / 2, 70 + i * 128), s, font=F(BOLD, 112), fill=(255, 255, 255, 255), anchor="mm")
    L["title"] = t
    cw = 920; c = rr((cw, 1400), 52, (255, 255, 255, 255)); d = ImageDraw.Draw(c)
    c.alpha_composite(rounded_img(icon.resize((124, 124), Image.LANCZOS), 28), (36, 36))
    d.text((186, 40), "Unsnooze - Challenge Alarm", font=F(BOLD, 36), fill=(0, 0, 0, 255)); d.text((186, 88), "Complete hard tasks to wake up", font=F(MED, 27), fill=(110, 110, 115, 255))
    d.text((186, 126), "★★★★★", font=F(STARS, 26), fill=(130, 130, 135, 255)); d.text((324, 126), "4.8", font=F(MED, 26), fill=(130, 130, 135, 255))
    d.rounded_rectangle((cw - 170, 62, cw - 36, 124), 31, fill=(236, 238, 245, 255)); d.text((cw - 103, 93), "GET", font=F(BOLD, 30), fill=(20, 110, 245, 255), anchor="mm")
    sw = (cw - 36 * 2 - 20 * 2) // 3; sh_ = int(sw * 1434 / 660)
    for i in range(3):
        c.alpha_composite(rounded_img(Image.open(ASSETS / f"shot{i + 1}.png").resize((sw, sh_), Image.LANCZOS), 26), (36 + i * (sw + 20), 190))
    c = c.crop((0, 0, cw, 190 + sh_ + 36)); m = Image.new("L", c.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, c.width - 1, c.height - 1), 52, fill=255)
    bgc = Image.new("RGBA", c.size, (255, 255, 255, 255)); bgc.alpha_composite(c); bgc.putalpha(m); L["card"] = shadowed(bgc, 30, 20, 80)
    bw, bh = 500, 148; bd = rr((bw, bh), 26, (0, 0, 0, 255)); d = ImageDraw.Draw(bd)
    d.rounded_rectangle((2, 2, bw - 3, bh - 3), 24, outline=(166, 166, 166, 255), width=3)
    bd.paste((255, 255, 255, 255), (26, 14), Image.open(ASSETS / "apple_mask.png").convert("L"))
    d.text((156, 22), "Download on the", font=F(MED, 30), fill=(255, 255, 255, 255)); d.text((154, 52), "App Store", font=F(MED, 64), fill=(255, 255, 255, 255))
    L["badge"] = shadowed(bd, 18, 10, 90)
    lb = Image.new("RGBA", (W, 110), (0, 0, 0, 0)); d = ImageDraw.Draw(lb); tw = d.textlength("LINK IN BIO", font=F(BOLD, 66)); x0 = (W - tw - 84) / 2
    d.text((x0, 12), "LINK IN BIO", font=F(BOLD, 66), fill=(255, 255, 255, 255)); lb.alpha_composite(emoji("👇", 70), (int(x0 + tw + 14), 18)); L["bio"] = lb
    return L


END = None      # spec["end"]: a per-video end card (tagline + two big lines) instead of the App Store listing card


def end_layers():
    L = C("cta", cta_layers); E = {}
    g = np.linspace(0, 1, H)[:, None]; top, bot = np.array([253, 243, 230]), np.array([247, 200, 164])
    E["bg"] = Image.fromarray((top * (1 - g) + bot * g)[:, None, :].repeat(W, 1).reshape(H, W, 3).astype("uint8")).convert("RGBA")

    def text(s, font, fill, track=0):
        d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); w = int(sum(d0.textlength(ch, font=font) + track for ch in s)) + 20
        im = Image.new("RGBA", (w, int(font.size * 1.45)), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 10
        for ch in s:
            d.text((x, 4), ch, font=font, fill=fill); x += d.textlength(ch, font=font) + track
        return im

    def fit(s, path, size, fill):
        d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        while size > 60 and d0.textlength(s, font=F(path, size)) > W - 150:
            size -= 6
        return text(s, F(path, size), fill)
    blk = INTER if os.path.exists(INTER) else BOLD
    E["name"] = text("Unsnooze", F(BOLD, 84), (226, 84, 36, 255)); E["tag"] = fit(END.get("tagline", "").upper(), BOLD, 38, (24, 30, 64, 255))
    big = (END.get("big") or ["GET UP.", "FOR REAL."])[:2]
    E["b1"] = fit(big[0].upper(), blk, 190, (24, 30, 64, 255)); E["b2"] = fit(big[-1].upper(), blk, 190, (226, 84, 36, 255))
    lb = text("LINK IN BIO", F(BOLD, 60), (24, 30, 64, 255)); l2 = Image.new("RGBA", (lb.width + 90, 110), (0, 0, 0, 0)); l2.alpha_composite(lb, (0, 10)); l2.alpha_composite(emoji("👇", 70), (lb.width + 6, 18)); E["bio"] = l2
    E["icon"], E["badge"] = L["icon"], L["badge"]
    return E


def end_card(t, t0):
    E = C("end", end_layers); im = E["bg"].copy(); u = t - t0

    def fade(key, y, at, rise=26):
        if u > at:
            p = eo((u - at) / 0.35); l = E[key].copy(); l.putalpha(l.getchannel("A").point(lambda v: int(v * p))); im.alpha_composite(l, (int((W - l.width) / 2), int(y + rise * (1 - p))))
    pop(im, E["icon"], W / 2, 400, t, t0, 0.3, scale=0.9)
    fade("name", 560, 0.12); fade("tag", 700, 0.3); fade("b1", 800, 0.45); fade("b2", 800 + E["b1"].height - 30, 0.6)
    yb = 800 + E["b1"].height + E["b2"].height + 70
    pop(im, E["badge"], W / 2, yb + 74, t, t0 + 0.95, 0.3, scale=1 + 0.03 * math.sin(max(0, u - 1.3) * 6.0))
    fade("bio", yb + 190, 1.2, 10)
    return im


def cta(t, t0):
    if END:
        return end_card(t, t0)
    L = C("cta", cta_layers); im = L["bg"].copy(); u = t - t0; card_h = L["card"].height; y_card = 640 + card_h / 2 - 60
    pop(im, L["icon"], W / 2, 200, t, t0, 0.3)
    if u > 0.12:
        p = eo((u - 0.12) / 0.3); l = L["title"].copy(); l.putalpha(l.getchannel("A").point(lambda v: int(v * p))); im.alpha_composite(l, (0, int(350 + 30 * (1 - p))))
    if u > 0.28:
        p = eo((u - 0.28) / 0.4); l = L["card"]; im.alpha_composite(l, (int((W - l.width) / 2), int(y_card - card_h / 2 + 500 * (1 - p))))
    y_b = y_card + card_h / 2 + 30
    pop(im, L["badge"], W / 2, y_b, t, t0 + 0.55, 0.3, scale=1 + 0.035 * math.sin(max(0, u - 0.9) * 6.0))
    if u > 0.8:
        p = eo((u - 0.8) / 0.3); l = L["bio"].copy(); l.putalpha(l.getchannel("A").point(lambda v: int(v * p))); im.alpha_composite(l, (0, int(y_b + 105 + 8 * math.sin(u * 5))))
    return im


# ------------------------------------------------------------------ audio
# Five original lo-fi beds (same instruments, different key / tempo / progression). A video uses spec["music"] if set
# (a name below), otherwise one is picked from its id, so tracks repeat now and then instead of changing every time.
TRACKS = {
    "sunday": (84, [[53, 57, 60, 64], [52, 55, 59, 62], [57, 60, 64, 67], [50, 53, 57, 60]], [41, 40, 45, 38]),   # the first one
    "slow_morning": (76, [[50, 53, 57, 60], [55, 59, 62, 65], [48, 52, 55, 59], [57, 60, 64, 67]], [38, 43, 36, 45]),
    "get_up": (92, [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 59], [55, 59, 62, 64]], [45, 41, 36, 43]),
    "late_night": (72, [[51, 55, 58, 62], [48, 51, 55, 58], [56, 60, 63, 67], [58, 62, 65, 68]], [39, 36, 44, 46]),
    "bright": (96, [[55, 59, 62, 66], [52, 55, 59, 62], [48, 52, 55, 59], [50, 54, 57, 60]], [43, 40, 36, 38]),
}
TRACK = "sunday"


# ------------------------------------------------------------------ looks (a new character + room every video)
SKINS = [("#f1c6a6", "#d49a7a", "#e89a8a"), ("#e0ac84", "#b88260", "#d8826a"), ("#c68a5e", "#9a6440", "#c86a4a"),
         ("#a5673f", "#7a4a2c", "#c0603f"), ("#7a4a2e", "#5a321c", "#9a4a32"), ("#5a3520", "#3e2414", "#7a3a26")]
HAIRS = ["#15100e", "#3a2416", "#6a3e1e", "#c89a50", "#a8442a", "#e8e0d0", "#e05a9a", "#3a6ad0", "#2a2a2a"]
HAIR_STYLES = ["curly", "buzz", "cap", "long", "bun", "afro", "spiky"]
OUTFITS = [("#7fe0b4", "#5cc49a", "#5a5d6a"), ("#f2a03a", "#d0802a", "#2e3a5a"), ("#e8556a", "#c03a50", "#3a3a40"),
           ("#5a8af0", "#3e6ad0", "#d8c8a8"), ("#b07ae8", "#8a58c8", "#2a2a30"), ("#f4f0e6", "#d8d2c4", "#4a6a9a"),
           ("#2a2a30", "#404048", "#8a8a90"), ("#f2d24a", "#d0b030", "#3a4a3a"), ("#3a9a6a", "#2a7a52", "#c8b89a"),
           ("#ff8ab0", "#e06a92", "#f4f0e6")]
ROOMS = [  # name, wall, wallTex, floorKind, floor colours, floorLine, quilt, rug, rugTrim, curtain, poster, wood, frame, sheet, extras
    ("cozy bedroom", "#b9c8f0", "plain", "wood", ["#9a6a42", "#8a5c38", "#a37046", "#91633c"], "#5a3a22", ["#d9534a", "#3f6fb5", "#e8b23a", "#4fa07a", "#9a5fb0", "#f0e6d0"], "#d9603a", "#f2dcae", "#5568c0", "#f06a39", "#7a4a28", "#e8e2d4", "#eeeae0", {"plant": True}),
    ("brick loft", "#e0a088", "brick", "wood", ["#5a3a28", "#4e3222", "#62402c"], "#2e1c12", ["#2e3a4a", "#d8d0c0", "#8a2e2a", "#2e3a4a"], "#3a4a5a", "#d8d0c0", "#2e2e34", "#e8c04a", "#3a2a20", "#2a2a2e", "#d8d0c0", {"lights": True, "lightsColor": "#ffd27a"}),
    ("dorm room", "#d8dce0", "block", "tile", ["#c8c0b0", "#bcb4a4"], "#9a9284", ["#3a5a9a", "#f2f2f2", "#3a5a9a", "#e8b23a"], "#3a5a9a", "#f2f2f2", "#8a9aa8", "#e8556a", "#b89a70", "#9aa4ae", "#f4f4f4", {"art": "#3a5a9a", "plant": False}),
    ("pastel room", "#f8c8d8", "dots", "carpet", ["#f0e4dc", "#e8dcd4"], "#d8c4b8", ["#ffb0c8", "#b0e0f0", "#fff0b0", "#c8b0f0"], "#b0e0f0", "#ffffff", "#ffffff", "#9a7ae8", "#e8d0b8", "#ffffff", "#ffffff", {"lights": True, "lightsColor": "#ffb0d0", "plant": True}),
    ("green studio", "#a8d8b0", "stripes", "wood", ["#c89a60", "#b88a54", "#d0a468"], "#8a6238", ["#f2e2b0", "#3a7a5a", "#e07a3a", "#f2e2b0"], "#e8b23a", "#3a7a5a", "#f2e2b0", "#3a7a5a", "#a07040", "#f2e2b0", "#fbf6e8", {"plant": True, "art": "#e07a3a"}),
    ("night owl den", "#7a6ad0", "plain", "carpet", ["#3a3450", "#342e48"], "#4a4466", ["#2a2a40", "#e8556a", "#2a2a40", "#5ac8e8"], "#5ac8e8", "#2a2a40", "#2a2a40", "#5ac8e8", "#2a2a34", "#1a1a22", "#d8d4f0", {"lights": True, "lightsColor": "#5ac8e8"}),
    ("sunny apartment", "#fbe6b0", "plain", "tile", ["#e8d8c0", "#dccab0"], "#c0ac90", ["#f2a03a", "#ffffff", "#5a8af0", "#ffffff"], "#5a8af0", "#fbe6b0", "#f2a03a", "#5a8af0", "#d8b080", "#ffffff", "#ffffff", {"plant": True, "art": "#5a8af0"}),
    ("gamer room", "#3a3a48", "block", "carpet", ["#2a2a32", "#26262e"], "#3a3a46", ["#e8556a", "#1a1a22", "#5af08a", "#1a1a22"], "#1a1a22", "#5af08a", "#e8556a", "#5af08a", "#1a1a22", "#2a2a32", "#c8c8d0", {"lights": True, "lightsColor": "#e8556a", "plant": False}),
]
PACKS = ["#f06a39", "#3a5a9a", "#2a2a30", "#e8b23a", "#3a9a6a", "#e8556a"]


def pick_look(spec, spec_path, name):
    """spec["look"] wins. Otherwise pick a character + room that differs from every recent animation, and save it in the spec."""
    import zlib
    if spec.get("look"):
        return spec["look"]
    used = []
    for f in sorted((HERE.parent / "work" / "anim").glob("*/spec.json"), key=lambda q: q.stat().st_mtime)[-12:]:
        try:
            lk = json.loads(f.read_text()).get("look") or {}
        except Exception:
            continue
        if f.resolve() != spec_path.resolve() and f.parent.name != "queue":
            used.append(lk or {"room": "cozy bedroom", "hairStyle": "curly", "skin": "#a5673f", "top": "#7fe0b4"})  # the original look
    import random
    rng = random.Random(zlib.crc32(name.encode()))
    rooms_recent = [u.get("room") for u in used[-len(ROOMS) + 1:]]
    room = next((r for r in rng.sample(ROOMS, len(ROOMS)) if r[0] not in rooms_recent), rng.choice(ROOMS))
    recent_chars = {(u.get("skin"), u.get("hairStyle"), u.get("top")) for u in used}
    for _ in range(200):
        sk, hs, hc, of = rng.choice(SKINS), rng.choice(HAIR_STYLES), rng.choice(HAIRS), rng.choice(OUTFITS)
        if (sk[0], hs, of[0]) not in recent_chars and not any(u.get("hairStyle") == hs or u.get("top") == of[0] or u.get("skin") == sk[0] for u in used[-3:]):
            break
    (rn, wall, wtex, fk, floor, fline, quilt, rug, rtrim, curtain, poster, wood, frame, sheet, extra) = room
    look = {"name": f"{rn} / {hs} hair", "room": rn, "skin": sk[0], "skinD": sk[1], "cheek": sk[2], "hair": hc, "hairStyle": hs,
            "glasses": rng.random() < 0.3, "beard": hs in ("buzz", "cap", "curly", "afro") and rng.random() < 0.25, "freckles": rng.random() < 0.25,
            "top": of[0], "top2": of[1], "pants": of[2], "shoe": rng.choice(["#f2f0ea", "#2a2a30", "#e8556a", "#5a8af0"]), "sole": rng.choice(["#f06a39", "#f2f0ea", "#2a2a30"]),
            "beardColor": hc if hc in ("#15100e", "#3a2416", "#6a3e1e", "#c89a50", "#a8442a", "#2a2a2a") else "#2a1a12", "pack": rng.choice(PACKS), "capColor": rng.choice(PACKS), "wall": wall, "wallTex": wtex, "floorKind": fk, "floor": floor, "floorLine": fline,
            "quilt": quilt, "rug": rug, "rugTrim": rtrim, "curtain": curtain, "poster": poster, "wood": wood, "frame": frame, "sheet": sheet,
            "plant": False, "lights": False, **extra}
    # body build + clothes (2026-11-28): never the same figure as the last video
    last = used[-1] if used else {}
    for _ in range(50):
        b = dict(tall=rng.choice([0.9, 1.0, 1.08]), wide=rng.choice([0.86, 1.0, 1.24]), headS=rng.choice([0.9, 1.0, 1.2]),
                 sleeves=rng.choice(["long", "short"]), shorts=rng.random() < 0.35, acc=rng.choice(["none", "none", "headphones", "scarf"]))
        if (b["wide"], b["headS"]) != (last.get("wide", 1.0), last.get("headS", 1.0)) and (b["wide"], b["headS"], b["tall"]) != (1.0, 1.0, 1.0):
            break
    look.update(b)
    spec["look"] = look
    if spec_path.name == "spec.json":
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    return look


def pick_track(spec, name):
    import zlib
    t = spec.get("music")
    return t if t in TRACKS else sorted(TRACKS)[zlib.crc32(name.encode()) % len(TRACKS)]


def music(n, lift):
    """Original lo-fi bed: soft electric-piano chords, then bass + drums from the 'lift' time."""
    bpm, chords, bass = TRACKS[TRACK]; beat = 60 / bpm; bar = beat * 4; out = np.zeros(n + SR * 4); N = lambda m: 440 * 2 ** ((m - 69) / 12)

    def ep(f, dur, vol):
        x = np.arange(int(dur * SR)) / SR; e = np.minimum(1, x / 0.01) * np.exp(-x * 1.6)
        return vol * e * (np.sin(TAU * f * x) + 0.35 * np.sin(TAU * 2 * f * x) * np.exp(-x * 4) + 0.12 * np.sin(TAU * 3 * f * x) * np.exp(-x * 7)) * (1 + 0.08 * np.sin(TAU * 4.5 * x))

    def add(x, t0):
        i0 = int(t0 * SR)
        if i0 < len(out):
            x = x[: len(out) - i0]; out[i0:i0 + len(x)] += x
    rng = np.random.default_rng(4); t, b = 0.0, 0
    while t < n / SR:
        ch = chords[b % 4]; full = t >= lift - 0.05
        for j, m in enumerate(ch):
            add(ep(N(m), bar, 0.16), t + j * 0.035); add(ep(N(m + (12 if j == 3 else 0)), beat * 2, 0.08), t + beat * 2.5 + j * 0.02)
        if full:
            for q in (0, 1.5, 2.5):
                x = np.arange(int(beat * 1.2 * SR)) / SR; add(0.32 * np.sin(TAU * N(bass[b % 4]) * x) * np.minimum(1, x / 0.01) * np.exp(-x * 3), t + q * beat)
            for q in range(4):
                x = np.arange(int(0.25 * SR)) / SR
                if q in (0, 2):
                    add(0.55 * np.sin(TAU * (48 + 70 * np.exp(-x * 30)) * x) * np.exp(-x * 14), t + q * beat)
                else:
                    nz = rng.standard_normal(len(x)); add(0.10 * (nz - np.convolve(nz, np.ones(8) / 8, "same")) * np.exp(-x * 22) + 0.2 * np.sin(TAU * 190 * x) * np.exp(-x * 26), t + q * beat)
                for h in (0, 0.5):
                    xh = np.arange(int(0.06 * SR)) / SR; nz = rng.standard_normal(len(xh)); add(0.035 * (nz - np.convolve(nz, np.ones(4) / 4, "same")) * np.exp(-xh * 70), t + (q + h) * beat)
        t += bar; b += 1
    out = np.convolve(out, np.ones(6) / 6, "same")[:n]
    return out / (np.abs(out).max() + 1e-9)


def build_audio(path, beats, total, cta0, voice):
    n = int(total * SR); a = np.zeros(n); tt = np.arange(n) / SR

    def put(x, t0, vol=1.0):
        i0 = int(max(0, t0) * SR); x = x[: max(0, n - i0)]; a[i0:i0 + len(x)] += x * vol

    def tone(t0, dur, f, vol):
        x = np.arange(int(dur * SR)) / SR; env = np.minimum(1, x / 0.006) * np.minimum(1, (dur - x) / 0.03)
        put(env * (0.5 * np.sin(TAU * f * x) + 0.5 * np.sign(np.sin(TAU * f * x))), t0, vol)

    def thud(t0):
        x = np.arange(int(0.22 * SR)) / SR; put(np.sin(TAU * (90 - 120 * x) * x) * np.exp(-x * 22), t0, 0.5)

    def chime(t0, notes, vol):
        for k, f in enumerate(notes):
            x = np.arange(int(1.2 * SR)) / SR; put(np.exp(-x * 4) * np.sin(TAU * f * x), t0 + k * 0.1, vol)
    ringf = sorted(glob.glob(str(ROOT / "sounds/alarm/alarm-clock-loop*.mp3"))) or sorted(glob.glob(str(ROOT / "sounds/alarm/*.mp3")))
    ring = load_audio(ringf[0]) if ringf else np.zeros(SR)
    ring = ring / (np.abs(ring).max() + 1e-9)

    def ring_span(t0, t1, vol=0.10):
        m = int((t1 - t0) * SR)
        if m <= SR // 10:
            return
        x = np.resize(ring, m).copy(); f = int(0.03 * SR); x[-f:] *= np.linspace(1, 0, f); x[:f] *= np.linspace(0, 1, f); put(x, t0, vol)
    rs = np.random.default_rng(7)

    def lp(x, k):
        return np.convolve(x, np.ones(k) / k, "same")

    def sfx(name, t0, vol=1.0, dur=None):
        """Synthesised sound effects (no files, no licences). Beats take "sfx": [{"name": "bus", "at": 0.2, "vol": 1, "dur": 2}]."""
        X = lambda sec: np.arange(int(sec * SR)) / SR
        if name == "whoosh":
            x = X(dur or 0.34); nz = lp(rs.standard_normal(len(x)), 14); put(nz / (np.abs(nz).max() + 1e-9) * np.sin(np.pi * x / x[-1]) ** 2, t0, 0.16 * vol)
        elif name == "pop":
            x = X(0.09); put(np.sin(TAU * (520 + 5200 * x) * x) * np.exp(-x * 40), t0, 0.22 * vol)
        elif name == "ding":
            x = X(0.9); put((np.sin(TAU * 1318 * x) + 0.6 * np.sin(TAU * 1976 * x)) * np.exp(-x * 5), t0, 0.12 * vol)
        elif name == "bell":
            x = X(dur or 1.1); put((np.sin(TAU * 2200 * x) + np.sin(TAU * 2930 * x) + 0.6 * np.sin(TAU * 3650 * x)) / 2.6 * (0.55 + 0.45 * np.sign(np.sin(TAU * 26 * x))) * np.minimum(1, (x[-1] - x) / 0.15), t0, 0.10 * vol)
        elif name == "bus":
            x = X(dur or 2.4); nz = lp(rs.standard_normal(len(x)), 220); nz = nz / (np.abs(nz).max() + 1e-9)
            eng = (0.6 * nz + 0.5 * np.sin(TAU * (52 + 14 * x) * x) * (1 + 0.3 * np.sin(TAU * 11 * x))) * np.minimum(1, x / 0.2) * np.minimum(1, (x[-1] - x) / 0.9)
            put(eng, t0, 0.30 * vol); h = X(0.45); hz = rs.standard_normal(len(h)); put((hz - lp(hz, 6)) * np.exp(-h * 7), t0, 0.07 * vol)
        elif name == "steps":
            x = X(0.12); k = 0.0
            while k < (dur or 1.2):
                put(np.sin(TAU * (130 - 300 * x) * x) * np.exp(-x * 34), t0 + k, 0.22 * vol); k += 0.27
        elif name == "scratch":
            x = X(0.32); nz = rs.standard_normal(len(x)); put(lp(nz, 5) * np.sin(TAU * (900 - 1900 * x) * x) * np.minimum(1, (x[-1] - x) / 0.05), t0, 0.22 * vol)
        elif name == "sad":
            for i, f0 in enumerate((233, 220, 207, 196)):
                x = X(0.34 if i < 3 else 0.75); f = f0 * (1 - 0.03 * x / x[-1]) * (1 + 0.012 * np.sin(TAU * 6 * x))
                put(lp(np.sign(np.sin(TAU * np.cumsum(f) / SR)) * 0.5 + np.sin(TAU * np.cumsum(f) / SR), 30) * np.minimum(1, x / 0.03) * np.minimum(1, (x[-1] - x) / 0.08), t0 + i * 0.36, 0.11 * vol)
        elif name == "tick":
            x = X(0.03); k = 0.0
            while k < (dur or 2.0):
                put(np.sin(TAU * (2400 if int(k * 2) % 2 == 0 else 1900) * x) * np.exp(-x * 160), t0 + k, 0.14 * vol); k += 0.5
        elif name == "flop":
            x = X(0.3); put(np.sin(TAU * (80 - 90 * x) * x) * np.exp(-x * 16), t0, 0.5 * vol); nz = lp(rs.standard_normal(len(x)), 40); put(nz / (np.abs(nz).max() + 1e-9) * np.exp(-x * 14), t0, 0.14 * vol)
        elif name == "sparkle":
            for i, f in enumerate((1568, 1976, 2349, 3136, 3951)):
                x = X(0.5); put(np.sin(TAU * f * x) * np.exp(-x * 9), t0 + i * 0.06, 0.06 * vol)
        elif name == "thud":
            thud(t0)
    for i, b in enumerate(beats):          # a soft whoosh on every cut, a pop when a card / phone / tile / bubble appears, plus the beat's own "sfx"
        if i and b["shot"] != "cta":
            sfx("whoosh", b["t0"] - 0.12, 0.8)
        for o in b.get("overlay", []):
            if o["type"] == "tiles":
                for q in range(len(o["names"][:3])):
                    sfx("pop", b["t0"] + float(o.get("ats", [0.08, 0.78, 1.4])[q]))
            elif o["type"] != "stamp":
                sfx("ding" if o["type"] == "bubble" else "pop", b["t0"] + float(o.get("at", 0.1)))
        for e in b.get("sfx", []):
            sfx(e["name"], b["t0"] + float(e.get("at", 0)), float(e.get("vol", 1)), e.get("dur"))
    for b in beats:
        s, t0, t1 = b["shot"], b["t0"], b["t1"]
        if s == "across_room_go":      # rings until he taps it at 78% of the shot
            ring_span(t0, t0 + 0.78 * (t1 - t0)); sfx("pop", t0 + 0.78 * (t1 - t0))
        if s == "back_to_bed":
            sfx("flop", t0 + 0.62 * (t1 - t0))
        if s in SMOKE:
            t = t0
            while t < t1 - 0.2:
                tone(t, 0.16, 3150, 0.05); t += 0.42
        if s in RINGING:
            ring_span(t0, t1)
        if s == "snooze_slaps":
            for r0, r1 in ((t0, t0 + 0.4), (t0 + 0.68, t0 + 1.05), (t0 + 1.33, t0 + 1.6)):
                ring_span(r0, r1); thud(r1)
        if s == "alarm_slapped":      # rings, gets slapped quiet at 0.75 / 1.5 / 2.25 s, starts again
            for r0, r1 in ((t0, t0 + 0.75), (t0 + 0.97, t0 + 1.5), (t0 + 1.72, t0 + 2.25), (t0 + 2.47, t1)):
                ring_span(r0, min(r1, t1))
                if r1 < t1 and r1 > t0 + 0.8:
                    thud(r1)
        if s == "alarm_thrown":
            thud(t0 + 0.8); ring_span(t0 + 1.6, t1)
        if s == "floor_ping":
            chime(t0 + 0.38, (1319, 1760), 0.12); ring_span(t0 + 0.6, t1)
        if s == "stretch_win":
            ring_span(t0, t0 + 0.9); chime(t0 + 0.9, (784, 988, 1175), 0.10)
        for o in b.get("overlay", []):
            if o["type"] == "stamp":
                thud(t0 + float(o.get("at", 0.1)))
    sfx("whoosh", cta0 - 0.05, 1.3, 0.6); chime(cta0 + CTA_IN - 0.1, (523, 659, 784, 1047), 0.05)
    a *= 0.6
    vo = np.zeros(n)
    for b in beats:
        if b.get("vo") is not None:
            v = b["vo"]; i0 = int(b["line_at"] * SR); v = v[: n - i0]; vo[i0:i0 + len(v)] += v * 0.9
    env = np.abs(vo); k = int(0.25 * SR); env = np.clip(np.convolve(env, np.ones(k) / k, mode="same") / 0.08, 0, 1)
    lift = next((b["t0"] for b in beats if b.get("lift")), beats[len(beats) // 2]["t0"])
    mg = float(_cfg().get("music_gain", 0.48))      # louder bed (Chika, 2026-11-28; was 0.34), ducked to half under the voice
    a += music(n, lift) * ((mg - 0.5 * mg * env) if voice else mg + 0.08)
    a += vo
    a = np.tanh(a * 1.1) * 0.95 * np.minimum(1, (total - tt) / 0.3)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype("<i2").tobytes())


# ------------------------------------------------------------------ main
def main():
    spec_path = Path(sys.argv[1]).resolve(); snap = "--snap" in sys.argv
    spec = json.loads(spec_path.read_text()); work = spec_path.parent; name = spec.get("id") or spec_path.stem
    beats = [dict(b, i=i) for i, b in enumerate(spec["beats"])]
    global TRACK
    TRACK = pick_track(spec, name); print("music track:", TRACK)
    global LOOK
    LOOK = pick_look(spec, spec_path, name); print("look:", LOOK.get("name", "custom"))
    global THEME
    th = pick_theme(spec, spec_path, name); THEME = THEMES[th]; print("theme:", th)
    global END, SOFTR
    END = None; SOFTR = spec.get("render") == "soft"      # the ending is ALWAYS the original download card (Chika, 2026-11-28: "you changed the original CTA graphic at the end... please don't do that"); spec["end"] is ignored
    for b in beats:
        if b["shot"] not in SHOTS and not (HERE / "lowpoly" / "index.html").read_text().count(f"S.{b['shot']} ="):
            sys.exit(f"unknown shot '{b['shot']}'. Shots: {sorted(SHOTS)} (or add S.{b['shot']} to anim/lowpoly/index.html)")
    global SEP
    SEP = spec.get("voice_sep")
    cta_line = spec.get("cta_line", "Download Unsnooze. Link in bio!")
    lines = [b.get("line") or re.sub(r"[*\n]", " ", b.get("caption", "")) for b in beats] + [cta_line]
    # voice: pre-made lines in spec["voice_dir"], else ElevenLabs, else captions only
    vdir = work / spec["voice_dir"] if spec.get("voice_dir") else work / "vo"
    have = lambda: all(glob.glob(str(vdir / f"l{i + 1:02d}.*")) for i in range(len(lines)))
    voice = False
    if spec.get("voice", True) and not snap:
        voice = have() or (elevenlabs(lines, vdir) and have())
    if "--require-voice" in sys.argv and not snap and not voice:
        sys.exit("voice: REQUIRED but missing -> no video built (fix ElevenLabs access, or skip tonight's animation)")
    cont = voice and (vdir / "continuous.json").exists()      # one take cut at the pauses: keep its own pacing and levels
    if cont:
        vos = [load_audio(glob.glob(str(vdir / f"l{i + 1:02d}.*"))[0]) for i in range(len(lines))]
        pk = max(np.abs(v).max() for v in vos) + 1e-9; vos = [v / pk for v in vos]
        for v in vos:      # tiny fades so no cut can click
            k = min(len(v) // 2, int(0.03 * SR)); v[:k] *= np.linspace(0, 1, k); v[-k:] *= np.linspace(1, 0, k)
    else:
        vos = [trim(load_audio(glob.glob(str(vdir / f"l{i + 1:02d}.*"))[0])) for i in range(len(lines))] if voice else [None] * len(lines)
        vos = [None if v is None else v / (np.abs(v).max() + 1e-9) for v in vos]
    t = 0.0
    for b, v in zip(beats, vos[:-1]):
        txt = re.sub(r"\[[a-z ]+\]|[*]", "", b.get("line") or b.get("caption", ""))
        ld = len(v) / SR if v is not None else max(0.9, len(txt) * 0.062)
        dur = max(float(b.get("min", 1.0 if cont else 1.3)), ld + (0.06 if cont else 0.3 if v is not None else 0.75)) if "dur" not in b else float(b["dur"])
        b.update(t0=round(t, 3), t1=round(t + dur, 3), line_at=round(t + (0.0 if cont else 0.12), 3), line_dur=ld, vo=v); t += dur
    cta0 = round(t, 3); cta_dur = max(3.6, (len(vos[-1]) / SR + 1.9) if vos[-1] is not None else 3.6); total = round(cta0 + cta_dur, 2)
    shots = []
    for b in beats:
        if b.get("then"):      # {"shot": "thinking", "then": {"shot": "shake_phone", "at": 1.6}}
            cut = b["t0"] + float(b["then"]["at"]); shots += [dict(name=b["shot"], t0=b["t0"], t1=cut, p=b.get("p", {})), dict(name=b["then"]["shot"], t0=cut, t1=b["t1"], p=b["then"].get("p", {}))]
        else:
            shots.append(dict(name=b["shot"], t0=b["t0"], t1=b["t1"], p=b.get("p", {})))
    (work / "spec.json").write_text(json.dumps(dict(fps=FPS, total=cta0, shots=shots), indent=1)) if spec_path.name != "spec.json" else None
    rdir = work / "render"; rdir.mkdir(exist_ok=True); (rdir / "spec.json").write_text(json.dumps(dict(fps=FPS, total=cta0, shots=shots, id=name, look=LOOK, render=spec.get("render", "ps1")), indent=1))
    lp = HERE / "lowpoly"
    if not (lp / "node_modules" / "playwright-core").exists():
        subprocess.run(["npm", "install", "--silent", "--no-audit", "--no-fund"], cwd=lp, check=True)
    if snap:
        times = ",".join(f"{(s['t0'] + s['t1']) / 2:.2f}" for s in shots)
        subprocess.run(["node", str(lp / "render.mjs"), str(rdir), "snap", times], check=True)
        fs = sorted(glob.glob(str(rdir / "snaps" / "s_*.png")))[-len(shots):]
        sh = Image.new("RGB", (180 * len(fs), 320))
        for i, f in enumerate(fs):
            sh.paste(Image.open(f).convert("RGB").resize((180, 320), Image.NEAREST), (i * 180, 0))
        sh.save(work / f"{name}.snaps.jpg"); print(json.dumps({"snaps": str(work / f'{name}.snaps.jpg'), "shots": [s["name"] for s in shots]})); return
    r = subprocess.run(["node", str(lp / "render.mjs"), str(rdir), "all"], capture_output=True, text=True)
    nfr = len(glob.glob(str(rdir / "frames" / "f_*.png")))
    if nfr < int(cta0 * FPS) - 2:
        sys.exit(f"3D render failed ({nfr} frames):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    art = None

    last = {}

    def frame(t):
        nonlocal art
        if t >= cta0:      # the card rises over the last shot (0.55 s) instead of cutting to it (Chika, 2026-11-28)
            u = t - cta0; card = cta(t, cta0 + CTA_IN * 0.5).convert("RGB")
            if u >= CTA_IN:
                return card
            if "im" not in last:
                last["im"] = scene(cta0 - 1.0 / FPS, False)
            pr = eo(u / CTA_IN); im = Image.eval(last["im"], lambda v: int(v * (1 - 0.45 * pr))); im.paste(card, (0, int(H * (1 - pr)))); return im
        return scene(t, True)

    def scene(t, cap):
        nonlocal art
        b = next((x for x in beats if x["t0"] <= t < x["t1"]), beats[-1])
        if b["shot"] == "store_art":      # the real "15+ ways to wake up" App Store screenshot, slow scroll
            art = art or Image.open(ASSETS / "shot3_hi.png").convert("RGB").resize((1188, 2580), Image.LANCZOS)
            u = eo((t - b["t0"]) / (b["t1"] - b["t0"])); ent = 1 - eo((t - b["t0"]) / 0.3); y0 = 60 + 430 * u
            fr = art.crop((54, int(y0), 54 + W, int(y0) + H))
            if ent > 0:
                bg = Image.new("RGB", (W, H), (244, 137, 91)); bg.paste(fr, (0, int(H * 0.5 * ent))); fr = bg
            im = fr.convert("RGBA")
        else:
            k = min(int(round(t * FPS)), nfr - 1)
            im = Image.open(rdir / "frames" / f"f_{k:05d}.png").convert("RGB").resize((W, H), Image.LANCZOS if SOFTR else Image.NEAREST).convert("RGBA")
            if SOFTR:      # gentle vignette
                im.alpha_composite(C("vig", lambda: Image.fromarray(np.dstack([np.zeros((H, W, 3), "uint8"), (np.clip((np.hypot(*(np.mgrid[0:H, 0:W] - np.array([H / 2, W / 2])[:, None, None]) / np.array([H * 0.62, W * 0.62])[:, None, None]) - 0.55) / 0.75, 0, 1) ** 1.6 * 150).astype("uint8")]), "RGBA")))
            draw_overlays(im, b, t)
        if cap:
            draw_caption(im, b, t)
        return im.convert("RGB")
    wav = work / f"{name}.wav"; build_audio(wav, beats + [dict(shot="cta", t0=cta0, t1=total, line_at=cta0 + CTA_IN + 0.1, vo=vos[-1])], total, cta0, voice)
    out = work / f"{name}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
                          "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for i in range(int(total * FPS)):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
    # contact sheet: the middle of every beat + the CTA
    ts = [(b["t0"] + b["t1"]) / 2 + 0.25 * (b["t1"] - b["t0"]) for b in beats] + [cta0 + 2.5]
    sh = Image.new("RGB", (216 * min(8, len(ts)), 384 * math.ceil(len(ts) / 8)))
    for i, t in enumerate(ts):
        sh.paste(frame(t).resize((216, 384)), ((i % 8) * 216, (i // 8) * 384))
    sh.save(work / f"{name}.sheet.jpg", quality=85)
    import shutil; shutil.rmtree(rdir / "frames", ignore_errors=True); wav.unlink(missing_ok=True)
    print(json.dumps({"video": str(out), "sheet": str(work / f"{name}.sheet.jpg"), "seconds": total, "voice": "elevenlabs" if voice else "none",
                      "beats": [(b["shot"], b["t0"], b["t1"]) for b in beats]}))


if __name__ == "__main__":
    main()
