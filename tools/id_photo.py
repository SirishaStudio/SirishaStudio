"""ID PHOTO — produce a passport-/visa-/stamp-size photo from any portrait
image at the correct mm size + DPI for printing.

Output is a JPEG sized exactly to the requested print dimensions in mm at the
chosen DPI, with a configurable border colour (default white). The portrait is
center-fitted (cover) so the face fills the frame without distortion.
"""

import os, time
import cv2
import numpy as np

from flask import Blueprint, render_template, request, jsonify
from . import utils
from config import OUTPUT_DIR

bp = Blueprint("id_photo", __name__)

# Common Indian passport sizes
PRESETS = [
    {"key": "passport",  "label": "Passport (35 × 45 mm)",  "w_mm": 35, "h_mm": 45},
    {"key": "stamp",     "label": "Stamp (25 × 35 mm)",     "w_mm": 25, "h_mm": 35},
    {"key": "visa",      "label": "Visa (50 × 70 mm)",      "w_mm": 50, "h_mm": 70},
    {"key": "usvisa",    "label": "US Visa (51 × 51 mm)",   "w_mm": 51, "h_mm": 51},
    {"key": "indian_id", "label": "Indian ID (35 × 35 mm)", "w_mm": 35, "h_mm": 35},
]

DEFAULT_DPI = 300


@bp.route("/id-photo")
def page():
    return render_template("tool_id_photo.html",
                           presets=PRESETS, default_dpi=DEFAULT_DPI)


def _hex_to_bgr(hex_str, default=(255, 255, 255)):
    if not hex_str:
        return default
    s = hex_str.lstrip("#")
    if len(s) != 6:
        return default
    try:
        r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16)
        return (b, g, r)  # OpenCV BGR
    except Exception:
        return default


def _fit_cover(img, w, h):
    """Resize then center-crop so img fills exactly (w,h)."""
    ih, iw = img.shape[:2]
    scale = max(w / iw, h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    x = max(0, (nw - w) // 2)
    y = max(0, (nh - h) // 2)
    return resized[y:y + h, x:x + w].copy()


@bp.route("/id-photo/process", methods=["POST"])
def process():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No image uploaded"})

    try:
        w_mm = float(request.form.get("w_mm") or 35)
        h_mm = float(request.form.get("h_mm") or 45)
        dpi  = int(request.form.get("dpi") or DEFAULT_DPI)
        bg   = _hex_to_bgr(request.form.get("bg") or "#ffffff")
        copies_per_a4 = int(request.form.get("copies") or 0)
    except Exception:
        return jsonify({"error": "Bad parameters"})

    uid, path = utils.save_upload(file)
    img = cv2.imread(path)
    if img is None:
        return jsonify({"error": "Could not read image"})

    px_w = max(1, int(round(w_mm / 25.4 * dpi)))
    px_h = max(1, int(round(h_mm / 25.4 * dpi)))

    # Build base white-background canvas, paste fitted image on it
    base = np.full((px_h, px_w, 3), bg, dtype=np.uint8)
    fitted = _fit_cover(img, px_w, px_h)
    base[:, :] = fitted

    out_single = utils.out_path(uid, "id")
    utils.write_jpg(out_single, base, quality=95)

    out = {"image": utils.public_url(uid, "id"),
           "size": f"{px_w} x {px_h} px @ {dpi} DPI ({w_mm}×{h_mm} mm)"}

    if copies_per_a4 > 0:
        # Build an A4 sheet (210x297 mm at the same DPI) packed with N copies.
        a4_w = int(round(210 / 25.4 * dpi))
        a4_h = int(round(297 / 25.4 * dpi))
        sheet = np.full((a4_h, a4_w, 3), 255, dtype=np.uint8)
        # arrange in a grid that fits — naive: rows x cols closest to copies
        cols = max(1, int(np.floor(a4_w / (px_w + 20))))
        rows_needed = int(np.ceil(copies_per_a4 / cols))
        gap_x = max(10, int((a4_w - cols * px_w) / (cols + 1)))
        gap_y = max(10, int((a4_h - rows_needed * px_h) / (rows_needed + 1)))
        n = 0
        for r in range(rows_needed):
            for c in range(cols):
                if n >= copies_per_a4: break
                x0 = gap_x + c * (px_w + gap_x)
                y0 = gap_y + r * (px_h + gap_y)
                if x0 + px_w <= a4_w and y0 + px_h <= a4_h:
                    sheet[y0:y0 + px_h, x0:x0 + px_w] = base
                    n += 1
        sheet_path = utils.out_path(uid, "id_sheet")
        utils.write_jpg(sheet_path, sheet, quality=95)
        out["sheet"] = utils.public_url(uid, "id_sheet")
        out["sheet_count"] = n

    return jsonify(out)
