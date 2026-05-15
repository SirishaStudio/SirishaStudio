"""RESUME MAKER — builds DOCX resumes matching real attached templates.

fresher_a  : Vijay Kumar style  — compact header, text quals, experience, job desc, inter skills
fresher_b  : Centered modern    — large name, tabular quals, skills section
ordinary_a : Karri Karthik style — 5-col edu table, computer skills, strengths, hobbies, profile last
ordinary_b : Emandi Kanaka style — personal details FIRST, edu bullets, comp skills, experience, objective, strengths, hobbies

Education qualification options stored in overrides.json → resume → edu_options.
"""

import os, json, time
from flask import Blueprint, render_template, request, jsonify
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from config import OUTPUT_DIR, BASE_DIR
from tools import utils

bp = Blueprint("resume", __name__)

DEFAULT_EDU_OPTIONS = [
    "SSC", "Diploma", "Inter", "Degree", "B.Tech", "M.Tech",
    "MBA", "MCA", "B.Com", "M.Com", "ITI", "Polytechnic"
]
OVERRIDES_PATH = os.path.join(BASE_DIR, "overrides.json")

TEMPLATES = {
    "fresher_a":  {"group": "fresher",   "label": "Fresher — Experience",  "blurb": "Name+S/o header · Qualifications list · Experience · Job Desc · Skills"},
    "fresher_b":  {"group": "fresher",   "label": "Fresher — Compact",     "blurb": "Centered name · Tabular qualifications · Clean layout"},
    "ordinary_a": {"group": "ordinary",  "label": "Ordinary — Professional","blurb": "Header table · 5-col edu · Computer skills · Strengths · Hobbies · Profile last"},
    "ordinary_b": {"group": "ordinary",  "label": "Ordinary — Detailed",   "blurb": "Personal details first · Edu bullets · Religion · Objective later · Strengths · Hobbies"},
}


# ============================================================
#  Helpers
# ============================================================
def _load_edu_options():
    try:
        with open(OVERRIDES_PATH) as f:
            data = json.load(f)
        opts = data.get("resume", {}).get("edu_options")
        if opts and isinstance(opts, list):
            return opts
    except Exception:
        pass
    return DEFAULT_EDU_OPTIONS[:]


def _set_margins(doc, top=0.6, bottom=0.6, left=0.7, right=0.7):
    for s in doc.sections:
        s.top_margin    = Inches(top)
        s.bottom_margin = Inches(bottom)
        s.left_margin   = Inches(left)
        s.right_margin  = Inches(right)


def _set_cell_border(cell, **kwargs):
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


def _hr(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    bot.set(qn("w:val"), "single")
    bot.set(qn("w:sz"), "8")
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), "000000")
    pBdr.append(bot)
    pPr.append(pBdr)


def _p(doc_or_cell, text="", *, bold=False, size=11, align=None,
       italic=False, space_after=2, underline=False):
    p = doc_or_cell.add_paragraph()
    if align == "center": p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right": p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "justify": p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        r = p.add_run(text)
        r.bold = bold; r.italic = italic; r.underline = underline
        r.font.size = Pt(size)
    return p


def _heading(doc, text, *, size=11, underline=True):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after  = Pt(2)
    r = p.add_run(text)
    r.bold = True; r.underline = underline
    r.font.size = Pt(size)
    return p


def _bullet(doc, items, size=11, prefix="•  "):
    for it in items:
        it = str(it).strip()
        if not it: continue
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(1)
        p.add_run(prefix).font.size = Pt(size)
        p.add_run(it).font.size = Pt(size)


def _kv(doc, label, value, *, size=11, lw=1.7):
    if not (value or "").strip(): return
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(lw), WD_TAB_ALIGNMENT.LEFT)
    r = p.add_run(label); r.bold = True; r.font.size = Pt(size)
    p.add_run("\t: " + value.strip()).font.size = Pt(size)


