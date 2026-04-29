"""RESUME MAKER — builds DOCX resumes from scratch (not template substitution).

Three layouts mirror the user's reference PDFs:

  - fresher  : ONE page, slim, no defaults assumed. Education list is dynamic
               (any number of rows). Header has D/O father, simple lines.
  - ordinary : Has a profile table, a 5-col education table, dynamic strengths
               and a dynamic experience list (NEVER pre-filled with defaults).
  - detailed : Mirrors the supplied PDF — large name header on left + email/cell
               on right, OBJECTIVE, 5-col EDUCATIONAL QUALIFICATION table
               (Qualification | University/College | Specialization | %/Marks
                | Year of Passing), WORK EXPERIENCE, TECHNICAL SKILLS, STRENGTHS,
               PERSONAL DETAILS, DECLARATION + signature.

Front-end sends a JSON payload describing fields + dynamic lists; we render a
fresh document so alignment is deterministic.
"""

import os
import time
from io import BytesIO

from flask import Blueprint, render_template, request, jsonify, send_file
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from config import OUTPUT_DIR

bp = Blueprint("resume", __name__)


# ============================================================
#  Templates metadata (used by the front-end picker)
# ============================================================
TEMPLATES = {
    "fresher": {
        "label": "Fresher",
        "blurb": "ONE page. Add any qualifications you have (SSC / Diploma / B.Tech / Degree …).",
    },
    "ordinary": {
        "label": "Ordinary",
        "blurb": "Education table + Strengths + your own Experience entries. No defaults.",
    },
    "detailed": {
        "label": "Detailed",
        "blurb": "Full layout: 5-column education table, work experience, skills, personal details.",
    },
}


# ============================================================
#  Small docx helpers
# ============================================================
def _set_cell_border(cell, **kwargs):
    """Set per-side cell borders. kwargs: top/bottom/left/right = sz_in_eighths."""
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for side in ("top", "left", "bottom", "right"):
        sz = kwargs.get(side, 4)
        el = borders.find(qn(f"w:{side}"))
        if el is None:
            el = OxmlElement(f"w:{side}")
            borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), "000000")


