/* =====================================================================
   WHITE-LABEL (C-9) — bascule unique. À true, aucune mention de la maison
   d'édition n'apparaît (dossier présentable tel quel, sous n'importe quelle
   marque). À false, un discret crédit d'édition s'affiche en 4e de couv.
   ===================================================================== */
const WHITE_LABEL = true;
(function credit(){
  const el = document.querySelector('[data-credit]');
  if (el) el.textContent = WHITE_LABEL ? '' : 'Édité par Yumi';
})();

/* --- Pagination : numéros à deux chiffres, jamais sur les pages sombres. */
(function paginate(){
  let n = 0;
  document.querySelectorAll('.page').forEach(pg=>{
    const num = pg.querySelector('.foot .num');
    n++;
    if (num) num.textContent = String(n).padStart(2,'0');
  });
})();

/* =====================================================================
   Emplacements de capture (F-3). onload AVANT src pour lire le ratio réel.
   ===================================================================== */
document.querySelectorAll('.photo input[type=file]').forEach(input=>{
  input.addEventListener('change', ()=>{
    const file = input.files && input.files[0];
    if (!file) return;
    const label = input.closest('.photo');
    const img   = label.querySelector('img');
    const cap   = label.closest('.shot').querySelector('.shot-cap');
    const reader = new FileReader();
    reader.onload = ()=>{
      const probe = new Image();
      probe.onload = ()=>{                       // onload AVANT d'assigner src
        label.style.setProperty('--ratio', probe.naturalWidth + ' / ' + probe.naturalHeight);
        img.src = reader.result;                 // rien ne quitte le poste
        label.classList.add('est-remplie');
        if (cap) cap.textContent = label.getAttribute('data-cap') || '';
      };
      probe.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
});

/* --- Repli impression (F-6). */
document.getElementById('btnPrint').addEventListener('click', ()=>{
  alert("Dans la fenêtre d'impression :\n\n• Marges → Aucune\n• Graphiques d'arrière-plan → coché\n• Échelle → 100 %\n\nPuis « Enregistrer au format PDF ».");
  window.print();
});

/* =====================================================================
   EXPORT PDF FIDÈLE (F-5) — pourquoi tout ce cirque :
   La boîte de dialogue d'impression impose SES marges et SON échelle, qui
   priment sur la feuille de style. Pour un PDF au pixel près, on rend
   nous-mêmes chaque page : HTML → <svg><foreignObject> → <canvas> (2,5×) →
   JPEG → PDF A4 écrit à la main, une image plein cadre par feuille.

   PIÈGES (chèrement appris) :
   • L'adresse du SVG doit être data:  — jamais blob: : ouvert en file://,
     un blob: « teinte » le canvas (tainted) et bloque toDataURL().
   • Le CSS doit voyager DANS le SVG (<style> en <![CDATA[…]]>) : le
     foreignObject est un document isolé, il n'hérite pas de la feuille du
     document hôte.
   • Les images des captures sont déjà en data: (FileReader) → aucune
     ressource externe, le canvas reste propre.
   ===================================================================== */
const prog = document.getElementById('prog');
function showProg(t){ prog.style.display='inline-block'; prog.textContent=t; }
function hideProg(){ prog.style.display='none'; }

function collectCss(){
  let css = '';
  document.querySelectorAll('style').forEach(s=> css += s.textContent + '\n');
  return css;
}

/* Une page → canvas via foreignObject. On clone, on retire les cadres restés
   vides (un dossier ne montre jamais un emplacement en attente), on sérialise
   en XHTML, on embarque le CSS, on passe par une URL data:. */
function pageToCanvas(page, scale){
  return new Promise((resolve, reject)=>{
    const W = page.offsetWidth, H = page.offsetHeight;
    const clone = page.cloneNode(true);
    clone.setAttribute('xmlns','http://www.w3.org/1999/xhtml');
    clone.style.margin = '0';
    clone.style.transform = 'none';
    // F-3 : les emplacements vides disparaissent à l'export.
    clone.querySelectorAll('.photo:not(.est-remplie)').forEach(p=>{
      const fig = p.closest('.shot'); (fig || p).remove();
    });
    const xhtml = new XMLSerializer().serializeToString(clone);
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="'+W+'" height="'+H+'">'+
        '<defs><style type="text/css"><![CDATA['+ collectCss() +']]></style></defs>'+
        '<foreignObject x="0" y="0" width="'+W+'" height="'+H+'">'+ xhtml +'</foreignObject>'+
      '</svg>';
    const url = 'data:image/svg+xml;charset=utf-8,'+ encodeURIComponent(svg);
    const img = new Image();
    img.onload = ()=>{
      const canvas = document.createElement('canvas');
      canvas.width  = Math.round(W*scale);
      canvas.height = Math.round(H*scale);
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';                 // fond blanc (pas de transparence)
      ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.setTransform(scale,0,0,scale,0,0);
      ctx.drawImage(img,0,0);
      resolve(canvas);
    };
    img.onerror = ()=> reject(new Error('Rendu SVG impossible (foreignObject).'));
    img.src = url;
  });
}

/* Base64 (data-URL JPEG) → octets bruts. */
function b64ToBytes(b64){
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i=0;i<bin.length;i++) out[i] = bin.charCodeAt(i);
  return out;
}

/* PDF A4 écrit à la main : 1 image JPEG plein cadre par page (DCTDecode).
   On suit les offsets d'octets pour la table xref. */
function buildPdf(pagesJpeg){                 // [{bytes:Uint8Array, w, h}]
  const A4W = 595.28, A4H = 841.89;           // A4 en points
  const enc = new TextEncoder();
  const chunks = []; let offset = 0; const xref = [];
  const push = (bytes)=>{ chunks.push(bytes); offset += bytes.length; };
  const put  = (s)=> push(enc.encode(s));
  const obj  = (id)=>{ xref[id] = offset; put(id+' 0 obj\n'); };
  const end  = ()=> put('endobj\n');

  put('%PDF-1.4\n');
  push(new Uint8Array([0x25,0xE2,0xE3,0xCF,0xD3,0x0A]));   // marqueur binaire

  const n = pagesJpeg.length;
  const kids = [];
  for (let i=0;i<n;i++) kids.push((3+i*3)+' 0 R');

  obj(1); put('<< /Type /Catalog /Pages 2 0 R >>\n'); end();
  obj(2); put('<< /Type /Pages /Count '+n+' /Kids ['+kids.join(' ')+'] >>\n'); end();

  for (let i=0;i<n;i++){
    const pageId=3+i*3, contentId=4+i*3, imgId=5+i*3;
    const content = 'q '+A4W+' 0 0 '+A4H+' 0 0 cm /Im'+i+' Do Q';
    obj(pageId);
    put('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 '+A4W+' '+A4H+']'+
        ' /Resources << /XObject << /Im'+i+' '+imgId+' 0 R >> >>'+
        ' /Contents '+contentId+' 0 R >>\n');
    end();
    obj(contentId);
    put('<< /Length '+content.length+' >>\nstream\n'+content+'\nendstream\n');
    end();
    const im = pagesJpeg[i];
    obj(imgId);
    put('<< /Type /XObject /Subtype /Image /Width '+im.w+' /Height '+im.h+
        ' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length '+im.bytes.length+' >>\nstream\n');
    push(im.bytes);
    put('\nendstream\n');
    end();
  }

  const startxref = offset;
  const total = 2 + n*3;
  let xr = 'xref\n0 '+(total+1)+'\n0000000000 65535 f \n';
  for (let id=1; id<=total; id++) xr += String(xref[id]||0).padStart(10,'0')+' 00000 n \n';
  put(xr);
  put('trailer\n<< /Size '+(total+1)+' /Root 1 0 R >>\nstartxref\n'+startxref+'\n%%EOF');

  const size = chunks.reduce((a,c)=>a+c.length,0);
  const buf = new Uint8Array(size);
  let p=0; for (const c of chunks){ buf.set(c,p); p+=c.length; }
  return new Blob([buf], {type:'application/pdf'});
}

document.getElementById('btnPdf').addEventListener('click', async ()=>{
  const btn = document.getElementById('btnPdf');
  btn.disabled = true;
  document.body.classList.add('mode-export');   // fige le format A4 (F-5)
  try{
    const pages = Array.from(document.querySelectorAll('.page'));
    const out = [];
    for (let i=0;i<pages.length;i++){
      showProg('Rendu page '+(i+1)+' / '+pages.length+'…');
      const canvas = await pageToCanvas(pages[i], 2.5);
      const jpeg = canvas.toDataURL('image/jpeg', 0.92).split(',')[1];
      out.push({ bytes:b64ToBytes(jpeg), w:canvas.width, h:canvas.height });
    }
    showProg('Assemblage du PDF…');
    const blob = buildPdf(out);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '__NOM_FICHIER__';
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 4000);
    showProg('PDF prêt ✓'); setTimeout(hideProg, 2500);
  }catch(e){
    hideProg();
    alert("Export PDF impossible :\n\n"+ (e && e.message ? e.message : e) +
          "\n\nRepli : bouton « Imprimer » → Enregistrer au format PDF.");
  }finally{
    document.body.classList.remove('mode-export');
    btn.disabled = false;
  }
});