def _two_col_header(doc, name, left_lines, right_lines, name_size=15):
    """Two-column header table: name+left block vs right block."""
    t = doc.add_table(rows=1, cols=2)
    t.autofit = True
    t.columns[0].width = Inches(4.0)
    t.columns[1].width = Inches(3.0)
    lc, rc = t.rows[0].cells
    pn = lc.paragraphs[0]
    pn.paragraph_format.space_after = Pt(2)
    r = pn.add_run(name or ""); r.bold = True; r.font.size = Pt(name_size)
    for line in left_lines:
        line = (line or "").strip()
        if line: _p(lc, line, size=10, space_after=0)
    for line in right_lines:
        line = (line or "").strip()
        if line: _p(rc, line, size=10, align="right", space_after=0)
    for cell in (lc, rc):
        _set_cell_border(cell, top=0, left=0, right=0, bottom=0)
    return t


def _declaration_footer(doc, name, place, date, size=11):
    _p(doc, "I hereby declare that the above information is true to the best of my knowledge.",
       size=size, align="justify")
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(5.5), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run(f"Place : {(place or '').strip()}").font.size = Pt(size)
    p.add_run("\tSignature").font.size = Pt(size)
    _p(doc, f"Date  : {(date or '').strip()}", size=size)
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p3.paragraph_format.space_before = Pt(8)
    p3.add_run(f"({(name or '').strip()})").font.size = Pt(size)


# ============================================================
#  fresher_a  — Vijay Kumar style
# ============================================================
def build_fresher_a(d):
    doc = Document()
    _set_margins(doc, top=0.5, bottom=0.5, left=0.65, right=0.65)
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"].paragraph_format.space_after = Pt(2)

    sec = d.get("enabled_sections", {})
    name   = (d.get("name") or "").strip()
    father = (d.get("father") or "").strip()
    gender = (d.get("gender") or "").strip().lower()
    rel    = "S/o:" if "female" not in gender else "D/o."

    # RESUME header
    p = _p(doc, "RESUME", bold=True, size=14, align="center", space_after=4)
    p.runs[0].underline = True

    # Name + S/o on one line
    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(2)
    r1 = p2.add_run(name + "  "); r1.bold = True; r1.font.size = Pt(12)
    if father:
        r2 = p2.add_run(rel + " " + father); r2.font.size = Pt(11)

    for line in [d.get("addr1"), d.get("addr2"), d.get("city")]:
        if (line or "").strip():
            _p(doc, line.strip(), size=11, space_after=0)
    if (d.get("mobile") or "").strip():
        _p(doc, "Mobile No : " + d["mobile"].strip(), size=11, space_after=0)
    if (d.get("email") or "").strip():
        _p(doc, "Mail ID   : " + d["email"].strip(), size=11)
    _hr(doc)

    if sec.get("objective", True):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run("Career Objective : "); r.bold = True; r.font.size = Pt(11)
        obj = (d.get("objective") or "To secure a challenging position where my skills are maximally utilized for self and the company.").strip()
        p.add_run(obj).font.size = Pt(11)

    if sec.get("qualifications", True):
        quals = [q for q in (d.get("qualifications") or [])
                 if (q.get("course") or "").strip()]
        if quals:
            _heading(doc, "Academic Qualification :")
            for q in quals:
                c = (q.get("course") or "").strip()
                i = (q.get("institute") or "").strip()
                y = (q.get("year") or "").strip()
                line = c
                if i: line += " from " + i
                if y: line += " (" + y + ")"
                line += "."
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                p.add_run(line).font.size = Pt(11)

    if sec.get("experience", True):
        exp = [x for x in (d.get("experience") or []) if str(x).strip()]
        if exp:
            _heading(doc, "Experience Summary :")
            _bullet(doc, exp, prefix="• ")

    if sec.get("job_desc", True):
        jd = [x for x in (d.get("job_desc") or []) if str(x).strip()]
        if jd:
            _heading(doc, "Job Description & Responsibilities :")
            _bullet(doc, jd, prefix="• ")

    if sec.get("skills_inter", True):
        si = [x for x in (d.get("skills_inter") or []) if str(x).strip()]
        if si:
            _heading(doc, "Inter Personal Skills :")
            _bullet(doc, si, prefix="• ")

    if sec.get("profile", True):
        _heading(doc, "Personal Details :")
        # Compact inline style: two fields per line
        lines = []
        # Line 1: Name + Father + DOB
        l1 = []
        if name: l1.append("Name : " + name)
        if father: l1.append(rel.rstrip(":") + "  : " + father)
        if (d.get("dob") or "").strip(): l1.append("D.O.B : " + d["dob"].strip())
        if l1:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            p.add_run("  ".join(l1)).font.size = Pt(11)
        # Line 2: Languages + Marital
        l2 = []
        if (d.get("languages") or "").strip(): l2.append("Languages Known : " + d["languages"].strip())
        if (d.get("marital") or "").strip(): l2.append("Marital Status : " + d["marital"].strip())
        if l2:
            p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
            p.add_run("  ".join(l2)).font.size = Pt(11)
        # Remaining
        for label, key in [("Gender", "gender"), ("Nationality", "nationality"),
                            ("Religion", "religion"), ("Hobbies", "hobbies")]:
            v = (d.get(key) or "").strip()
            if v:
                p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
                r1 = p.add_run(label + " : "); r1.bold = True; r1.font.size = Pt(11)
                p.add_run(v).font.size = Pt(11)

    if sec.get("declaration", True):
        _heading(doc, "Declaration :")
        _declaration_footer(doc, name, d.get("place"), d.get("date"))

    return doc


