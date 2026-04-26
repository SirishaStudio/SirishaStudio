# Sirisha Studio — Card Processor

A Flask web app with multiple ID-card tools that crop cards out of source PDFs/
images, let you fine-tune brightness/levels in the browser, and print front+back
side-by-side on A4 (matching your offline batch printer's exact mm sizes).

## Tools

| Route           | What it does                                              |
|-----------------|-----------------------------------------------------------|
| `/short-aadhar` | Aadhar PDF → cropped front/back, with PHOTO region levels |
| `/long-aadhar`  | Aadhar PDF → full page, plus digital signature check      |
| `/pan`          | PAN PDF → cropped front/back                              |
| `/voter`        | Voter PDF/JPG/PNG → cropped front/back                    |
| `/rc`           | Vehicle RC two-page PDF → front (page 1) + back (page 2)  |
| `/senior`       | Senior Citizen PDF → cropped front/back (500 DPI source)  |

## Stack

- **Language:** Python 3.12
- **Framework:** Flask (dev server in dev, gunicorn in prod)
- **Image:** OpenCV (`opencv-python-headless`), `pdf2image`, `numpy`
- **Signatures:** `pyhanko` (best-effort presence + integrity check)
- **System dep:** `poppler` (required by `pdf2image`)

## Project Layout

```
config.py                 # POPPLER_PATH + dirs (edit here for Windows)
app.py                    # registers blueprints, landing page, /file/<name>
tools/
  utils.py                # shared helpers (PDF→img, crop, signature check)
  aadhar_short.py         # /short-aadhar
  aadhar_long.py          # /long-aadhar
  pan.py                  # /pan
  voter.py                # /voter
  rc.py                   # /rc
  senior.py               # /senior
templates/
  index.html              # landing page (tile grid)
  tool_dual.html          # shared two-canvas UI
  tool_single.html        # shared one-canvas UI (long aadhar)
static/
  css/style.css
  js/dual_tool.js         # client-side levels + history for dual tools
  js/single_tool.js       # client-side levels + history for single tool
  js/print_a4.js          # shared A4 print (matches offline mm sizes)
uploads/                  # incoming files (runtime)
outputs/                  # generated crops (runtime)
```

## Running

The `Start application` workflow runs `python app.py` on port 5000 (host
`0.0.0.0`).

## Deployment

Configured for autoscale with gunicorn:

```
gunicorn --bind=0.0.0.0:5000 --reuse-port --timeout=300 app:app
```

## Switching machines

Edit only `config.py` → `POPPLER_PATH`:

- Windows: set to your local poppler `bin` folder.
- Linux / Mac / Replit: leave as `None`.
