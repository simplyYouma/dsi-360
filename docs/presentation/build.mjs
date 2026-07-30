#!/usr/bin/env node
/**
 * ─────────────────────────────────────────────────────────────────────────
 *  Générateur du DOSSIER DE PRÉSENTATION (magazine de marque → PDF A4)
 * ─────────────────────────────────────────────────────────────────────────
 *
 *  Un dossier par POS. Chaque fichier produit est AUTONOME : CSS et JS
 *  inline, logos en data-URI, aucune ressource distante — il s'ouvre hors
 *  ligne et s'envoie par mail tel quel.
 *
 *  POURQUOI un générateur plutôt que cinq fichiers écrits à la main :
 *  le moteur (géométrie A4, export PDF, pièges d'impression) est identique
 *  pour tous. Le dupliquer cinq fois, c'est cinq endroits où corriger le
 *  même bug d'impression. Ici : un moteur, cinq contenus, cinq identités.
 *
 *  Chaque dossier porte les COULEURS et le LOGO de son propre POS, repris
 *  des tokens de l'application — pas une charte inventée pour l'occasion.
 *
 *  Usage :  node docs/presentation/build.mjs
 */
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { decodePng, detourer, recadrer, repeindre, estMonochrome, versDataUri } from "./_moteur/logo.mjs";
import { preparerImage, rasteriser } from "./_moteur/image.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ENGINE = join(HERE, "_moteur");
const RACINE = resolve(HERE, "..", "..");   // racine du dépôt

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
/** Le texte de contenu accepte <br>, <span class="accent">…</span> et <b>. */
const rich = (s) => String(s);

/** "#RRGGBB" → "r,g,b", pour les rgba() des voiles et du store. */
const versRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(",");

// ── Logos ───────────────────────────────────────────────────────────────

/**
 * Prépare les deux versions du logo (fond clair / fond sombre) + son ratio.
 *
 * Les fichiers d'origine ne sont pas homogènes : YUMIAM et BOUTIKII sont
 * noirs sur un fond blanc opaque, The Tailor est blanc sur transparent,
 * GlowUp est en couleur. On détoure, on recadre sur la marque (les fichiers
 * ont 25 à 40 % de vide autour, qui rapetissait le logo d'autant), puis :
 *   • logo monochrome → repeint à l'encre du POS sur clair, en blanc sur
 *     sombre : la marque reste lisible sur les deux rythmes de page ;
 *   • logo en couleur → gardé tel quel, on ne repeint pas une identité.
 * Un `.svg` est pris tel quel : c'est déjà un fichier propre et léger.
 */
async function preparerLogo(deck) {
    const chemin = resolve(RACINE, deck.logoFile);
    // Un SVG d'export vectoriel pèse ici 570 Ko de chemins : rasterisé à la
    // taille réellement affichée, il tombe à quelques dizaines de kilo-octets
    // et rejoint le même traitement que les autres logos.
    const source = chemin.endsWith(".svg")
        ? await rasteriser(chemin)
        : chemin;

    const net = recadrer(detourer(decodePng(source)));
    const ratio = +(net.width / net.height).toFixed(3);
    if (estMonochrome(net)) {
        return {
            clair: versDataUri(repeindre(net, deck.palette.ink)),
            sombre: versDataUri(repeindre(net, "#FFFFFF")),
            ratio,
        };
    }
    // Logo en couleur : mêmes couleurs des deux côtés. Si sa lisibilité sur
    // fond sombre est douteuse, le contenu déclare logoFileSombre.
    const uri = versDataUri(net);
    const sombre = deck.logoFileSombre
        ? versDataUri(recadrer(detourer(decodePng(
            deck.logoFileSombre.endsWith(".svg")
                ? await rasteriser(resolve(RACINE, deck.logoFileSombre))
                : resolve(RACINE, deck.logoFileSombre)))))
        : uri;
    return { clair: uri, sombre, ratio };
}

/** Hauteurs du logo, plafonnées en largeur : un logotype 5:1 et un emblème
 *  1:1 doivent avoir la même présence sans réglage à la main. */
