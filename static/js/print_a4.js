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
