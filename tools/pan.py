"""PAN — single PDF page, two card crops on the same page.
Crops match your offline pan script exactly.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("pan", __name__)

# y1:y2, x1:x2  (700 DPI source)
FRONT_CROP = (6084, 7682, 331, 2832)
BACK_CROP  = (6108, 7686, 2957, 5446)


@bp.route("/pan")
def page():
    return render_template(
        "tool_dual.html",
        title="PAN",
        process_url="/pan/process",
        accept=".pdf,.jpg,.jpeg,.png",
        needs_password=True,
        photo_region=None,
        erase_region=None,
        defaults={"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2},
    )


@bp.route("/pan/process", methods=["POST"])
def process():
    file = request.files.get("file")
    password = request.form.get("password", "")
    if not file:
        return jsonify({"error": "No file uploaded"})

    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)

    try:
        if ext == "pdf":
            password = utils.auto_password_from_name(file.filename, password)
            try:
                img = utils.pdf_to_image(path, password=password, dpi=700)
            except Exception:
                return jsonify({"ask_password": True})
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
        return jsonify({"error": "Source image too small for PAN crops (need a 700-DPI render of a real PAN PDF)."})

    f_path = utils.out_path(uid, "f")
    b_path = utils.out_path(uid, "b")
    utils.write_jpg(f_path, front)
    utils.write_jpg(b_path, back)

    return jsonify({
        "front": utils.public_url(uid, "f"),
        "back":  utils.public_url(uid, "b"),
    })
