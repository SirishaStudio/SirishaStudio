"""Project-wide configuration.

Edit the CONFIG block below when switching between Windows (VS Code) and Linux/Replit.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
#  CONFIG  ->  change ONLY this block when switching machines
# ============================================================
#
#  Windows (VS Code on your laptop):
#       POPPLER_PATH = r"C:\Users\rao\Documents\work\poppler-25.12.0\Library\bin"
#
#  Linux / Mac / Replit:
#       POPPLER_PATH = None      # poppler is on PATH already
#
POPPLER_PATH = r"C:\Users\rao\Documents\work\poppler-25.12.0\Library\bin"
# ============================================================
