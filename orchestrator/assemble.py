"""Turn generated clips + plan into a finished 9:16 ad with on-screen text (Arabic or English)."""
import glob
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont, features

# With libraqm (bundled in Pillow wheels) Pillow shapes Arabic itself; otherwise we pre-shape.
RAQM = features.check("raqm")

W, H, FPS = 720, 1280, 24
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_font(lang):
    # Tajawal (SIL Open Font License) covers Arabic + Latin + digits, so mixed captions render cleanly
    cands = [os.path.join(ROOT, "fonts", "Tajawal-Bold.ttf")] if (RAQM or lang != "ar") else []
    if lang == "ar":
        cands += glob.glob(os.path.join(ROOT, "fonts", "*Arabic*Bold*.ttf"))
        cands += ["/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
                  "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
                  "/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf"]
    cands += glob.glob(os.path.join(ROOT, "fonts", "NotoSans-Bold.ttf"))
    cands += ["/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for c in cands:
        if os.path.exists(c):
            return c
    raise RuntimeError("no usable font found (install fonts-noto-core)")


def _font(lang, size):
    engine = ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC
    return ImageFont.truetype(_find_font(lang), size, layout_engine=engine)


def _kw(lang):
    return {"direction": "rtl", "language": "ar"} if (RAQM and lang == "ar") else {}


def _shape(text, lang):
    if lang != "ar" or RAQM:
        return text
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(text))


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_overlay(text, lang, path, y_frac=0.70, size=58, big=False):
    """Transparent PNG with a rounded dark box and centered text."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not text.strip():
        img.save(path)
        return path
    d = ImageDraw.Draw(img)
    font = _font(lang, size)
    # wrap on logical text (words), then shape each line for display
    lines = _wrap(d, text, font, W - 140) if lang != "ar" else _wrap_ar(d, text, font, W - 140, lang)
    shaped = [_shape(ln, lang) for ln in lines]
    lh = int(size * 1.45)
    box_h = lh * len(shaped) + 40
    widths = [d.textlength(s, font=font, **_kw(lang)) for s in shaped]
    box_w = int(min(W - 60, max(widths) + 70))
    y0 = int(H * y_frac - box_h / 2)
    x0 = (W - box_w) // 2
    fill = (0, 0, 0, 175) if not big else (10, 10, 14, 200)
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=28, fill=fill)
    for i, s in enumerate(shaped):
        tw = d.textlength(s, font=font, **_kw(lang))
        d.text(((W - tw) / 2, y0 + 20 + i * lh), s, font=font, fill=(255, 255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 255), **_kw(lang))
    img.save(path)
    return path


def _wrap_ar(d, text, font, max_w, lang):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(_shape(test, lang), font=font, **_kw(lang)) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def watermark(path, label):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f_ar = _font("ar", 54)
    f_en = _font("en", 50)
    ar_txt = _shape("معاينة", "ar")
    en_txt = f"PREVIEW  {label}"
    for row in range(0, H * 2, 260):
        for col in range(-400, W * 2, 900):
            x = col + (row // 260 % 2) * 350
            d.text((x, row), ar_txt, font=f_ar, fill=(255, 255, 255, 70), **_kw("ar"))
            d.text((x + d.textlength(ar_txt, font=f_ar, **_kw("ar")) + 30, row + 4), en_txt, font=f_en, fill=(255, 255, 255, 70))
    layer = layer.rotate(28, resample=Image.BICUBIC)
    img.alpha_composite(layer.crop((W // 2, H // 2, W // 2 + W, H // 2 + H)))
    img.save(path)
    return path


def corner_badge(path, label):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font("en", 26)
    tw = d.textlength(label, font=font)
    d.rounded_rectangle([W - tw - 44, 34, W - 18, 80], radius=14, fill=(0, 0, 0, 120))
    d.text((W - tw - 31, 40), label, font=font, fill=(255, 255, 255, 210))
    img.save(path)
    return path


def end_card(path, cta, lang, photo=None):
    img = Image.new("RGB", (W, H), (14, 16, 22))
    if photo and os.path.exists(photo):
        try:
            p = Image.open(photo).convert("RGB")
            p.thumbnail((W - 120, int(H * 0.55)))
            img.paste(p, ((W - p.width) // 2, int(H * 0.12)))
        except Exception:  # noqa: BLE001 - bad image -> plain card
            pass
    img.save(path)
    ov = text_overlay(cta, lang, path + ".txt.png", y_frac=0.80 if photo else 0.5, size=66, big=True)
    base = Image.open(path).convert("RGBA")
    base.alpha_composite(Image.open(ov))
    base.convert("RGB").save(path)
    os.remove(ov)
    return path


def _ff(args):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-800:])


def build(clips, plan, lang, out_path, work, photo=None, mode="preview", label="@ReelsArabiBot"):
    """mode: preview (big watermark) | badge (small corner brand) | clean"""
    os.makedirs(work, exist_ok=True)
    extra = None
    if mode == "preview":
        extra = watermark(os.path.join(work, "wm.png"), label)
    elif mode == "badge":
        extra = corner_badge(os.path.join(work, "badge.png"), label)

    segs = []
    scenes = plan.get("scenes", [])
    for i, clip in enumerate(clips):
        cap = scenes[i]["caption"] if i < len(scenes) else ""
        ov = text_overlay(cap, lang, os.path.join(work, f"cap_{i}.png"))
        seg = os.path.join(work, f"seg_{i}.mp4")
        inputs = ["-i", clip, "-i", ov] + (["-i", extra] if extra else [])
        chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[v0];"
                 f"[v0][1:v]overlay=0:0[v1]")
        chain += ";[v1][2:v]overlay=0:0[vout]" if extra else ";[v1]null[vout]"
        _ff([*inputs, "-filter_complex", chain, "-map", "[vout]", "-an",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", seg])
        segs.append(seg)

    card = end_card(os.path.join(work, "card.png"), plan.get("cta", ""), lang, photo)
    seg = os.path.join(work, "seg_end.mp4")
    inputs = ["-loop", "1", "-t", "2.5", "-i", card] + (["-i", extra] if extra else [])
    chain = f"[0:v]scale={W}:{H},fps={FPS},setsar=1,format=yuv420p[v0]"
    chain += ";[v0][1:v]overlay=0:0,format=yuv420p[vout]" if extra else ";[v0]null[vout]"
    _ff([*inputs, "-filter_complex", chain, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", seg])
    segs.append(seg)

    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write(f"file '{os.path.abspath(s)}'\n")
    # silent audio track: some platforms dislike video-only files
    _ff(["-f", "concat", "-safe", "0", "-i", lst, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", out_path])
    return out_path