# ============================================================
#  fresher_b  — Compact centered style
# ============================================================
def build_fresher_b(d):
    doc = Document()
    _set_margins(doc, top=0.5, bottom=0.5, left=0.65, right=0.65)
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"].paragraph_format.space_after = Pt(2)

    sec = d.get("enabled_sections", {})
    name = (d.get("name") or "").strip()

    p = _p(doc, name, bold=True, size=16, align="center", space_after=2)
    father = (d.get("father") or "").strip()
    if father:
        gender = (d.get("gender") or "").strip().lower()
        rel = "D/o." if "female" in gender else "S/o."
        _p(doc, rel + "  " + father, size=11, align="center", space_after=1)
    parts = []
    if (d.get("mobile") or "").strip(): parts.append(d["mobile"].strip())
    if (d.get("email") or "").strip():  parts.append(d["email"].strip())
    if parts: _p(doc, "  |  ".join(parts), size=10, align="center", space_after=1)
    addr = [x for x in [d.get("addr1"), d.get("addr2"), d.get("city")] if (x or "").strip()]
    if addr: _p(doc, ", ".join(a.strip() for a in addr), size=10, align="center", space_after=4)
    _hr(doc)

    if sec.get("objective", True):
        _heading(doc, "CAREER OBJECTIVE")
        _p(doc, (d.get("objective") or "Seeking a challenging position to contribute and grow within an organisation.").strip(), size=11, align="justify")

    if sec.get("qualifications", True):
        quals = [q for q in (d.get("qualifications") or []) if (q.get("course") or "").strip()]
        if quals:
            _heading(doc, "ACADEMIC QUALIFICATIONS")
            t = doc.add_table(rows=1 + len(quals), cols=3)
            t.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for i, h in enumerate(["Qualification", "Institution", "Year"]):
                c = t.rows[0].cells[i]; c.text = ""
                p2 = c.paragraphs[0]; p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p2.add_run(h); r.bold = True; r.font.size = Pt(10)
                _shade_cell(c, "DCE6F1"); _set_cell_border(c, top=6, bottom=6, left=6, right=6)
            for ri, q in enumerate(quals):
                for ci, key in enumerate(["course", "institute", "year"]):
                    c = t.rows[ri+1].cells[ci]; c.text = ""
                    p2 = c.paragraphs[0]; p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p2.add_run((q.get(key) or "").strip()).font.size = Pt(10)
                    _set_cell_border(c, top=4, bottom=4, left=4, right=4)

    if sec.get("experience", True):
        exp = [x for x in (d.get("experience") or []) if str(x).strip()]
        _heading(doc, "EXPERIENCE")
        if exp: _bullet(doc, exp)
        else: _p(doc, "Fresher.", size=11)

    if sec.get("profile", True):
        _heading(doc, "PERSONAL PROFILE")
        for label, key in [("Date of Birth", "dob"), ("Gender", "gender"),
                            ("Nationality", "nationality"), ("Marital Status", "marital"),
                            ("Languages Known", "languages"), ("Hobbies", "hobbies")]:
            _kv(doc, label, (d.get(key) or ""))

    if sec.get("declaration", True):
        _heading(doc, "DECLARATION")
        _declaration_footer(doc, name, d.get("place"), d.get("date"))

    return doc


