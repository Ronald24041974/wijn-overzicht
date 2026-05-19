"""Afbeeldingsverwerking voor Vercel — zonder rembg (te zwaar voor serverless).
Gebruikt PIL flood-fill + morfologische smoothing voor achtergrondverwijdering."""
import io
import re
import json
import base64
from collections import deque


def _clean_alpha(img):
    from PIL import Image as _Image
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    r, g, b, a = img.split()
    black = _Image.new("L", img.size, 0)
    opaque_mask = a.point(lambda v: 255 if v > 0 else 0)
    r = _Image.composite(r, black, opaque_mask)
    g = _Image.composite(g, black, opaque_mask)
    b = _Image.composite(b, black, opaque_mask)
    a = a.point(lambda v: 0 if v < 16 else v)
    return _Image.merge("RGBA", (r, g, b, a))


def _smooth_alpha(img):
    from PIL import Image as _Image, ImageFilter as _IF
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    r, g, b, a = img.split()
    a_bin  = a.point(lambda v: 255 if v > 127 else 0)
    a_dil  = a_bin.filter(_IF.MaxFilter(size=3))
    a_cls  = a_dil.filter(_IF.MinFilter(size=3))
    a_blur = a_cls.filter(_IF.GaussianBlur(radius=1.5))
    a_out  = a_blur.point(lambda v: 0 if v < 40 else (255 if v > 200 else int((v - 40) * 255 // 160)))
    return _Image.merge("RGBA", (r, g, b, a_out))


def _is_white_background(img, threshold=240):
    from PIL import Image as _Image
    rgb = img.convert("RGB")
    w, h = rgb.size
    border = []
    step_x = max(1, w // 30)
    step_y = max(1, h // 30)
    for x in range(0, w, step_x):
        border.append(rgb.getpixel((x, 0)))
        border.append(rgb.getpixel((x, h - 1)))
    for y in range(0, h, step_y):
        border.append(rgb.getpixel((0, y)))
        border.append(rgb.getpixel((w - 1, y)))
    white = sum(1 for r, g, b in border if r > threshold and g > threshold and b > threshold)
    return white / len(border) > 0.85


def _remove_bg_white(img_bytes: bytes) -> bytes:
    from PIL import Image as _Image, ImageFilter as _IF
    img = _Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    if max(img.size) > 1200:
        img.thumbnail((1200, 1200), _Image.LANCZOS)
    w, h = img.size
    data = img.load()
    THR = 238

    def is_bg(px):
        return px[0] > THR and px[1] > THR and px[2] > THR

    visited = [[False] * h for _ in range(w)]
    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not visited[x][y]:
                visited[x][y] = True
                queue.append((x, y))
    for y in range(1, h - 1):
        for x in (0, w - 1):
            if not visited[x][y]:
                visited[x][y] = True
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        if not is_bg(data[x, y]):
            continue
        r, g, b, _ = data[x, y]
        data[x, y] = (r, g, b, 0)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
                visited[nx][ny] = True
                queue.append((nx, ny))

    alpha = img.split()[3]
    alpha = alpha.filter(_IF.MaxFilter(size=3))
    alpha = alpha.filter(_IF.MinFilter(size=3))
    alpha = alpha.filter(_IF.GaussianBlur(radius=1.2))
    alpha = alpha.point(lambda v: 0 if v < 40 else (255 if v > 200 else int((v - 40) * 255 // 160)))
    r2, g2, b2, _ = img.split()
    result = _Image.merge("RGBA", (r2, g2, b2, alpha))
    result = _clean_alpha(result)

    a_ch = result.split()[3]
    bbox = a_ch.getbbox()
    if bbox:
        side_buf = max(10, int((bbox[2] - bbox[0]) * 0.08))
        result = result.crop((max(0, bbox[0] - side_buf), 0, min(result.width, bbox[2] + side_buf), result.height))
        result = _clean_alpha(result)

    rw, rh = result.size
    pad = max(16, int(max(rw, rh) * 0.06))
    canvas = _Image.new("RGBA", (rw + 2 * pad, rh + 2 * pad), (0, 0, 0, 0))
    canvas.paste(result, (pad, pad), result)
    TARGET_H = 600
    cw, ch = canvas.size
    if ch != TARGET_H:
        canvas = canvas.resize((max(1, round(cw * TARGET_H / ch)), TARGET_H), _Image.LANCZOS)
    canvas = _clean_alpha(canvas)
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


def _remove_background_fallback(img_bytes: bytes) -> bytes:
    from PIL import Image as _Image
    img = _Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    if max(img.size) > 800:
        img.thumbnail((800, 800), _Image.LANCZOS)
    data = img.load()
    w, h = img.size
    border_pixels = []
    for x in range(0, w, max(1, w // 20)):
        border_pixels.extend([data[x, 0], data[x, h - 1]])
    for y in range(0, h, max(1, h // 20)):
        border_pixels.extend([data[0, y], data[w - 1, y]])
    light = [p for p in border_pixels if (p[0] + p[1] + p[2]) // 3 > 180]
    if len(light) < len(border_pixels) // 3:
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    avg_r = sum(p[0] for p in light) // len(light)
    avg_g = sum(p[1] for p in light) // len(light)
    avg_b = sum(p[2] for p in light) // len(light)
    tol = 45 * 3

    def is_bg(px):
        return abs(px[0] - avg_r) + abs(px[1] - avg_g) + abs(px[2] - avg_b) < tol

    visited = [[False] * h for _ in range(w)]
    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not visited[x][y]:
                visited[x][y] = True
                queue.append((x, y))
    for y in range(1, h - 1):
        for x in (0, w - 1):
            if not visited[x][y]:
                visited[x][y] = True
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        px = data[x, y]
        if not is_bg(px):
            continue
        data[x, y] = (px[0], px[1], px[2], 0)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
                visited[nx][ny] = True
                queue.append((nx, ny))
    bbox = img.split()[3].getbbox()
    if bbox:
        img = img.crop(bbox)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def remove_background(img_bytes: bytes) -> bytes:
    from PIL import Image as _Image
    try:
        img = _Image.open(io.BytesIO(img_bytes)).convert("RGB")
        if max(img.size) > 1200:
            img.thumbnail((1200, 1200), _Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        cropped_bytes = buf.getvalue()
        if _is_white_background(img):
            return _remove_bg_white(cropped_bytes)
        return _remove_background_fallback(cropped_bytes)
    except Exception:
        return _remove_background_fallback(img_bytes)


def has_transparency(img_bytes: bytes) -> bool:
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes))
    if img.mode == "P" and "transparency" in img.info:
        img = img.convert("RGBA")
    elif img.mode not in ("RGBA", "PA"):
        return False
    alpha = img.convert("RGBA").split()[-1]
    total = alpha.width * alpha.height
    transparent = sum(1 for v in alpha.getdata() if v == 0)
    return transparent / total > 0.15


def normalize_transparent(img_bytes: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    img = _smooth_alpha(img)
    img = _clean_alpha(img)
    w, h = img.size
    if w > h * 1.1:
        img = img.rotate(-90, expand=True)
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        side_buf = max(10, int((bbox[2] - bbox[0]) * 0.08))
        img = img.crop((max(0, bbox[0] - side_buf), 0, min(img.width, bbox[2] + side_buf), img.height))
    rw, rh = img.size
    pad = max(16, int(max(rw, rh) * 0.06))
    canvas = Image.new("RGBA", (rw + 2 * pad, rh + 2 * pad), (0, 0, 0, 0))
    canvas.paste(img, (pad, pad), img)
    TARGET_H = 600
    cw, ch = canvas.size
    if ch != TARGET_H:
        canvas = canvas.resize((max(1, round(cw * TARGET_H / ch)), TARGET_H), Image.LANCZOS)
    canvas = _clean_alpha(canvas)
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


def make_thumbnail(img_bytes: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes))
    if img.mode in ("P", "PA"):
        img = img.convert("RGBA")
    elif img.mode != "RGBA":
        img = img.convert("RGBA")
    img = _clean_alpha(img)
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        buf_px = max(4, int((bbox[3] - bbox[1]) * 0.02))
        img = img.crop((max(0, bbox[0] - buf_px), max(0, bbox[1] - buf_px),
                        min(img.width, bbox[2] + buf_px), min(img.height, bbox[3] + buf_px)))
        img = _clean_alpha(img)
    img.thumbnail((80, 120), Image.LANCZOS)
    img = _clean_alpha(img)
    canvas = Image.new("RGBA", (80, 120), (0, 0, 0, 0))
    offset = ((80 - img.width) // 2, (120 - img.height) // 2)
    alpha = img.split()[3]
    canvas.paste(img.convert("RGB"), offset, alpha)
    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return buf.getvalue()


def process_and_store_image(name: str, img_bytes: bytes, db_conn) -> int:
    """Verwerk afbeelding, maak thumbnail en sla op in DB. Geeft updatedAt terug."""
    import time
    from ._helpers import sanitize_filename
    processed = remove_background(img_bytes) if not has_transparency(img_bytes) else normalize_transparent(img_bytes)
    thumb = make_thumbnail(processed)
    now = int(time.time())
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE wines SET image_data=%s, thumb_data=%s, updatedat=%s WHERE name=%s",
            (processed, thumb, now, name)
        )
    db_conn.commit()
    return now
