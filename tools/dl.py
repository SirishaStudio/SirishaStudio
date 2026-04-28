"""DL — Driving Licence: TWO-PAGE PDF (page 1 = front, page 2 = back).

Like RC, but DL has a portrait photo on the FRONT, so it gets the same dual
PHOTO + GLOBAL levels treatment as PAN.
"""

from flask import Blueprint, render_template, request, jsonify
from . import utils

bp = Blueprint("dl", __name__)

# ============================================================
#  EDITABLE DEFAULTS — change values here for new built-ins.
# ============================================================
TOOL_KEY     = "dl"
DPI          = 700

# Each page is cropped to this rectangle (y1, y2, x1, x2). Update to fit your DLs.
FRONT_CROP   = [0, 1488, 0, 2344]
BACK_CROP    = [0, 1488, 0, 2344]

# Photo on the FRONT (your spec, given at canvas 2344x1488 = front_crop dims).
PHOTO_REGION_72DPI = {"x": 1791, "y": 314, "w": 401, "h": 401}
FRONT_CANVAS_72DPI = {"w": 2344, "h": 1488}

LEVELS       = {"g_black": 0, "g_gamma": 1.0, "p_white": 255, "p_gamma": 1.0}
PRINT_SCALE  = 1.00
# ============================================================


def _cfg():
    return utils.merged(TOOL_KEY, {
        "front_crop": FRONT_CROP, "back_crop": BACK_CROP,
        "photo_region_72dpi": PHOTO_REGION_72DPI,
        "front_canvas_72dpi": FRONT_CANVAS_72DPI,
        "levels": LEVELS, "print_scale": PRINT_SCALE, "dpi": DPI,
    })


@bp.route("/dl")
def page():
    c = _cfg()
    return render_template(
        "tool_dual.html",
        title="Driving Licence (DL)", tool_key=TOOL_KEY,
        process_url="/dl/process",
        accept=".pdf",
        needs_password=False,
        photo_region=None,
        photo_regions={
            "regions_72dpi": {"main": c["photo_region_72dpi"]},
            "front_canvas_72dpi": c["front_canvas_72dpi"],
        },
        erase_region=None,
        defaults=c["levels"],
        print_scale=c["print_scale"],
        print_mode="dual",
        modes=None,
        cfg=c,
    )


@bp.route("/dl/process", methods=["POST"])
def process():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"})

    c = _cfg()
    uid, path = utils.save_upload(file)
    ext = utils.file_ext(file.filename)
    if ext != "pdf":
        return jsonify({"error": "DL requires a 2-page PDF"})

    try:
        pages = utils.pdf_to_images_all(path, dpi=c["dpi"])
    except Exception as e:
        return jsonify({"error": f"PDF read failed: {e}"})
    if not pages:
        return jsonify({"error": "Empty PDF"})

    fy1, fy2, fx1, fx2 = c["front_crop"]
    front = utils.safe_crop(pages[0], fy1, fy2, fx1, fx2)
    if front is None:
        return jsonify({"error": "Front page too small for DL crop."})
    utils.write_jpg(utils.out_path(uid, "f"), front)

    out = {"front": utils.public_url(uid, "f"), "back": None}

    if len(pages) >= 2:
        by1, by2, bx1, bx2 = c["back_crop"]
        back = utils.safe_crop(pages[1], by1, by2, bx1, bx2)
        if back is not None:
            utils.write_jpg(utils.out_path(uid, "b"), back)
            out["back"] = utils.public_url(uid, "b")

    return jsonify(out)
