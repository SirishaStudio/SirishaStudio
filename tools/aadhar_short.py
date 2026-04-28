"""SHORT AADHAR — single PDF page, two card crops on the same page."""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("aadhar_short", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
#  (Dev Mode in the UI can override these without code changes.)
# ============================================================
TOOL_KEY     = "aadhar_short"
DPI          = 700
FRONT_CROP   = [5565, 7128, 478, 2928]   # y1, y2, x1, x2
BACK_CROP    = [5570, 7128, 3031, 5476]
PHOTO_REGION = {"x": 223, "y": 338, "w": 516, "h": 633}
ERASE_REGION = {"x": 2189, "y": 0, "w": 188, "h": 28}
LEVELS       = {"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2}
PRINT_SCALE  = 1.00
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "front_crop": FRONT_CROP, "back_crop": BACK_CROP,
        "photo_region": PHOTO_REGION, "erase_region": ERASE_REGION,
        "levels": LEVELS, "print_scale": PRINT_SCALE, "dpi": DPI,
    })


@bp.route("/short-aadhar")
def page():
    c = _cfg()
    return render_template(
        "tool_dual.html",
        title="Short Aadhar", tool_key=TOOL_KEY,
        process_url="/short-aadhar/process",
        accept=".pdf,.jpg,.jpeg,.png",
        needs_password=True,
        photo_region=c["photo_region"],
        photo_regions=None,
        erase_region=c["erase_region"],
        defaults=c["levels"],
        print_scale=c["print_scale"],
        print_mode="dual",
        modes=None,
        cfg=c,
    )


@bp.route("/short-aadhar/process", methods=["POST"])
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

    fy1, fy2, fx1, fx2 = c["front_crop"]
    by1, by2, bx1, bx2 = c["back_crop"]
    front = utils.safe_crop(img, fy1, fy2, fx1, fx2)
    back  = utils.safe_crop(img, by1, by2, bx1, bx2)
    if front is None or back is None:
        return jsonify({"error": "Source image too small for Aadhar crops (need a 700-DPI render of a real Aadhar PDF)."})

    utils.write_jpg(utils.out_path(uid, "f"), front)
    utils.write_jpg(utils.out_path(uid, "b"), back)

    return jsonify({"front": utils.public_url(uid, "f"), "back": utils.public_url(uid, "b")})
