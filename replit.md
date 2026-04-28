# Sirisha Studio — Card Processor

A Flask web app with multiple ID-card tools that crop cards out of source PDFs/
images, let you fine-tune brightness/levels in the browser, paste a digital-
signature screenshot onto Long Aadhar, download the adjusted images as JPG, and
print front+back on A4 (matching your offline batch printer's exact mm sizes).

## Tools

| Route           | What it does                                                  |
|-----------------|---------------------------------------------------------------|
| `/short-aadhar` | Aadhar PDF → cropped front/back, with PHOTO region levels     |
| `/long-aadhar`  | Aadhar PDF → full page; paste signature screenshot overlay    |
| `/pan`          | PAN PDF → cropped front/back. **Old / New** mode toggle       |
| `/voter`        | Voter PDF/JPG/PNG → front/back. Two photo regions on front    |
| `/rc`           | Vehicle RC two-page PDF → front (page 1) + back (page 2)      |
| `/dl`           | Driving Licence two-page PDF → front (with photo) + back      |
| `/senior`       | Senior Citizen PDF → cropped front/back (500 DPI source)      |
| `/custom`       | Draw FRONT/BACK rectangles on any uploaded card; save preset  |
| `/convert`      | PDF↔JPG/DOCX, image format swaps, images→one PDF or each→PDF  |
| `/enhance`      | Multi-image batch: lighten/darken/whiten/dark-fix; print PDF  |
| `/resume`       | Fresher / Ordinary / Detailed templates → filled DOCX         |

## Important behaviours

- **A4 print descale**: every print is multiplied by **0.97** (`GLOBAL_PRINT_DESCALE` in
  `config.py`).
- **Per-tool print scale**: PAN defaults to **1.02**; RC prints to the **top-left
  corner** of A4; everything else is centered dual-card.
- **Defaults**: Aadhar Black 128 / Gamma 1.2; PAN Black 80 / Gamma 1.2;
  Voter Black 65 / Gamma 1.3; RC Black 0 / Gamma 1.0 (no auto color filter).
- **Drag & drop**: drop a PDF/image anywhere on a tool page; on Long Aadhar,
  pasting (Ctrl + V) or dropping an image after the PDF treats it as the
  signature overlay.
- **Download**: every tool has a JPG download button (97% quality, with
  overlay baked in).
- **Dev Mode** (orange button on every tool page):
  - View / clear saved overrides
  - "Save current sliders as default" -> persists `levels` for that tool
  - "Pick on FRONT/BACK/IMAGE" -> drag a rectangle, get exact canvas-pixel
    coords, save as `photo_region`. Useful when sending coords to the agent.

## Stack

- **Language:** Python 3.12
- **Framework:** Flask (dev server in dev, gunicorn in prod)
- **Image:** OpenCV (`opencv-python-headless`), `pdf2image`, `numpy`
- **System dep:** `poppler` (required by `pdf2image`)

## Project Layout

```
config.py                 # POPPLER_PATH + GLOBAL_PRINT_DESCALE
overrides.json            # runtime overrides written by Dev Mode
app.py                    # registers blueprints, /, /file/<n>, /dev/overrides/*
tools/
  utils.py                # shared helpers + overrides loader
  aadhar_short.py         # /short-aadhar
  aadhar_long.py          # /long-aadhar
  pan.py                  # /pan          (Old/New toggle)
  voter.py                # /voter        (2 photo regions)
  rc.py                   # /rc           (corner print)
  dl.py                   # /dl           (photo region)
  senior.py               # /senior
templates/
  index.html              # tile picker
  tool_dual.html          # shared two-canvas UI
  tool_single.html        # one-canvas UI + signature paste
static/
  css/style.css
  js/dual_tool.js         # multi-tool client logic
  js/single_tool.js       # long-aadhar client logic + paste overlay
  js/print_a4.js          # all A4 print modes + downloadCanvas helper
  js/dev_mode.js          # dev panel + region picker
uploads/                  # incoming files (runtime)
outputs/                  # generated crops (runtime)
```

## Editing defaults

Each tool file's TOP block (`# EDITABLE DEFAULTS`) holds plain Python constants:
crop coords, photo regions, level defaults, print scale, DPI. Change those for
permanent defaults. For ad-hoc overrides without touching code, use **Dev Mode**
on the tool page.

## Running

The `Start application` workflow runs `python app.py` on port 5000 (host
`0.0.0.0`).

## Deployment

Configured for autoscale with gunicorn:

```
gunicorn --bind=0.0.0.0:5000 --reuse-port --timeout=300 app:app
```

## Switching machines (Windows / Linux)

Edit only `config.py` → `POPPLER_PATH`:

- Windows: set to your local poppler `bin` folder.
- Linux / Mac / Replit: leave as `None` (auto-falls back if Windows path
  doesn't exist on this machine, so you don't have to edit at all).
