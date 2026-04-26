/* Shared A4 print used by every tool.
 *
 * Card sizes match the offline batch printer exactly:
 *   - A4               210 x 297 mm
 *   - Card             85.6 x 53.98 mm  (CR80, identical to physical card)
 *   - Border            0.254 mm        (= 7 px @ 700 DPI)
 *   - Center gap        2.286 mm        (= 63 px @ 700 DPI, between front/back)
 *   - Top margin        5.08  mm        (= 140 px @ 700 DPI)
 */

window.printDualA4 = function(frontCanvas, backCanvas){
  if(!frontCanvas || !backCanvas) return;
  const front = frontCanvas.toDataURL("image/jpeg", 0.95);
  const back  = backCanvas.toDataURL("image/jpeg",  0.95);

  const html = `
  <!doctype html><html><head><meta charset="utf-8"><title>Print</title>
  <style>
    @page { size: A4 portrait; margin: 0; }
    html, body { margin:0; padding:0; background:white; }
    .page { width:210mm; height:297mm; padding-top:5.08mm; }
    .pair { display:flex; justify-content:center; gap:2.286mm; }
    img   { width:85.6mm; height:53.98mm;
            border:0.254mm solid black; display:block; }
  </style></head><body>
    <div class="page">
      <div class="pair">
        <img src="${front}">
        <img src="${back}">
      </div>
    </div>
    <script>window.onload = () => setTimeout(() => window.print(), 200);<\/script>
  </body></html>`;

  const w = window.open("");
  w.document.write(html);
  w.document.close();
};

window.printSingleA4 = function(canvas){
  if(!canvas) return;
  const url = canvas.toDataURL("image/jpeg", 0.95);
  const html = `
  <!doctype html><html><head><meta charset="utf-8"><title>Print</title>
  <style>
    @page { size: A4 portrait; margin: 8mm; }
    html, body { margin:0; padding:0; background:white; }
    img { width:100%; height:auto; display:block; }
  </style></head><body>
    <img src="${url}">
    <script>window.onload = () => setTimeout(() => window.print(), 200);<\/script>
  </body></html>`;
  const w = window.open("");
  w.document.write(html);
  w.document.close();
};
