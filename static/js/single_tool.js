/* Single-image tool runtime — used by Long Aadhar (full PDF page).
 * Adds: drag&drop file upload, paste/drop signature image overlay,
 * download (with overlay baked in), Dev Mode hookup.
 */

(function(){
  const cfg = window.TOOL_CONFIG;
  const $ = id => document.getElementById(id);

  const canvas = $("img");
  const ctx = canvas.getContext("2d");
  const PHOTO = cfg.photo_region || null;

  let original = null;
  let history   = [];
  let redoStack = [];

  // Signature overlay state (positioned in CSS-pixel coords on the canvas)
  // We render it as a positioned <div><img></div> over the canvas during edit,
  // then bake into a flattened canvas for Print / Download.
  const overlay = {
    img: null,            // HTMLImageElement
    visible: false,
    cx: 50, cy: 50,       // CSS pixels relative to canvas
    cw: 120, ch: 120,
    dragging: false,
    resizing: false,
    dragOff: {x:0, y:0}
  };

  function setStatus(msg, cls=""){
    const el = $("status");
    el.innerText = msg;
    el.className = cls;
  }

  // ---------- UPLOAD ----------
  function doUpload(file){
    if(!file){ setStatus("Pick a file first.", "err"); return; }
    const fd = new FormData();
    fd.append("file", file);
    if($("password")) fd.append("password", $("password").value);

    setStatus("Processing…");
    fetch(cfg.process_url, { method:"POST", body:fd })
      .then(r => r.json())
      .then(d => {
        if(d.ask_password){ setStatus("Wrong / missing PDF password.", "err"); return; }
        if(d.error){ setStatus(d.error, "err"); return; }

        setStatus("");
        history = []; redoStack = [];
        original = null;
        load(d.image);
        $("area").style.display = "block";
      })
      .catch(e => setStatus("Error: " + e, "err"));
  }
  window.upload = function(){ doUpload($("file").files[0]); };

  function load(src){
    const img = new Image();
    img.onload = () => {
      canvas.width  = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      original = ctx.getImageData(0, 0, canvas.width, canvas.height);
      apply(true);
      // Re-position overlay default near photo region after canvas sized
      if(cfg.allow_paste_overlay){
        positionOverlayDefault();
      }
    };
    img.src = src + "?t=" + Date.now();
  }

  function levels(v, black, gamma){
    if(v > 240) return 255;
    let n = (v - black) / (255 - black);
    n = Math.max(0, Math.min(1, n));
    return Math.pow(n, 1/gamma) * 255;
  }

  function snapshot(){
    history.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    if(history.length > 20) history.shift();
  }

  function apply(initial=false){
    if(!original) return;
    if(!initial){ snapshot(); redoStack = []; }

    const gB = +$("g_black").value;
    const gG = +$("g_gamma").value;
    const pW = $("p_white") ? +$("p_white").value : 255;
    const pG = $("p_gamma") ? +$("p_gamma").value : 1;

    $("g_black_v").innerText = gB;
    $("g_gamma_v").innerText = gG.toFixed(1);
    if($("p_white_v")) $("p_white_v").innerText = pW;
    if($("p_gamma_v")) $("p_gamma_v").innerText = pG.toFixed(1);

    const out = new ImageData(new Uint8ClampedArray(original.data), original.width);
    const w = out.width;

    for(let i = 0; i < out.data.length; i += 4){
      let isPhoto = false;
      if(PHOTO){
        const px = i >> 2;
        const x  = px % w;
        const y  = (px / w) | 0;
        isPhoto = (x > PHOTO.x && x < PHOTO.x + PHOTO.w &&
                   y > PHOTO.y && y < PHOTO.y + PHOTO.h);
      }
      for(let c = 0; c < 3; c++){
        const v = original.data[i + c];
        if(isPhoto){
          let n = v / pW;
          n = Math.pow(n, 1/pG);
          out.data[i + c] = Math.max(0, Math.min(255, n * 255));
        } else {
          out.data[i + c] = levels(v, gB, gG);
        }
      }
    }
    ctx.putImageData(out, 0, 0);
  }

  window.undo = function(){
    if(history.length === 0) return;
    redoStack.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    ctx.putImageData(history.pop(), 0, 0);
  };
  window.redo = function(){
    if(redoStack.length === 0) return;
    history.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    ctx.putImageData(redoStack.pop(), 0, 0);
  };

  // ---------- DOWNLOAD (with overlay baked) ----------
  function flattenedCanvas(){
    if(!overlay.visible || !overlay.img) return canvas;
    const c2 = document.createElement("canvas");
    c2.width = canvas.width; c2.height = canvas.height;
    const c2x = c2.getContext("2d");
    c2x.drawImage(canvas, 0, 0);
    // Convert overlay CSS rect -> canvas-pixel rect
    const sx = canvas.width  / canvas.clientWidth;
    const sy = canvas.height / canvas.clientHeight;
    c2x.drawImage(overlay.img,
      overlay.cx * sx, overlay.cy * sy,
      overlay.cw * sx, overlay.ch * sy);
    return c2;
  }
  window.downloadImg = function(){
    if(!original){ setStatus("Process a file first.", "err"); return; }
    const fname = cfg.tool_key + "_" + new Date().toISOString().slice(0,19).replace(/[:T-]/g,"") + ".jpg";
    window.downloadCanvas(flattenedCanvas(), fname);
  };

  // ---------- PRINT (with overlay baked) ----------
  window.printA4 = function(){
    if(!original){ setStatus("Process a file first.", "err"); return; }
    window.printSingleA4(flattenedCanvas(), { scale: cfg.print_scale });
  };

  // ---------- PASTE / DROP signature overlay ----------
  if(cfg.allow_paste_overlay){
    const box = $("overlay_box");
    const oimg = $("overlay_img");
    const sigPicker = $("sig_file");
    const removeBtn = $("sig_remove");

    function setOverlay(imgEl){
      overlay.img = imgEl;
      overlay.visible = true;
      oimg.src = imgEl.src;
      box.style.display = "block";
      removeBtn.disabled = false;
      placeOverlay();
    }

    window.removeSig = function(){
      overlay.img = null; overlay.visible = false;
      box.style.display = "none";
      removeBtn.disabled = true;
    };

    function loadFromBlob(blob){
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => setOverlay(img);
      img.src = url;
    }

    sigPicker.addEventListener("change", () => {
      const f = sigPicker.files[0];
      if(f) loadFromBlob(f);
    });

    // PASTE from clipboard (Ctrl + V anywhere on the page)
    document.addEventListener("paste", e => {
      const items = (e.clipboardData || {}).items || [];
      for(const it of items){
        if(it.type && it.type.indexOf("image/") === 0){
          const blob = it.getAsFile();
          if(blob) loadFromBlob(blob);
          e.preventDefault();
          break;
        }
      }
    });

    // Drag-drop image OR file
    document.addEventListener("drop", e => {
      const dt = e.dataTransfer;
      if(!dt) return;
      const f = dt.files && dt.files[0];
      if(!f) return;
      if(f.type && f.type.indexOf("image/") === 0 && original){
        // image after a PDF is loaded -> treat as signature paste
        loadFromBlob(f); e.preventDefault();
      }
    });

    // ---- drag & resize the overlay box ----
    function placeOverlay(){
      box.style.left   = overlay.cx + "px";
      box.style.top    = overlay.cy + "px";
      box.style.width  = overlay.cw + "px";
      box.style.height = overlay.ch + "px";
    }
    function positionOverlayDefault(){
      // Put it roughly in the lower-right area where Aadhar tick lives
      overlay.cx = Math.round(canvas.clientWidth  * 0.55);
      overlay.cy = Math.round(canvas.clientHeight * 0.05);
      overlay.cw = 120; overlay.ch = 120;
      placeOverlay();
    }

    box.addEventListener("mousedown", ev => {
      if(ev.target.classList.contains("resize-handle")){
        overlay.resizing = true;
      } else {
        overlay.dragging = true;
        overlay.dragOff.x = ev.clientX - overlay.cx;
        overlay.dragOff.y = ev.clientY - overlay.cy;
      }
      ev.preventDefault();
    });
    document.addEventListener("mousemove", ev => {
      if(overlay.dragging){
        overlay.cx = ev.clientX - overlay.dragOff.x;
        overlay.cy = ev.clientY - overlay.dragOff.y;
        placeOverlay();
      } else if(overlay.resizing){
        const r = box.getBoundingClientRect();
        overlay.cw = Math.max(20, ev.clientX - r.left);
        overlay.ch = Math.max(20, ev.clientY - r.top);
        placeOverlay();
      }
    });
    document.addEventListener("mouseup", () => {
      overlay.dragging = overlay.resizing = false;
    });
  }

  // ---------- DRAG & DROP file (PDF/image) ----------
  ["dragenter","dragover"].forEach(ev =>
    document.addEventListener(ev, e => {
      e.preventDefault();
      if(!original) $("dropzone").classList.add("drop-show");
    })
  );
  ["dragleave","drop"].forEach(ev =>
    document.addEventListener(ev, e => {
      $("dropzone").classList.remove("drop-show");
    })
  );
  document.addEventListener("drop", e => {
    const dt = e.dataTransfer;
    const f = dt && dt.files && dt.files[0];
    if(!f) return;
    // If no image loaded yet -> treat as file upload
    if(!original){
      e.preventDefault();
      $("file").files = dt.files;
      doUpload(f);
    }
    // else: handled by overlay-paste branch above
  });

  // ---------- SLIDERS ----------
  document.querySelectorAll("input[type=range]").forEach(el => {
    el.oninput = () => apply();
  });

  // ---------- DEV API hookup ----------
  window.DEV_API = {
    canvases: { img: canvas },
    getLevels(){
      const o = { g_black:+$("g_black").value, g_gamma:+$("g_gamma").value };
      if($("p_white")) o.p_white = +$("p_white").value;
      if($("p_gamma")) o.p_gamma = +$("p_gamma").value;
      return o;
    }
  };
})();
