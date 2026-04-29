# Sirisha Studio

A Flask web app with multiple ID-card / image / document tools (Aadhar, PAN,
Voter, RC, DL, Senior, Custom card crops, plus Convert / Enhance / Resume
builder, ID Photo, Compress, QR code).

It runs the same way on Replit and on your Windows laptop in VS Code.

---

## ✨ Quick start on Windows (VS Code)

Double-click is enough — no commands to type.

### 1. One-time install on your PC

You only need to do this once.

1. **Install Python 3.11 or 3.12** from <https://www.python.org/downloads/>
   ⚠ During install **tick the box "Add Python to PATH"**.

2. **Download Poppler** (required for any PDF tool):
   - Go to <https://github.com/oschwartz10612/poppler-windows/releases>
   - Download the latest `Release-XX.XX.X-0.zip`
   - Unzip it anywhere — for example `C:\Users\<you>\Documents\work\poppler-25.12.0\`
   - Open **`config.py`** in this project and update the `POPPLER_PATH` line so it
     points to the **`Library\bin`** folder inside that poppler folder, e.g.

     ```python
     POPPLER_PATH = r"C:\Users\rao\Documents\work\poppler-25.12.0\Library\bin"
     ```

3. **Double-click `setup.bat`** in this folder.
   It will create a private virtual-env in `.venv\` and install every dependency
   from `requirements.txt`. Wait for it to finish.

### 2. Every time after that

Just **double-click `run.bat`**.

The console window will say:

```
Starting Sirisha Studio on http://127.0.0.1:5000
```

Open <http://127.0.0.1:5000> in your browser.
To stop the server, click the console window and press **Ctrl + C**.

---

## 🧑‍💻 Running it from inside VS Code

1. `File ▸ Open Folder…` and pick this project folder.
2. Press **Ctrl+Shift+P → Python: Select Interpreter** and choose the one inside
   `.venv\Scripts\python.exe` (it appears in the list after you ran `setup.bat`).
3. Open `app.py` and press **F5** — VS Code runs Flask in debug mode.

If `.venv` does not exist yet, open the integrated terminal (Ctrl+`) and run
`setup.bat` once first.

---

## 🐧 Running it on Linux / Mac / Replit

```bash
pip install -r requirements.txt
sudo apt-get install poppler-utils      # Linux only
python app.py
```

`config.py` automatically falls back to the system `PATH` for poppler when the
Windows folder doesn't exist on this machine, so you don't have to edit it.

---

## 📁 What's in the box

| Folder / file       | Purpose                                                 |
|---------------------|---------------------------------------------------------|
| `app.py`            | Flask app — registers every tool and starts the server  |
| `main.py`           | Tiny WSGI entry point used by gunicorn in production    |
| `config.py`         | **Edit `POPPLER_PATH` here** when switching machines    |
| `requirements.txt`  | All Python dependencies (used by setup.bat / pip)       |
| `setup.bat`         | One-time installer (creates .venv + installs reqs)      |
| `run.bat`           | Double-click launcher                                   |
| `tools/`            | One Python file per tool — defaults at the top of each  |
| `templates/`        | HTML templates                                          |
| `static/`           | CSS / JS / icons                                        |
| `uploads/`          | Files you upload land here at runtime                   |
| `outputs/`          | Generated JPGs / PDFs / DOCXs land here                 |
| `overrides.json`    | Saved Dev Mode tweaks (per tool)                        |

---

## 🛠️ Tools

The home page groups them into four sections:

**Cards** — Short Aadhar · Long Aadhar · PAN · Voter · RC · DL · Senior
**Conversions** — Convert · Enhance · Resume Maker
**Studio Utilities** — ID Photo · Compress · QR Code
**Custom** — Custom Card (draw your own crops)

See `replit.md` for the full per-tool reference and Dev Mode notes.

---

## ❓ Troubleshooting (Windows)

| Problem                                                           | Fix                                                                                       |
|-------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| Double-clicking `run.bat` flashes and closes                      | Right-click → **Run as administrator**, or open a Command Prompt and run `run.bat` there. |
| `'py' is not recognised…`                                         | Re-install Python with **"Add Python to PATH"** ticked.                                   |
| PDF tools error with `Unable to get page count` / `pdfinfo` issue | Poppler isn't installed or `POPPLER_PATH` in `config.py` is wrong.                        |
| Browser shows nothing on `localhost:5000`                         | Check the `run.bat` window for an error message — it'll say what crashed.                 |
| `pip install` fails on `Pillow` / `opencv`                        | You're on Python 3.13 (no wheels yet). Use Python 3.11 or 3.12.                           |
| Want to wipe and re-install                                       | Delete the `.venv\` folder and double-click `setup.bat` again.                            |

---

## 🚀 Deploying

On Replit the app deploys with `gunicorn app:app` (already configured).
For your local PC you don't need this — `run.bat` is enough.
