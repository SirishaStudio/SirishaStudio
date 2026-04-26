"""RC — TWO-PAGE PDF (page 1 = front, page 2 = back).
Auto applies your alpha=1.2 / beta=-40 levels server-side, like the offline script.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("rc", __name__)

CROP_W = 2464
CROP_H = 1543
X_START = 0
Y_START = 0
ALPHA = 1.2
BETA = -40


@bp.route("/rc")
def page():
    return render_template(
        "tool_dual.html",
        title="RC (Vehicle Registration)",
        process_url="/rc/process",
        accept=".pdf",
        needs_password=False,
        photo_region=None,
        erase_region=None,
        defaults={"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2},
    )


@bp.route("/rc/process", methods=["POST"])
def process():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"})

    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)
    if ext != "pdf":
        return jsonify({"error": "RC requires a 2-page PDF"})

    try:
        pages = utils.pdf_to_images_all(path, dpi=700)
    except Exception as e:
        return jsonify({"error": f"PDF read failed: {e}"})

    if not pages:
        return jsonify({"error": "Empty PDF"})

    front = utils.safe_crop(pages[0], Y_START, Y_START + CROP_H, X_START, X_START + CROP_W)
    if front is None:
        return jsonify({"error": "Front page too small for RC crop."})
    front = utils.apply_levels(front, alpha=ALPHA, beta=BETA)
    utils.write_jpg(utils.out_path(uid, "f"), front)

    out = {"front": utils.public_url(uid, "f"), "back": None}

    if len(pages) >= 2:
        back = utils.safe_crop(pages[1], Y_START, Y_START + CROP_H, X_START, X_START + CROP_W)
        if back is not None:
            back = utils.apply_levels(back, alpha=ALPHA, beta=BETA)
            utils.write_jpg(utils.out_path(uid, "b"), back)
            out["back"] = utils.public_url(uid, "b")

    return jsonify(out)
