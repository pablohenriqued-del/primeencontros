"""Promotional card generator (1080x1080 PNG) for massagista profiles.
Composes the main photo with brand overlay, name, neighborhood, rating, and CTA.
Used by the owner to share on Instagram/Status — viralizes the profile."""
import logging
from io import BytesIO
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1080
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

BRAND_RED = (220, 38, 38)
BRAND_RED_DARK = (153, 27, 27)
WHITE = (255, 255, 255)
DIM = (200, 200, 200)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


async def _fetch_image(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        fetch_url = url
        if "/api/files/" in url:
            path = url.split("/api/files/", 1)[1]
            fetch_url = f"http://127.0.0.1:8001/api/files/{path}"
        async with httpx.AsyncClient(timeout=10.0) as hc:
            r = await hc.get(fetch_url, headers={"User-Agent": "Mozilla/5.0 (PromoCard)"})
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as ex:
        logging.warning(f"[promo_card] fetch failed for {url}: {ex}")
        return None


def _cover_square(im: Image.Image, size: int) -> Image.Image:
    """Crop to square (center) and resize to size."""
    w, h = im.size
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    cropped = im.crop((left, top, left + s, top + s))
    return cropped.resize((size, size), Image.LANCZOS)


def _draw_text_center(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill, max_width: Optional[int] = None):
    # truncate text if longer than max_width
    if max_width:
        while font.getlength(text) > max_width and len(text) > 2:
            text = text[:-2]
    w = font.getlength(text)
    draw.text(((SIZE - w) / 2, y), text, font=font, fill=fill)


def _star_polygon(cx: float, cy: float, r: float):
    """Returns a 5-point star polygon centered at (cx,cy) with radius r."""
    import math
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * 0.42
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


async def generate_promo_card(
    *,
    main_image_url: str,
    name: str,
    bairro: str,
    rating: float,
    reviews: int,
    cta_domain: str = "primeencontros.com.br",
    verified: bool = False,
) -> bytes:
    """Returns PNG bytes of the 1080x1080 promotional card."""
    # 1) Background = blurred main image with dark vignette
    base = await _fetch_image(main_image_url)
    if base is None:
        # Fallback: solid red gradient
        canvas = Image.new("RGB", (SIZE, SIZE), (10, 10, 10))
    else:
        bg = _cover_square(base, SIZE).filter(ImageFilter.GaussianBlur(40))
        # Darken via overlay
        dark = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
        canvas = Image.blend(bg, dark, 0.55)

    # 2) Vertical gradient bottom for legibility
    grad = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for i in range(SIZE):
        # darker towards bottom for text area
        alpha = int(200 * (i / SIZE) ** 2)
        gd.line([(0, i), (SIZE, i)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), grad).convert("RGB")

    # 3) Center the actual photo as a rounded square (centered, ~620px)
    if base is not None:
        photo = _cover_square(base, 620)
        mask = Image.new("L", (620, 620), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, 620, 620), radius=48, fill=255)
        photo_pos = ((SIZE - 620) // 2, 130)
        # White ring shadow
        ring = Image.new("RGBA", (640, 640), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.rounded_rectangle((0, 0, 640, 640), radius=56, outline=BRAND_RED, width=8)
        canvas.paste(photo, photo_pos, mask)
        canvas.paste(ring, (photo_pos[0] - 10, photo_pos[1] - 10), ring)

    draw = ImageDraw.Draw(canvas)

    # 4) Top brand bar
    draw.rectangle((0, 0, SIZE, 90), fill=(0, 0, 0))
    draw.rectangle((0, 86, SIZE, 90), fill=BRAND_RED)
    brand_font = _font(38, bold=True)
    sub_font = _font(20, bold=False)
    draw.text((54, 22), "Prime", font=brand_font, fill=WHITE)
    p_w = brand_font.getlength("Prime ")
    draw.text((54 + p_w, 22), "Encontros", font=brand_font, fill=BRAND_RED)
    draw.text((54, 60), "MASSAGEM PREMIUM · RIO DE JANEIRO", font=sub_font, fill=DIM)

    # Verified badge (top-right)
    if verified:
        bf = _font(22, bold=True)
        text = "✓ VERIFICADA"
        tw = bf.getlength(text)
        pad = 18
        bx2 = SIZE - 40
        bx1 = bx2 - tw - 2 * pad
        draw.rounded_rectangle((bx1, 26, bx2, 70), radius=22, fill=BRAND_RED)
        draw.text((bx1 + pad, 34), text, font=bf, fill=WHITE)

    # 5) Name (centered below photo)
    name_y = 790
    name_font = _font(72, bold=True)
    _draw_text_center(draw, name.upper(), name_y, name_font, WHITE, max_width=SIZE - 120)

    # 6) Bairro pill
    bairro_text = bairro.upper()
    bf2 = _font(26, bold=True)
    pad_x = 28
    pad_y = 12
    tw = bf2.getlength(bairro_text)
    pill_w = tw + 2 * pad_x
    pill_x = (SIZE - pill_w) / 2
    pill_y = name_y + 92
    draw.rounded_rectangle((pill_x, pill_y, pill_x + pill_w, pill_y + 56), radius=28, fill=BRAND_RED)
    draw.text((pill_x + pad_x, pill_y + pad_y), bairro_text, font=bf2, fill=WHITE)

    # 7) Stars + rating
    stars_y = pill_y + 86
    if reviews > 0 and rating > 0:
        # 5 stars, golden filled up to rating
        star_r = 22
        gap = 14
        total_w = 5 * (star_r * 2) + 4 * gap
        start_x = (SIZE - total_w) / 2 + star_r
        for i in range(5):
            cx = start_x + i * (star_r * 2 + gap)
            filled = i < round(rating)
            pts = _star_polygon(cx, stars_y + star_r, star_r)
            color = (251, 191, 36) if filled else (80, 80, 80)
            draw.polygon(pts, fill=color)
        rf = _font(24, bold=True)
        rating_str = f"{rating:.1f}  ({reviews} avaliações)"
        _draw_text_center(draw, rating_str, stars_y + star_r * 2 + 12, rf, DIM)

    # 8) CTA bar (bottom)
    cta_y = SIZE - 110
    draw.rectangle((0, cta_y, SIZE, SIZE), fill=BRAND_RED)
    cta_font = _font(34, bold=True)
    sub_cta = _font(22, bold=False)
    msg = "RESERVE EM"
    _draw_text_center(draw, msg, cta_y + 14, sub_cta, (255, 220, 220))
    _draw_text_center(draw, cta_domain, cta_y + 44, cta_font, WHITE)

    # Export
    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