# ============================================================
#  ordinary_a  — Karri Karthik style
# ============================================================
def build_ordinary_a(d):
    doc = Document()
    _set_margins(doc, top=0.6, bottom=0.6, left=0.7, right=0.7)
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"].paragraph_format.space_after = Pt(2)

    sec = d.get("enabled_sections", {})
    name   = (d.get("name") or "").strip()
    father = (d.get("father") or "").strip()
    gender = (d.get("gender") or "").strip().lower()
    rel    = "D/O" if "female" in gender else "S/O"

    # Header
    _p(doc, "RESUME", bold=True, size=15, align="center", underline=False)

    # Large name, then S/O line, then address
    p_name = doc.add_paragraph()
    p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_name.paragraph_format.space_after = Pt(2)
    r = p_name.add_run(name); r.bold = True; r.font.size = Pt(14)

    if father:
        p_rel = doc.add_paragraph()
        p_rel.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_rel.paragraph_format.space_after = Pt(2)
        p_rel.add_run(rel + " " + father).font.size = Pt(11)

    # Address + contact two-col
    addr_parts = [x.strip() for x in [d.get("addr1"), d.get("addr2"), d.get("city")] if (x or "").strip()]
    contact_parts = []
    if (d.get("email") or "").strip():  contact_parts.append("email : " + d["email"].strip())
    if (d.get("mobile") or "").strip(): contact_parts.append("Phone : +" + d["mobile"].strip().lstrip("+"))

    if addr_parts or contact_parts:
        t = doc.add_table(rows=1, cols=2)
        t.autofit = True
        lc, rc = t.rows[0].cells
        for line in addr_parts:
            _p(lc, line, size=10, space_after=0)
        for line in contact_parts:
            _p(rc, line, size=10, align="right", space_after=0)
        for cell in (lc, rc):
            _set_cell_border(cell, top=0, left=0, right=0, bottom=0)

    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    if sec.get("objective", True):
        _heading(doc, "CAREER OBJECTIVE :", size=11)
        obj = (d.get("objective") or "To work in an organisation that will give me a platform to utilise my knowledge and enrich my expertise in the process of growing the organisation and myself.").strip()
        _p(doc, obj, size=11, align="justify")

    if sec.get("education", True):
        _heading(doc, "EDUCATIONAL QUALIFICATIONS :", size=11)
        edu = [e for e in (d.get("education") or [])
               if any((e.get(k) or "").strip() for k in ("c1","c2","c3","c4","c5"))]
        if not edu:
            _p(doc, "(No education rows added.)", italic=True)
        else:
            headers = ["Course (Stream)/\nExamination", "Institution",
                       "UNIVERSITY / BOARD", "Year of\nPassing", "Percentage\nmarks"]
            t = doc.add_table(rows=1 + len(edu), cols=5)
            t.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for i, h in enumerate(headers):
                c = t.rows[0].cells[i]; c.text = ""
                p2 = c.paragraphs[0]; p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r2 = p2.add_run(h); r2.bold = True; r2.font.size = Pt(9)
                _shade_cell(c, "DCE6F1"); _set_cell_border(c, top=6, bottom=6, left=6, right=6)
                c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for ri, row in enumerate(edu):
                for ci, key in enumerate(["c1","c2","c3","c4","c5"]):
                    c = t.rows[ri+1].cells[ci]; c.text = ""
                    p2 = c.paragraphs[0]; p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p2.add_run((row.get(key) or "").strip()).font.size = Pt(9)
                    _set_cell_border(c, top=4, bottom=4, left=4, right=4)
                    c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    if sec.get("comp_skills", True):
        cs = [x for x in (d.get("comp_skills") or []) if str(x).strip()]
        if cs:
            _heading(doc, "COMPUTER SKILLS :", size=11)
            _bullet(doc, cs)

    if sec.get("strengths", True):
        st = [x for x in (d.get("strengths") or []) if str(x).strip()]
        if st:
            _heading(doc, "STRENGTHS :", size=11)
            _bullet(doc, st)

    if sec.get("hobbies", True):
        hb = [x for x in (d.get("hobbies_list") or []) if str(x).strip()]
        if hb:
            _heading(doc, "HOBBIES", size=11)
            _bullet(doc, hb)

    if sec.get("profile", True):
        _heading(doc, "PERSONAL PROFILE :", size=11)
        # First line: NAME  FATHER/HUSBAND NAME  GENDER (inline)
        line1 = []
        if name:   line1.append("NAME  :  " + name)
        rel_lbl = "HUSBAND NAME" if (d.get("marital") or "").lower() == "married" else "FATHER NAME"
        if father: line1.append(rel_lbl + "  :  " + father)
        if (d.get("gender") or "").strip(): line1.append("GENDER  :  " + d["gender"].strip().upper())
        if line1:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            p.add_run("  ".join(line1)).font.size = Pt(11)
        for label, key in [("DATE OF BIRTH", "dob"), ("MARITAL STATUS", "marital"),
                            ("LANGUAGES", "languages"), ("NATIONALITY", "nationality")]:
            v = (d.get(key) or "").strip()
            if v:
                p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
                r1 = p.add_run(label); r1.bold = True; r1.font.size = Pt(11)
                tabs = p.paragraph_format.tab_stops
                tabs.add_tab_stop(Inches(1.8), WD_TAB_ALIGNMENT.LEFT)
                p.add_run("\t:  " + v).font.size = Pt(11)
        # Address
        addr_str = "  ".join(x.strip() for x in [d.get("addr1"), d.get("addr2"), d.get("city")] if (x or "").strip())
        if addr_str:
            _kv(doc, "Address", addr_str, lw=1.8)

    if sec.get("declaration", True):
        _heading(doc, "DECLARATION :", size=11)
        _p(doc, "I hereby declare that the information given above is true to the best of my knowledge belief.", size=11, align="justify")
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.add_run("DATE :").font.size = Pt(11)
        p2 = doc.add_paragraph()
        p2.paragraph_format.space_after = Pt(6)
        p2.add_run("PLACE : " + (d.get("place") or "VISAKHAPATNAM")).font.size = Pt(11)
        p3 = doc.add_paragraph(); p3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p3.add_run("(" + name + ")").font.size = Pt(11)

    return doc


