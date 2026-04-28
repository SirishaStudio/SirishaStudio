"""LONG / FULL AADHAR — keep the entire PDF page; expose the photo region inside
it for levels controls. The user can also paste/drop a screenshot of the digital-
signature tick (taken from Adobe Reader) onto the page; that's handled entirely
client-side as a draggable, resizable overlay that's baked in on Print/Download.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("aadhar_long", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
# ============================================================
TOOL_KEY     = "aadhar_long"
DPI          = 700
# Photo region inside the FULL-page Aadhar PDF (700 DPI source pixels).
# = front-crop offset (478, 5565) + short-aadhar PHOTO_REGION (223, 338, 516, 633).
PHOTO_REGION = {"x": 478 + 223, "y": 5565 + 338, "w": 516, "h": 633}
LEVELS       = {"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2}
PRINT_SCALE  = 1.00
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "photo_region": PHOTO_REGION, "levels": LEVELS,
        "print_scale": PRINT_SCALE, "dpi": DPI,
    })


@bp.route("/long-aadhar")
def page():
    c = _cfg()
    return render_template(
        "tool_single.html",
        title="Long Aadhar (Full Page)", tool_key=TOOL_KEY,
        process_url="/long-aadhar/process",
        accept=".pdf,.jpg,.jpeg,.png",
        needs_password=True,
        photo_region=c["photo_region"],
        defaults=c["levels"],
        print_scale=c["print_scale"],
        allow_paste_overlay=True,
        cfg=c,
    )


@bp.route("/long-aadhar/process", methods=["POST"])
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

    out = utils.out_path(uid, "full")
    utils.write_jpg(out, img)
    return jsonify({"image": utils.public_url(uid, "full")})
