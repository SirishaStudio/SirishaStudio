"""Project-wide configuration.

Edit ONLY the POPPLER block below when switching between Windows (VS Code) and
Linux/Replit. Every per-tool default lives at the TOP of that tool's file inside
tools/ — they're plain Python constants, easy to change.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR    = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR    = os.path.join(BASE_DIR, "outputs")
OVERRIDES_PATH = os.path.join(BASE_DIR, "overrides.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
#  POPPLER  ->  edit ONLY this block when switching machines
# ============================================================
#  Windows (VS Code on your laptop):
#       POPPLER_PATH = r"C:\Users\rao\Documents\work\poppler-25.12.0\Library\bin"
#  Linux / Mac / Replit:
#       POPPLER_PATH = None      # poppler is on PATH already
#
POPPLER_PATH = r"C:\Users\rao\Documents\work\poppler-25.12.0\Library\bin"
# ============================================================

# Auto-fallback so the SAME file works on Replit/Linux without editing:
# if the configured Windows folder doesn't exist on this machine, use PATH.
if POPPLER_PATH and not os.path.isdir(POPPLER_PATH):
    POPPLER_PATH = None


# ============================================================
#  GLOBAL PRINT DESCALE
#  When printing to A4, every layout is rendered at this fraction
#  of full size (you asked for 97 %).
# ============================================================
GLOBAL_PRINT_DESCALE = 0.97