# ============================================================
#  ordinary_b  — Emandi Kanaka style (personal details FIRST)
# ============================================================
def build_ordinary_b(d):
    doc = Document()
    _set_margins(doc, top=0.65, bottom=0.65, left=0.75, right=0.75)
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"].paragraph_format.space_after = Pt(2)

    sec = d.get("enabled_sections", {})
    name   = (d.get("name") or "").strip()
    father = (d.get("father") or "").strip()
    gender = (d.get("gender") or "").strip().lower()
    rel    = "D/o." if "female" in gender else "S/o."

    # RESUME centered
    p = _p(doc, "RESUME", bold=True, size=15, align="center", space_after=4)
    p.runs[0].underline = True

    # Header two-col: name+relation+address left, Cell: right
    name_line = name
    if father: name_line += "  " + rel + " " + father
    addr_lines = [x.strip() for x in [d.get("addr1"), d.get("addr2"), d.get("city")] if (x or "").strip()]
    contact_lines = []
    if (d.get("mobile") or "").strip(): contact_lines.append("Cell: " + d["mobile"].strip())
    if (d.get("email") or "").strip():  contact_lines.append("Email: " + d["email"].strip())
    _two_col_header(doc, name_line, addr_lines, contact_lines, name_size=13)

    if sec.get("profile", True):
        _heading(doc, "PERSONAL DETAILS :", size=11)
        for label, key in [
            ("Name", "name"), ("Father Name", "father"),
            ("Date of Birth", "dob"), ("Gender", "gender"),
            ("Marital Status", "marital"), ("Religion", "religion"),
            ("Nationality", "nationality"), ("Languages Known", "languages"),
        ]:
            _kv(doc, label, (d.get(key) or ""), lw=1.8)

    if sec.get("education", True):
        _heading(doc, "EDUCATION QUALIFICATION :", size=11)
        quals = [q for q in (d.get("qualifications") or []) if (q.get("course") or "").strip()]
        if quals:
            for q in quals:
                c = (q.get("course") or "").strip()
                i = (q.get("institute") or "").strip()
                y = (q.get("year") or "").strip()
                line = c
                if i: line += " from " + i
                if y: line += " (" + y + ")"
                line += "."
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.left_indent = Inches(0.3)
                p.add_run("•  " + line).font.size = Pt(11)

    if sec.get("comp_skills", True):
        cs = [x for x in (d.get("comp_skills") or []) if str(x).strip()]
        if cs:
            _heading(doc, "COMPUTER SKILLS :", size=11)
            _bullet(doc, cs)

    if sec.get("experience", True):
        exp = [x for x in (d.get("experience") or []) if str(x).strip()]
        if exp:
            _heading(doc, "Previous work experience :", size=11)
            _bullet(doc, exp)

    if sec.get("objective", True):
        _heading(doc, "CAREER OBJECTIVE :", size=11)
        obj = (d.get("objective") or "To enjoy work while working in an esteemed organisation with scope to learn and grow.").strip()
        _p(doc, obj, size=11, align="justify")

    if sec.get("strengths", True):
        st = [x for x in (d.get("strengths") or []) if str(x).strip()]
        if st:
            _heading(doc, "PERSONAL STRENGTHS :", size=11)
            _bullet(doc, st)

    if sec.get("hobbies", True):
        hb = [x for x in (d.get("hobbies_list") or []) if str(x).strip()]
        if hb:
            _heading(doc, "HOBBIES :", size=11)
            _bullet(doc, hb)

    if sec.get("declaration", True):
        _heading(doc, "DECLARATION :", size=11)
        _p(doc, "I hereby declare that the above written particulars are true to the best of my knowledge and belief.", size=11, align="justify")
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(10)
        p.add_run("(" + name + ")").font.size = Pt(11)
        p2 = doc.add_paragraph()
        p2.paragraph_format.space_after = Pt(0)
        tabs = p2.paragraph_format.tab_stops
        tabs.add_tab_stop(Inches(5.0), WD_TAB_ALIGNMENT.RIGHT)
        p2.add_run("Place: " + (d.get("place") or "").strip()).font.size = Pt(11)
        p2.add_run("\tDate: " + (d.get("date") or "").strip()).font.size = Pt(11)

    return doc


