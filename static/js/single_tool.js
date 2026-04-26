/* Single-image tool runtime — used by Long Aadhar.
 * Reads window.TOOL_CONFIG injected by the template.
 */

(function(){
  const cfg = window.TOOL_CONFIG;

  const canvas = document.getElementById("img");
  const ctx = canvas.getContext("2d");

  let original = null;
  let history   = [];
  let redoStack = [];

  const PHOTO = cfg.photo_region || null;

  const $ = (id) => document.getElementById(id);

  function setStatus(msg, cls=""){
    const el = $("status");
    el.innerText = msg;
    el.className = cls;
  }

  function showSignature(info){
    const box = $("sig");
    if(!info){ box.innerHTML = ""; return; }
    if(info.error){
      box.innerHTML = `<span class="sig-badge"><span class="dot"></span>Signature check unavailable</span>`;
      return;
    }
    if(!info.signed){
      box.innerHTML = `<span class="sig-badge bad"><span class="dot"></span>Not digitally signed</span>`;
      return;
    }
    const cls = info.intact === true ? "ok" : (info.intact === false ? "bad" : "");
    const label = info.intact === true ? "Signature intact"
                : info.intact === false ? "Signature broken"
                : "Signed";
    const signer = info.signer ? ` <span class="signer">· ${info.signer}</span>` : "";
    box.innerHTML = `<span class="sig-badge ${cls}"><span class="dot"></span>${label}${signer}</span>`;
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
    showSignature(null);

    fetch(cfg.process_url, { method:"POST", body:fd })
      .then(r => r.json())
      .then(d => {
        if(d.ask_password){ setStatus("Wrong / missing PDF password.", "err"); return; }
        if(d.error){ setStatus(d.error, "err"); return; }

        setStatus("");
        showSignature(d.signature);
        history = []; redoStack = [];
        original = null;

        load(d.image);
        $("area").style.display = "block";
      })
      .catch(e => setStatus("Error: " + e, "err"));
  };

  function load(src){
    const img = new Image();
    img.onload = () => {
      canvas.width  = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      original = ctx.getImageData(0, 0, canvas.width, canvas.height);
      apply(true);
    };
    img.src = src;
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

  window.printA4 = function(){
    if(!original){ setStatus("Process a file first.", "err"); return; }
    window.printSingleA4(canvas);
  };

  document.querySelectorAll("input[type=range]").forEach(el => {
    el.oninput = () => apply();
  });
})();
