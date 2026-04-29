"""Sirisha Studio — multi-tool card processor.

This file just wires routes together. Each tool lives in its own module under
tools/; per-tool defaults are at the TOP of each tool file. Edit POPPLER_PATH
in config.py when switching between Windows and Linux.
"""

import os
from flask import Flask, render_template, send_file, request, jsonify
from config import OUTPUT_DIR, GLOBAL_PRINT_DESCALE

from tools           import utils
from tools.aadhar_short import bp as aadhar_short_bp
from tools.aadhar_long  import bp as aadhar_long_bp
from tools.pan          import bp as pan_bp
from tools.voter        import bp as voter_bp
from tools.rc           import bp as rc_bp
from tools.dl           import bp as dl_bp
from tools.senior       import bp as senior_bp
from tools.custom       import bp as custom_bp
from tools.convert      import bp as convert_bp
from tools.enhance      import bp as enhance_bp
from tools.resume       import bp as resume_bp
from tools.id_photo     import bp as id_photo_bp
from tools.compress     import bp as compress_bp
from tools.qr           import bp as qr_bp


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024  # 256 MB uploads (Enhance batches)

app.register_blueprint(aadhar_short_bp)
app.register_blueprint(aadhar_long_bp)
app.register_blueprint(pan_bp)
app.register_blueprint(voter_bp)
app.register_blueprint(rc_bp)
app.register_blueprint(dl_bp)
app.register_blueprint(senior_bp)
app.register_blueprint(custom_bp)
app.register_blueprint(convert_bp)
app.register_blueprint(enhance_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(id_photo_bp)
app.register_blueprint(compress_bp)
app.register_blueprint(qr_bp)


# Tools grouped into sections for the home page (in display order).
TOOL_SECTIONS = [
    {
        "title": "Cards",
        "blurb": "Crop / level / print front + back of identity cards.",
        "tools": [
            {"href": "/short-aadhar", "title": "Short Aadhar",   "desc": "PDF → cropped front + back"},
            {"href": "/long-aadhar",  "title": "Long Aadhar",    "desc": "Full page + paste signature tick"},
            {"href": "/pan",          "title": "PAN",            "desc": "Old / New PAN modes, separate photo zones"},
            {"href": "/voter",        "title": "Voter ID",       "desc": "PDF / image → front + back"},
            {"href": "/rc",           "title": "RC",             "desc": "2-page PDF → front + back"},
            {"href": "/dl",           "title": "Driving Licence","desc": "2-page PDF, auto-trim borders"},
            {"href": "/senior",       "title": "Senior Citizen", "desc": "PDF → cropped front + back"},
        ],
    },
    {
        "title": "Conversions, Enhance, Resume",
        "blurb": "File conversions, batch image enhancement, and resume DOCX builder.",
        "tools": [
            {"href": "/convert", "title": "Convert",      "desc": "PDF / image / DOCX any-to-any"},
            {"href": "/enhance", "title": "Enhance",      "desc": "Batch lighten / darken / fix dark / PDF"},
            {"href": "/resume",  "title": "Resume Maker", "desc": "Fresher / Ordinary / Detailed → DOCX"},
        ],
    },
    {
        "title": "Studio Utilities",
        "blurb": "Daily helpers — passport photos, file-size compression, QR codes.",
        "tools": [
            {"href": "/id-photo", "title": "ID Photo",  "desc": "Passport / Visa / Stamp size + A4 sheet"},
            {"href": "/compress", "title": "Compress",  "desc": "Bring an image under a target KB"},
            {"href": "/qr",       "title": "QR Code",   "desc": "Text / URL / UPI / Wi-Fi → PNG"},
        ],
    },
    {
        "title": "Custom",
        "blurb": "When the card type isn't above — draw your own crops, save as preset.",
        "tools": [
            {"href": "/custom", "title": "Custom Card",
             "desc": "Draw FRONT/BACK boxes, save preset"},
        ],
    },
]


@app.route("/")
def home():
    return render_template("index.html",
                           sections=TOOL_SECTIONS,
                           descale=GLOBAL_PRINT_DESCALE)


@app.route("/tray")
def tray():
    return render_template("tray.html")


@app.route("/file/<name>")
def file(name):
    return send_file(os.path.join(OUTPUT_DIR, name))


# ---------------------- Dev Mode endpoints ----------------------

@app.route("/dev/overrides")
def dev_overrides_all():
    return jsonify(utils.load_overrides())


@app.route("/dev/overrides/<tool_key>", methods=["GET", "POST", "DELETE"])
def dev_overrides_tool(tool_key):
    if request.method == "GET":
        return jsonify(utils.load_overrides().get(tool_key, {}))

    if request.method == "DELETE":
        data = utils.load_overrides()
        data.pop(tool_key, None)
        utils.save_overrides(data)
        return jsonify({"ok": True})

    patch = request.get_json(silent=True) or {}
    merged = utils.patch_overrides(tool_key, patch)
    return jsonify({"ok": True, "current": merged})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
