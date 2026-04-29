/* Dual-card tool runtime — used by Short Aadhar, PAN, Voter, RC, DL, Senior. */

(function(){
  const cfg = window.TOOL_CONFIG;
  const $ = id => document.getElementById(id);

  const frontCanvas = $("front");
  const backCanvas  = $("back");
  const fctx = frontCanvas.getContext("2d");
  const bctx = backCanvas.getContext("2d");

  let originalFront = null;
  let originalBack  = null;
  let history   = [];
  let redoStack = [];
  let backReady = false;

  // ----- Photo regions (canvas-pixel coords) -----
  // Either single PHOTO from cfg.photo_region, OR multiple regions auto-scaled
  // from cfg.photo_regions (72-DPI canvas spec). Computed after load().
  let computedPhotoRegions = [];
  const ERASE = cfg.erase_region || null;

  function computePhotoRegions(canvas){
    computedPhotoRegions = [];
    if(cfg.photo_region){
      computedPhotoRegions.push(cfg.photo_region);
    }
    if(cfg.photo_regions){
      const spec  = cfg.photo_regions.front_canvas_72dpi;
      const list  = cfg.photo_regions.regions_72dpi || {};
      const sx = canvas.width  / spec.w;
      const sy = canvas.height / spec.h;
      for(const k of Object.keys(list)){
        const r = list[k];
        computedPhotoRegions.push({
          x: r.x * sx, y: r.y * sy, w: r.w * sx, h: r.h * sy
        });
      }
    }
  }

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
    if($("mode_select")) fd.append("mode", $("mode_select").value);

    setStatus("Processing…");
    fetch(cfg.process_url, { method:"POST", body:fd })
      .then(r => r.json())
      .then(d => {
        if(d.ask_password){ setStatus("Wrong / missing PDF password.", "err"); return; }
        if(d.error){ setStatus(d.error, "err"); return; }

        setStatus("");
        history = []; redoStack = [];
        originalFront = null; originalBack = null;
        backReady = !!d.back;

        // Per-mode photo region (e.g. PAN Old vs New) — backend tells us
        // which zone to mask for THIS specific upload.
        if(d.photo_region) cfg.photo_region = d.photo_region;

        backCanvas.parentElement.style.display = backReady ? "" : "none";
        load(frontCanvas, fctx, d.front, true);
        if(backReady) load(backCanvas, bctx, d.back, false);

        $("area").style.display = "block";
      })
      .catch(e => setStatus("Error: " + e, "err"));
  }

  window.upload = function(){
    const f = $("file").files[0];
    doUpload(f);
  };

  function load(canvas, ctx, src, isFront){
    const img = new Image();
    img.onload = () => {
      canvas.width  = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
      if(isFront){
        originalFront = data;
        computePhotoRegions(canvas);
      } else {
        originalBack = data;
      }
      maybeAutoApply();
    };
    img.src = src + "?t=" + Date.now();
  }

  function maybeAutoApply(){
    if(!originalFront) return;
    if(backReady && !originalBack) return;
    apply(true);
  }

  // ---------- LEVELS ----------
  function levels(v, black, gamma){
    if(v > 240) return 255;
    let n = (v - black) / (255 - black);
    n = Math.max(0, Math.min(1, n));
    return Math.pow(n, 1/gamma) * 255;
  }

  function snapshot(){
    history.push({
      f: fctx.getImageData(0, 0, frontCanvas.width, frontCanvas.height),
      b: backReady ? bctx.getImageData(0, 0, backCanvas.width, backCanvas.height) : null
    });
    if(history.length > 30) history.shift();
  }

  function inAnyPhoto(x, y){
    for(const r of computedPhotoRegions){
      if(x > r.x && x < r.x + r.w && y > r.y && y < r.y + r.h) return true;
    }
    return false;
  }

  function apply(initial = false){
    if(!originalFront) return;
    if(!initial){ snapshot(); redoStack = []; }

    const gB = +$("g_black").value;
    const gG = +$("g_gamma").value;
    const pW = $("p_white") ? +$("p_white").value : 255;
    const pG = $("p_gamma") ? +$("p_gamma").value : 1;

    $("g_black_v").innerText = gB;
    $("g_gamma_v").innerText = gG.toFixed(1);
    if($("p_white_v")) $("p_white_v").innerText = pW;
    if($("p_gamma_v")) $("p_gamma_v").innerText = pG.toFixed(1);

    // FRONT
    const f  = new ImageData(new Uint8ClampedArray(originalFront.data), originalFront.width);
    const fw = f.width;
    const hasPhoto = computedPhotoRegions.length > 0;
    for(let i = 0; i < f.data.length; i += 4){
      let isPhoto = false;
      if(hasPhoto){
        const px = i >> 2;
        const x  = px % fw;
        const y  = (px / fw) | 0;
        isPhoto = inAnyPhoto(x, y);
      }
      for(let c = 0; c < 3; c++){
        const v = originalFront.data[i + c];
        if(isPhoto){
          let n = v / pW;
          n = Math.pow(n, 1/pG);
          f.data[i + c] = Math.max(0, Math.min(255, n * 255));
        } else {
          f.data[i + c] = levels(v, gB, gG);
        }
      }
    }
    if(ERASE) eraseRegion(f);
    fctx.putImageData(f, 0, 0);

    // BACK
    if(backReady && originalBack){
      const b = new ImageData(new Uint8ClampedArray(originalBack.data), originalBack.width);
      for(let i = 0; i < b.data.length; i += 4){
        for(let c = 0; c < 3; c++){
          b.data[i + c] = levels(originalBack.data[i + c], gB, gG);
        }
      }
      if(ERASE) eraseRegion(b);
      bctx.putImageData(b, 0, 0);
    }
  }

  function eraseRegion(img){
    if(!ERASE) return;
    for(let y = ERASE.y; y < ERASE.y + ERASE.h; y++){
      for(let x = ERASE.x; x < ERASE.x + ERASE.w; x++){
        const i = (y * img.width + x) * 4;
        if(i < 0 || i >= img.data.length) continue;
        img.data[i] = 255; img.data[i+1] = 255; img.data[i+2] = 255;
      }
    }
  }

  // ---------- UNDO / REDO ----------
  window.undo = function(){
    if(history.length === 0) return;
    redoStack.push({
      f: fctx.getImageData(0, 0, frontCanvas.width, frontCanvas.height),
      b: backReady ? bctx.getImageData(0, 0, backCanvas.width, backCanvas.height) : null
    });
    const last = history.pop();
    fctx.putImageData(last.f, 0, 0);
    if(backReady && last.b) bctx.putImageData(last.b, 0, 0);
  };

  window.redo = function(){
    if(redoStack.length === 0) return;
    history.push({
      f: fctx.getImageData(0, 0, frontCanvas.width, frontCanvas.height),
      b: backReady ? bctx.getImageData(0, 0, backCanvas.width, backCanvas.height) : null
    });
    const next = redoStack.pop();
    fctx.putImageData(next.f, 0, 0);
    if(backReady && next.b) bctx.putImageData(next.b, 0, 0);
  };

  // ---------- DOWNLOAD ----------
  function fname(side){
    return cfg.tool_key + "_" + side + "_" + new Date().toISOString().slice(0,19).replace(/[:T-]/g,"") + ".jpg";
  }
  window.downloadFront = function(){
    if(!originalFront){ setStatus("Process a file first.", "err"); return; }
    window.downloadCanvas(frontCanvas, fname("front"));
  };
  window.downloadBack = function(){
    if(!backReady){ setStatus("No back image.", "err"); return; }
    window.downloadCanvas(backCanvas, fname("back"));
  };

  // ---------- TRAY ----------
  window.addToTray = function(){
    if(!originalFront){ setStatus("Process a file first.", "err"); return; }
    const ok = window.trayAdd(
      cfg.title || cfg.tool_key,
      cfg.print_scale || 1.0,
      frontCanvas,
      backReady ? backCanvas : null
    );
    if(ok){ setStatus("Added to tray (" + window.trayCount() + " card" + (window.trayCount()===1?"":"s") + " queued).", "ok"); }
  };

  // ---------- PRINT ----------
  window.printA4 = function(){
    if(!originalFront){ setStatus("Process a file first.", "err"); return; }
    const opts = { scale: cfg.print_scale };
    if(cfg.print_mode === "corner"){
      if(backReady) window.printCornerDualA4(frontCanvas, backCanvas, opts);
      else          window.printCornerA4(frontCanvas, opts);
      return;
    }
    if(backReady) window.printDualA4(frontCanvas, backCanvas, opts);
    else          window.printSingleA4(frontCanvas, opts);
  };

  // ---------- DRAG & DROP (whole page) ----------
  ["dragenter","dragover"].forEach(ev =>
    document.addEventListener(ev, e => {
      e.preventDefault(); $("dropzone").classList.add("drop-show");
    })
  );
  ["dragleave","drop"].forEach(ev =>
    document.addEventListener(ev, e => {
      if(ev === "dragleave" && e.target !== document.documentElement) return;
      $("dropzone").classList.remove("drop-show");
    })
  );
  document.addEventListener("drop", e => {
    e.preventDefault();
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if(f){ $("file").files = e.dataTransfer.files; doUpload(f); }
  });

  // ---------- SLIDER EVENTS ----------
  document.querySelectorAll("input[type=range]").forEach(el => {
    el.oninput = () => apply();
  });

  // ---------- DEV API hookup ----------
  window.DEV_API = {
    canvases: { front: frontCanvas, back: backCanvas },
    getLevels(){
      const o = { g_black:+$("g_black").value, g_gamma:+$("g_gamma").value };
      if($("p_white")) o.p_white = +$("p_white").value;
      if($("p_gamma")) o.p_gamma = +$("p_gamma").value;
      return o;
    }
  };
})();
