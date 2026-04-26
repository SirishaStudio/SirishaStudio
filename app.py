import os
import uuid
import cv2
from flask import Flask, render_template, request, jsonify, send_file
from pdf2image import convert_from_path

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD = os.path.join(BASE_DIR, "uploads")
OUTPUT = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

POPPLER_PATH = r"C:\Users\rao\Documents\work\poppler-25.12.0\Library\bin"

FRONT_CROP = (5565, 7128, 478, 2928)
BACK_CROP  = (5570, 7128, 3031, 5476)

ERASE = (842, 11, 63, 12)

def erase(img):
    x,y,w,h = ERASE
    cv2.rectangle(img, (x,y), (x+w,y+h), (255,255,255), -1)
    return img


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/aadhar")
def aadhar():
    return render_template("aadhar.html")


@app.route("/process-aadhar", methods=["POST"])
def process():

    file = request.files.get("file")
    password = request.form.get("password", "")

    uid = str(uuid.uuid4())[:8]
    path = os.path.join(UPLOAD, uid + "_" + file.filename)
    file.save(path)

    ext = file.filename.split('.')[-1].lower()
    img_path = path

    if ext == "pdf":

        name = file.filename.split('.')[0]

        if len(name) == 8:
            password = name

        try:
            pages = convert_from_path(
                path,
                dpi=700,
                poppler_path=POPPLER_PATH,
                userpw=password if password else None
            )
        except:
            return jsonify({"ask_password": True})

        if not pages:
            return jsonify({"error": "Failed to open PDF"})

        img_path = os.path.join(UPLOAD, uid+".jpg")
        pages[0].save(img_path, "JPEG", quality=95)

    img = cv2.imread(img_path)

    fy1,fy2,fx1,fx2 = FRONT_CROP
    by1,by2,bx1,bx2 = BACK_CROP

    front = erase(img[fy1:fy2, fx1:fx2])
    back  = erase(img[by1:by2, bx1:bx2])

    f_path = os.path.join(OUTPUT, uid+"_f.jpg")
    b_path = os.path.join(OUTPUT, uid+"_b.jpg")

    cv2.imwrite(f_path, front)
    cv2.imwrite(b_path, back)

    return jsonify({
        "front": "/file/"+uid+"_f.jpg",
        "back": "/file/"+uid+"_b.jpg"
    })


@app.route("/file/<name>")
def file(name):
    return send_file(os.path.join(OUTPUT, name))


if __name__ == "__main__":
    app.run(debug=True)