const hauteurs = (ratio) => ({
    grand: `${Math.min(34, 148 / ratio).toFixed(1)}mm`,
    petit: `${Math.min(12, 46 / ratio).toFixed(1)}mm`,
});

// ── Composants de page ──────────────────────────────────────────────────
// Une fonction par INTENTION de page. La forme impose la doctrine : une
// idée par page, pas de page fourre-tout.

const foot = (nom) =>
    `  <div class="spacer"></div>\n  <div class="foot"><span>${esc(nom)} — Dossier de présentation</span><span class="num"></span></div>`;

/** Emplacement de capture : vide, il DISPARAÎT à l'export (cf. deck.js). */
const shot = (label, large = true) => `  <figure class="shot">
    <label class="photo${large ? " photo--large" : ""}" data-cap="${esc(label)}">
      <input type="file" accept="image/*" hidden>
      <span class="hint"><b>+</b> ${esc(label)}</span>
      <img alt="">
    </label>
    <figcaption class="shot-cap"></figcaption>
  </figure>`;

/**
 * Le STORE des couvertures à sujet détouré.
 *
 * Écrit ici, arrêt par arrêt, plutôt qu'en CSS : il faut une lamelle par
 * niveau d'opacité, et une opacité qui décroît sur toute la hauteur. Un
 * `repeating-linear-gradient` ne sait pas faire varier sa couleur d'une
 * répétition à l'autre, et un `mask-image` ne survit pas de façon fiable au
 * clonage dans le foreignObject de l'export PDF. Une longue suite de stops,
 * elle, se rasterise partout à l'identique.
 *
 * @param hauteur  hauteur du store, en mm
 * @param lamelles nombre de lattes
 * @param alphaMax opacité de la latte la plus basse (juste sur la coupure)
 */
const STORE = { avant: 52, apres: 30, lamelles: 30, alphaMax: 0.34 };

function store(ink) {
    const hauteur = STORE.avant + STORE.apres;
    const pas = hauteur / STORE.lamelles;
    const trait = Math.min(0.5, pas * 0.28); // la latte reste fine : c'est un store, pas des rayures
    // Le store est le plus marqué exactement sur la ligne de coupure, et
    // s'efface des deux côtés : vers le haut il se dissout dans la page,
    // vers le bas il libère le personnage. Sans cette seconde pente, la
    // dernière latte trancherait le visuel d'un trait net.
    const coupure = STORE.avant / hauteur;
    const lattes = [];
    for (let i = 0; i < STORE.lamelles; i++) {
        const t = i / (STORE.lamelles - 1);
        const intensite = t <= coupure
            ? Math.pow(t / coupure, 2.1)
            : Math.pow(1 - (t - coupure) / (1 - coupure), 1.4);
        const a = (STORE.alphaMax * intensite).toFixed(3);
        const y = i * pas + (pas - trait);
        lattes.push(`transparent ${(i * pas).toFixed(2)}mm`, `transparent ${y.toFixed(2)}mm`);
        lattes.push(`rgba(255,255,255,${a}) ${y.toFixed(2)}mm`, `rgba(255,255,255,${a}) ${(y + trait).toFixed(2)}mm`);
    }
    // Sous les lattes, un fondu à l'encre part exactement de la ligne de
    // coupure et s'efface vers le bas : le bord net du fichier source se
    // dissout dans le fond au lieu de trancher. Au-dessus de la coupure ce
    // fondu est de l'encre sur de l'encre, donc invisible.
    const fondu = `linear-gradient(to bottom,`
        + ` rgba(${ink},.96) 0mm, rgba(${ink},.96) ${STORE.avant}mm,`
        + ` rgba(${ink},0) ${hauteur}mm)`;
    return `linear-gradient(to bottom, ${lattes.join(",")}), ${fondu}`;
}

/** Les couches d'illustration d'une couverture (cf. deck.css). */
function habillage(t, deck) {
    const base = `  <div class="fond ${t}"></div>\n  <div class="voile ${t}"></div>`;
    if (t !== "portrait" || !deck?.cover?.file) return base;
    const h = STORE.avant + STORE.apres;
    return `${base}
  <div class="store" style="height:${h}mm; bottom:calc(var(--cover-h) - ${STORE.apres}mm); background:${store(versRgb(deck.palette.ink))}"></div>`;
}

