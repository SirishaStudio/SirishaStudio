"""SENIOR CITIZENSHIP — single PDF page, two crops on the same page.
Source uses 500 DPI like the offline script.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("senior", __name__)

# At 500 DPI:
F_X, F_Y, F_W, F_H = 1208, 802, 1662, 1046
B_X, B_Y, B_W, B_H = 1211, 2190, 1662, 1046


@bp.route("/senior")
def page():
    return render_template(
        "tool_dual.html",
        title="Senior Citizen Card",
        process_url="/senior/process",
        accept=".pdf",
        needs_password=True,
        photo_region=None,
        erase_region=None,
        defaults={"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2},
    )


@bp.route("/senior/process", methods=["POST"])
def process():
    file = request.files.get("file")
    password = request.form.get("password", "")
    if not file:
        return jsonify({"error": "No file uploaded"})

    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)
    if ext != "pdf":
        return jsonify({"error": "Senior Citizen requires a PDF"})

    password = utils.auto_password_from_name(file.filename, password)

    try:
        img = utils.pdf_to_image(path, password=password, dpi=500)
    except Exception:
        return jsonify({"ask_password": True})

    front = utils.safe_crop(img, F_Y, F_Y + F_H, F_X, F_X + F_W)
    back  = utils.safe_crop(img, B_Y, B_Y + B_H, B_X, B_X + B_W)
    if front is None or back is None:
        return jsonify({"error": "Source too small for Senior Citizen crops."})

    utils.write_jpg(utils.out_path(uid, "f"), front, quality=98)
    utils.write_jpg(utils.out_path(uid, "b"), back,  quality=98)

    return jsonify({
        "front": utils.public_url(uid, "f"),
        "back":  utils.public_url(uid, "b"),
    })
