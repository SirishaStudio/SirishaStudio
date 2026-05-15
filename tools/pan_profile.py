"""PAN Profile — stores named applicant profiles and provides three image converters.

Photo spec      : JPEG, 200 DPI, 3.5 × 2.5 cm  (≈ 276 × 197 px), ≤ 50 KB
Signature spec  : JPEG, 200 DPI, 2.0 × 4.5 cm  (≈ 157 × 354 px), ≤ 50 KB
Document spec   : PDF, max 300 KB per page

Profiles saved to pan_profile.json in project root.
Structure: { "profiles": [ { "label": "...", "saved_at": epoch, ...fields... } ] }
"""

import os, io, json, time
from flask import Blueprint, render_template, request, jsonify, send_file
from PIL import Image
from config import BASE_DIR, OUTPUT_DIR

bp = Blueprint("pan_profile", __name__)

PROFILE_PATH = os.path.join(BASE_DIR, "pan_profile.json")

DPI = 200
PHOTO_W, PHOTO_H = int(round(3.5 * DPI / 2.54)), int(round(2.5 * DPI / 2.54))   # 276 × 197
SIG_W,   SIG_H   = int(round(4.5 * DPI / 2.54)), int(round(2.0 * DPI / 2.54))   # 354 × 157
MAX_PHOTO_KB     = 50
MAX_SIG_KB       = 50
MAX_DOC_PAGE_KB  = 300


def _load_profiles():
    try:
        with open(PROFILE_PATH) as f:
            data = json.load(f)
        if isinstance(data, list):
            # migrate old flat list structure
            return data
        return data.get("profiles", [])
    except Exception:
        return []


def _save_profiles(profiles):
    with open(PROFILE_PATH, "w") as f:
        json.dump({"profiles": profiles}, f, indent=2)


def _compress_jpeg(img: Image.Image, max_kb: int, w: int, h: int) -> bytes:
    img = img.convert("RGB").resize((w, h), Image.LANCZOS)
    lo, hi, best = 10, 95, None
    while lo <= hi:
        mid = (lo + hi) // 2
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=mid, dpi=(DPI, DPI))
        if buf.tell() <= max_kb * 1024:
            best = buf.getvalue(); lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=10, dpi=(DPI, DPI)); best = buf.getvalue()
    return best


# ============================================================
#  Routes
# ============================================================
@bp.route("/pan-profile")
def page():
    return render_template("tool_pan_profile.html")


@bp.route("/pan-profile/profiles", methods=["GET"])
def get_profiles():
    return jsonify({"profiles": _load_profiles()})


@bp.route("/pan-profile/save", methods=["POST"])
def save_profile():
    j = request.get_json(silent=True) or {}
    label = (j.get("label") or "").strip()
    if not label:
        return jsonify({"error": "Label is required"})
    profiles = _load_profiles()
    # Remove existing with same label (update)
    profiles = [p for p in profiles if p.get("label") != label]
    entry = dict(j)
    entry["label"] = label
    entry["saved_at"] = int(time.time())
    profiles.append(entry)
    _save_profiles(profiles)
    return jsonify({"ok": True, "label": label})


@bp.route("/pan-profile/delete", methods=["POST"])
def delete_profile():
    j = request.get_json(silent=True) or {}
    label = (j.get("label") or "").strip()
    profiles = _load_profiles()
    profiles = [p for p in profiles if p.get("label") != label]
    _save_profiles(profiles)
    return jsonify({"ok": True})


@bp.route("/pan-profile/convert-photo", methods=["POST"])
def convert_photo():
    f = request.files.get("file")
    if not f: return jsonify({"error": "No file"})
    try:
        data = _compress_jpeg(Image.open(f.stream), MAX_PHOTO_KB, PHOTO_W, PHOTO_H)
    except Exception as e:
        return jsonify({"error": str(e)})
    nm = f"pan_photo_{int(time.time())}.jpg"
    path = os.path.join(OUTPUT_DIR, nm)
    with open(path, "wb") as fp: fp.write(data)
    return jsonify({"out": f"/file/{nm}", "name": nm,
                    "size_kb": round(len(data)/1024, 1), "dims": f"{PHOTO_W}×{PHOTO_H} px"})


@bp.route("/pan-profile/convert-signature", methods=["POST"])
def convert_signature():
    f = request.files.get("file")
    if not f: return jsonify({"error": "No file"})
    try:
        data = _compress_jpeg(Image.open(f.stream), MAX_SIG_KB, SIG_W, SIG_H)
    except Exception as e:
        return jsonify({"error": str(e)})
    nm = f"pan_signature_{int(time.time())}.jpg"
    path = os.path.join(OUTPUT_DIR, nm)
    with open(path, "wb") as fp: fp.write(data)
    return jsonify({"out": f"/file/{nm}", "name": nm,
                    "size_kb": round(len(data)/1024, 1), "dims": f"{SIG_W}×{SIG_H} px"})


@bp.route("/pan-profile/convert-document", methods=["POST"])
def convert_document():
    f = request.files.get("file")
    if not f: return jsonify({"error": "No file"})
    try:
        from pdf2image import convert_from_bytes
        from config import POPPLER_PATH
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        raw = f.read()
        pages_pil = (convert_from_bytes(raw, dpi=150, poppler_path=POPPLER_PATH)
                     if ext == "pdf" else [Image.open(io.BytesIO(raw)).convert("RGB")])
        compressed = []
        for pg in pages_pil:
            lo, hi, best = 20, 95, None
            while lo <= hi:
                mid = (lo + hi) // 2
                b = io.BytesIO(); pg.save(b, "JPEG", quality=mid)
                if b.tell() <= MAX_DOC_PAGE_KB * 1024:
                    best = b.getvalue(); lo = mid + 1
                else: hi = mid - 1
            if best is None:
                b = io.BytesIO(); pg.save(b, "JPEG", quality=10); best = b.getvalue()
            compressed.append(Image.open(io.BytesIO(best)).convert("RGB"))
        nm = f"pan_document_{int(time.time())}.pdf"
        out = os.path.join(OUTPUT_DIR, nm)
        compressed[0].save(out, "PDF", save_all=True,
                           append_images=compressed[1:], resolution=150.0)
        return jsonify({"out": f"/file/{nm}", "name": nm,
                        "pages": len(compressed), "total_kb": round(os.path.getsize(out)/1024, 1)})
    except Exception as e:
        return jsonify({"error": str(e)})