/**
 * Couverture. Deux compositions, imposées par le visuel :
 *  • décor plein cadre → le texte descend et s'appuie sur le bas de page ;
 *  • sujet détouré     → le texte remonte, le sujet occupe la bande basse.
 * Dans les deux cas le logo est présent une seule fois, jamais deux.
 */
function couverture(p, d, { titre, accroche, kicker }) {
    const t = d.cover.type;
    const haut = t === "portrait";
    const logo = `  <span class="cover-logo"></span>`;
    const texte = `  <div class="kicker" style="margin-bottom:${haut ? "7mm" : "8mm"}">${esc(kicker)}</div>
${haut ? "" : logo + "\n"}  <h1 style="font-size:${p.size ?? "30pt"}; line-height:1.05; letter-spacing:-.03em; margin-top:${haut ? "0" : "12mm"}">${rich(titre)}</h1>
  <p class="hook">${rich(accroche)}</p>`;

    // Un seul logo par couverture. Le même emblème répété en haut et en bas
    // ne se lit pas comme une signature, mais comme une hésitation.
    return `<section class="page dark cover ${t}">
${habillage(t, d)}
  <div class="cover-top">
${haut ? logo : `    <span></span>`}
    <div class="kicker">${esc(d.tagline)}</div>
  </div>
${haut ? `  <div style="height:14mm"></div>\n${texte}` : `  <div class="spacer"></div>\n${texte}`}
</section>`;
}

/**
 * Habillage de la 4e de couverture : un decor plein cadre se rejoue bien en
 * cloture, un sujet detoure non — il a deja fait son effet, le remontrer le
 * banalise. Dans ce cas on ferme sur les halos de la couleur de marque.
 */
const dosHabillage = (d) => (d.cover.type === "portrait" ? "aura" : d.cover.type);

/** Longueur de la plus longue ligne d'un manifeste (les <br> sont voulus). */
function tailleManifeste(phrase) {
    const lignes = phrase.split(/<br\s*\/?>/i).map((l) => l.replace(/<[^>]+>/g, "").trim());
    const max = Math.max(...lignes.map((l) => l.length));
    return max <= 19 ? "42pt" : max <= 25 ? "34pt" : max <= 32 ? "28pt" : "23pt";
}

