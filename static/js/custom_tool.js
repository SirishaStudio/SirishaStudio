/* Custom Card builder. Lets the user draw FRONT and BACK rectangles directly
 * on a source image, then crops + applies levels server-side.
 *
 * Saves named presets (DPI + crops + levels) to overrides.json so the next time
 * the same card type comes in, they pick the preset and are ready to print.
 */
(function(){
  const cfg = window.TOOL_CONFIG;
  const $ = id => document.getElementById(id);
  const PRESETS = window.PRESETS || [];

  const srcImg = $("src_img");
  const srcArea = $("src_area");
  const rectFront = $("rect_front");
  const rectBack  = $("rect_back");

  const frontCanvas = $("front");
  const backCanvas  = $("back");
  const fctx = frontCanvas.getContext("2d");
  const bctx = backCanvas.getContext("2d");

  let originalFront = null, originalBack = null;
  let backReady = false;
  let uid = null;
  let imgW = 0, imgH = 0;
  let pickSideName = null;
  let dragStart = null;
  let crops = { front: null, back: null };

  function setStatus(msg, cls=""){
    const e = $("status"); e.innerText = msg; e.className = cls;
  }

  // ---------- LOAD source ----------
  window.loadSrc = function(){
    const f = $("file").files[0];
    if(!f){ setStatus("Pick a file first.","err"); return; }
    const fd = new FormData();
    fd.append("file", f);
    fd.append("password", $("password").value);
    fd.append("dpi", $("dpi").value);
    setStatus("Loading…");
    fetch("/custom/load", { method:"POST", body:fd })
      .then(r => r.json())
      .then(d => {
        if(d.ask_password){ setStatus("Wrong / missing PDF password.","err"); return; }
        if(d.error){ setStatus(d.error,"err"); return; }
        uid = d.uid; imgW = d.w; imgH = d.h;
        srcImg.onload = () => { srcArea.style.display = "block"; };
        srcImg.src = d.image + "?t=" + Date.now();
        crops = { front: null, back: null };
        rectFront.style.display = "none";
        rectBack.style.display  = "none";
        $("save_bar").style.display = "block";
        $("rect_status").innerText = "Pick FRONT or BACK, then drag on the image.";
        setStatus("");
      });
  };

  // ---------- PICK rectangle ----------
  window.pickSide = function(name){
    pickSideName = name;
    setStatus("Drag on the image to mark the " + name.toUpperCase() + " crop.");
    [$("btn_pick_front"), $("btn_pick_back")].forEach(b => b.classList.remove("primary"));
    $("btn_pick_" + name).classList.add("primary");
  };

  function onMouseDown(ev){
    if(!pickSideName) return;
    const r = srcImg.getBoundingClientRect();
    dragStart = { x: ev.clientX - r.left, y: ev.clientY - r.top };
    const which = pickSideName === "front" ? rectFront : rectBack;
    Object.assign(which.style, {
      left: dragStart.x + "px", top: dragStart.y + "px",
      width: "0px", height: "0px", display: "block"
    });
    ev.preventDefault();
  }
  function onMouseMove(ev){
    if(!dragStart) return;
    const r = srcImg.getBoundingClientRect();
    const x = ev.clientX - r.left, y = ev.clientY - r.top;
    const which = pickSideName === "front" ? rectFront : rectBack;
    const x1 = Math.min(dragStart.x, x), y1 = Math.min(dragStart.y, y);
    const w = Math.abs(x - dragStart.x), h = Math.abs(y - dragStart.y);
    Object.assign(which.style, {
      left: x1 + "px", top: y1 + "px",
      width: w + "px", height: h + "px"
    });
  }
  function onMouseUp(){
    if(!dragStart) return;
    const which = pickSideName === "front" ? rectFront : rectBack;
    const css = which.getBoundingClientRect();
    const r   = srcImg.getBoundingClientRect();
    // map CSS pixels -> source-image pixels
    const sx = imgW / srcImg.clientWidth;
    const sy = imgH / srcImg.clientHeight;
    crops[pickSideName] = {
      x: Math.round((css.left - r.left) * sx),
      y: Math.round((css.top  - r.top)  * sy),
      w: Math.round(css.width  * sx),
      h: Math.round(css.height * sy)
    };
    $("rect_status").innerText =
      "FRONT " + (crops.front ? "OK " : "—") +
      "  BACK " + (crops.back ? "OK" : "—");
    dragStart = null;
  }
  srcImg.addEventListener("mousedown", onMouseDown);
  document.addEventListener("mousemove", onMouseMove);
  document.addEventListener("mouseup",   onMouseUp);

  // ---------- CROP ----------
  window.cropNow = function(){
    if(!uid){ setStatus("Load a file first.","err"); return; }
    if(!crops.front){ setStatus("Pick a FRONT rectangle first.","err"); return; }
    setStatus("Cropping…");
    fetch("/custom/process", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ uid, front: crops.front, back: crops.back })
    }).then(r => r.json()).then(d => {
      if(d.error){ setStatus(d.error,"err"); return; }
      backReady = !!d.back;
      backCanvas.parentElement.style.display = backReady ? "" : "none";
      load(frontCanvas, fctx, d.front, true);
      if(backReady) load(backCanvas, bctx, d.back, false);
      $("area").style.display = "block";
      setStatus("");
    });
  };

  function load(c, x, src, isFront){
    const img = new Image();
    img.onload = () => {
      c.width = img.width; c.height = img.height;
      x.drawImage(img, 0, 0);
      const data = x.getImageData(0, 0, c.width, c.height);
      if(isFront) originalFront = data; else originalBack = data;
      apply();
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
  function apply(){
    if(!originalFront) return;
    const gB = +$("g_black").value, gG = +$("g_gamma").value;
    $("g_black_v").innerText = gB;
    $("g_gamma_v").innerText = gG.toFixed(1);
    function applyTo(orig, ctx){
      const out = new ImageData(new Uint8ClampedArray(orig.data), orig.width);
      for(let i = 0; i < out.data.length; i += 4){
        for(let c = 0; c < 3; c++) out.data[i+c] = levels(orig.data[i+c], gB, gG);
      }
      ctx.putImageData(out, 0, 0);
    }
    applyTo(originalFront, fctx);
    if(backReady && originalBack) applyTo(originalBack, bctx);
  }
  document.querySelectorAll("#area input[type=range]").forEach(el => el.oninput = apply);

  // ---------- DOWNLOAD / PRINT ----------
  window.downloadFront = function(){
    if(!originalFront){ setStatus("Crop first.","err"); return; }
    window.downloadCanvas(frontCanvas, "custom_front.jpg");
  };
  window.downloadBack = function(){
    if(!backReady){ setStatus("No back.","err"); return; }
    window.downloadCanvas(backCanvas, "custom_back.jpg");
  };
  window.printA4 = function(){
    if(!originalFront){ setStatus("Crop first.","err"); return; }
    if(backReady) window.printDualA4(frontCanvas, backCanvas, { scale: cfg.print_scale });
    else          window.printSingleA4(frontCanvas, { scale: cfg.print_scale });
  };

  // ---------- PRESETS ----------
  window.applyPreset = function(name){
    if(!name) return;
    const p = PRESETS.find(x => x.name === name);
    if(!p) return;
    if(p.dpi)  $("dpi").value = p.dpi;
    if(p.front){ crops.front = p.front; }
    if(p.back) { crops.back  = p.back;  }
    if(p.levels){
      if(p.levels.g_black != null) $("g_black").value = p.levels.g_black;
      if(p.levels.g_gamma != null) $("g_gamma").value = p.levels.g_gamma;
    }
    $("preset_name").value = name;
    setStatus("Preset loaded. Hit Load file → Crop. (Re-pick rectangles if image differs.)", "ok");
  };

  window.savePreset = function(){
    const name = $("preset_name").value.trim();
    if(!name){ setStatus("Give the preset a name.","err"); return; }
    if(!crops.front){ setStatus("Pick at least a FRONT crop first.","err"); return; }
    const lv = { g_black:+$("g_black").value, g_gamma:+$("g_gamma").value };
    fetch("/custom/preset", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        name, dpi: +$("dpi").value,
        front: crops.front, back: crops.back, levels: lv
      })
    }).then(r => r.json()).then(d => {
      if(d.error){ setStatus(d.error,"err"); return; }
      setStatus("Preset saved. Reload to see it in the dropdown.","ok");
    });
  };

  window.deletePreset = function(){
    const name = $("preset_name").value.trim();
    if(!name) return;
    if(!confirm("Delete preset '"+name+"'?")) return;
    fetch("/custom/preset?name=" + encodeURIComponent(name), { method:"DELETE" })
      .then(r => r.json()).then(_ => {
        setStatus("Deleted. Reload page.","ok");
      });
  };

  // ---------- DEV API hookup ----------
  window.DEV_API = {
    canvases: { front: frontCanvas, back: backCanvas },
    getLevels(){
      return { g_black:+$("g_black").value, g_gamma:+$("g_gamma").value };
    }
  };
})();
