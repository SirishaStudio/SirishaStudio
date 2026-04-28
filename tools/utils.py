"""Shared helpers: PDF -> image, password handling, file IO, runtime overrides."""

import os
import json
import copy
import uuid
import cv2
import numpy as np
from pdf2image import convert_from_path

from config import POPPLER_PATH, UPLOAD_DIR, OUTPUT_DIR, OVERRIDES_PATH


def save_upload(file):
    """Save uploaded file to UPLOAD_DIR and return (uid, path)."""
    uid = str(uuid.uuid4())[:8]
    path = os.path.join(UPLOAD_DIR, uid + "_" + file.filename)
    file.save(path)
    return uid, path


def file_ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def pdf_to_image(path, password=None, dpi=700, page=1, last_page=None):
    """Convert a (possibly password-protected) PDF page to an OpenCV BGR image.
    Raises if the password is wrong / pdf can't be opened.
    """
    pages = convert_from_path(
        path,
        dpi=dpi,
        poppler_path=POPPLER_PATH,
        userpw=password if password else None,
        first_page=page,
        last_page=last_page if last_page else page,
    )
    if not pages:
        raise RuntimeError("Empty PDF")
    arr = np.array(pages[0])
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def pdf_to_images_all(path, password=None, dpi=700):
    """Return list of OpenCV BGR images for every page."""
    pages = convert_from_path(
        path,
        dpi=dpi,
        poppler_path=POPPLER_PATH,
        userpw=password if password else None,
    )
    return [cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR) for p in pages]


def auto_password_from_name(filename, password):
    """If user gave no password but the filename stem looks like a password
    (Aadhar uses 8-char names, PAN/Senior use numeric stems), use that.
    """
    if password:
        return password
    stem = filename.rsplit(".", 1)[0]
    if len(stem) == 8 or stem.isdigit():
        return stem
    return ""


def write_jpg(path, img, quality=95):
    cv2.imwrite(path, img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])


def safe_crop(img, y1, y2, x1, x2):
    """Clamp crop bounds to the image and return None if the result is empty."""
    h, w = img.shape[:2]
    y1 = max(0, min(int(y1), h)); y2 = max(0, min(int(y2), h))
    x1 = max(0, min(int(x1), w)); x2 = max(0, min(int(x2), w))
    if y2 <= y1 or x2 <= x1:
        return None
    return img[y1:y2, x1:x2].copy()


def out_path(uid, suffix):
    """e.g. out_path('abc12345', 'f') -> /<OUTPUT_DIR>/abc12345_f.jpg"""
    return os.path.join(OUTPUT_DIR, f"{uid}_{suffix}.jpg")


def public_url(uid, suffix):
    return f"/file/{uid}_{suffix}.jpg"


def apply_levels(img, alpha=1.0, beta=0):
    """Linear contrast/brightness."""
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


# ---------------------- Runtime overrides (Dev Mode) ----------------------
#
# Each tool's blueprint declares its EDITABLE constants at the TOP of its file.
# Dev Mode in the browser writes JSON patches into overrides.json; this helper
# deep-merges them on top of the in-code defaults whenever the tool runs.

def _deep_merge(base, over):
    out = copy.deepcopy(base)
    if not isinstance(over, dict):
        return out
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_overrides():
    if not os.path.exists(OVERRIDES_PATH):
        return {}
    try:
        with open(OVERRIDES_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_overrides(data):
    with open(OVERRIDES_PATH, "w") as f:
        json.dump(data, f, indent=2)


def merged(tool_key, defaults):
    """Return defaults merged with the user's saved overrides for this tool."""
    return _deep_merge(defaults, load_overrides().get(tool_key, {}))


def patch_overrides(tool_key, patch):
    """Deep-merge `patch` into overrides.json[tool_key] and persist."""
    data = load_overrides()
    data[tool_key] = _deep_merge(data.get(tool_key, {}), patch or {})
    save_overrides(data)
    return data[tool_key]