const PAGES = {
    /** Couverture — le visuel d'accueil du produit, le logo, un titre. */
    cover: (p, d) => couverture(p, d, { titre: p.title, accroche: p.hook, kicker: "Dossier de présentation" }),

    /** Le constat — le monde du lecteur, avec ses mots. Sans accuser.
     *  Bloc centré verticalement : selon qu'il y a quatre ou six cartes, le
     *  vide se répartit au-dessus et en dessous plutôt que de tomber d'un
     *  seul côté. */
    constat: (p) => `<section class="page dark">
  <div class="spacer"></div>
  <div class="kicker">${esc(p.kicker ?? "Aujourd'hui")}</div>
  <h2 style="margin-top:6mm; max-width:150mm">${rich(p.title)}</h2>
  <div class="cards">
${p.cards.map((c) => `    <div class="card"><b>${esc(c.t)}</b><span>${esc(c.d)}</span></div>`).join("\n")}
  </div>
  <div class="spacer"></div>
</section>`,

    /** La réponse — promesse + capture principale + parcours numéroté. */
    reponse: (p, d) => `<section class="page">
  <div class="kicker">${esc(p.kicker ?? "La réponse")}</div>
  <h2 style="margin-top:6mm">${rich(p.title)}</h2>
  <p class="lead" style="margin-top:5mm; max-width:130mm">${rich(p.lead)}</p>
${shot(p.shot)}
  <div class="steps">
${p.steps.map((s, i) => `    <div class="step"><div class="no">0${i + 1}</div><div class="tx">${esc(s)}</div></div>`).join("\n")}
  </div>
${foot(d.name)}
</section>`,

    /** Avant / après — le contraste fait le travail. */
    avantApres: (p, d) => `<section class="page">
  <div class="kicker">${esc(p.kicker ?? "Le changement")}</div>
  <h2 style="margin-top:6mm">${rich(p.title)}</h2>
  <div class="split">
    <div class="col before">
      <h3>Avant</h3>
      <ul>
${p.before.map((l) => `        <li>${esc(l)}</li>`).join("\n")}
      </ul>
    </div>
    <div class="col after">
      <h3>Avec ${esc(d.name)}</h3>
      <ul>
${p.after.map((l) => `        <li>${esc(l)}</li>`).join("\n")}
      </ul>
    </div>
  </div>
${foot(d.name)}
</section>`,

    /** Une capacité par page — titre-bénéfice, texte court, capture. */
    capacite: (p, d) => `<section class="page">
  <div class="kicker">${esc(p.kicker)}</div>
  <h2 style="margin-top:6mm">${rich(p.title)}</h2>
  <p style="margin-top:5mm">${rich(p.body)}</p>
${p.shot ? shot(p.shot, p.large !== false) : ""}
${p.result ? `  <div class="result"><b>${esc(p.result.t)}</b><span>${rich(p.result.d)}</span></div>` : ""}
${foot(d.name)}
</section>`,

    /** Manifeste — une seule phrase, sombre. La page qu'on retient.
     *  La taille suit la ligne la plus longue : une phrase trop ample se
     *  replierait toute seule et casserait les retours voulus par l'auteur.
     *  Mieux vaut la réduire d'un cran que la laisser se rompre n'importe où. */
    manifeste: (p) => `<section class="page dark">
  <div class="manifesto">
    <div class="big" style="font-size:${p.size ?? tailleManifeste(p.phrase)}">${rich(p.phrase)}</div>
  </div>
</section>`,

    /** Les preuves — chiffres nus, jamais noyés dans un paragraphe. */
    preuves: (p, d) => `<section class="page">
  <div class="kicker">${esc(p.kicker ?? "En chiffres")}</div>
  <h2 style="margin-top:6mm">${rich(p.title)}</h2>
  <div class="figs">
${p.figs.map((f) => `    <div class="fig"><div class="n">${esc(f.n)}${f.u ? `<span class="u">${esc(f.u)}</span>` : ""}</div><div class="k">${esc(f.k)}</div></div>`).join("\n")}
  </div>
${foot(d.name)}
</section>`,

    /** Ce que vous récupérez / mise en place — bénéfices en termes humains. */
    benefices: (p, d) => `<section class="page">
  <div class="kicker">${esc(p.kicker)}</div>
  <h2 style="margin-top:6mm">${rich(p.title)}</h2>
  <div class="benefits">
${p.items.map((b) => `    <div class="benefit"><b>${esc(b.t)}</b><p>${esc(b.d)}</p></div>`).join("\n")}
  </div>
${foot(d.name)}
</section>`,

    /** Quatrième de couverture — une invitation sobre, puis le contact.
     *  Le dossier se referme comme il s'ouvre : mêmes couches, même logo. */
    dos: (p, d) => `<section class="page dark cover ${dosHabillage(d)}">
${habillage(dosHabillage(d), null)}
  <div class="cover-top">
    <span class="cover-logo"></span>
    <div class="kicker">${esc(p.kicker ?? "Une démonstration ?")}</div>
  </div>
  <div class="spacer"></div>
  <h1 style="font-size:30pt; line-height:1.05; letter-spacing:-.03em">${rich(p.title)}</h1>
  <p class="hook">${rich(p.hook)}</p>
  <div style="margin-top:11mm; letter-spacing:.02em">
    <div class="kicker">Contact</div>
    <div style="font-size:13pt; color:#fff; font-weight:700; margin-top:3mm">${esc(d.contact.name)}</div>
    <div style="font-size:11pt; color:var(--on-dark-soft); margin-top:2mm">${esc(d.contact.phone)}&nbsp;&nbsp;·&nbsp;&nbsp;${esc(d.contact.email)}</div>
    <span data-credit style="display:block; margin-top:5mm; font-size:8.5pt; color:var(--on-dark-mute)"></span>
  </div>
</section>`,
};

/** Barre d'outils écran (retirée à l'impression et à l'export). */
const TOOLBAR = `<div class="toolbar">
  <span class="prog" id="prog"></span>
  <button class="ghost" id="btnPrint" type="button">Imprimer</button>
  <button id="btnPdf" type="button">Télécharger le PDF</button>
</div>`;

