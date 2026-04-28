"""RESUME MAKER — fills the example resume DOCX templates with the user's
data using string replacement at the run level so paragraph formatting stays
intact.

The example data inside each template (real names, addresses, etc) acts as
the "placeholder" — we map known phrases → user-supplied values.
"""

import os, time, copy
from flask import Blueprint, render_template, request, jsonify, send_file
from docx import Document

from config import OUTPUT_DIR

bp = Blueprint("resume", __name__)
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "resume_templates")


# ---------- replacement maps ----------
# (search_text, form_field, default_if_blank)
# Order matters: longer/most-specific first.
TEMPLATES = {
    "fresher": {
        "label": "Fresher",
        "blurb": "Single page, simple. Use when there's no work experience.",
        "file":  "fresher.docx",
        # Pre-replace the embedded example values:
        "subs": [
            ("Boori Eswara Rao", "father", ""),
            ("Boori Jyothi",     "name",   ""),
            ("D.No: 37-92-217/3 ,Asrr Nagar,",       "addr1",  ""),
            ("Srinivasa  Nagar, Burma Camp,",        "addr2",  ""),
            ("Visakhapatnam- 530008",                "city",   ""),
            ("xxxxx",                                "mobile", ""),
            ("bxxxxhi72@gmail.com",                  "email",  ""),
            ("Dr.V.S. Krishna Degree College ,Maddilapalam", "degree", ""),
            ("Krishna Vocational College,Maddilapalam",      "inter",  ""),
            ("G.V.M.C High School , Madhavadhara",           "ssc",    ""),
            ("21 -05 -xxxx",   "dob",       ""),
            ("Female",         "gender",    "Male"),
            ("Indian",         "nationality","Indian"),
            ("Unmarried",      "marital",   "Unmarried"),
            ("Telugu, English","languages", "Telugu, English"),
        ],
    },
    "ordinary": {
        "label": "Ordinary",
        "blurb": "Has a profile table, education table and short experience.",
        "file":  "ordinary.docx",
        "subs": [
            ("AATLA TEJASWARI", "name", ""),    # personal-profile name
            ("AATLA xxxx",      "name", ""),    # header name
            ("23-11/1,JAIBHARAT NAGAR,", "addr1", ""),
            ("BHARMA CAMP,",             "addr2", ""),
            ("VISAKHAPATNAM-[PIN]",      "city",  ""),
            ("9550xxxx74",               "mobile",""),
            ("xxxxxxxxx@gmail.com",      "email", ""),
            ("RAO",                      "father",""),
            ("13-08-2007",               "dob",   ""),
            ("Female",                   "gender","Male"),
            ("Indian",                   "nationality","Indian"),
            ("Unmarried",                "marital","Unmarried"),
            ("Telugu, English, & Hindi.","languages","Telugu, English"),
            ("(NAme of the person)",     "name",  ""),
        ],
    },
    "detailed": {
        "label": "Detailed",
        "blurb": "Larger layout with strengths, hobbies, and education table.",
        "file":  "detailed.docx",
        "subs": [
            ("VILLURI DINESH", "name", ""),
            ("D.No:  36-92-229/9,  ASSR NAGAR,", "addr1", ""),
            ("BURMA CAMP,",                      "addr2", ""),
            ("Visakhapatnam-530008",             "city",  ""),
            ("79950xxxxx",                       "mobile",""),
            ("vxxxxxxxxh25@gmail.com",           "email", ""),
            ("xxxxU",                            "name",  ""),  # personal profile
            ("(xxxxx )",                         "name",  ""),  # signature line
            ("27-06-2005",                       "dob",   ""),
            ("Male",                             "gender","Male"),
            ("Hindu",                            "religion","Hindu"),
            ("Unmarried",                        "marital","Unmarried"),
            ("Indian",                           "nationality","Indian"),
            (" English ,Telugu , Hindi",         "languages"," English, Telugu, Hindi"),
        ],
    },
}


def _do_replace(doc, mapping):
    """Walk every paragraph (incl. those inside tables) and replace text.
    Combines runs so search terms split across runs are still matched, then
    writes the result back into the first run keeping its formatting."""
    def replace_in_paragraph(p):
        full = "".join(r.text for r in p.runs)
        if not full:
            return
        new = full
        for src, dst in mapping:
            if src and src in new:
                new = new.replace(src, dst)
        if new != full:
            if not p.runs:
                p.add_run(new); return
            p.runs[0].text = new
            for r in p.runs[1:]:
                r.text = ""

    for p in doc.paragraphs:
        replace_in_paragraph(p)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_in_paragraph(p)


@bp.route("/resume")
def page():
    return render_template("tool_resume.html", templates=TEMPLATES)


@bp.route("/resume/build", methods=["POST"])
def build():
    j = request.get_json(silent=True) or {}
    tpl_key = j.get("template")
    if tpl_key not in TEMPLATES:
        return jsonify({"error": "Unknown template"})

    tpl = TEMPLATES[tpl_key]
    src = os.path.normpath(os.path.join(TEMPLATE_DIR, tpl["file"]))
    if not os.path.exists(src):
        return jsonify({"error": f"Template file missing: {tpl['file']}"})

    fields = j.get("fields") or {}

    # build a [(search_text, replacement)] list, longest first
    pairs = []
    for src_text, field_key, default in tpl["subs"]:
        v = (fields.get(field_key) or "").strip()
        if not v:
            v = default
        pairs.append((src_text, v))
    pairs.sort(key=lambda x: -len(x[0]))

    doc = Document(src)
    _do_replace(doc, pairs)

    # tables: optionally let the user replace the academic-qualifications row
    # contents for ordinary/detailed (simple mapping by row index keys edu_r1..)
    edu = j.get("education") or []   # list of dicts with c1..cN
    if edu and doc.tables:
        t = doc.tables[0]
        for i, row_data in enumerate(edu):
            ri = i + 1   # row 0 is header
            if ri >= len(t.rows): break
            cells = t.rows[ri].cells
            for k, val in row_data.items():
                try:
                    ci = int(str(k).lstrip("c")) - 1
                except Exception:
                    continue
                if 0 <= ci < len(cells) and val:
                    # replace cell text while preserving formatting of the first run
                    for p in cells[ci].paragraphs:
                        for r in p.runs:
                            r.text = ""
                    p = cells[ci].paragraphs[0]
                    if p.runs:
                        p.runs[0].text = val
                    else:
                        p.add_run(val)

    safe_name = (fields.get("name") or "resume").strip().replace(" ", "_")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "-_") or "resume"
    out_name = f"{safe_name}_{tpl_key}_{int(time.time())}.docx"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    doc.save(out_path)
    return jsonify({"out": f"/file/{out_name}", "name": out_name})
