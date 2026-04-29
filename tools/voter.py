"""VOTER — single PDF / image, two crops on the same page.

Voter front carries a single photo zone (locked-in coords from your Dev-Mode
pick). Levels are tuned for typical voter PDFs.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("voter", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
# ============================================================
TOOL_KEY     = "voter"
DPI          = 700

FRONT_CROP   = [925, 2415, 320, 2690]    # y1, y2, x1, x2
BACK_CROP    = [925, 2420, 3178, 5555]

# Photo region on the FRONT (locked-in from Dev Mode pick).
PHOTO_REGIONS_72DPI = {
    "color": {"x": 84, "y": 569, "w": 608, "h": 797},
}
FRONT_CANVAS_72DPI = {"w": 2370, "h": 1490}
BACK_CANVAS_72DPI  = {"w": 2377, "h": 1495}

# Locked-in: Black 65 / Gamma 1.3 / White 255 / Photo Gamma 1.3
LEVELS       = {"g_black": 65, "g_gamma": 1.3, "p_white": 255, "p_gamma": 1.3}
PRINT_SCALE  = 1.00
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "front_crop": FRONT_CROP, "back_crop": BACK_CROP,
        "photo_regions_72dpi": PHOTO_REGIONS_72DPI,
        "front_canvas_72dpi": FRONT_CANVAS_72DPI,
        "back_canvas_72dpi":  BACK_CANVAS_72DPI,
        "levels": LEVELS, "print_scale": PRINT_SCALE, "dpi": DPI,
    })


@bp.route("/voter")
def page():
    c = _cfg()
    return render_template(
        "tool_dual.html",
        title="Voter ID", tool_key=TOOL_KEY,
        process_url="/voter/process",
        accept=".pdf,.jpg,.jpeg,.png",
        needs_password=False,
        photo_region=None,
        photo_regions={
            "regions_72dpi": c["photo_regions_72dpi"],
            "front_canvas_72dpi": c["front_canvas_72dpi"],
        },
        erase_region=None,
        defaults=c["levels"],
        print_scale=c["print_scale"],
        print_mode="dual",
        modes=None,
        cfg=c,
    )


@bp.route("/voter/process", methods=["POST"])
def process():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"})

    c = _cfg()
    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)

    try:
        if ext == "pdf":
            try:
                img = utils.pdf_to_image(path, dpi=c["dpi"])
            except Exception as e:
                return jsonify({"error": f"PDF read failed: {e}"})
        else:
            import cv2
            img = cv2.imread(path)
            if img is None:
                return jsonify({"error": "Could not read image"})
    except Exception as e:
        return jsonify({"error": str(e)})

    fy1, fy2, fx1, fx2 = c["front_crop"]
    by1, by2, bx1, bx2 = c["back_crop"]
    front = utils.safe_crop(img, fy1, fy2, fx1, fx2)
    back  = utils.safe_crop(img, by1, by2, bx1, bx2)
    if front is None or back is None:
        return jsonify({"error": "Source too small for Voter crops."})

    utils.write_jpg(utils.out_path(uid, "f"), front)
    utils.write_jpg(utils.out_path(uid, "b"), back)
    return jsonify({"front": utils.public_url(uid, "f"), "back": utils.public_url(uid, "b")})