BUILDERS = {
    "fresher_a":  build_fresher_a,
    "fresher_b":  build_fresher_b,
    "ordinary_a": build_ordinary_a,
    "ordinary_b": build_ordinary_b,
}


# ============================================================
#  Routes
# ============================================================
@bp.route("/resume")
def page():
    return render_template("tool_resume.html",
                           templates=TEMPLATES,
                           edu_options=_load_edu_options())


@bp.route("/resume/edu-options", methods=["GET"])
def get_edu_options():
    return jsonify({"options": _load_edu_options()})


@bp.route("/resume/edu-options", methods=["POST"])
def set_edu_options():
    j = request.get_json(silent=True) or {}
    opts = j.get("options")
    if not isinstance(opts, list):
        return jsonify({"error": "options must be a list"})
    opts = [str(o).strip() for o in opts if str(o).strip()]
    try:
        with open(OVERRIDES_PATH) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("resume", {})["edu_options"] = opts
    with open(OVERRIDES_PATH, "w") as f:
        json.dump(data, f, indent=2)
    return jsonify({"ok": True, "options": opts})


@bp.route("/resume/build", methods=["POST"])
def build():
    j = request.get_json(silent=True) or {}
    tpl_key = j.get("template")
    if tpl_key not in BUILDERS:
        return jsonify({"error": f"Unknown template: {tpl_key}"})
    fields = j.get("fields") or {}
    payload = dict(fields)
    payload.update({
        "education":        j.get("education")     or [],
        "experience":       j.get("experience")    or [],
        "strengths":        j.get("strengths")     or [],
        "comp_skills":      j.get("comp_skills")   or [],
        "qualifications":   j.get("qualifications") or [],
        "job_desc":         j.get("job_desc")      or [],
        "skills_inter":     j.get("skills_inter")  or [],
        "hobbies_list":     j.get("hobbies_list")  or [],
        "enabled_sections": j.get("enabled_sections") or {},
    })
    try:
        doc = BUILDERS[tpl_key](payload)
    except Exception as e:
        return jsonify({"error": f"Build failed: {e}"})

    safe_name = (fields.get("name") or "resume").strip().replace(" ", "_")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "-_") or "resume"
    variant = TEMPLATES.get(tpl_key, {}).get("label", tpl_key).replace(" ", "_").replace("—", "-")
    out_name = f"{safe_name}_{variant}_{int(time.time())}.docx"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    doc.save(out_path)
    return jsonify({"out": f"/file/{out_name}", "name": out_name})
