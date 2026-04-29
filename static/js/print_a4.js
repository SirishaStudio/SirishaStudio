/* Shared A4 print used by every tool.
 *
 * Card sizes match your offline batch printer exactly:
 *   - A4               210 x 297 mm
 *   - Card             85.6 x 53.98 mm  (CR80, identical to physical card)
 *   - Border            0.254 mm
 *   - Center gap        2.286 mm        (between front / back)
 *   - Top margin        5.08  mm
 *
 * Every layout is then multiplied by GLOBAL_DESCALE (97 %) per your spec, so
 * the printer never blows the cards a hair too big. Each tool can pass its own
 * `scale` (PAN uses 1.02, etc.) which combines with the global descale.
 */

window.GLOBAL_DESCALE = 0.97;

function _finalScale(toolScale){
  return (toolScale || 1.0) * window.GLOBAL_DESCALE;
}

window.printDualA4 = function(frontCanvas, backCanvas, opts){
  if(!frontCanvas || !backCanvas) return;
  opts = opts || {};
  const s = _finalScale(opts.scale);
  const cardW = (85.6  * s).toFixed(3);
  const cardH = (53.98 * s).toFixed(3);
  const gap   = (2.286 * s).toFixed(3);
  const top   = (5.08  * s).toFixed(3);

  const front = frontCanvas.toDataURL("image/jpeg", 0.95);
  const back  = backCanvas.toDataURL("image/jpeg",  0.95);

  const html = `
  <!doctype html><html><head><meta charset="utf-8"><title>Print</title>
  <style>
    @page { size: A4 portrait; margin: 0; }
    html, body { margin:0; padding:0; background:white; }
    .page { width:210mm; height:297mm; padding-top:${top}mm; }
    .pair { display:flex; justify-content:center; gap:${gap}mm; }
    img   { width:${cardW}mm; height:${cardH}mm;
            border:0.254mm solid black; display:block;
            image-rendering: -webkit-optimize-contrast; }
  </style></head><body>
    <div class="page">
      <div class="pair">
        <img src="${front}">
        <img src="${back}">
      </div>
    </div>
    <script>window.onload = () => setTimeout(() => window.print(), 250);<\/script>
  </body></html>`;
  _open(html);
};

window.printSingleA4 = function(canvas, opts){
  if(!canvas) return;
  opts = opts || {};
  const s = _finalScale(opts.scale);
  const url = canvas.toDataURL("image/jpeg", 0.95);
  const margin = 8;
  // Single image fills width; descale via max-width so it fits at s%.
  const widthPct = (s * 100).toFixed(2);
  const html = `
  <!doctype html><html><head><meta charset="utf-8"><title>Print</title>
  <style>
    @page { size: A4 portrait; margin: ${margin}mm; }
    html, body { margin:0; padding:0; background:white; }
    img { width:${widthPct}%; height:auto; display:block; margin:0 auto; }
  </style></head><body>
    <img src="${url}">
    <script>window.onload = () => setTimeout(() => window.print(), 250);<\/script>
  </body></html>`;
  _open(html);
};

/* RC corner mode: print a single card in the top-LEFT corner of A4 so RC and
 * DL printouts are visually distinguishable. */
window.printCornerA4 = function(canvas, opts){
  if(!canvas) return;
  opts = opts || {};
  const s = _finalScale(opts.scale);
  const cardW = (85.6  * s).toFixed(3);
  const cardH = (53.98 * s).toFixed(3);
  const url = canvas.toDataURL("image/jpeg", 0.95);
  const html = `
  <!doctype html><html><head><meta charset="utf-8"><title>Print</title>
  <style>
    @page { size: A4 portrait; margin: 0; }
    html, body { margin:0; padding:0; background:white; }
    .corner { position:absolute; top:5mm; left:5mm; }
    img { width:${cardW}mm; height:${cardH}mm;
          border:0.254mm solid black; display:block;
          image-rendering: -webkit-optimize-contrast; }
  </style></head><body>
    <div class="corner"><img src="${url}"></div>
    <script>window.onload = () => setTimeout(() => window.print(), 250);<\/script>
  </body></html>`;
  _open(html);
};

/* RC + back: two cards stacked in the LEFT column (top-left). */
window.printCornerDualA4 = function(frontCanvas, backCanvas, opts){
  if(!frontCanvas || !backCanvas) return;
  opts = opts || {};
  const s = _finalScale(opts.scale);
  const cardW = (85.6  * s).toFixed(3);
  const cardH = (53.98 * s).toFixed(3);
  const gap   = (2.286 * s).toFixed(3);
  const front = frontCanvas.toDataURL("image/jpeg", 0.95);
  const back  = backCanvas.toDataURL("image/jpeg",  0.95);
  const html = `
  <!doctype html><html><head><meta charset="utf-8"><title>Print</title>
  <style>
    @page { size: A4 portrait; margin: 0; }
    html, body { margin:0; padding:0; background:white; }
    .col { position:absolute; top:5mm; left:5mm;
           display:flex; flex-direction:column; gap:${gap}mm; }
    img { width:${cardW}mm; height:${cardH}mm;
          border:0.254mm solid black; display:block;
          image-rendering: -webkit-optimize-contrast; }
  </style></head><body>
    <div class="col">
      <img src="${front}">
      <img src="${back}">
    </div>
    <script>window.onload = () => setTimeout(() => window.print(), 250);<\/script>
  </body></html>`;
  _open(html);
};

