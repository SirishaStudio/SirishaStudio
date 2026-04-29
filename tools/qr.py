"""QR — generate QR codes for text / URL / UPI payments. Saved as PNG so it
prints crisp."""

import os, time
import qrcode
from qrcode.constants import ERROR_CORRECT_M, ERROR_CORRECT_H

from flask import Blueprint, render_template, request, jsonify
from . import utils
from config import OUTPUT_DIR

bp = Blueprint("qr", __name__)


@bp.route("/qr")
def page():
    return render_template("tool_qr.html")


@bp.route("/qr/process", methods=["POST"])
def process():
    j = request.get_json(silent=True) or {}
    mode = (j.get("mode") or "text").lower()
    box = max(4, min(int(j.get("box_size") or 10), 30))
    border = max(1, min(int(j.get("border") or 2), 10))
    high_ec = bool(j.get("high_ec"))

    if mode == "upi":
        pa = (j.get("pa") or "").strip()
        pn = (j.get("pn") or "").strip()
        am = (j.get("am") or "").strip()
        cu = (j.get("cu") or "INR").strip()
        tn = (j.get("tn") or "").strip()
        if not pa:
            return jsonify({"error": "UPI ID (pa) is required"})
        parts = [f"pa={pa}"]
        if pn: parts.append("pn=" + pn.replace(" ", "%20"))
        if am: parts.append("am=" + am)
        if cu: parts.append("cu=" + cu)
        if tn: parts.append("tn=" + tn.replace(" ", "%20"))
        data = "upi://pay?" + "&".join(parts)
    elif mode == "url":
        data = (j.get("data") or "").strip()
        if not data:
            return jsonify({"error": "URL is required"})
        if not (data.startswith("http://") or data.startswith("https://")):
            data = "https://" + data
    elif mode == "wifi":
        ssid = (j.get("ssid") or "").strip()
        pwd  = (j.get("pwd") or "").strip()
        enc  = (j.get("enc") or "WPA").upper()
        if not ssid:
            return jsonify({"error": "Wi-Fi SSID is required"})
        data = f"WIFI:T:{enc};S:{ssid};P:{pwd};;"
    else:  # text
        data = (j.get("data") or "").strip()
        if not data:
            return jsonify({"error": "Text content is required"})

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H if high_ec else ERROR_CORRECT_M,
        box_size=box, border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    uid = str(int(time.time())) + "_" + str(os.getpid())[:4]
    out_name = f"qr_{uid}.png"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    img.save(out_path, "PNG")
    return jsonify({"image": f"/file/{out_name}", "data": data})
