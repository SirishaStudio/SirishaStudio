"""Shared helpers: PDF -> image, password handling, signature check, file IO."""

import os
import uuid
import cv2
import numpy as np
from pdf2image import convert_from_path

from config import POPPLER_PATH, UPLOAD_DIR, OUTPUT_DIR


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
    y1 = max(0, min(y1, h)); y2 = max(0, min(y2, h))
    x1 = max(0, min(x1, w)); x2 = max(0, min(x2, w))
    if y2 <= y1 or x2 <= x1:
        return None
    return img[y1:y2, x1:x2].copy()


def out_path(uid, suffix):
    """e.g. out_path('abc12345', 'f') -> /<OUTPUT_DIR>/abc12345_f.jpg"""
    return os.path.join(OUTPUT_DIR, f"{uid}_{suffix}.jpg")


def public_url(uid, suffix):
    return f"/file/{uid}_{suffix}.jpg"


def apply_levels(img, alpha=1.0, beta=0):
    """Linear contrast/brightness (used by RC tool, matches alpha=1.2/beta=-40)."""
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


# ---------------------- Aadhar digital signature check ----------------------

def check_pdf_signature(path, password=None):
    """Returns dict: {signed: bool, signer: str|None, intact: bool|None, error: str|None}.
    Best-effort: works on most UIDAI Aadhar PDFs.
    """
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.pdf_utils.crypt import StandardSecurityHandler

        with open(path, "rb") as f:
            reader = PdfFileReader(f, strict=False)
            if reader.encrypted and password:
                try:
                    reader.decrypt(password)
                except Exception:
                    pass

            sigs = list(reader.embedded_signatures)
            if not sigs:
                return {"signed": False, "signer": None, "intact": None, "error": None}

            sig = sigs[0]
            signer = None
            try:
                cert = sig.signer_cert
                if cert is not None:
                    signer = cert.subject.human_friendly
            except Exception:
                signer = None

            intact = None
            try:
                intact = bool(sig.compute_integrity_info().intact)
            except Exception:
                try:
                    intact = bool(sig.summarise_integrity_info().intact)
                except Exception:
                    intact = None

            return {"signed": True, "signer": signer, "intact": intact, "error": None}
    except Exception as e:
        return {"signed": False, "signer": None, "intact": None, "error": str(e)}
