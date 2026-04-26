"""Sirisha Studio — multi-tool card processor (Aadhar / PAN / Voter / RC / Senior).

This file just wires routes together. Each tool lives in its own module under tools/.
Edit POPPLER_PATH in config.py when switching between Windows and Linux.
"""

import os
from flask import Flask, render_template, send_file
from config import OUTPUT_DIR

from tools.aadhar_short import bp as aadhar_short_bp
from tools.aadhar_long  import bp as aadhar_long_bp
from tools.pan          import bp as pan_bp
from tools.voter        import bp as voter_bp
from tools.rc           import bp as rc_bp
from tools.senior       import bp as senior_bp


app = Flask(__name__)

app.register_blueprint(aadhar_short_bp)
app.register_blueprint(aadhar_long_bp)
app.register_blueprint(pan_bp)
app.register_blueprint(voter_bp)
app.register_blueprint(rc_bp)
app.register_blueprint(senior_bp)


@app.route("/")
def home():
    tools = [
        {"href": "/short-aadhar", "title": "Short Aadhar",  "desc": "PDF → cropped front + back"},
        {"href": "/long-aadhar",  "title": "Long Aadhar",   "desc": "Full page + signature check"},
        {"href": "/pan",          "title": "PAN",           "desc": "PDF → cropped front + back"},
        {"href": "/voter",        "title": "Voter ID",      "desc": "PDF / image → front + back"},
        {"href": "/rc",           "title": "RC",            "desc": "2-page PDF → front + back"},
        {"href": "/senior",       "title": "Senior Citizen","desc": "PDF → cropped front + back"},
    ]
    return render_template("index.html", tools=tools)


@app.route("/file/<name>")
def file(name):
    return send_file(os.path.join(OUTPUT_DIR, name))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
