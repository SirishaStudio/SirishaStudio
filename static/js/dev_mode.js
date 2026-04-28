/* Dev Mode — shared by dual + single tools.
 * Provides:
 *   - toggleDev()   : show/hide the dev panel
 *   - devReload()   : refresh saved overrides JSON dump
 *   - devReset()    : delete this tool's overrides
 *   - devSaveLevels(): save current slider values as defaults for this tool
 *   - devPick(which): drag a rectangle on a canvas to capture coords
 *   - devSavePhoto(): save the picked rectangle as photo_region for this tool
 *
 * Tools are responsible for exposing window.DEV_API = { canvases, getLevels }.
 */

window.DEV = (function(){
  const $ = id => document.getElementById(id);
  let lastPick = null;
  let pickActive = null;
  let pickOverlay = null;
  let startPx = null;

  function tool(){ return window.TOOL_CONFIG.tool_key; }

  window.toggleDev = function(){
    const p = $("dev_panel");
    const open = p.style.display === "none";
    p.style.display = open ? "block" : "none";
    if(open) devReload();
  };

  window.devReload = async function(){
    const r = await fetch("/dev/overrides/" + tool());
    const j = await r.json();
    $("dev_dump").innerText = JSON.stringify(j, null, 2);
  };

  window.devReset = async function(){
    if(!confirm("Delete saved overrides for this tool?")) return;
    await fetch("/dev/overrides/" + tool(), { method:"DELETE" });
    devReload();
    flash("Cleared. Refresh the page to see in-code defaults.");
  };

  window.devSaveLevels = async function(){
    if(!window.DEV_API || !window.DEV_API.getLevels){
      flash("Tool not ready."); return;
    }
    const lv = window.DEV_API.getLevels();
    await fetch("/dev/overrides/" + tool(), {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ levels: lv })
    });
    flash("Saved. New defaults: " + JSON.stringify(lv));
    devReload();
  };

  window.devPick = function(which){
    if(!window.DEV_API || !window.DEV_API.canvases){
      flash("Open a file first."); return;
    }
    const c = window.DEV_API.canvases[which];
    if(!c){ flash("Canvas '"+which+"' not found."); return; }
    pickActive = c;
    flash("Drag a rectangle on the " + which.toUpperCase() + " image…");

    // overlay div sits above the canvas to capture mouse
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
      rectDiv.style.left = startPx.x + "px";
      rectDiv.style.top  = startPx.y + "px";
      rectDiv.style.width = "0px";
      rectDiv.style.height = "0px";
      rectDiv.style.display = "block";
    };
    pickOverlay.onmousemove = ev => {
      if(!startPx) return;
      const r = pickOverlay.getBoundingClientRect();
      const x = ev.clientX - r.left, y = ev.clientY - r.top;
      const x1 = Math.min(startPx.x, x), y1 = Math.min(startPx.y, y);
      rectDiv.style.left = x1 + "px"; rectDiv.style.top = y1 + "px";
      rectDiv.style.width  = Math.abs(x - startPx.x) + "px";
      rectDiv.style.height = Math.abs(y - startPx.y) + "px";
    };
    pickOverlay.onmouseup = ev => {
      if(!startPx) return;
      const r = pickOverlay.getBoundingClientRect();
      const x = ev.clientX - r.left, y = ev.clientY - r.top;
      const cssX1 = Math.min(startPx.x, x);
      const cssY1 = Math.min(startPx.y, y);
      const cssW  = Math.abs(x - startPx.x);
      const cssH  = Math.abs(y - startPx.y);
      // map CSS pixels back to canvas pixels
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
    pickOverlay = null; startPx = null; pickActive = null;
  }

  window.devSavePhoto = async function(){
    if(!lastPick){ flash("Nothing picked yet."); return; }
    const patch = {
      photo_region: { x:lastPick.x, y:lastPick.y, w:lastPick.w, h:lastPick.h }
    };
    await fetch("/dev/overrides/" + tool(), {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(patch)
    });
    flash("Saved. Reload page to see new region applied.");
    devReload();
  };

  function flash(msg){
    const m = document.getElementById("dev_save_msg");
    if(m){ m.innerText = msg; setTimeout(() => { m.innerText = ""; }, 4000); }
    const s = document.getElementById("status");
    if(s){ s.innerText = msg; }
  }

  return { flash };
})();
