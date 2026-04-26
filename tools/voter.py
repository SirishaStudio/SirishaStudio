"""VOTER — single PDF/Image, two crops on the same page."""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("voter", __name__)

# y1:y2, x1:x2  (700 DPI source)
FRONT_CROP = (925, 2415, 320, 2690)
BACK_CROP  = (925, 2420, 3178, 5555)


@bp.route("/voter")
def page():
    return render_template(
        "tool_dual.html",
        title="Voter ID",
        process_url="/voter/process",
        accept=".pdf,.jpg,.jpeg,.png",
        needs_password=False,
        photo_region=None,
        erase_region=None,
        defaults={"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2},
    )


@bp.route("/voter/process", methods=["POST"])
def process():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"})

    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)

    try:
        if ext == "pdf":
            try:
                img = utils.pdf_to_image(path, dpi=700)
            except Exception as e:
                return jsonify({"error": f"PDF read failed: {e}"})
        else:
            import cv2
            img = cv2.imread(path)
            if img is None:
                return jsonify({"error": "Could not read image"})
    except Exception as e:
        return jsonify({"error": str(e)})

    fy1, fy2, fx1, fx2 = FRONT_CROP
    by1, by2, bx1, bx2 = BACK_CROP
    front = utils.safe_crop(img, fy1, fy2, fx1, fx2)
    back  = utils.safe_crop(img, by1, by2, bx1, bx2)
    if front is None or back is None:
        return jsonify({"error": "Source too small for Voter crops."})

    f_path = utils.out_path(uid, "f")
    b_path = utils.out_path(uid, "b")
    utils.write_jpg(f_path, front)
    utils.write_jpg(b_path, back)

    return jsonify({
        "front": utils.public_url(uid, "f"),
        "back":  utils.public_url(uid, "b"),
    })