def _shade_cell(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _set_margins(doc, top=0.7, bottom=0.7, left=0.7, right=0.7):
    for section in doc.sections:
        section.top_margin = Inches(top)
        section.bottom_margin = Inches(bottom)
        section.left_margin = Inches(left)
        section.right_margin = Inches(right)


def _para(doc_or_cell, text="", *, bold=False, size=11, align=None, italic=False,
          color=None, space_after=0):
    p = doc_or_cell.add_paragraph()
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor(*color)
    return p


def _section_heading(doc, text, *, size=12, underline=True):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    r.underline = underline
    return p


def _bullets(doc, items, size=11):
    for it in items:
        if not it:
            continue
        p = doc.add_paragraph(style=None)
        p.paragraph_format.left_indent = Inches(0.35)
        p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run("•  ")
        r1.font.size = Pt(size)
        r2 = p.add_run(str(it))
        r2.font.size = Pt(size)


def _kv_dotted(doc, label, value, *, size=11, label_w=2.0, total_w=6.4):
    """Render 'Label .........: Value' lines used in personal-details blocks."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(label_w), WD_TAB_ALIGNMENT.LEFT)
    r1 = p.add_run(label)
    r1.bold = True
    r1.font.size = Pt(size)
    r2 = p.add_run("\t: " + (value or ""))
    r2.font.size = Pt(size)
    return p


# ============================================================
#  Builders
# ============================================================
def _hdr_contact_table(doc, name, lines_left, lines_right, name_size=18):
    """Left = name + address; Right = mobile/email — used by ordinary/detailed."""
    t = doc.add_table(rows=1, cols=2)
    t.autofit = True
    t.columns[0].width = Inches(4.0)
    t.columns[1].width = Inches(3.0)
    left, right = t.rows[0].cells
    # NAME (large, bold)
    pn = left.paragraphs[0]
    pn.paragraph_format.space_after = Pt(2)
    r = pn.add_run(name or "")
    r.bold = True
    r.font.size = Pt(name_size)
    for line in lines_left:
        if line:
            _para(left, line, size=10, space_after=0)
    for line in lines_right:
        if line:
            _para(right, line, size=10, align="right", space_after=0)
    # No borders on this header table
    for cell in (left, right):
        _set_cell_border(cell, top=0, left=0, right=0, bottom=0)
    return t


def _hr(doc):
    """Horizontal rule paragraph."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "8")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


def build_fresher(d):
    """Single-page fresher resume with dynamic education list."""
    doc = Document()
    _set_margins(doc, top=0.5, bottom=0.5, left=0.6, right=0.6)

    # Tighten default paragraph spacing for one page
    style = doc.styles["Normal"]
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(2)

    # RESUME header
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("RESUME")
    r.bold = True
    r.underline = True
    r.font.size = Pt(14)
    p.paragraph_format.space_after = Pt(4)

    # Name + D/O father
    name = (d.get("name") or "").strip()
    father = (d.get("father") or "").strip()
    _para(doc, name, bold=True, size=13)
    if father:
        _para(doc, f"D/O  {father}", size=11)

    # Address + contact
    for line in [d.get("addr1"), d.get("addr2"), d.get("city")]:
        line = (line or "").strip()
        if line:
            _para(doc, line, size=10, space_after=0)

    mobile = (d.get("mobile") or "").strip()
    email = (d.get("email") or "").strip()
    if mobile:
        _para(doc, f"Mobile No : {mobile}", size=10, space_after=0)
    if email:
        _para(doc, f"Email Id  : {email}", size=10)

    _hr(doc)

    # CAREER OBJECTIVE
    _section_heading(doc, "CAREER OBJECTIVE:")
    objective = (d.get("objective") or "").strip()
    if not objective:
        objective = ("To obtain a challenging and responsible position in an "
                     "organization that contributes towards its growth using my "
                     "abilities and knowledge.")
    _para(doc, objective, size=11, align="justify")

    # ACADEMIC QUALIFICATIONS — DYNAMIC list
    _section_heading(doc, "ACADEMIC QUALIFICATIONS:")
    quals = d.get("qualifications") or []
    valid = [q for q in quals if (q.get("course") or "").strip()
             or (q.get("institute") or "").strip()]
    if not valid:
        _para(doc, "(No qualifications added.)", size=11, italic=True,
              color=(120, 120, 120))
    else:
        for q in valid:
            course = (q.get("course") or "").strip()
            inst = (q.get("institute") or "").strip()
            year = (q.get("year") or "").strip()
            line = course
            if inst:
                line += "   --   " + inst
            if year:
                line += f"   ({year})"
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(line)
            r.font.size = Pt(11)

    # EXPERIENCE
    _section_heading(doc, "EXPERIENCE:")
    _para(doc, "Fresher.", size=11)

    # PERSONAL PROFILE
    _section_heading(doc, "PERSONAL PROFILE:")
    for label, key in [
        ("Date of Birth", "dob"),
        ("Gender", "gender"),
        ("Nationality", "nationality"),
        ("Marital Status", "marital"),
        ("Languages Known", "languages"),
        ("Hobbies", "hobbies"),
    ]:
        v = (d.get(key) or "").strip()
        if v:
            _kv_dotted(doc, label, v, size=11, label_w=1.7)

    # DECLARATION
    _section_heading(doc, "DECLARATION:")
    _para(doc,
          "I hereby declare that the information furnished above is true to the "
          "best of my knowledge.", size=11, align="justify")

    place = (d.get("place") or "").strip()
    date = (d.get("date") or "").strip()
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(0)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(5.5), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run(f"Place : {place}").font.size = Pt(11)
    p.add_run(f"\tSignature").font.size = Pt(11)
    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    p2.add_run(f"Date  : {date}").font.size = Pt(11)
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p3.paragraph_format.space_before = Pt(8)
    p3.add_run(f"({name})").font.size = Pt(11)

    return doc


def build_ordinary(d):
    """Ordinary resume with profile + 5-col edu table + DYNAMIC experience."""
    doc = Document()
    _set_margins(doc, top=0.6, bottom=0.6, left=0.7, right=0.7)
    style = doc.styles["Normal"]
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(2)

    # Top RESUME header centered
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("RESUME")
    r.bold = True
    r.underline = True
    r.font.size = Pt(15)

    # Header w/ name on left, contact on right
    name = (d.get("name") or "").strip()
    addr_lines = [d.get("addr1"), d.get("addr2"), d.get("city")]
    contact_lines = []
    if (d.get("mobile") or "").strip():
        contact_lines.append("Mobile : " + d.get("mobile").strip())
    if (d.get("email") or "").strip():
        contact_lines.append("Mail Id : " + d.get("email").strip())
    _hdr_contact_table(doc, name, addr_lines, contact_lines, name_size=15)
    _hr(doc)

    # CAREER OBJECTIVE
    _section_heading(doc, "CAREER OBJECTIVE")
    objective = (d.get("objective") or "").strip() or \
        ("Looking for growth-oriented organisation to contribute my services "
         "thereby developing as an effective professional.")
    _para(doc, objective, size=11, align="justify")

    # EDUCATION — 5-column dynamic table
    _section_heading(doc, "EDUCATIONAL QUALIFICATION")
    edu = d.get("education") or []
    edu = [e for e in edu if any((e.get(k) or "").strip()
                                 for k in ("c1", "c2", "c3", "c4", "c5"))]
    headers = ["ACADEMIC\nQUALIFICATION", "NAME OF INSTITUTE",
               "BOARD / UNIVERSITY", "YEAR OF PASSING", "PERCENTAGE"]
    t = doc.add_table(rows=1 + len(edu), cols=5)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.autofit = True
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(10)
        _shade_cell(c, "DCE6F1")
        _set_cell_border(c, top=6, bottom=6, left=6, right=6)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for ri, row in enumerate(edu):
        cells = t.rows[ri + 1].cells
        for ci, key in enumerate(["c1", "c2", "c3", "c4", "c5"]):
            c = cells[ci]
            c.text = ""
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run((row.get(key) or "").strip())
            r.font.size = Pt(10)
            _set_cell_border(c, top=4, bottom=4, left=4, right=4)
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    # STRENGTHS
    strengths = [s for s in (d.get("strengths") or []) if s.strip()]
    if strengths:
        _section_heading(doc, "STRENGTHS")
        _bullets(doc, strengths)

    # EXPERIENCE — DYNAMIC, no defaults
    experiences = [x for x in (d.get("experience") or []) if x.strip()]
    _section_heading(doc, "EXPERIENCE")
    if experiences:
        _bullets(doc, experiences)
    else:
        _para(doc, "Fresher.", size=11)

    # PERSONAL PROFILE
    _section_heading(doc, "PERSONAL PROFILE")
    for label, key in [
        ("Name", "name"),
        ("Father's Name", "father"),
        ("Date of Birth", "dob"),
        ("Gender", "gender"),
        ("Nationality", "nationality"),
        ("Marital Status", "marital"),
        ("Languages Known", "languages"),
        ("Hobbies", "hobbies"),
    ]:
        v = (d.get(key) or "").strip()
        if v:
            _kv_dotted(doc, label, v, size=11, label_w=1.7)

    # DECLARATION
    _section_heading(doc, "DECLARATION")
    _para(doc,
          "I hereby declare that the above information is true to the best of "
          "my knowledge.", size=11, align="justify")
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(5.5), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run(f"Place : {(d.get('place') or '').strip()}").font.size = Pt(11)
    p.add_run("\tSignature").font.size = Pt(11)
    p2 = doc.add_paragraph()
    p2.add_run(f"Date  : {(d.get('date') or '').strip()}").font.size = Pt(11)
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p3.paragraph_format.space_before = Pt(8)
    p3.add_run(f"({name})").font.size = Pt(11)

    return doc


def build_detailed(d):
    """Detailed resume that mirrors the user's reference PDF layout."""
    doc = Document()
    _set_margins(doc, top=0.7, bottom=0.7, left=0.8, right=0.8)
    style = doc.styles["Normal"]
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(2)

    # Centered RESUME word
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("RESUME")
    r.bold = True
    r.underline = True
    r.font.size = Pt(15)
    p.paragraph_format.space_after = Pt(4)

    # Header: name on left, email/cell on right
    name = (d.get("name") or "").strip()
    contact = []
    if (d.get("email") or "").strip():
        contact.append("Email: " + d.get("email").strip())
    if (d.get("mobile") or "").strip():
        contact.append("Cell: " + d.get("mobile").strip())
    _hdr_contact_table(doc, name, [], contact, name_size=14)

    # Objective
    _section_heading(doc, "CAREER OBJECTIVE:")
    objective = (d.get("objective") or "").strip() or \
        ("To Obtain Challenging And Responsible Position In an Organization, "
         "Contributing Towards Its Growth Using My Abilities And Knowledge.")
    _para(doc, objective, size=11, align="justify")

    # EDUCATIONAL QUALIFICATION — 5-col table from PDF
    _section_heading(doc, "EDUCATIONAL QUALIFICATION:")
    edu = d.get("education") or []
    edu = [e for e in edu if any((e.get(k) or "").strip()
                                 for k in ("c1", "c2", "c3", "c4", "c5"))]
    headers = ["Qualification", "University / College Name", "Specialization",
               "Percentage / Marks", "Year of Passing"]
    t = doc.add_table(rows=1 + len(edu), cols=5)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Set rough column widths summing to ~6.5"
    widths = [Inches(1.1), Inches(2.0), Inches(1.3), Inches(1.0), Inches(1.1)]
    for col, w in zip(t.columns, widths):
        col.width = w
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        c.width = widths[i]
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(10)
        _shade_cell(c, "DCE6F1")
        _set_cell_border(c, top=6, bottom=6, left=6, right=6)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for ri, row in enumerate(edu):
        cells = t.rows[ri + 1].cells
        for ci, key in enumerate(["c1", "c2", "c3", "c4", "c5"]):
            c = cells[ci]
            c.width = widths[ci]
            c.text = ""
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run((row.get(key) or "").strip())
            r.font.size = Pt(10)
            _set_cell_border(c, top=4, bottom=4, left=4, right=4)
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    # WORK EXPERIENCE — dynamic, never defaulted
    work = [x for x in (d.get("experience") or []) if x.strip()]
    _section_heading(doc, "WORK EXPERIENCE:")
    if work:
        _bullets(doc, work)
    else:
        _para(doc, "Fresher.", size=11)

    # TECHNICAL SKILLS — dynamic key:value list
    skills = [s for s in (d.get("skills") or [])
              if (s.get("label") or "").strip() or (s.get("value") or "").strip()]
    if skills:
        _section_heading(doc, "TECHNICAL SKILLS:")
        for s in skills:
            label = (s.get("label") or "").strip()
            value = (s.get("value") or "").strip()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.space_after = Pt(2)
            tabs = p.paragraph_format.tab_stops
            tabs.add_tab_stop(Inches(2.6), WD_TAB_ALIGNMENT.LEFT)
            p.add_run("•  ").font.size = Pt(11)
            r1 = p.add_run(label)
            r1.font.size = Pt(11)
            r2 = p.add_run(f"\t: {value}")
            r2.font.size = Pt(11)

    # STRENGTHS
    strengths = [s for s in (d.get("strengths") or []) if s.strip()]
    if strengths:
        _section_heading(doc, "STRENGTHS:")
        for s in strengths:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run("➢  " + s)
            r.font.size = Pt(11)

    # PERSONAL DETAILS
    _section_heading(doc, "PERSONAL DETAILS:")
    for label, key in [
        ("Name", "name"),
        ("Father's Name", "father"),
        ("Date of Birth", "dob"),
        ("Gender", "gender"),
        ("Religion", "religion"),
        ("Marital Status", "marital"),
        ("Nationality", "nationality"),
        ("Languages Known", "languages"),
        ("Hobbies", "hobbies"),
    ]:
        v = (d.get(key) or "").strip()
        if v:
            _kv_dotted(doc, label, v, size=11, label_w=1.9)

    # Communication Address (multi-line)
    addr = [(d.get(k) or "").strip() for k in ("addr1", "addr2", "city")]
    addr = [a for a in addr if a]
    if addr:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run("Communication Address")
        r1.bold = True
        r1.font.size = Pt(11)
        r2 = p.add_run("\t: " + addr[0])
        r2.font.size = Pt(11)
        tabs = p.paragraph_format.tab_stops
        tabs.add_tab_stop(Inches(1.9), WD_TAB_ALIGNMENT.LEFT)
        for line in addr[1:]:
            p2 = doc.add_paragraph()
            p2.paragraph_format.space_after = Pt(0)
            p2.paragraph_format.left_indent = Inches(2.05)
            p2.add_run(line).font.size = Pt(11)

    # DECLARATION
    _section_heading(doc, "DECLARATION:")
    _para(doc,
          "I hereby declare that the above information is true to the best of "
          "my knowledge.", size=11, align="justify")
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(5.5), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run(f"Place : {(d.get('place') or '').strip()}").font.size = Pt(11)
    p.add_run("\tSignature").font.size = Pt(11)
    p2 = doc.add_paragraph()
    p2.add_run(f"Date  : {(d.get('date') or '').strip()}").font.size = Pt(11)
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p3.paragraph_format.space_before = Pt(8)
    p3.add_run(f"({name})").font.size = Pt(11)

    return doc


BUILDERS = {
    "fresher":  build_fresher,
    "ordinary": build_ordinary,
    "detailed": build_detailed,
}


# ============================================================
#  Routes
# ============================================================
@bp.route("/resume")
def page():
    return render_template("tool_resume.html", templates=TEMPLATES)


@bp.route("/resume/build", methods=["POST"])
def build():
    j = request.get_json(silent=True) or {}
    tpl_key = j.get("template")
    if tpl_key not in BUILDERS:
        return jsonify({"error": "Unknown template"})

    fields = j.get("fields") or {}
    # Pass dynamic lists through too
    payload = dict(fields)
    payload["education"] = j.get("education") or []
    payload["experience"] = j.get("experience") or []
    payload["strengths"] = j.get("strengths") or []
    payload["skills"] = j.get("skills") or []
    payload["qualifications"] = j.get("qualifications") or []

    try:
        doc = BUILDERS[tpl_key](payload)
    except Exception as e:
        return jsonify({"error": f"Build failed: {e}"})

    safe_name = (fields.get("name") or "resume").strip().replace(" ", "_")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "-_") or "resume"
    out_name = f"{safe_name}_{tpl_key}_{int(time.time())}.docx"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    doc.save(out_path)
    return jsonify({"out": f"/file/{out_name}", "name": out_name})
