/* =====================================================================
   MANUEL — comportements d'écran
   Trois choses, et rien de plus : suivre la lecture dans le sommaire,
   filtrer le sommaire à la frappe, ouvrir l'impression avec les bons
   réglages. Aucune dépendance.
   ===================================================================== */

/* --- 1. Le sommaire suit la lecture --------------------------------
   IntersectionObserver plutôt qu'un écouteur de défilement : le navigateur
   fait le calcul lui-même, sans repeindre à chaque pixel parcouru.
   La marge basse (-70%) fait basculer l'entrée active quand le titre
   atteint le tiers haut de l'écran — là où l'œil lit — et non quand il
   effleure le bas. */
(function suivreLecture(){
  const liens = new Map();
  document.querySelectorAll('.som-lien').forEach((a) => {
    liens.set(a.getAttribute('href').slice(1), a);
  });
  const cibles = [...document.querySelectorAll('h1[id], h2[id]')];
  if (!cibles.length) return;

  let courant = null;
  const obs = new IntersectionObserver((entrees) => {
    for (const e of entrees) {
      if (!e.isIntersecting) continue;
      const a = liens.get(e.target.id);
      if (!a || a === courant) continue;
      courant?.classList.remove('actif');
      a.classList.add('actif');
      courant = a;
      // Garder l'entrée active visible dans un sommaire plus long que l'écran.
      a.scrollIntoView({ block: 'nearest' });
    }
  }, { rootMargin: '0px 0px -70% 0px', threshold: 0 });

  cibles.forEach((c) => obs.observe(c));
})();

/* --- 2. Filtrer le sommaire ----------------------------------------
   Un manuel de cette taille se consulte plus qu'il ne se lit : on cherche
   « SLA » ou « sauvegarde », pas le chapitre 5. Le filtre est accent- et
   casse-insensible — « échéance » se trouve en tapant « echeance ». */
(function filtrerSommaire(){
  const champ = document.getElementById('recherche-sommaire');
  if (!champ) return;
  const aplatir = (s) =>
    s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

  const entrees = [...document.querySelectorAll('.som-lien')].map((a) => ({
    el: a,
    texte: aplatir(a.textContent),
    n1: a.classList.contains('n1'),
  }));

  champ.addEventListener('input', () => {
    const q = aplatir(champ.value.trim());
    if (!q) { entrees.forEach((e) => { e.el.hidden = false; }); return; }
    // Un chapitre reste affiché si l'une de ses sections correspond :
    // sinon on verrait des sections orphelines, sans titre au-dessus.
    let chapitre = null;
    let chapitreVu = false;
    for (const e of entrees) {
      if (e.n1) {
        if (chapitre) chapitre.el.hidden = !chapitreVu;
        chapitre = e;
        chapitreVu = e.texte.includes(q);
        e.el.hidden = true;
        continue;
      }
      const ok = e.texte.includes(q) || (chapitre?.texte.includes(q) ?? false);
      e.el.hidden = !ok;
      if (ok) chapitreVu = true;
    }
    if (chapitre) chapitre.el.hidden = !chapitreVu;
  });

  // Échap vide le filtre sans quitter le champ.
  champ.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { champ.value = ''; champ.dispatchEvent(new Event('input')); }
  });
})();

/* --- 3. Impression / PDF -------------------------------------------
   Le manuel s'écoule sur des pages A4 ; c'est le moteur d'impression du
   navigateur qui pagine, avec la feuille @page du document. On rappelle
   donc les deux réglages qui, mal posés, abîment le rendu : des marges
   imposées par la boîte de dialogue écraseraient celles du document, et
   sans les graphiques d'arrière-plan les encadrés et pastilles
   ressortiraient blancs. */
document.getElementById('btn-imprimer')?.addEventListener('click', () => {
  alert(
    "Dans la fenêtre d'impression :\n\n" +
    "  • Destination → Enregistrer au format PDF\n" +
    "  • Marges → Par défaut (celles du document)\n" +
    "  • Graphiques d'arrière-plan → coché\n" +
    "  • Échelle → 100 %\n\n" +
    "Le sommaire cliquable de gauche est remplacé, sur papier, par un " +
    "sommaire imprimé placé après la couverture."
  );
  window.print();
});

/* --- 4. Ancres : copier le lien d'une section -----------------------
   Sur un manuel partagé, « va voir le 5.4 » est moins utile qu'un lien.
   Un clic sur un titre de section copie son adresse. */
document.querySelectorAll('h2[id]').forEach((h) => {
  h.style.cursor = 'pointer';
  h.title = 'Cliquer pour copier le lien de cette section';
  h.addEventListener('click', () => {
    const url = location.href.split('#')[0] + '#' + h.id;
    void navigator.clipboard?.writeText(url);
    const avant = h.style.color;
    h.style.color = 'var(--accent)';
    setTimeout(() => { h.style.color = avant; }, 450);
  });
});
