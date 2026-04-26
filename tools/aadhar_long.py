"""LONG / FULL AADHAR — keep the entire PDF page; expose the same PHOTO region
inside it so the user can re-use the levels controls.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("aadhar_long", __name__)

# Photo region inside the FULL-page Aadhar PDF (700 DPI, source pixels).
# These match where the photo lives in the full uncropped page (i.e. the front
# crop offset added to the short-aadhar PHOTO_REGION).
#   front crop x1 = 478, y1 = 5565  (from aadhar_short.py)
#   short photo (canvas-pixel) x = 223, y = 338, w = 516, h = 633
#  -> full-page photo: (478 + 223, 5565 + 338, 516, 633)
PHOTO_REGION_FULL = {"x": 478 + 223, "y": 5565 + 338, "w": 516, "h": 633}


@bp.route("/long-aadhar")
def page():
    return render_template(
        "tool_single.html",
        title="Long Aadhar (Full Page)",
        process_url="/long-aadhar/process",
        accept=".pdf,.jpg,.jpeg,.png",
        needs_password=True,
        photo_region=PHOTO_REGION_FULL,
        defaults={"g_black": 128, "g_gamma": 1.2, "p_white": 255, "p_gamma": 1.2},
    )


@bp.route("/long-aadhar/process", methods=["POST"])
def process():
    file = request.files.get("file")
    password = request.form.get("password", "")
    if not file:
        return jsonify({"error": "No file uploaded"})

    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)

    sig_info = None

    try:
        if ext == "pdf":
            password = utils.auto_password_from_name(file.filename, password)

            # signature check first (best-effort, never blocks processing)
            sig_info = utils.check_pdf_signature(path, password=password)

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

    out = utils.out_path(uid, "full")
    utils.write_jpg(out, img)

    return jsonify({
        "image": utils.public_url(uid, "full"),
        "signature": sig_info,
    })
