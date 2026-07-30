#!/usr/bin/env node
/**
 * ─────────────────────────────────────────────────────────────────────────
 *  Générateur du MANUEL — un fichier HTML autonome, imprimable en A4
 * ─────────────────────────────────────────────────────────────────────────
 *
 *  Le manuel produit est AUTONOME : styles et comportements sont inline,
 *  aucune ressource distante. Il s'ouvre hors ligne, se transmet par mail
 *  tel quel, et s'enregistre en PDF depuis le navigateur.
 *
 *  POURQUOI UN GÉNÉRATEUR plutôt qu'un gros fichier HTML écrit à la main :
 *   1. Le sommaire — écran ET papier — se déduit des chapitres. Écrit à la
 *      main, il diverge du contenu dès la première section déplacée.
 *   2. La numérotation (chapitre, section) est calculée. Insérer une
 *      section au milieu ne demande pas de renuméroter les suivantes.
 *   3. L'identité (nom du produit, organisation, accent) est un paramètre :
 *      le même manuel se décline pour un autre déploiement en changeant
 *      `identite.mjs`, sans toucher au texte.
 *
 *  Usage :  node docs/manuel/build.mjs
 */
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { IDENTITE } from './identite.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const MOTEUR = join(ICI, '_moteur');

const echap = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** Identifiant d'ancre stable : « 5.4 » → `s-5-4`. Il ne dépend PAS du
 *  libellé — renommer une section ne casse donc pas les liens partagés. */
const ancre = (...n) => `s-${n.join('-')}`;

// ── Chargement des chapitres ────────────────────────────────────────────
// Un fichier par chapitre, préfixé par son rang (`01-…`, `02-…`) : l'ordre
// de lecture est celui du disque, visible d'un `ls`, sans index à tenir.

const fichiers = readdirSync(join(ICI, 'contenu'))
  .filter((f) => f.endsWith('.mjs'))
  .sort();

const chapitres = [];
for (const f of fichiers) {
  const mod = await import(`file://${join(ICI, 'contenu', f)}`);
  const ch = mod.chapitre;
  if (!ch) throw new Error(`${f} n'exporte pas \`chapitre\``);
  chapitres.push(ch);
}

// Numérotation : les annexes sont lettrées (A, B, C…), les chapitres
// chiffrés. Deux séries distinctes, comme dans tout ouvrage de référence.
let nChapitre = 0;
let nAnnexe = 0;
for (const ch of chapitres) {
  ch.rang = ch.annexe
    ? String.fromCharCode(65 + nAnnexe++)
    : String(++nChapitre);
  ch.sections.forEach((s, i) => { s.rang = `${ch.rang}.${i + 1}`; });
}

// ── Rendu ───────────────────────────────────────────────────────────────

const rendreChapitre = (ch) => {
  const idCh = ancre(ch.rang);
  return `<section class="chapitre">
  <div class="chapitre-num">${echap(ch.annexe ? `Annexe ${ch.rang}` : `Chapitre ${ch.rang}`)}</div>
  <h1 id="${idCh}">${echap(ch.titre)}</h1>
  ${ch.intro ? `<p class="chapitre-intro">${ch.intro}</p>` : ''}
${ch.sections.map((s) => `
  <h2 id="${ancre(...s.rang.split('.'))}">${echap(s.rang)} &nbsp;${echap(s.titre)}</h2>
${s.corps.trim()}
`).join('\n')}
</section>`;
};

/** Sommaire de gauche (écran) — chapitres et sections, filtrables. */
const sommaireEcran = chapitres.map((ch) => {
  const lignes = [
    `<a class="som-lien n1" href="#${ancre(ch.rang)}"><span class="num">${echap(ch.rang)}</span><span>${echap(ch.titre)}</span></a>`,
    ...ch.sections.map((s) =>
      `<a class="som-lien n2" href="#${ancre(...s.rang.split('.'))}"><span class="num">${echap(s.rang)}</span><span>${echap(s.titre)}</span></a>`),
  ];
  return lignes.join('\n');
}).join('\n');

/** Sommaire imprimé — placé après la couverture, invisible à l'écran. */
const sommairePapier = chapitres.map((ch) => {
  const lignes = [
    `<div class="ligne"><span class="num">${echap(ch.rang)}</span><span>${echap(ch.titre)}</span></div>`,
    ...ch.sections.map((s) =>
      `<div class="ligne n2"><span class="num">${echap(s.rang)}</span><span>${echap(s.titre)}</span></div>`),
  ];
  return lignes.join('\n');
}).join('\n');

// ── Assemblage ──────────────────────────────────────────────────────────

let css = readFileSync(join(MOTEUR, 'manuel.css'), 'utf8');
for (const [clef, valeur] of Object.entries({
  __ACCENT__: IDENTITE.accent,
  __ACCENT_SOFT__: IDENTITE.accentDoux,
  __SECONDAIRE__: IDENTITE.secondaire,
})) css = css.split(clef).join(valeur);

// Un paramètre oublié, c'est une couleur cassée dans le PDF final : on
// échoue ici, bruyamment, plutôt que de livrer un document abîmé.
const restants = [...new Set([...css.matchAll(/__[A-Z_]+__/g)].map((m) => m[0]))];
if (restants.length) throw new Error(`Paramètres non résolus : ${restants.join(', ')}`);

const js = readFileSync(join(MOTEUR, 'manuel.js'), 'utf8');

const html = `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${echap(IDENTITE.produit)} — ${echap(IDENTITE.titreManuel)}</title>
<style>
${css}
</style>
</head>
<body>

<aside class="sommaire" aria-label="Sommaire">
  <div class="sommaire-tete">
    <div class="sommaire-produit">${echap(IDENTITE.produit)}</div>
    <div class="sommaire-sous">${echap(IDENTITE.titreManuel)} · version ${echap(IDENTITE.version)}</div>
  </div>
  <div class="sommaire-recherche">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <input id="recherche-sommaire" type="search" placeholder="Chercher dans le manuel…"
           autocomplete="off" aria-label="Filtrer le sommaire">
  </div>
  <nav class="sommaire-nav">
${sommaireEcran}
  </nav>
</aside>

<main class="doc">
  <div class="feuille">

    <header class="couverture">
      <div class="couv-marque">${echap(IDENTITE.produit)}</div>
      <h1 class="couv-titre">${IDENTITE.titreCouverture}</h1>
      <p class="couv-sous">${IDENTITE.sousTitre}</p>
      <div class="couv-meta">
        <div><b>Document</b>${echap(IDENTITE.titreManuel)}</div>
        <div><b>Version</b>${echap(IDENTITE.version)}</div>
        <div><b>Édition</b>${echap(IDENTITE.edition)}</div>
        <div><b>Diffusion</b>${echap(IDENTITE.diffusion)}</div>
      </div>
    </header>

    <section id="sommaire-imprime">
      <h1>Sommaire</h1>
${sommairePapier}
    </section>

${chapitres.map(rendreChapitre).join('\n\n')}

  </div>
</main>

<div class="barre">
  <button type="button" class="clair" id="btn-imprimer">Enregistrer en PDF</button>
</div>

<script>
${js}
</script>
</body>
</html>
`;

const sortie = resolve(ICI, '..', IDENTITE.fichier);
writeFileSync(sortie, html, 'utf8');

const nbSections = chapitres.reduce((n, c) => n + c.sections.length, 0);
console.log(
  `✓ ${IDENTITE.fichier}  ·  ${chapitres.length} chapitres · ${nbSections} sections · ` +
  `${(html.length / 1024).toFixed(0)} Ko`
);
