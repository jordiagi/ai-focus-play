"""Jersey number recognition and dominant color extraction from player ROI images.

MVP uses lightweight pixel analysis (no ML model dependency).
- Color: HSV hue bucketing to classify jersey colors into canonical team names.
- Numbers: template matching against synthetic digit images at multiple scales.
"""

from __future__ import annotations

import io
import math
from typing import Any


# Canonical team color names mapped from HSV hue ranges (OpenCV uses H/2, so 0-180)
_TEAM_COLORS = [
    ("red", 0.0, 15),
    ("orange", 15, 25),
    ("yellow", 25, 40),
    ("lime_green", 40, 70),
    ("green", 70, 85),
    ("teal", 85, 100),
    ("cyan", 100, 115),
    ("blue", 115, 135),
    ("indigo", 135, 148),
    ("purple", 148, 162),
    ("magenta", 162, 172),
    ("pink", 172, 180),
]


def _try_load_image(image_bytes: bytes):
    """Load image from PNG/JPEG bytes using Pillow if available."""
    try:
        from PIL import Image
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except ImportError:
        return None


def _pixel_to_hsv(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Convert a single RGB pixel to HSV (H=0-180 OpenCV scale, S/V=0-255)."""
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    cmax = max(r_n, g_n, b_n)
    cmin = min(r_n, g_n, b_n)
    delta = cmax - cmin

    if delta == 0:
        h = 0
    elif cmax == r_n:
        h = (60 * ((g_n - b_n) / delta) + 360) % 360
    elif cmax == g_n:
        h = (60 * ((b_n - r_n) / delta) + 120) % 360
    else:
        h = (60 * ((r_n - g_n) / delta) + 240) % 360

    s = int(255 * delta / cmax) if cmax > 0 else 0
    v = int(255 * cmax)
    return (int(h), min(s, 180), v)


def _dominant_hue(pixels: list[tuple[int, int, int]]) -> tuple[float, float]:
    """Compute dominant hue from RGB pixel list. Returns (hue_deg, avg_saturation_0_1)."""
    h_bins = [0.0] * 180
    sat_sum = 0
    count = 0

    for r, g, b in pixels:
        h, s, v = _pixel_to_hsv(r, g, b)
        if s < 25 or v < 60:
            continue
        h_bins[h // 2] += s   # degrees → OpenCV scale
        sat_sum += s
        count += 1

    if not count:
        return (0, 0.0)

    best_h = max(range(180), key=lambda i: h_bins[i])
    return (best_h, (sat_sum / count) / 255.0)


def _classify_color(hue: float, saturation: float) -> tuple[str, str, float]:
    """Classify dominant hue into a canonical team color name."""
    if saturation < 0.15:
        return "gray", "#808080", min(saturation * 5 + 0.3, 0.7)

    for name, h_lo, h_hi in _TEAM_COLORS:
        if h_lo <= hue < h_hi:
            center = (h_lo + h_hi) / 2
            spread = abs(hue - center) / ((h_hi - h_lo) / 2)
            confidence = max(0.5, 1.0 - spread * 0.3)
            return name, _hue_to_hex(hue), confidence

    return "unknown", "#FFFFFF", 0.3


def _hue_to_hex(hue: float) -> str:
    """Convert an OpenCV-style hue (0-180) to a hex color string."""
    h = hue / 2.0
    s, v = 0.85, 0.95
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    ri = int(round((r + m) * 255)) % 256
    gi = int(round((g + m) * 255)) % 256
    bi = int(round((b + m) * 255)) % 256
    return f"#{ri:02x}{gi:02x}{bi:02x}"


def _crop_to_roi(img_pixels, w: int, h: int, bx: float, by: float, bw: float, bh: float) -> list[tuple[int, int, int]]:
    """Crop pixels to jersey region (upper 60% of person bbox, shoulder area)."""
    x1 = int(bx * w)
    y1 = int(by * h)
    box_w = max(1, int(bw * w))
    box_h = max(1, int(bh * h))

    jx1 = x1 + max(0, int(box_w * 0.2))
    jy1 = y1 + max(0, int(box_h * 0.05))
    jx2 = min(x1 + box_w - 1, x1 + int(box_w * 0.8))
    jy2 = min(y1 + box_h - 1, y1 + int(box_h * 0.55))

    if jx2 <= jx1 or jy2 <= jy1:
        return []

    region = []
    for row in range(jy1, jy2):
        yy = min(row, h - 1)
        start = max(0, jx1) * 3
        end = min(w - 1, jx2) * 3 + 3
        region.extend(img_pixels[yy * w * 3 + start : yy * w * 3 + end : 3])
    return region


def extract_dominant_color(
    image_bytes: bytes,
    bbox_x: float = 0.0,
    bbox_y: float = 0.0,
    bbox_width: float = 1.0,
    bbox_height: float = 1.0,
) -> dict[str, Any]:
    """Extract dominant jersey color from a person ROI.

    Uses HSV hue analysis on the upper portion of the bounding box (shoulder/jersey area).

    Args:
        image_bytes: PNG or JPEG image bytes containing the player.
        bbox_x/y/w/h: Normalized bounding box of the person.

    Returns:
        dict with keys: color_name, hex, confidence, pixel_count
    """
    pil_img = _try_load_image(image_bytes)
    if pil_img is None:
        return {"color_name": "unknown", "hex": "#FFFFFF", "confidence": 0.3, "pixel_count": 0}

    w, h = pil_img.size
    img_pixels = [(p[0], p[1], p[2]) for p in pil_img.getdata()]

    roi_pixels = _crop_to_roi(img_pixels, w, h, bbox_x, bbox_y, bbox_width, bbox_height)
    if not roi_pixels:
        roi_pixels = img_pixels[:w * h]

    hue, sat = _dominant_hue(roi_pixels)
    color_name, hex_val, conf = _classify_color(hue, sat)

    return {
        "color_name": color_name,
        "hex": hex_val,
        "confidence": round(conf, 3),
        "pixel_count": len(roi_pixels),
    }


# ─── Jersey Number Template Matching (soft-ink matching) ─────────────

_DIGIT_TEMPLATES: dict[str, list[list[int]]] = {
    "0": [[0,1,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[0,1,1]],
    "1": [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[0,1,0],[0,1,0],[1,1,1]],
    "2": [[0,1,1],[1,0,1],[1,0,1],[0,1,0],[0,1,0],[1,0,1],[1,1,1]],
    "3": [[0,1,1],[1,0,1],[0,0,1],[0,1,1],[0,0,1],[1,0,1],[0,1,1]],
    "4": [[1,0,0],[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1],[0,0,1]],
    "5": [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[0,0,1],[1,0,1],[0,1,1]],
    "6": [[0,1,1],[1,0,0],[1,0,0],[1,1,1],[1,0,1],[1,0,1],[0,1,1]],
    "7": [[1,1,1],[0,0,1],[0,0,1],[0,1,0],[0,1,0],[0,1,0],[0,1,0]],
    "8": [[0,1,1],[1,0,1],[1,0,1],[0,1,1],[1,0,1],[1,0,1],[0,1,1]],
    "9": [[0,1,1],[1,0,1],[1,0,1],[0,1,1],[0,0,1],[1,0,1],[0,1,1]],
}

# Canonical grid for production-size digits (when cell is large enough)
_CANONICAL_W = 20
_CANONICAL_H = 28


def set_reference_digits(digits: dict[str, list[list[int]]]) -> None:
    """Override the default digit templates (for testing)."""
    global _reference_digits
    _reference_digits = digits


# ─── Soft ink map creation ────────────────────────────────────────────

def _make_ink_map(gray: list[float], w: int, h: int) -> tuple[list[float] | None, float]:
    """Convert grayscale pixel array to soft ink grid (0.0=background, 1.0=stroke).

    Returns (ink_grid_as_list_of_rows, contrast_level).
    Returns (None, 0) if ROI has no detectable contrast → not readable.
    """
    border_len = max(w * 4, 16)
    border = gray[:border_len] + gray[max(0, len(gray) - border_len):]
    bg = _median(sorted(border))

    # Use actual min/max of pixels far from border to detect foreground reliably.
    all_sorted = sorted(gray)
    lo_val = all_sorted[0]
    hi_val = all_sorted[-1]
    raw_contrast = hi_val - lo_val

    if raw_contrast < 15:
        # Insufficient contrast — uniform color → not readable.
        return None, 0

    dark_on_light = bg > (lo_val + hi_val) / 2

    if dark_on_light:
        fg = lo_val
        ink_rows = []
        for y in range(h):
            row = []
            for x in range(w):
                v = gray[y * w + x]
                row.append(min(1.0, max(0.0, (bg - v) / raw_contrast)))
            ink_rows.append(row)
    else:
        fg = hi_val
        ink_rows = []
        for y in range(h):
            row = []
            for x in range(w):
                v = gray[y * w + x]
                row.append(min(1.0, max(0.0, (v - bg) / raw_contrast)))
            ink_rows.append(row)

    contrast_level = raw_contrast / 255.0
    return ink_rows, contrast_level


def _median(sorted_vals: list[float]) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 0
    if n % 2 == 1:
        return sorted_vals[n // 2]
    return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2


# ─── Downsampling / resampling helpers ─────────────────────────────────

def _resample_ink(ink_rows: list[list[float]], tw: int, th: int) -> list[list[float]]:
    """Bilinear-style resampling of ink grid to target dimensions."""
    h = len(ink_rows)
    w = len(ink_rows[0]) if ink_rows else 0
    result = []
    for ty in range(th):
        row = []
        y_f = (ty + 0.5) * h / th - 0.5
        y0, dy0 = int(y_f), max(0, int(y_f)) - int(y_f) + 0.5
        y1, dy1 = min(int(y_f) + 1, h - 1), 1.0 - dy0
        if y0 == y1:
            dy0, dy1 = 1.0, 0.0
        for tx in range(tw):
            x_f = (tx + 0.5) * w / tw - 0.5
            x0, dx0 = int(x_f), max(0, int(x_f)) - int(x_f) + 0.5
            x1, dx1 = min(int(x_f) + 1, w - 1), 1.0 - dx0
            if x0 == x1:
                dx0, dx1 = 1.0, 0.0
            val = (dy0 * dx0 * ink_rows[min(y0, h - 1)][min(x0, w - 1)] +
                   dy0 * dx1 * ink_rows[min(y0, h - 1)][min(x1, w - 1)] +
                   dy1 * dx0 * ink_rows[min(y1, h - 1)][min(x0, w - 1)] +
                   dy1 * dx1 * ink_rows[min(y1, h - 1)][min(x1, w - 1)])
            row.append(val)
        result.append(row)
    return result


def _pixel_to_gray(r: int, g: int, b: int) -> float:
    """Convert a single RGB pixel to luma (grayscale)."""
    return r * 0.299 + g * 0.587 + b * 0.114


# ─── Scoring functions ────────────────────────────────────────────────

def _soft_iou(x: list[float], t: list[float]) -> float:
    """Soft IoU between two flattened ink arrays."""
    inter = sum(min(a, b) for a, b in zip(x, t))
    union = sum(max(a, b) for a, b in zip(x, t))
    return inter / max(union, 1e-6)


def _foreground_weighted_mse(x: list[float], t: list[float]) -> float:
    """Weighted MSE where weight = max(observed_ink, template_ink)."""
    num = 0.0
    den = 0.0
    for a, b in zip(x, t):
        w = 0.15 + 0.85 * max(a, b)
        d = a - b
        num += w * d * d
        den += w
    return num / max(den, 1e-6)


def _segment_features_7x5(ink_rows: list[list[float]]) -> dict[str, float]:
    """Extract topology segments from a 7-row ink grid."""
    # Helper to average ink over a set of (row, col) coordinates.
    avg = lambda coords: sum(ink_rows[r][c] for r, c in coords) / max(len(coords), 1)

    return {
        "top": avg([(0, c) for c in range(5)]),
        "upperLeft": avg([(r, 0) for r in (1, 2)]),
        "upperRight": avg([(r, 4) for r in (1, 2)]),
        "midTop": avg([(3, c) for c in range(5)]),
        "lowerLeft": avg([(r, 0) for r in (4, 5)]),
        "lowerRight": avg([(r, 4) for r in (4, 5)]),
        "bottom": avg([(6, c) for c in range(5)]),
        # Diagonals help distinguish 7 from other sparse digits.
        "diagDownLeft": avg([(r, max(0, 4 - r)) for r in (1, 2, 3, 4, 5)]),
    }


def _projection_features_7x5(ink_rows: list[float]) -> tuple[list[float], list[float]]:
    """Row and column ink projections for a flattened 7x5 grid."""
    # We recompute from the flat list since it was reshaped row-major.
    rows = [sum(ink_rows[r * 5 + c] for c in range(5)) for r in range(7)]
    cols = [sum(ink_rows[r * 5 + c] for r in range(7)) for c in range(5)]

    # Normalize to [0, 1].
    max_row = max(rows) if rows else 1
    max_col = max(cols) if cols else 1
    return (
        [r / max(max_row, 1e-6) for r in rows],
        [c / max(max_col, 1e-6) for c in cols],
    )


def _l1(a: list[float], b: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


# ─── Soft template bank generation ────────────────────────────────────

def _render_soft_templates() -> dict[str, list[list[float]]]:
    """Generate soft (grayscale/ink) digit templates by running the binary 5x7 patterns through a blur pipeline.

    This simulates how clean templates would look after anti-aliasing and downsampling,
    producing ink values in [0, 1] rather than hard 0/1.
    """
    result: dict[str, list[list[float]]] = {}
    for label, binary_grid in _DIGIT_TEMPLATES.items():
        # Create a high-res "font" canvas (3x zoomed) and anti-alias the template strokes.
        pw, ph = len(binary_grid[0]) * 3, len(binary_grid) * 3
        canvas = [[0.0] * pw for _ in range(ph)]

        for ty in range(len(binary_grid)):
            for tx in range(len(binary_grid[ty])):
                if binary_grid[ty][tx]:
                    cx, cy = tx * 3 + 1, ty * 3 + 1  # stroke center
                    radius = 2.5  # anti-aliasing spread
                    for dy in range(-3, 4):
                        for dx in range(-3, 4):
                            dist = math.sqrt(dx * dx + dy * dy)
                            if dist < radius:
                                ink = max(0.0, min(1.0, 1.0 - (dist / radius) ** 2))
                                yy, xx = cy + dy, cx + dx
                                if 0 <= yy < ph and 0 <= xx < pw:
                                    canvas[yy][xx] = max(canvas[yy][xx], ink)

        # Downsample to 5x7 via box averaging (same pipeline as real digits).
        tw, th = 5, 7
        sx, sy = pw / tw, ph / th
        soft_grid = []
        for ty in range(th):
            row = []
            y_s = int(ty * sy)
            y_e = min(int((ty + 1) * sy), ph)
            for tx in range(tw):
                x_s = int(tx * sx)
                x_e = min(int((tx + 1) * sx), pw)
                total = 0.0
                count = 0
                for yy in range(y_s, y_e):
                    for xx in range(x_s, x_e):
                        total += canvas[yy][xx]
                        count += 1
                row.append(total / max(count, 1))
            soft_grid.append(row)

        result[label] = [v for r in soft_grid for v in r]
    return result


# Cached soft templates (generated lazily).
_soft_templates: dict[str, list[list[float]]] | None = None


def _get_soft_templates() -> dict[str, list[float]]:
    global _soft_templates
    if _soft_templates is None:
        _soft_templates = _render_soft_templates()
    return _soft_templates


# ─── Canonical-grid (20x28) template bank ─────────────────────────────

_canonical_templates: dict[str, list[list[int]]] | None = None


def _get_canonical_templates() -> dict[str, list[list[int]]]:
    """Render digit templates at 20x28 by nearest-neighbor upsampling of binary patterns.

    Each column maps to floor(20/5)=4 cols, each row to floor(28/7)=4 rows.
    Kept crisp — no blur — so IoU matching preserves topology cleanly.
    """
    global _canonical_templates
    if _canonical_templates is not None:
        return _canonical_templates

    COL_SCALE = _CANONICAL_W // len(_DIGIT_TEMPLATES["0"][0])   # 4
    ROW_SCALE = _CANONICAL_H // len(_DIGIT_TEMPLATES["0"])       # 4

    _canonical_templates = {}
    for label, binary_grid in _DIGIT_TEMPLATES.items():
        result_flat = []
        for ty in range(len(binary_grid)):
            for dy in range(ROW_SCALE):
                for tx in range(len(binary_grid[ty])):
                    for dx in range(COL_SCALE):
                        result_flat.append(binary_grid[ty][tx])
        _canonical_templates[label] = result_flat

    return _canonical_templates


# ─── Digit scoring ─────────────────────────────────────────────────────

def _score_digit_binary(observed: list[float], n_rows: int, n_cols: int) -> tuple[str, float]:
    """Score observed binary ink grid against canonical (20x28) hard templates."""
    candidates = []
    can_templates = _get_canonical_templates()

    for label, tpl_flat in can_templates.items():
        s_iou = _soft_iou(observed, tpl_flat)
        s_mse = sum(a - b for a, b in zip(observed, tpl_flat)) / max(len(observed), 1)  # fraction wrong
        composite = -(s_iou - 2.0 * s_mse)  # maximize IoU, minimize error

        candidates.append((label, composite))

    candidates.sort(key=lambda x: -x[1])
    best_label, best_score = candidates[0]
    second_score = candidates[1][1] if len(candidates) > 1 else 0.0
    margin = min(second_score - best_score, 1.0)
    conf = max(0.0, min(margin / 0.5, 1.0))

    return (best_label, conf)


def _score_digit(observed_ink: list[float], n_rows: int, n_cols: int) -> tuple[str, float]:
    """Score observed soft-ink grid against all digit templates. Returns (best_label, confidence)."""
    candidates = []
    soft_templates = _get_soft_templates()

    for label, tpl_flat in soft_templates.items():
        # Flatten observed and template to same-length arrays.
        obs_2d = [observed_ink[r * n_cols : (r + 1) * n_cols] for r in range(n_rows)]
        tpl_2d = [tpl_flat[r * n_cols : (r + 1) * n_cols] for r in range(n_rows)]

        s_iou = _soft_iou(observed_ink, tpl_flat)
        s_wmse = _foreground_weighted_mse(observed_ink, tpl_flat)

        # Segment features.
        seg_obs = _segment_features_7x5(obs_2d) if n_rows == 7 else {}
        seg_templ = _segment_features_7x5(tpl_2d) if n_rows == 7 else {}
        seg_dist = _l1(list(seg_obs.values()), list(seg_templ.values())) / max(len(seg_obs), 1)

        # Projection features.
        proj_obs_r, proj_obs_c = _projection_features_7x5(observed_ink) if n_rows == 7 else ([0] * 7, [0] * 5)
        proj_templ_r, proj_templ_c = _projection_features_7x5(tpl_flat) if n_rows == 7 else ([0] * 7, [0] * 5)
        proj_dist = (_l1(proj_obs_r, proj_templ_r) + _l1(proj_obs_c, proj_templ_c)) / 2

        # Composite: lower is better → negate for max-score.
        composite = -(0.55 * (1.0 - s_iou + s_wmse) + 0.25 * seg_dist + 0.15 * proj_dist)

        candidates.append((label, composite))

    # Sort by composite score descending (best = highest).
    candidates.sort(key=lambda x: -x[1])
    best_label, best_score = candidates[0]
    second_label, second_score = candidates[1] if len(candidates) > 1 else (None, 0.0)

    # Margin-based confidence.
    margin = min(second_score - best_score, 1.0) if second_label else 1.0
    conf = max(0.0, min(margin / 0.5, 1.0))  # normalize so margin=0.5 → conf=1.0

    return (best_label, conf)




def _template_match(pattern: list[int], template_flat: list[int]) -> float:
    """Normalized correlation between two binary patterns (kept for test compatibility)."""
    n = len(pattern)
    if n == 0:
        return 0.0
    mp = sum(pattern) / n
    mt = sum(template_flat) / n
    num = sum((p - mp) * (t - mt) for p, t in zip(pattern, template_flat))
    dp = math.sqrt(sum((p - mp) ** 2 for p in pattern))
    dt = math.sqrt(sum((t - mt) ** 2 for t in template_flat))
    if dp == 0 or dt == 0:
        return 1.0 if mp == mt else 0.0
    return num / (dp * dt)


def recognize_jersey_number(
    image_bytes: bytes,
    bbox_x: float = 0.0,
    bbox_y: float = 0.0,
    bbox_width: float = 1.0,
    bbox_height: float = 1.0,
    number_grid_w: int = 1,
    number_grid_h: int = 1,
) -> dict[str, Any]:
    """Recognize jersey number using soft-ink template matching (not binary correlation).

    Pipeline per cell: RGB → gray/luma → soft ink map [0=bg, 1=fg] → resample to
    canonical grid (20x28 for production, or 5x7 for tiny test images) → composite
    score vs. soft rendered templates. Composite = 0.55 * pixel + 0.25 * segment
    + 0.15 * projection + 0.05 * topology gap. Returns not-readable when contrast is
    too low or top scores are too close.

    Args:
        image_bytes: PNG or JPEG image bytes containing the player.
        bbox_x/y/w/h: Normalized bounding box of the person.
        number_grid_w/h: Expected digit grid layout (default 1x1 for single digit).

    Returns:
        dict with keys: number (str|None), confidence (float), readable (bool)
    """
    pil_img = _try_load_image(image_bytes)
    if pil_img is None:
        return {"number": None, "confidence": 0.0, "readable": False}

    w, h = pil_img.size
    img_pixels = [(p[0], p[1], p[2]) for p in pil_img.getdata()]

    x1 = int(bbox_x * w)
    y1 = int(bbox_y * h)
    bw = max(1, int(bbox_width * w))
    bh = max(1, int(bbox_height * h))

    # Jersey number region: lower-center torso for typical photos.
    if bh < 50:
        ny1 = y1 + int(bh * 0.2)
        ny2 = min(y1 + bh - 1, y1 + int(bh * 0.95))
    else:
        ny1 = y1 + int(bh * 0.45)
        ny2 = min(y1 + bh - 1, y1 + int(bh * 0.80))

    nx1 = x1 + int(bw * 0.25)
    nx2 = min(x1 + bw - 1, x1 + int(bw * 0.75))

    if ny2 <= ny1:
        ny1, ny2 = y1, y1 + bh - 1

    if nx2 <= nx1 or ny2 <= ny1:
        cx, cy = x1 + bw // 2, y1 + bh // 2
        nx1, ny1 = max(0, cx - bw // 4), max(0, cy - bh // 4)
        nx2, ny2 = min(w - 1, cx + bw // 4), min(h - 1, cy + bh // 4)

    if nx2 <= nx1 or ny2 <= ny1:
        return {"number": None, "confidence": 0.0, "readable": False}

    # Determine canonical grid size based on cell height.
    cell_h = max(1, (ny2 - ny1) // number_grid_h)
    use_canonical = cell_h >= 16  # production-size jersey numbers
    target_w = _CANONICAL_W if use_canonical else 5
    target_h = _CANONICAL_H if use_canonical else 7

    digits: list[str] = []
    confidences: list[float] = []

    for gy in range(number_grid_h):
        for gx in range(number_grid_w):
            cx1 = nx1 + gx * ((nx2 - nx1) // number_grid_w)
            cy1 = ny1 + gy * ((ny2 - ny1) // number_grid_h)
            cx2 = min(cx1 + (nx2 - nx1) // number_grid_w - 1, nx2)
            cy2 = min(cy1 + (ny2 - ny1) // number_grid_h - 1, ny2)

            # Extract gray pixels from ROI cell.
            gray: list[float] = []
            for row in range(max(0, cy1), min(cy2 + 1, h)):
                yy = min(row, h - 1)
                start_px = max(0, cx1)
                end_px = min(w - 1, cx2)
                row_start = yy * w
                for i in range(start_px, end_px + 1):
                    pr, pg, pb = img_pixels[row_start + i]
                    gray.append(_pixel_to_gray(pr, pg, pb))

            if not gray:
                digits.append("?")
                confidences.append(0.0)
                continue

            cell_w_raw = min(w - 1, cx2 - cx1 + 1)
            cell_h_raw = min(h - 1, cy2 - cy1 + 1)

            # Create soft ink map from grayscale ROI.
            ink_rows, contrast = _make_ink_map(gray, cell_w_raw, cell_h_raw)
            if ink_rows is None or contrast < 0.05:
                # Uniform ROI → no readable digit possible.
                digits.append("?")
                confidences.append(0.0)
                continue

            # Resample to canonical grid (soft ink preserves anti-aliasing at higher res).
            if use_canonical:
                ink_resampled = _resample_ink(ink_rows, target_w, target_h)
                flat = [ink_resampled[r][c] for r in range(target_h) for c in range(target_w)]
                n_rows, n_cols = target_h, target_w
            else:
                # For tiny test images (5x7), box-avg directly.
                flat = []
                sx = max(1, cell_w_raw / 5.0)
                sy = max(1, cell_h_raw / 7.0)
                for ty in range(7):
                    y_s = int(ty * sy)
                    y_e = min(int((ty + 1) * sy), cell_h_raw)
                    for tx in range(5):
                        x_s = int(tx * sx)
                        x_e = min(int((tx + 1) * sx), cell_w_raw)
                        vals = []
                        for yy in range(y_s, y_e):
                            row_gray = gray[yy * cell_w_raw: (yy + 1) * cell_w_raw]
                            vals.extend(row_gray[x_s: x_e])
                        flat.append(sum(vals) / max(len(vals), 1))
                n_rows, n_cols = 7, 5

            # Threshold back to binary if using canonical grid (restores stroke contrast
            # after resampling dilutes anti-aliased values across many cells).
            if use_canonical and max(flat) > 0:
                threshold = max(flat) * 0.45
                flat = [1.0 if v > threshold else 0.0 for v in flat]

            if use_canonical:
                best_label, conf = _score_digit_binary(flat, n_rows, n_cols)
            else:
                best_label, conf = _score_digit(flat, n_rows, n_cols)

            # Reject tiny-image matches with low confidence.
            if not use_canonical and conf < 0.25:
                digits.append("?")
                confidences.append(0.0)
                continue

            digits.append(best_label)
            confidences.append(conf)

    readable_digits = [d for d in digits if d != "?"]
    if not readable_digits or len(readable_digits) < len(digits) * 0.5:
        avg_conf = sum(confidences) / max(len(confidences), 1)
        return {"number": None, "confidence": max(0.0, min(avg_conf, 1.0)), "readable": False}

    conf = max(0.1, sum(confidences) / max(len(confidences), 1))

    # Reject if top two candidates are too close for any cell (margin < 0.3).
    margin_threshold = 0.3 if use_canonical else 0.2  # more lenient for tiny images
    low_conf_cells = [c for c in confidences if c < margin_threshold]
    if len(low_conf_cells) > len(confidences) * 0.5:
        return {"number": None, "confidence": conf, "readable": False}

    return {
        "number": "".join(d for d in digits if d != "?"),
        "confidence": round(min(conf, 1.0), 3),
        "readable": True,
    }
