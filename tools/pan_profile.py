"""PAN Profile — stores applicant data and provides three image converters.

Photo spec      : JPEG, 200 DPI, 3.5 × 2.5 cm  (≈ 276 × 197 px), ≤ 50 KB
Signature spec  : JPEG, 200 DPI, 2.0 × 4.5 cm  (≈ 157 × 354 px), ≤ 50 KB
Document spec   : PDF, max 300 KB per page

Profile data is saved to pan_profile.json in the project root.
"""

import os
import io
import json
import time
import math

from flask import Blueprint, render_template, request, jsonify, send_file
from PIL import Image

from config import BASE_DIR, OUTPUT_DIR

bp = Blueprint("pan_profile", __name__)

PROFILE_PATH = os.path.join(BASE_DIR, "pan_profile.json")

# PAN website image specs
PHOTO_SIZE_CM   = (3.5, 2.5)   # width × height
SIG_SIZE_CM     = (4.5, 2.0)   # width × height  (landscape: 4.5 wide, 2 tall)
DPI             = 200
MAX_PHOTO_KB    = 50
MAX_SIG_KB      = 50
MAX_DOC_PAGE_KB = 300

# Convert cm → px at 200 DPI
def _cm_to_px(cm): return int(round(cm * DPI / 2.54))

PHOTO_W = _cm_to_px(PHOTO_SIZE_CM[0])   # ≈ 276
PHOTO_H = _cm_to_px(PHOTO_SIZE_CM[1])   # ≈ 197
SIG_W   = _cm_to_px(SIG_SIZE_CM[0])     # ≈ 354
SIG_H   = _cm_to_px(SIG_SIZE_CM[1])     # ≈ 157


def _load_profile():
    try:
        with open(PROFILE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_profile(data):
    with open(PROFILE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _compress_jpeg(img: Image.Image, max_kb: int, target_w: int, target_h: int) -> bytes:
    """Resize image to target dims, then binary-search quality to stay under max_kb."""
    img = img.convert("RGB")
    img = img.resize((target_w, target_h), Image.LANCZOS)
    lo, hi = 10, 95
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=mid, dpi=(DPI, DPI))
        size = buf.tell()
        if size <= max_kb * 1024:
            best = buf.getvalue()
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        # Last resort: minimum quality
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=10, dpi=(DPI, DPI))
        best = buf.getvalue()
    return best


# ============================================================
#  Routes
# ============================================================
@bp.route("/pan-profile")
def page():
    profile = _load_profile()
    return render_template("tool_pan_profile.html", profile=profile)


@bp.route("/pan-profile/data", methods=["GET"])
def get_data():
    return jsonify(_load_profile())


@bp.route("/pan-profile/data", methods=["POST"])
def save_data():
    j = request.get_json(silent=True) or {}
    profile = _load_profile()
    profile.update(j)
    _save_profile(profile)
    return jsonify({"ok": True})


@bp.route("/pan-profile/convert-photo", methods=["POST"])
def convert_photo():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file"})
    try:
        img = Image.open(f.stream)
        data = _compress_jpeg(img, MAX_PHOTO_KB, PHOTO_W, PHOTO_H)
    except Exception as e:
        return jsonify({"error": str(e)})

    profile = _load_profile()
    safe_name = (profile.get("first_name", "") + "_" +
                 profile.get("last_name", "")).strip("_") or "applicant"
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "-_")
    out_name = f"{safe_name}_pan_photo_{int(time.time())}.jpg"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    with open(out_path, "wb") as fp:
        fp.write(data)

    size_kb = len(data) / 1024
    return jsonify({
        "out": f"/file/{out_name}",
        "name": out_name,
        "size_kb": round(size_kb, 1),
        "dims": f"{PHOTO_W}×{PHOTO_H} px",
    })


@bp.route("/pan-profile/convert-signature", methods=["POST"])
def convert_signature():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file"})
    try:
        img = Image.open(f.stream)
        data = _compress_jpeg(img, MAX_SIG_KB, SIG_W, SIG_H)
    except Exception as e:
        return jsonify({"error": str(e)})

    profile = _load_profile()
    safe_name = (profile.get("first_name", "") + "_" +
                 profile.get("last_name", "")).strip("_") or "applicant"
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "-_")
    out_name = f"{safe_name}_pan_signature_{int(time.time())}.jpg"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    with open(out_path, "wb") as fp:
        fp.write(data)

    size_kb = len(data) / 1024
    return jsonify({
        "out": f"/file/{out_name}",
        "name": out_name,
        "size_kb": round(size_kb, 1),
        "dims": f"{SIG_W}×{SIG_H} px",
    })


@bp.route("/pan-profile/convert-document", methods=["POST"])
def convert_document():
    """Accept PDF or image; output PDF with each page ≤ 300 KB."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file"})

    try:
        from pdf2image import convert_from_bytes
        from config import POPPLER_PATH
        import pypdf

        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        raw = f.read()

        if ext == "pdf":
            pages_pil = convert_from_bytes(raw, dpi=150,
                                           poppler_path=POPPLER_PATH)
        else:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            pages_pil = [img]

        # Compress each page to ≤ 300 KB as JPEG then wrap in PDF
        page_images = []
        for pg in pages_pil:
            buf = io.BytesIO()
            lo, hi = 20, 95
            best = None
            while lo <= hi:
                mid = (lo + hi) // 2
                b = io.BytesIO()
                pg.save(b, "JPEG", quality=mid)
                if b.tell() <= MAX_DOC_PAGE_KB * 1024:
                    best = b.getvalue()
                    lo = mid + 1
                else:
                    hi = mid - 1
            if best is None:
                b = io.BytesIO(); pg.save(b, "JPEG", quality=10)
                best = b.getvalue()
            page_images.append(Image.open(io.BytesIO(best)).convert("RGB"))

        profile = _load_profile()
        safe_name = (profile.get("first_name", "") + "_" +
                     profile.get("last_name", "")).strip("_") or "applicant"
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "-_")
        out_name = f"{safe_name}_pan_document_{int(time.time())}.pdf"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        page_images[0].save(out_path, "PDF", save_all=True,
                            append_images=page_images[1:], resolution=150.0)

        total_kb = os.path.getsize(out_path) / 1024
        return jsonify({
            "out": f"/file/{out_name}",
            "name": out_name,
            "pages": len(page_images),
            "total_kb": round(total_kb, 1),
        })

    except Exception as e:
        return jsonify({"error": str(e)})
