"""DL — Driving Licence: TWO-PAGE PDF (page 1 = front, page 2 = back).

Like RC, but DL has a portrait photo on the FRONT, so it gets the same dual
PHOTO + GLOBAL levels treatment as PAN.

DL PDFs commonly come with two thick black borders. After the page crop, we
auto-trim those borders by detecting the inset bounding box of non-near-black
pixels. The user can disable auto-trim or specify manual margins through
Dev Mode (saved per-tool in overrides.json).
"""

import cv2
import numpy as np

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("dl", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
# ============================================================
TOOL_KEY     = "dl"
DPI          = 700

# Each page is cropped to this rectangle (y1, y2, x1, x2). Update to fit your DLs.
FRONT_CROP   = [0, 1488, 0, 2344]
BACK_CROP    = [0, 1488, 0, 2344]

# Photo on the FRONT (your spec, given at canvas 2344x1488 = front_crop dims).
PHOTO_REGION_72DPI = {"x": 1791, "y": 314, "w": 401, "h": 401}
FRONT_CANVAS_72DPI = {"w": 2344, "h": 1488}

LEVELS       = {"g_black": 0, "g_gamma": 1.0, "p_white": 255, "p_gamma": 1.0}
PRINT_SCALE  = 1.00

# Auto-trim of the two black borders DL PDFs ship with.
#   threshold      = pixel value below which we consider it "border black"
#   inner_pad_px   = after detecting the inset, push in another N px to be safe
#                    (eats hairline border remains)
#   max_trim_pct   = safety cap; refuses to trim more than X% of width/height
#                    on any edge so we never over-crop a real card.
AUTO_TRIM = {
    "enabled": True,
    "threshold": 30,
    "inner_pad_px": 4,
    "max_trim_pct": 25,
}
# Manual trim in pixels (applied AFTER auto-trim, so you can fine-tune).
# Edit via Dev Mode -> "DL border trim" panel.
MANUAL_TRIM = {"top": 0, "bottom": 0, "left": 0, "right": 0}
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "front_crop": FRONT_CROP, "back_crop": BACK_CROP,
        "photo_region_72dpi": PHOTO_REGION_72DPI,
        "front_canvas_72dpi": FRONT_CANVAS_72DPI,
        "levels": LEVELS, "print_scale": PRINT_SCALE, "dpi": DPI,
        "auto_trim": AUTO_TRIM,
        "manual_trim": MANUAL_TRIM,
    })


def _auto_trim_borders(img, settings):
    """Find the bounding box of non-near-black pixels and crop tightly.
    Falls back to the original image if the detection looks degenerate.
    """
    if img is None or not settings.get("enabled", True):
        return img
    h, w = img.shape[:2]
    threshold = int(settings.get("threshold", 30))
    pad = int(settings.get("inner_pad_px", 4))
    max_pct = float(settings.get("max_trim_pct", 25)) / 100.0

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = gray > threshold

    cols = np.where(mask.any(axis=0))[0]
    rows = np.where(mask.any(axis=1))[0]
    if cols.size == 0 or rows.size == 0:
        return img

    x1, x2 = int(cols[0]), int(cols[-1]) + 1
    y1, y2 = int(rows[0]), int(rows[-1]) + 1

    x1 = min(x1 + pad, w);  y1 = min(y1 + pad, h)
    x2 = max(x2 - pad, 0);  y2 = max(y2 - pad, 0)

    # Safety: refuse to trim more than max_trim_pct on any side.
    cap_left   = int(w * max_pct)
    cap_right  = int(w * max_pct)
    cap_top    = int(h * max_pct)
    cap_bottom = int(h * max_pct)
    x1 = min(x1, cap_left)
    y1 = min(y1, cap_top)
    x2 = max(x2, w - cap_right)
    y2 = max(y2, h - cap_bottom)

    if x2 <= x1 or y2 <= y1:
        return img
    return img[y1:y2, x1:x2].copy()


def _manual_trim(img, m):
    if img is None: return img
    h, w = img.shape[:2]
    t = max(0, int(m.get("top", 0)));     b = max(0, int(m.get("bottom", 0)))
    l = max(0, int(m.get("left", 0)));    r = max(0, int(m.get("right", 0)))
    if t + b >= h or l + r >= w:
        return img
    return img[t:h - b, l:w - r].copy()


@bp.route("/dl")
def page():
    c = _cfg()
    return render_template(
        "tool_dual.html",
        title="Driving Licence (DL)", tool_key=TOOL_KEY,
        process_url="/dl/process",
        accept=".pdf",
        needs_password=False,
        photo_region=None,
        photo_regions={
            "regions_72dpi": {"main": c["photo_region_72dpi"]},
            "front_canvas_72dpi": c["front_canvas_72dpi"],
        },
        erase_region=None,
        defaults=c["levels"],
        print_scale=c["print_scale"],
        print_mode="dual",
        modes=None,
        cfg=c,
        # extra panels for tool_dual.html to render in DEV mode
        dev_extras={
            "dl_border": True,
            "dl_border_settings": {
                "auto_trim": c["auto_trim"],
                "manual_trim": c["manual_trim"],
            },
        },
    )


@bp.route("/dl/process", methods=["POST"])
def process():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"})

    c = _cfg()
    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)
    if ext != "pdf":
        return jsonify({"error": "DL requires a 2-page PDF"})

    try:
        pages = utils.pdf_to_images_all(path, dpi=c["dpi"])
    except Exception as e:
        return jsonify({"error": f"PDF read failed: {e}"})
    if not pages:
        return jsonify({"error": "Empty PDF"})

    fy1, fy2, fx1, fx2 = c["front_crop"]
    front = utils.safe_crop(pages[0], fy1, fy2, fx1, fx2)
    if front is None:
        return jsonify({"error": "Front page too small for DL crop."})
    front = _auto_trim_borders(front, c["auto_trim"])
    front = _manual_trim(front, c["manual_trim"])
    utils.write_jpg(utils.out_path(uid, "f"), front)

    out = {"front": utils.public_url(uid, "f"), "back": None}

    if len(pages) >= 2:
        by1, by2, bx1, bx2 = c["back_crop"]
        back = utils.safe_crop(pages[1], by1, by2, bx1, bx2)
        if back is not None:
            back = _auto_trim_borders(back, c["auto_trim"])
            back = _manual_trim(back, c["manual_trim"])
            utils.write_jpg(utils.out_path(uid, "b"), back)
            out["back"] = utils.public_url(uid, "b")

    return jsonify(out)
