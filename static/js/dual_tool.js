/* Dual-card tool runtime — used by Short Aadhar, PAN, Voter, RC, Senior.
 * Reads window.TOOL_CONFIG injected by the template.
 */

(function(){
  const cfg = window.TOOL_CONFIG;

  const frontCanvas = document.getElementById("front");
  const backCanvas  = document.getElementById("back");
  const fctx = frontCanvas.getContext("2d");
  const bctx = backCanvas.getContext("2d");

  let originalFront = null;
  let originalBack  = null;
  let history   = [];
  let redoStack = [];
  let backReady = false;

  const PHOTO = cfg.photo_region || null;
  const ERASE = cfg.erase_region || null;

  const $ = (id) => document.getElementById(id);

  function setStatus(msg, cls=""){
    const el = $("status");
    el.innerText = msg;
    el.className = cls;
  }

  // ---------- UPLOAD ----------
  window.upload = function(){
    const fileEl = $("file");
    const file = fileEl.files[0];
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
        originalFront = null; originalBack = null;
        backReady = !!d.back;

        // hide back canvas if missing (e.g. RC with single-page PDF)
        backCanvas.style.display = backReady ? "" : "none";

        load(frontCanvas, fctx, d.front, true);
        if(backReady) load(backCanvas, bctx, d.back, false);

        $("area").style.display = "block";
      })
      .catch(e => setStatus("Error: " + e, "err"));
  };

  function load(canvas, ctx, src, isFront){
    const img = new Image();
    img.onload = () => {
      canvas.width  = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
      if(isFront) originalFront = data; else originalBack = data;
      maybeAutoApply();
    };
    img.src = src;
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
    const snap = {
      f: fctx.getImageData(0, 0, frontCanvas.width, frontCanvas.height),
      b: backReady ? bctx.getImageData(0, 0, backCanvas.width, backCanvas.height) : null
    };
    history.push(snap);
    if(history.length > 30) history.shift();
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
    for(let i = 0; i < f.data.length; i += 4){
      let isPhoto = false;
      if(PHOTO){
        const px = i >> 2;
        const x  = px % fw;
        const y  = (px / fw) | 0;
        isPhoto = (x > PHOTO.x && x < PHOTO.x + PHOTO.w &&
                   y > PHOTO.y && y < PHOTO.y + PHOTO.h);
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

  // ---------- PRINT ----------
  window.printA4 = function(){
    if(!originalFront){ setStatus("Process a file first.", "err"); return; }
    if(backReady){
      window.printDualA4(frontCanvas, backCanvas);
    } else {
      window.printSingleA4(frontCanvas);
    }
  };

  // ---------- SLIDER EVENTS ----------
  document.querySelectorAll("input[type=range]").forEach(el => {
    el.oninput = () => apply();
  });
})();