// ── Assemblage ──────────────────────────────────────────────────────────

function render(deck, logo, couverture) {
    const p = deck.palette;
    const h = hauteurs(logo.ratio);
    const remplacements = {
        __INK__: p.ink, __INK_RGB__: versRgb(p.ink), __PAPER__: p.paper, __SOFT__: p.soft,
        __BODY__: p.body, __TAUPE__: p.taupe, __HAIR__: p.hair,
        __ACCENT__: p.accent, __ACCENT_RGB__: versRgb(p.accent), __ACCENT_DARK__: p.accentDark, __ACCENT_SOFT__: p.accentSoft,
        __ON_DARK__: p.onDark, __ON_DARK_SOFT__: p.onDarkSoft, __ON_DARK_MUTE__: p.onDarkMute,
        __LOGO_CLAIR__: logo.clair, __LOGO_SOMBRE__: logo.sombre, __LOGO_RATIO__: String(logo.ratio),
    };
    let css = readFileSync(join(ENGINE, "deck.css"), "utf8");
    for (const [clef, valeur] of Object.entries(remplacements)) css = css.split(clef).join(valeur);
    css += `\n/* Dimensions du logo, dérivées du ratio du fichier réel. */\n.page{ --logo-h-grand:${h.grand}; --logo-h-petit:${h.petit}; }\n`;
    if (couverture) {
        css += `.page{ --cover:url("${couverture.uri}"); }\n`;
        // Le sujet détouré occupe toute la largeur : sa hauteur en découle,
        // et c'est elle qui positionne le store au millimètre près.
        css += `.page{ --cover-h:${(210 / (couverture.w / couverture.h)).toFixed(1)}mm; }\n`;
    }

    const js = readFileSync(join(ENGINE, "deck.js"), "utf8")
        .split("__NOM_FICHIER__").join(`${deck.name.replace(/\s+/g, "-")}-presentation.pdf`);

    // Un placeholder oublié = une couleur cassée dans le PDF final : on
    // préfère échouer ici, bruyamment, que livrer un dossier abîmé.
    const restants = [...css.matchAll(/__[A-Z_]+__/g)].map((m) => m[0]);
    if (restants.length) throw new Error(`Placeholders non résolus : ${[...new Set(restants)].join(", ")}`);

    const body = deck.pages
        .map((pg, i) => {
            const fn = PAGES[pg.type];
            if (!fn) throw new Error(`Type de page inconnu : ${pg.type}`);
            return `<!-- ===== ${String(i + 1).padStart(2, "0")} · ${(pg.note ?? pg.type).toUpperCase()} ===== -->\n${fn(pg, deck)}`;
        })
        .join("\n\n");

    return `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(deck.name)} — Dossier de présentation</title>
<style>
${css}
</style>
</head>
<body>

${body}

${TOOLBAR}

<script>
${js}
</script>
</body>
</html>
`;
}

// ── Exécution ───────────────────────────────────────────────────────────

const only = process.argv[2];
for (const file of readdirSync(join(HERE, "contenu")).filter((f) => f.endsWith(".mjs"))) {
    const slug = file.replace(/\.mjs$/, "");
    if (only && only !== slug) continue;
    const { deck } = await import(`file://${join(HERE, "contenu", file)}`);

    const logo = await preparerLogo(deck);
    const couverture = deck.cover.file
        ? await preparerImage(resolve(RACINE, deck.cover.file), {
            largeur: deck.cover.type === "portrait" ? 1100 : 1400,
            transparent: deck.cover.type === "portrait",
        })
        : null;

    const html = render(deck, logo, couverture);
    writeFileSync(resolve(HERE, "..", deck.fichier), html, "utf8");
    console.log(
        `✓ ${slug.padEnd(12)} ${String(deck.pages.length).padStart(2)} pages · ` +
        `${(html.length / 1024).toFixed(0).padStart(4)} Ko · logo ${logo.ratio}:1 · ` +
        `couverture ${deck.cover.type}${couverture ? ` ${couverture.ko} Ko` : ""} · accent ${deck.palette.accent}`
    );
}
