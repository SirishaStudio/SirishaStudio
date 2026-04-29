"""CUSTOM CARD — define crops + photo region + levels visually in the browser
and save as a named preset. Useful when a customer brings a card type you've
never seen before. Presets are persisted to overrides.json under TOOL_KEY.
"""

from flask import Blueprint, render_template, request, jsonify, send_file
import os, base64, time
import cv2

from . import utils
from config import OUTPUT_DIR

bp = Blueprint("custom", __name__)

TOOL_KEY = "custom"
DPI = 300                                  # lighter than card tools — for speed
LEVELS = {"g_black": 0, "g_gamma": 1.0, "p_white": 255, "p_gamma": 1.0}
PRINT_SCALE = 1.00

# Built-in presets that ship with the app — user-created presets are added on
# top via overrides.json.
DEFAULT_PRESETS = [
    {
        "name": "cisf",
        "dpi": 300,
        "front": {"x": 15, "y": 23, "w": 979, "h": 598},
        "back":  None,
        "levels": {"g_black": 0, "g_gamma": 1.0},
        "saved_at": 1777380357,
        "builtin": True,
    },
]


def _cfg():
    cfg = utils.merged(TOOL_KEY, {
        "levels": LEVELS, "print_scale": PRINT_SCALE, "dpi": DPI,
        "presets": [],
    })
    # Merge built-in presets in front, but never duplicate names from overrides
    user_presets = list(cfg.get("presets") or [])
    user_names = {p.get("name") for p in user_presets}
    merged_presets = [p for p in DEFAULT_PRESETS if p.get("name") not in user_names] + user_presets
    cfg["presets"] = merged_presets
    return cfg


@bp.route("/custom")
def page():
    c = _cfg()
    return render_template("tool_custom.html",
        title="Custom Card", tool_key=TOOL_KEY,
        defaults=c["levels"], dpi=c["dpi"],
        print_scale=c["print_scale"],
        presets=c.get("presets", []) or [],
    )


@bp.route("/custom/load", methods=["POST"])
def load():
    """Render an uploaded file at the given DPI; return the source-image URL +
    its width/height so the browser can draw rectangle pickers in image space."""
    file = request.files.get("file")
    password = request.form.get("password", "")
    dpi = int(request.form.get("dpi") or DPI)
    if not file:
        return jsonify({"error": "No file uploaded"})

    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)

    try:
        if ext == "pdf":
            password = utils.auto_password_from_name(file.filename, password)
            try:
                img = utils.pdf_to_image(path, password=password, dpi=dpi)
            except Exception:
                return jsonify({"ask_password": True})
        else:
            img = cv2.imread(path)
            if img is None:
                return jsonify({"error": "Could not read image"})
    except Exception as e:
        return jsonify({"error": str(e)})

    src_path = utils.out_path(uid, "src")
    utils.write_jpg(src_path, img, quality=92)
    h, w = img.shape[:2]
    return jsonify({
        "uid": uid,
        "image": utils.public_url(uid, "src"),
        "w": w, "h": h,
    })


@bp.route("/custom/process", methods=["POST"])
def process():
    """Crop the source image with the user-drawn rectangles."""
    j = request.get_json(silent=True) or {}
    uid = j.get("uid")
    src = os.path.join(OUTPUT_DIR, f"{uid}_src.jpg")
    if not uid or not os.path.exists(src):
        return jsonify({"error": "Source image expired — re-upload"})

    img = cv2.imread(src)
    if img is None:
        return jsonify({"error": "Could not read source"})

    out = {}
    for side in ("front", "back"):
        rect = j.get(side)
        if not rect:
            continue
        x = int(rect["x"]); y = int(rect["y"])
        w = int(rect["w"]); h = int(rect["h"])
        crop = utils.safe_crop(img, y, y + h, x, x + w)
        if crop is None:
            return jsonify({"error": f"{side} crop is outside image"})
        path = utils.out_path(uid, side[0])
        utils.write_jpg(path, crop)
        out[side] = utils.public_url(uid, side[0])

    if not out:
        return jsonify({"error": "Draw at least a FRONT crop on the source image"})
    return jsonify(out)


@bp.route("/custom/preset", methods=["POST", "DELETE"])
def preset():
    data = utils.load_overrides()
    cur = data.get(TOOL_KEY, {})
    presets = list(cur.get("presets", []) or [])

    if request.method == "DELETE":
        name = request.args.get("name", "")
        # Don't allow deleting built-ins (they re-merge from defaults anyway)
        presets = [p for p in presets if p.get("name") != name]
    else:
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Preset needs a name"})
        new = {
            "name": name,
            "dpi":  body.get("dpi", DPI),
            "front": body.get("front"),
            "back":  body.get("back"),
            "levels": body.get("levels") or LEVELS,
            "saved_at": int(time.time()),
        }
        presets = [p for p in presets if p.get("name") != name] + [new]

    cur["presets"] = presets
    data[TOOL_KEY] = cur
    utils.save_overrides(data)
    # Return merged list (built-ins + user) so the UI shows everything
    user_names = {p.get("name") for p in presets}
    merged_presets = [p for p in DEFAULT_PRESETS if p.get("name") not in user_names] + presets
    return jsonify({"ok": True, "presets": merged_presets})