function _open(html){
  const w = window.open("");
  w.document.write(html);
  w.document.close();
}

/* ---------------- PRINT TRAY (multi-card batch) ----------------
 *
 * Cards are queued in sessionStorage as JPEG dataURLs so the user can
 * stack any mix of card types (e.g. 3 PAN + 1 Voter) and print them all
 * onto as many A4 sheets as needed from /tray.
 *
 * Each tray entry:
 *   { id, ts, label, scale, front, back?  }
 *   - label   : "PAN", "Voter ID", …
 *   - scale   : per-tool print scale (PAN 1.02, others 1.0)
 *   - front   : data URL JPEG
 *   - back    : data URL JPEG (omitted for single-side tools)
 *
 * Quality stays at 0.95 to match printDualA4 / printSingleA4.
 */

window.TRAY_KEY = "sirisha_print_tray_v1";

window.trayLoad = function(){
  try { return JSON.parse(sessionStorage.getItem(window.TRAY_KEY) || "[]"); }
  catch(e){ return []; }
};

window.traySave = function(list){
  sessionStorage.setItem(window.TRAY_KEY, JSON.stringify(list));
  window.trayBadgeRefresh();
};

window.trayCount = function(){ return window.trayLoad().length; };

window.trayAdd = function(label, scale, frontCanvas, backCanvas){
  if(!frontCanvas) return false;
  const list = window.trayLoad();
  const entry = {
    id:    "c_" + Date.now() + "_" + Math.floor(Math.random()*1000),
    ts:    Date.now(),
    label: label || "Card",
    scale: scale || 1.0,
    front: frontCanvas.toDataURL("image/jpeg", 0.95),
    back:  backCanvas ? backCanvas.toDataURL("image/jpeg", 0.95) : null,
  };
  list.push(entry);
  try { window.traySave(list); }
  catch(e){
    alert("Tray is full — too many cards stored in this browser session.\n" +
          "Print or clear the tray and try again.");
    return false;
  }
  return true;
};

window.trayRemove = function(id){
  window.traySave(window.trayLoad().filter(x => x.id !== id));
};

window.trayClear = function(){
  sessionStorage.removeItem(window.TRAY_KEY);
  window.trayBadgeRefresh();
};

/* Refresh any "Tray (N)" badges on the current page. */
window.trayBadgeRefresh = function(){
  const n = window.trayCount();
  document.querySelectorAll("[data-tray-badge]").forEach(el => {
    el.innerText = n > 0 ? ("Tray (" + n + ")") : "Tray";
  });
};
if(typeof document !== "undefined"){
  document.addEventListener("DOMContentLoaded", () => window.trayBadgeRefresh());
}

/* Lay out an arbitrary tray on as many A4 pages as needed.
 *
 * Layout:
 *   - 1 card per row = front + back side by side (or front alone)
 *   - All cards drawn at their own per-card scale
 *   - 4 rows per A4 page (53.98 mm * 4 + gaps + 5 mm top ≈ 228 mm < 297 mm)
 *   - More than 4 cards → page-break and continue
 */
window.printTrayA4 = function(tray){
  if(!tray || !tray.length) return;
  const ROWS_PER_PAGE = 4;
  const GAP_MM   = 2.286;
  const TOP_MM   = 5.08;
  const ROW_GAP  = 4.0;   // gap BETWEEN rows on the same page

  // Build pages
  const pages = [];
  for(let i = 0; i < tray.length; i += ROWS_PER_PAGE){
    pages.push(tray.slice(i, i + ROWS_PER_PAGE));
  }

  const pageHTML = pages.map((cards, pIdx) => {
    const rows = cards.map(c => {
      const s     = (c.scale || 1.0) * window.GLOBAL_DESCALE;
      const cardW = (85.6  * s).toFixed(3);
      const cardH = (53.98 * s).toFixed(3);
      const gap   = (GAP_MM * s).toFixed(3);
      const imgs  = c.back
        ? `<img src="${c.front}" style="width:${cardW}mm;height:${cardH}mm">
           <img src="${c.back}"  style="width:${cardW}mm;height:${cardH}mm">`
        : `<img src="${c.front}" style="width:${cardW}mm;height:${cardH}mm">`;
      return `<div class="row" style="display:flex;justify-content:center;gap:${gap}mm;margin-bottom:${ROW_GAP}mm">${imgs}</div>`;
    }).join("");
    const brk = (pIdx < pages.length - 1) ? "page-break-after:always;" : "";
    return `<div class="page" style="${brk}width:210mm;height:297mm;padding-top:${TOP_MM}mm;box-sizing:border-box">${rows}</div>`;
  }).join("");

  const html = `
  <!doctype html><html><head><meta charset="utf-8"><title>Print Tray</title>
  <style>
    @page { size: A4 portrait; margin: 0; }
    html, body { margin:0; padding:0; background:white; }
    img { border:0.254mm solid black; display:block;
          image-rendering: -webkit-optimize-contrast; }
  </style></head><body>
    ${pageHTML}
    <script>window.onload = () => setTimeout(() => window.print(), 250);<\/script>
  </body></html>`;
  _open(html);
};

/* ---------------- DOWNLOAD HELPERS ---------------- */

window.downloadCanvas = function(canvas, filename){
  if(!canvas) return;
  // High-quality JPG so it can be reused for prints / batch.
  canvas.toBlob((blob) => {
    if(!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "image.jpg";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 0);
  }, "image/jpeg", 0.97);
};
