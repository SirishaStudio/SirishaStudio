"""PAN — single PDF page, two card crops on the same page.

Old-style and New-style PAN PDFs have DIFFERENT alignments AND different photo
zones, so we keep two complete coordinate sets and a `mode` toggle in the UI.
The backend returns the active `photo_region` so the front-end levels code
masks the right area for the selected mode.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("pan", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
# ============================================================
TOOL_KEY     = "pan"
DPI          = 700

# NEW style PAN PDF — crop coords (y1, y2, x1, x2) of front + back on the page.
CROP_NEW           = {"front": [6084, 7682, 331, 2832],
                      "back":  [6108, 7686, 2957, 5446]}
# Photo zone on the cropped NEW front (canvas-pixel space, ~2501x1598).
PHOTO_REGION_NEW   = {"x": 68,  "y": 294, "w": 435, "h": 533}

# OLD style PAN PDF — different crop window on the page.
CROP_OLD           = {"front": [6332, 7760,  662, 2940],
                      "back":  [6328, 7763, 2989, 5275]}
# Photo zone on the cropped OLD front (different position than NEW).
# Adjustable any time from Dev Mode → "Pick on FRONT" → "Save as photo region"
# while in OLD mode.
PHOTO_REGION_OLD   = {"x": 1500, "y": 280, "w": 720, "h": 880}

FRONT_CANVAS_72DPI = {"w": 2501, "h": 1598}

# PAN auto-darkens slightly, so default Black is 80, Gamma 1.2:
LEVELS       = {"g_black": 80, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2}

# 102 % print scale (cards print very slightly larger than physical):
PRINT_SCALE  = 1.02
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "crop_new":         CROP_NEW,
        "crop_old":         CROP_OLD,
        "photo_region_new": PHOTO_REGION_NEW,
        "photo_region_old": PHOTO_REGION_OLD,
        # `photo_region` is only used to seed the page; the real one is sent
        # back per-process in JSON so the JS uses the right one for the mode.
        "photo_region":      PHOTO_REGION_NEW,
        "front_canvas_72dpi": FRONT_CANVAS_72DPI,
        "levels": LEVELS,
        "print_scale": PRINT_SCALE, "dpi": DPI,
    })


@bp.route("/pan")
def page():
    c = _cfg()
    return render_template(
        "tool_dual.html",
        title="PAN", tool_key=TOOL_KEY,
        process_url="/pan/process",
        accept=".pdf,.jpg,.jpeg,.png",
        needs_password=True,
        photo_region=c["photo_region_new"],
        photo_regions=None,
        erase_region=None,
        defaults=c["levels"],
        print_scale=c["print_scale"],
        print_mode="dual",
        modes=[{"key": "new", "label": "New PAN"},
               {"key": "old", "label": "Old PAN"}],
        cfg=c,
    )


@bp.route("/pan/process", methods=["POST"])
def process():
    file = request.files.get("file")
    password = request.form.get("password", "")
    mode = (request.form.get("mode") or "new").lower()
    if not file:
        return jsonify({"error": "No file uploaded"})

    c = _cfg()
    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)

    try:
        if ext == "pdf":
            password = utils.auto_password_from_name(file.filename, password)
            try:
                img = utils.pdf_to_image(path, password=password, dpi=c["dpi"])
            except Exception:
                return jsonify({"ask_password": True})
        else:
            import cv2
            img = cv2.imread(path)
            if img is None:
                return jsonify({"error": "Could not read image"})
    except Exception as e:
        return jsonify({"error": str(e)})

    crop = c["crop_old"] if mode == "old" else c["crop_new"]
    photo_region = c["photo_region_old"] if mode == "old" else c["photo_region_new"]

    fy1, fy2, fx1, fx2 = crop["front"]
    by1, by2, bx1, bx2 = crop["back"]
    front = utils.safe_crop(img, fy1, fy2, fx1, fx2)
    back  = utils.safe_crop(img, by1, by2, bx1, bx2)
    if front is None or back is None:
        return jsonify({"error": "Source image too small for PAN crops "
                                 f"(mode={mode}). Make sure you picked the right Old/New mode."})

    utils.write_jpg(utils.out_path(uid, "f"), front)
    utils.write_jpg(utils.out_path(uid, "b"), back)
    return jsonify({
        "front": utils.public_url(uid, "f"),
        "back":  utils.public_url(uid, "b"),
        "photo_region": photo_region,   # tell the JS which zone to mask
        "mode": mode,
    })
