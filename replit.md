# Studio — Aadhar Tool

A simple Flask web app that takes an Aadhar PDF (or image), splits it into front
and back crops, and lets the user fine-tune brightness/levels in the browser.

## Stack

- **Language:** Python 3.12
- **Framework:** Flask (development server in dev, gunicorn in production)
- **Image processing:** OpenCV (`opencv-python-headless`), `pdf2image`
- **System dep:** `poppler` / `poppler-utils` (required by `pdf2image`)

## Project Layout

- `app.py` — Flask app, routes, and image processing pipeline
- `templates/index.html` — Landing page
- `templates/aadhar.html` — Aadhar tool UI (canvas + level sliders)
- `uploads/` — Incoming files (created at runtime)
- `outputs/` — Generated crops (created at runtime)

## Running

The workflow `Start application` runs `python app.py` and serves on port 5000
(host `0.0.0.0`) for the Replit preview.

## Deployment

Configured for autoscale with gunicorn:

```
gunicorn --bind=0.0.0.0:5000 --reuse-port --timeout=300 app:app
```

## Notes

- The original repo had a hard-coded Windows `POPPLER_PATH`; on Replit/Linux
  poppler is on `PATH`, so `POPPLER_PATH` is set to `None`.
