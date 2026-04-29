"""PAN — single PDF page, two card crops on the same page.

ONE coordinate set is used for both Old- and New-style PAN PDFs (you finalised
to a single layout). The mode toggle was removed; if you ever need a separate
old layout, override `crop` via Dev Mode.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("pan", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
# ============================================================
TOOL_KEY     = "pan"
DPI          = 700

# Single, finalised PAN crop (y1, y2, x1, x2):
CROP         = {"front": [6084, 7682, 331, 2832],
                "back":  [6108, 7686, 2957, 5446]}

# Photo zone on the FRONT after crop. Locked-in coords from your Dev-Mode pick.
# Cropped front is roughly 2501 x 1598; coords are in canvas-pixel space.
PHOTO_REGION       = {"x": 68, "y": 294, "w": 435, "h": 533}
FRONT_CANVAS_72DPI = {"w": 2501, "h": 1598}

# PAN auto-darkens slightly, so default Black is 80, Gamma 1.2:
LEVELS       = {"g_black": 80, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2}

# 102 % print scale (cards print very slightly larger than physical):
PRINT_SCALE  = 1.02
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "crop": CROP,
        "photo_region": PHOTO_REGION,
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
        photo_region=c["photo_region"],
        photo_regions=None,
        erase_region=None,
        defaults=c["levels"],
        print_scale=c["print_scale"],
        print_mode="dual",
        modes=None,
        cfg=c,
    )


@bp.route("/pan/process", methods=["POST"])
def process():
    file = request.files.get("file")
    password = request.form.get("password", "")
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

    crop = c["crop"]
    fy1, fy2, fx1, fx2 = crop["front"]
    by1, by2, bx1, bx2 = crop["back"]
    front = utils.safe_crop(img, fy1, fy2, fx1, fx2)
    back  = utils.safe_crop(img, by1, by2, bx1, bx2)
    if front is None or back is None:
        return jsonify({"error": "Source image too small for PAN crops (need a real PAN PDF)."})

    utils.write_jpg(utils.out_path(uid, "f"), front)
    utils.write_jpg(utils.out_path(uid, "b"), back)
    return jsonify({"front": utils.public_url(uid, "f"), "back": utils.public_url(uid, "b")})
