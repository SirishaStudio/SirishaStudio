"""ENHANCE — quick batch fixes for photos.

Quick actions: lighten, darken, whiten (CLAHE), dark-mode fix.
Hidden advanced sliders: hue, saturation, manual gamma.

Workflow:
  /enhance/upload   → get UIDs + thumbnails
  /enhance/apply    → apply an action to a list of UIDs (server overwrites
                      the working JPG; an UNDO copy is kept per-UID)
  /enhance/undo     → restore previous version
  /enhance/zip      → bundle UIDs as zip
  /enhance/pdf      → render UIDs as one A4 PDF (one image per page)
"""

import os, time, shutil, zipfile, io
from flask import Blueprint, render_template, request, jsonify, send_file
import cv2
import numpy as np
from PIL import Image
import pillow_heif

from . import utils
from config import OUTPUT_DIR

pillow_heif.register_heif_opener()
bp = Blueprint("enhance", __name__)

WORK_DIR = OUTPUT_DIR
IMG_EXTS = {"jpg","jpeg","png","webp","heic","heif","avif","bmp","gif","tif","tiff"}


def _work(uid, suffix=""):
    return os.path.join(WORK_DIR, f"{uid}_enh{suffix}.jpg")


def _undo(uid):
    return os.path.join(WORK_DIR, f"{uid}_enh_undo.jpg")


def _thumb(uid):
    return os.path.join(WORK_DIR, f"{uid}_enh_thumb.jpg")


@bp.route("/enhance")
def page():
    return render_template("tool_enhance.html", title="Enhance")


@bp.route("/enhance/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Pick at least one image"})
    out = []
    for f in files:
        if not f or not f.filename:
            continue
        ext = utils.file_ext(f.filename)
        if ext not in IMG_EXTS:
            out.append({"name": f.filename, "error": "not an image"}); continue
        uid, raw = utils.save_upload(f)
        try:
            with Image.open(raw) as im:
                im = im.convert("RGB")
                im.save(_work(uid), "JPEG", quality=92)
                # thumb
                im.thumbnail((220, 220))
                im.save(_thumb(uid), "JPEG", quality=82)
            shutil.copy(_work(uid), _undo(uid))
            out.append({
                "uid": uid, "name": f.filename,
                "thumb": f"/file/{uid}_enh_thumb.jpg",
                "full":  f"/file/{uid}_enh.jpg",
            })
        except Exception as e:
            out.append({"name": f.filename, "error": str(e)})
    return jsonify({"items": out})


# ---------- image ops ----------
def _lighten(img, amount=30):
    return cv2.convertScaleAbs(img, alpha=1.0, beta=amount)

def _darken(img, amount=25):
    return cv2.convertScaleAbs(img, alpha=1.0, beta=-amount)

def _clahe_whiten(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    cl = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    out = cv2.merge((cl, a, b))
    out = cv2.cvtColor(out, cv2.COLOR_LAB2BGR)
    # gentle white pull
    return cv2.convertScaleAbs(out, alpha=1.05, beta=8)

def _dark_fix(img):
    """For pictures shot in the dark: gamma boost shadows then gentle CLAHE."""
    inv_g = 1.0 / 0.55
    table = np.array([((i / 255.0) ** inv_g) * 255 for i in range(256)]).astype("uint8")
    boosted = cv2.LUT(img, table)
    return _clahe_whiten(boosted)

def _hue(img, deg):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.int16)
    hsv[..., 0] = (hsv[..., 0] + int(deg / 2)) % 180
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

def _sat(img, mul):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * mul, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

