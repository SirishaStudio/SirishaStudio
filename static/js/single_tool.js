/* Single-image tool runtime — used by Long Aadhar (full PDF page).
 *
 * Key change vs prior version: the signature OVERLAY position is stored as
 * FRACTIONS (0–1) of the canvas client size. On every redraw / resize / zoom,
 * pixel positions are recomputed from fractions, so the box stays glued to the
 * same spot on the underlying image even when the browser is zoomed.
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

  // Overlay state — STORED AS FRACTIONS of canvas client size:
  const overlay = {
    img: null,
    visible: false,
    fx: 0.55, fy: 0.05, fw: 0.18, fh: 0.18,  // fractional bounds
    dragging: false,
    resizing: false,
    grabFx: 0, grabFy: 0
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
      if(overlay.visible) placeOverlay();
    };
    img.src = src + "?t=" + Date.now();
  }

  // ---------- LEVELS ----------
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
        const x = px % w, y = (px / w) | 0;
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

  // ---------- DOWNLOAD / PRINT (overlay baked) ----------
  function flattenedCanvas(){
    if(!overlay.visible || !overlay.img) return canvas;
    const c2 = document.createElement("canvas");
    c2.width = canvas.width; c2.height = canvas.height;
    const c2x = c2.getContext("2d");
    c2x.drawImage(canvas, 0, 0);
    // Convert overlay fractions into canvas-pixel rect
    const x = overlay.fx * canvas.width;
    const y = overlay.fy * canvas.height;
    const w = overlay.fw * canvas.width;
    const h = overlay.fh * canvas.height;
    c2x.drawImage(overlay.img, x, y, w, h);
    return c2;
  }
  window.downloadImg = function(){
    if(!original){ setStatus("Process a file first.", "err"); return; }
    const fname = cfg.tool_key + "_" + new Date().toISOString().slice(0,19).replace(/[:T-]/g,"") + ".jpg";
    window.downloadCanvas(flattenedCanvas(), fname);
  };
  window.printA4 = function(){
    if(!original){ setStatus("Process a file first.", "err"); return; }
    window.printSingleA4(flattenedCanvas(), { scale: cfg.print_scale });
  };

  // ---------- OVERLAY (paste signature) ----------
  if(cfg.allow_paste_overlay){
    const box = $("overlay_box");
    const oimg = $("overlay_img");
    const sigPicker = $("sig_file");
    const removeBtn = $("sig_remove");

    function setOverlay(imgEl){
      overlay.img = imgEl;
      overlay.visible = true;
      oimg.src = imgEl.src;
      // reset position to top-right area (fractions)
      overlay.fx = 0.55; overlay.fy = 0.04;
      overlay.fw = 0.18; overlay.fh = 0.10;
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

    document.addEventListener("drop", e => {
      const dt = e.dataTransfer;
      if(!dt) return;
      const f = dt.files && dt.files[0];
      if(!f) return;
      if(f.type && f.type.indexOf("image/") === 0 && original){
        loadFromBlob(f); e.preventDefault();
      }
    });

    // ---- placement: convert fractions -> CSS pixels ----
    function placeOverlay(){
      const w = canvas.clientWidth, h = canvas.clientHeight;
      box.style.left   = (overlay.fx * w) + "px";
      box.style.top    = (overlay.fy * h) + "px";
      box.style.width  = (overlay.fw * w) + "px";
      box.style.height = (overlay.fh * h) + "px";
    }

    // ---- drag / resize → update fractions ----
    box.addEventListener("mousedown", ev => {
      const r = box.getBoundingClientRect();
      const cw = canvas.clientWidth, ch = canvas.clientHeight;
      if(ev.target.classList.contains("resize-handle")){
        overlay.resizing = true;
      } else {
        overlay.dragging = true;
        // grab offset in fractions
        overlay.grabFx = (ev.clientX - r.left) / cw;
        overlay.grabFy = (ev.clientY - r.top)  / ch;
      }
      ev.preventDefault();
    });
    document.addEventListener("mousemove", ev => {
      if(!overlay.dragging && !overlay.resizing) return;
      const cr = canvas.getBoundingClientRect();
      const cw = canvas.clientWidth, ch = canvas.clientHeight;
      if(overlay.dragging){
        overlay.fx = ((ev.clientX - cr.left) / cw) - overlay.grabFx;
        overlay.fy = ((ev.clientY - cr.top)  / ch) - overlay.grabFy;
        placeOverlay();
      } else if(overlay.resizing){
        const r = box.getBoundingClientRect();
        const newCssW = Math.max(20, ev.clientX - r.left);
        const newCssH = Math.max(20, ev.clientY - r.top);
        overlay.fw = newCssW / cw;
        overlay.fh = newCssH / ch;
        placeOverlay();
      }
    });
    document.addEventListener("mouseup", () => {
      overlay.dragging = overlay.resizing = false;
    });

    // Keep overlay glued to canvas on window resize / browser zoom.
    let raf = null;
    function reflow(){
      if(raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => { if(overlay.visible) placeOverlay(); });
    }
    window.addEventListener("resize", reflow);
    if(window.ResizeObserver){
      new ResizeObserver(reflow).observe(canvas);
    }
  }

  // ---------- DRAG & DROP file ----------
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
    if(!original){
      e.preventDefault();
      $("file").files = dt.files;
      doUpload(f);
    }
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
