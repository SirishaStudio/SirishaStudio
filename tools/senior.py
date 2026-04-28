"""SENIOR CITIZENSHIP — single PDF page, two crops on the same page.
Source rendered at 500 DPI like the offline script (matches your old crop math).
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("senior", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
#  Crop math is identical to your offline script (700 DPI source coords scaled
#  to 500 DPI):
#    F_X = int(1692 * 500/700) = 1208     F_W = int(2328 * 500/700) = 1662
#    F_Y = int(1123 * 500/700) = 802      F_H = int(1465 * 500/700) = 1046
#    B_X = int(1696 * 500/700) = 1211     B_Y = int(3066 * 500/700) = 2190
# ============================================================
TOOL_KEY     = "senior"
DPI          = 500

# y1, y2, x1, x2 (rendered at DPI above)
FRONT_CROP   = [802,  802 + 1046, 1208, 1208 + 1662]
BACK_CROP    = [2190, 2190 + 1046, 1211, 1211 + 1662]

# Photo region on the FRONT after crop, given at 72-DPI display canvas.
# Cropped front is 1662 x 1046 @ 72 DPI -> JS scales these into canvas pixels.
PHOTO_REGION_72DPI = {"x": 25.9, "y": 122.1, "w": 129.8, "h": 162.6}
FRONT_CANVAS_72DPI = {"w": 1662, "h": 1046}

LEVELS       = {"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2}
PRINT_SCALE  = 1.00
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "front_crop": FRONT_CROP, "back_crop": BACK_CROP,
        "photo_region_72dpi": PHOTO_REGION_72DPI,
        "front_canvas_72dpi": FRONT_CANVAS_72DPI,
        "levels": LEVELS, "print_scale": PRINT_SCALE, "dpi": DPI,
    })


@bp.route("/senior")
def page():
    c = _cfg()
    return render_template(
        "tool_dual.html",
        title="Senior Citizen Card", tool_key=TOOL_KEY,
        process_url="/senior/process",
        accept=".pdf",
        needs_password=True,
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
    )


@bp.route("/senior/process", methods=["POST"])
def process():
    file = request.files.get("file")
    password = request.form.get("password", "")
    if not file:
        return jsonify({"error": "No file uploaded"})

    c = _cfg()
    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)
    if ext != "pdf":
        return jsonify({"error": "Senior Citizen requires a PDF"})

    password = utils.auto_password_from_name(file.filename, password)

    try:
        img = utils.pdf_to_image(path, password=password, dpi=c["dpi"])
    except Exception:
        return jsonify({"ask_password": True})

    fy1, fy2, fx1, fx2 = c["front_crop"]
    by1, by2, bx1, bx2 = c["back_crop"]
    front = utils.safe_crop(img, fy1, fy2, fx1, fx2)
    back  = utils.safe_crop(img, by1, by2, bx1, bx2)
    if front is None or back is None:
        return jsonify({"error": "Source too small for Senior Citizen crops."})

    utils.write_jpg(utils.out_path(uid, "f"), front, quality=98)
    utils.write_jpg(utils.out_path(uid, "b"), back,  quality=98)
    return jsonify({"front": utils.public_url(uid, "f"), "back": utils.public_url(uid, "b")})