def _gamma(img, g):
    inv = 1.0 / max(0.05, g)
    table = np.array([((i / 255.0) ** inv) * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(img, table)


@bp.route("/enhance/apply", methods=["POST"])
def apply():
    j = request.get_json(silent=True) or {}
    uids = j.get("uids") or []
    op = j.get("op")
    params = j.get("params") or {}
    if not uids:
        return jsonify({"error":"Select at least one image"})

    updated = []
    for uid in uids:
        path = _work(uid)
        if not os.path.exists(path):
            updated.append({"uid": uid, "error":"expired"}); continue
        img = cv2.imread(path)
        if img is None:
            updated.append({"uid": uid, "error":"unreadable"}); continue

        # save undo
        shutil.copy(path, _undo(uid))

        try:
            if   op == "lighten":  img = _lighten(img, int(params.get("amount", 30)))
            elif op == "darken":   img = _darken(img,  int(params.get("amount", 25)))
            elif op == "whiten":   img = _clahe_whiten(img)
            elif op == "dark_fix": img = _dark_fix(img)
            elif op == "hue":      img = _hue(img, float(params.get("deg", 0)))
            elif op == "sat":      img = _sat(img, float(params.get("mul", 1.0)))
            elif op == "gamma":    img = _gamma(img, float(params.get("g", 1.0)))
            else:
                updated.append({"uid": uid, "error":"unknown op"}); continue
        except Exception as e:
            updated.append({"uid": uid, "error": str(e)}); continue

        cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        # refresh thumb
        try:
            with Image.open(path) as pim:
                pim.thumbnail((220, 220))
                pim.save(_thumb(uid), "JPEG", quality=82)
        except Exception:
            pass
        updated.append({
            "uid": uid,
            "thumb": f"/file/{uid}_enh_thumb.jpg?t={int(time.time()*1000)}",
            "full":  f"/file/{uid}_enh.jpg?t={int(time.time()*1000)}",
        })
    return jsonify({"items": updated})


@bp.route("/enhance/undo", methods=["POST"])
def undo():
    j = request.get_json(silent=True) or {}
    uids = j.get("uids") or []
    out = []
    for uid in uids:
        u = _undo(uid); w = _work(uid)
        if os.path.exists(u):
            shutil.copy(u, w)
            try:
                with Image.open(w) as pim:
                    pim.thumbnail((220, 220))
                    pim.save(_thumb(uid), "JPEG", quality=82)
            except Exception:
                pass
            out.append({
                "uid": uid,
                "thumb": f"/file/{uid}_enh_thumb.jpg?t={int(time.time()*1000)}",
                "full":  f"/file/{uid}_enh.jpg?t={int(time.time()*1000)}",
            })
        else:
            out.append({"uid": uid, "error":"no undo"})
    return jsonify({"items": out})


@bp.route("/enhance/zip", methods=["POST"])
def make_zip():
    j = request.get_json(silent=True) or {}
    uids = j.get("uids") or []
    if not uids:
        return jsonify({"error":"none selected"})
    name = f"enhanced_{int(time.time())}.zip"
    full = os.path.join(WORK_DIR, name)
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED) as zf:
        for uid in uids:
            p = _work(uid)
            if os.path.exists(p):
                zf.write(p, f"{uid}.jpg")
    return jsonify({"out": f"/file/{name}"})


@bp.route("/enhance/pdf", methods=["POST"])
def make_pdf():
    """Render selected images as a single A4 PDF (one per page, contained, centered)."""
    j = request.get_json(silent=True) or {}
    uids = j.get("uids") or []
    if not uids:
        return jsonify({"error":"none selected"})

    # A4 @ 200 DPI = 1654 x 2339
    A4 = (1654, 2339)
    pages = []
    for uid in uids:
        p = _work(uid)
        if not os.path.exists(p): continue
        im = Image.open(p).convert("RGB")
        im.thumbnail((A4[0] - 40, A4[1] - 40))
        page = Image.new("RGB", A4, "white")
        page.paste(im, ((A4[0] - im.size[0]) // 2, (A4[1] - im.size[1]) // 2))
        pages.append(page)
    if not pages:
        return jsonify({"error":"no readable images"})

    name = f"enhanced_{int(time.time())}.pdf"
    full = os.path.join(WORK_DIR, name)
    pages[0].save(full, "PDF", resolution=200.0,
                  save_all=True, append_images=pages[1:])
    return jsonify({"out": f"/file/{name}"})
