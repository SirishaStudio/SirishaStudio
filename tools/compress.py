"""COMPRESS — bring an image's file size down to a target KB by binary-searching
the JPEG quality. Useful for govt portals that demand "image must be < 100 KB".
"""

import os, time
import cv2
import numpy as np

from flask import Blueprint, render_template, request, jsonify
from . import utils
from config import OUTPUT_DIR

bp = Blueprint("compress", __name__)


@bp.route("/compress")
def page():
    return render_template("tool_compress.html")


def _encode_jpg(img, quality):
    ok, buf = cv2.imencode(".jpg", img,
                           [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return None
    return buf.tobytes()


def _scale(img, factor):
    h, w = img.shape[:2]
    nw = max(1, int(round(w * factor)))
    nh = max(1, int(round(h * factor)))
    return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)


@bp.route("/compress/process", methods=["POST"])
def process():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No image uploaded"})

    try:
        target_kb = float(request.form.get("target_kb") or 100)
        max_dim = int(request.form.get("max_dim") or 0)  # 0 = keep original
    except Exception:
        return jsonify({"error": "Bad parameters"})

    uid, path = utils.save_upload(file)
    img = cv2.imread(path)
    if img is None:
        return jsonify({"error": "Could not read image"})

    if max_dim > 0:
        h, w = img.shape[:2]
        m = max(h, w)
        if m > max_dim:
            img = _scale(img, max_dim / m)

    target_bytes = int(target_kb * 1024)

    # Binary search quality 95 -> 20
    best_buf = None
    best_q = 95
    lo, hi = 20, 95
    # First check: if maximum quality already fits, take it.
    buf95 = _encode_jpg(img, 95)
    if buf95 is not None and len(buf95) <= target_bytes:
        best_buf, best_q = buf95, 95
    else:
        for _ in range(8):
            mid = (lo + hi) // 2
            buf = _encode_jpg(img, mid)
            if buf is None:
                break
            if len(buf) <= target_bytes:
                best_buf, best_q = buf, mid
                lo = mid + 1
            else:
                hi = mid - 1

    # If still too big, progressively scale down + retry quality search
    scale = 1.0
    while best_buf is None and scale > 0.2:
        scale *= 0.85
        scaled = _scale(img, scale)
        for q in (75, 60, 50, 40, 30, 20):
            buf = _encode_jpg(scaled, q)
            if buf and len(buf) <= target_bytes:
                best_buf, best_q = buf, q
                break

    if best_buf is None:
        return jsonify({"error": "Could not reach the target size — try a larger target."})

    out_name = f"{uid}_compressed.jpg"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    with open(out_path, "wb") as f:
        f.write(best_buf)
    kb = len(best_buf) / 1024.0
    return jsonify({
        "image": f"/file/{out_name}",
        "size_kb": round(kb, 1),
        "quality": best_q,
        "target_kb": target_kb,
    })
