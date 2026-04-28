/* Dev Mode — shared by dual + single tools.
 *
 * NEW behaviour:
 *  - Always shows what's CURRENTLY persisted in overrides.json for this tool
 *  - Save buttons re-fetch the persisted state immediately so you can see the change
 *  - "Apply now" re-runs the level pipeline so saved defaults take effect without reload
 *  - Region picker stores both the picked rect and the canvas dims it was picked at
 */
window.DEV = (function(){
  const $ = id => document.getElementById(id);
  let lastPick = null;
  let pickOverlay = null;
  let startPx = null;

  function tool(){ return window.TOOL_CONFIG.tool_key; }

  // ------- panel show/hide -------
  window.toggleDev = function(){
    const p = $("dev_panel");
    const open = p.style.display === "none" || p.style.display === "";
    p.style.display = open ? "block" : "none";
    if(open) devReload();
  };

  // ------- read saved state -------
  window.devReload = async function(){
    try{
      const r = await fetch("/dev/overrides/" + tool());
      const j = await r.json();
      const empty = !j || Object.keys(j).length === 0;
      $("dev_dump").innerText = empty
        ? "(none — using built-in defaults from tools/" + tool() + ".py)"
        : JSON.stringify(j, null, 2);
      const badge = $("dev_status_badge");
      if(badge) badge.innerText = empty ? "no overrides" : "overrides ACTIVE";
      if(badge) badge.className = empty ? "dev-badge muted" : "dev-badge ok";
    } catch(e){
      $("dev_dump").innerText = "Failed to load: " + e;
    }
  };

  // ------- clear -------
  window.devReset = async function(){
    if(!confirm("Delete saved overrides for this tool?")) return;
    await fetch("/dev/overrides/" + tool(), { method:"DELETE" });
    flash("Cleared.");
    devReload();
  };

  // ------- save current sliders as default -------
  window.devSaveLevels = async function(){
    if(!window.DEV_API || !window.DEV_API.getLevels){
      flash("Tool not ready."); return;
    }
    const lv = window.DEV_API.getLevels();
    const r = await fetch("/dev/overrides/" + tool(), {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ levels: lv })
    });
    const j = await r.json();
    if(j.ok){
      flash("SAVED. New defaults will load every time.", "ok");
      devReload();
    } else {
      flash("Save failed.", "err");
    }
  };

  // ------- pick region -------
  window.devPick = function(which){
    if(!window.DEV_API || !window.DEV_API.canvases){
      flash("Open a file first."); return;
    }
    const c = window.DEV_API.canvases[which];
    if(!c){ flash("Canvas '"+which+"' not found."); return; }
    flash("Drag a rectangle on the " + which.toUpperCase() + " image…");

    pickOverlay = document.createElement("div");
    pickOverlay.className = "pick-overlay";
    const wrap = c.parentElement;
    wrap.style.position = "relative";
    pickOverlay.style.position = "absolute";
    pickOverlay.style.left = c.offsetLeft + "px";
    pickOverlay.style.top  = c.offsetTop + "px";
    pickOverlay.style.width  = c.clientWidth + "px";
    pickOverlay.style.height = c.clientHeight + "px";
    wrap.appendChild(pickOverlay);

    const rectDiv = document.createElement("div");
    rectDiv.className = "pick-rect";
    pickOverlay.appendChild(rectDiv);

    pickOverlay.onmousedown = ev => {
      const r = pickOverlay.getBoundingClientRect();
      startPx = { x: ev.clientX - r.left, y: ev.clientY - r.top };
      Object.assign(rectDiv.style, {
        left: startPx.x + "px", top: startPx.y + "px",
        width: "0px", height: "0px", display: "block"
      });
    };
    pickOverlay.onmousemove = ev => {
      if(!startPx) return;
      const r = pickOverlay.getBoundingClientRect();
      const x = ev.clientX - r.left, y = ev.clientY - r.top;
      const x1 = Math.min(startPx.x, x), y1 = Math.min(startPx.y, y);
      Object.assign(rectDiv.style, {
        left: x1 + "px", top: y1 + "px",
        width: Math.abs(x - startPx.x) + "px",
        height: Math.abs(y - startPx.y) + "px"
      });
    };
    pickOverlay.onmouseup = ev => {
      if(!startPx) return;
      const r = pickOverlay.getBoundingClientRect();
      const x = ev.clientX - r.left, y = ev.clientY - r.top;
      const cssX1 = Math.min(startPx.x, x);
      const cssY1 = Math.min(startPx.y, y);
      const cssW  = Math.abs(x - startPx.x);
      const cssH  = Math.abs(y - startPx.y);
      const sx = c.width  / c.clientWidth;
      const sy = c.height / c.clientHeight;
      lastPick = {
        x: Math.round(cssX1 * sx),
        y: Math.round(cssY1 * sy),
        w: Math.round(cssW * sx),
        h: Math.round(cssH * sy),
        canvas_w: c.width,
        canvas_h: c.height,
        which: which
      };
      $("dev_picked").innerText = JSON.stringify(lastPick, null, 2);
      cleanupPick();
    };
  };

  function cleanupPick(){
    if(pickOverlay && pickOverlay.parentElement){
      pickOverlay.parentElement.removeChild(pickOverlay);
    }
    pickOverlay = null; startPx = null;
  }

  // ------- save the picked rect as photo region -------
  window.devSavePhoto = async function(){
    if(!lastPick){ flash("Nothing picked yet."); return; }
    // Save in BOTH layouts so any of the per-tool files can read it:
    const rect = { x:lastPick.x, y:lastPick.y, w:lastPick.w, h:lastPick.h };
    const patch = {
      photo_region: rect,
      photo_region_72dpi: rect,
      front_canvas_72dpi: { w:lastPick.canvas_w, h:lastPick.canvas_h },
      photo_regions_72dpi: { main: rect },
    };
    const r = await fetch("/dev/overrides/" + tool(), {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(patch)
    });
    if((await r.json()).ok){
      flash("SAVED. Re-process the file to see the new region in action.", "ok");
      devReload();
    }
  };

  // ------- inline status banner -------
  function flash(msg, cls=""){
    const m = document.getElementById("dev_save_msg");
    if(m){
      m.innerText = msg;
      m.className = "dev-msg " + cls;
      setTimeout(() => { if(m.innerText === msg) m.innerText = ""; }, 5000);
    }
    const s = document.getElementById("status");
    if(s){ s.innerText = msg; s.className = cls; }
  }

  // Reload on first script load so the dev panel is correct if user opens it
  document.addEventListener("DOMContentLoaded", () => {
    if(document.getElementById("dev_dump")) devReload();
  });

  return { flash, devReload };
})();
