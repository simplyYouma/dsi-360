/**
 * Le rapport du soir, composé en PDF.
 *
 * Il ne PHOTOGRAPHIE pas l'écran (cf. `common/exportVisuels`, réservé aux graphiques) : l'écran
 * porte des boutons « Démarrer », « Terminer », des icônes de verdict — du mobilier de saisie qui
 * n'a rien à faire dans un document remis à la hiérarchie. Et une capture donne une image : on n'y
 * cherche pas un mot, on n'en cite pas une ligne, elle pèse et elle floute à l'impression.
 *
 * Le document est donc dessiné en texte : sélectionnable, cherchable, net à toute échelle, et
 * léger. Il reprend la charte de la plateforme (`common/pdfCharte`) — logo AFG Bank Mali, pied de
 * page paginé — pour qu'un rapport archivé se reconnaisse au premier coup d'œil.
 *
 * Il circule entre plusieurs lecteurs, souvent imprimé et désolidarisé. D'où trois partis pris :
 * une synthèse en tête, que l'on puisse ne lire qu'elle ; le relevé des anomalies juste après,
 * parce que c'est ce qu'un supérieur cherche en premier ; et un rappel d'identité en haut de
 * chaque page suivante, pour qu'une feuille détachée dise encore de quelle nuit elle parle.
 */
import { jsPDF } from 'jspdf';
import {
  ENCRE,
  MARGE,
  PIED_H,
  dessinerEnteteMarque,
  dessinerPieds,
  nomDeFichier,
} from '@/common/pdfCharte';
import {
  estReglee,
  grouperParSection,
  heure,
  jour,
  type DetailEod,
  type EtapeEod,
  type StatutEtape,
} from './eodApi';

/** Colonnes du tableau, en millimètres. La somme fait exactement la largeur utile d'une A4
 *  portrait (210 − 2 × 14) : aucune colonne ne déborde, aucun blanc ne traîne à droite. */
const COLONNES = [
  { titre: 'Étape', largeur: 56 },
  { titre: 'Début', largeur: 19 },
  { titre: 'Fin', largeur: 19 },
  { titre: 'Verdict', largeur: 28 },
  { titre: 'Observations', largeur: 60 },
] as const;

const PAD = 1.6; // mm — respiration intérieure d'une cellule
const LIGNE = 3.5; // mm — interligne à 8 pt
const CORPS = 8; // pt
const H_ENTETE_TABLEAU = 6; // mm
const H_BANDE_SECTION = 7; // mm

type Encre = readonly [number, number, number];

/** Le verdict porte la seule couleur du document. Le reste est en noir et gris : si tout était
 *  coloré, une anomalie ne se verrait plus en parcourant vingt-huit lignes. */
function encreVerdict(statut: StatutEtape): Encre {
  if (statut === 'Anomalie') return ENCRE.alerte;
  if (statut === 'Complété') return ENCRE.ok;
  return ENCRE.attenue;
}

function abscisses(): number[] {
  const xs: number[] = [];
  let x = MARGE;
  for (const c of COLONNES) {
    xs.push(x);
    x += c.largeur;
  }
  return xs;
}

/** « 7 h 02 » — la durée de la soirée, telle qu'on la commente en comité. */
function duree(debut: string | null, fin: string | null): string {
  if (debut === null || fin === null) return '—';
  const minutes = Math.round((new Date(fin).getTime() - new Date(debut).getTime()) / 60000);
  if (!Number.isFinite(minutes) || minutes < 0) return '—';
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`;
}

/** La plage, sans flèche : « → » n'appartient pas à l'encodage des polices standard du PDF et
 *  sortait à l'impression en « !' ». Un tiret demi-cadratin dit la même chose et existe, lui. */
function plage(s: DetailEod): string {
  const debut = s.debut_effectif === null ? '—' : heure(s.debut_effectif);
  const fin = s.fin_effective === null ? 'en cours' : heure(s.fin_effective);
  return `${debut} – ${fin}`;
}

/** Ligne d'en-tête du tableau, reposée en haut de chaque page : un tableau qui continue sans ses
 *  titres oblige le lecteur à remonter d'une page pour savoir ce qu'il lit. */
function dessinerEnteteTableau(pdf: jsPDF, y: number, largeurUtile: number): number {
  pdf.setFillColor(248, 249, 251);
  pdf.rect(MARGE, y, largeurUtile, H_ENTETE_TABLEAU, 'F');
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(7);
  pdf.setTextColor(...ENCRE.attenue);
  const xs = abscisses();
  COLONNES.forEach((c, i) => {
    pdf.text(c.titre.toUpperCase(), (xs[i] ?? MARGE) + PAD, y + 4);
  });
  pdf.setDrawColor(...ENCRE.filet);
  pdf.line(MARGE, y + H_ENTETE_TABLEAU, MARGE + largeurUtile, y + H_ENTETE_TABLEAU);
  return y + H_ENTETE_TABLEAU;
}

/** Le titre de section vit DANS le tableau, en bande.
 *
 * Il ouvrait auparavant un tableau par section, en-tête compris : quatre des cinq sections du
 * déroulé ne portent qu'une étape, et le document passait plus de place à se présenter qu'à
 * rendre compte. */
function dessinerBandeSection(
  pdf: jsPDF,
  titre: string,
  reglees: number,
  total: number,
  y: number,
  largeurUtile: number,
): number {
  pdf.setFillColor(241, 243, 246);
  pdf.rect(MARGE, y, largeurUtile, H_BANDE_SECTION, 'F');
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(7.5);
  pdf.setTextColor(...ENCRE.texte);
  pdf.text(titre.toUpperCase(), MARGE + PAD, y + 4.8);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(...ENCRE.attenue);
  pdf.text(`${reglees} / ${total} réglées`, MARGE + largeurUtile - PAD, y + 4.8, {
    align: 'right',
  });
  return y + H_BANDE_SECTION;
}

interface Cellules {
  etape: string[];
  debut: string;
  fin: string;
  valeur: string | null;
  verdict: StatutEtape;
  observations: string[];
}

function cellules(pdf: jsPDF, e: EtapeEod): Cellules {
  // `splitTextToSize` mesure avec la police COURANTE. Sans ce réglage, le découpage héritait des
  // 7 pt de la bande de section ou de l'en-tête : plus de caractères tenaient par ligne qu'à
  // 8 pt, et les observations débordaient du cadre à l'impression.
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(CORPS);
  const largeurEtape = COLONNES[0].largeur - 2 * PAD;
  const largeurObs = COLONNES[4].largeur - 2 * PAD;
  // L'aide de l'étape (« Seulement les soirs de fin de mois… ») est portée par le déroulé de
  // référence, pas par la nuit : elle explique le geste, elle ne rend pas compte. Hors rapport.
  return {
    etape: pdf.splitTextToSize(e.libelle, largeurEtape),
    debut: e.nature === 'valeur' ? '' : heure(e.debut),
    fin: e.nature === 'valeur' ? '' : heure(e.fin),
    valeur: e.nature === 'valeur' ? (e.valeur ?? '—') : null,
    verdict: e.statut,
    observations: pdf.splitTextToSize(e.notes ?? '', largeurObs),
  };
}

function hauteurLigne(c: Cellules): number {
  const lignes = Math.max(c.etape.length, c.observations.length, 1);
  return 2 * PAD + lignes * LIGNE;
}

function dessinerLigne(
  pdf: jsPDF,
  e: EtapeEod,
  c: Cellules,
  y: number,
  largeurUtile: number,
): void {
  const h = hauteurLigne(c);
  if (e.statut === 'Anomalie') {
    // La ligne entière porte la marque, comme à l'écran : sur vingt-huit lignes, un mot rouge
    // dans une colonne étroite se manque.
    pdf.setFillColor(252, 240, 240);
    pdf.rect(MARGE, y, largeurUtile, h, 'F');
  }
  const xs = abscisses();
  const base = y + PAD + LIGNE - 0.9; // ligne de base du premier interligne

  pdf.setFontSize(CORPS);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(...ENCRE.texte);
  pdf.text(c.etape, (xs[0] ?? MARGE) + PAD, base);

  if (c.valeur !== null) {
    // « System Date » : ce qui compte n'est pas quand on a regardé, mais ce qu'on a lu. La valeur
    // occupe les deux colonnes d'heures, exactement comme sur l'écran de pointage.
    pdf.text(c.valeur, (xs[1] ?? MARGE) + PAD, base);
  } else {
    pdf.text(c.debut, (xs[1] ?? MARGE) + PAD, base);
    pdf.text(c.fin, (xs[2] ?? MARGE) + PAD, base);
  }

  pdf.setTextColor(...encreVerdict(c.verdict));
  pdf.text(c.verdict, (xs[3] ?? MARGE) + PAD, base);

  pdf.setTextColor(...ENCRE.attenue);
  pdf.text(c.observations, (xs[4] ?? MARGE) + PAD, base);

  pdf.setDrawColor(...ENCRE.filet);
  pdf.line(MARGE, y + h, MARGE + largeurUtile, y + h);
}

/** Le bandeau de synthèse : ce que la hiérarchie lit en premier, et souvent seul. */
function dessinerSynthese(pdf: jsPDF, s: DetailEod, y: number, largeurUtile: number): number {
  const cases: { etiquette: string; valeur: string; encre: Encre }[] = [
    { etiquette: 'Journée comptable', valeur: jour(s.journee), encre: ENCRE.texte },
    { etiquette: 'Statut', valeur: s.statut, encre: ENCRE.texte },
    {
      etiquette: 'Opérateur',
      valeur: s.responsable === null ? '—' : `${s.responsable.prenom} ${s.responsable.nom}`,
      encre: ENCRE.texte,
    },
    { etiquette: 'Nature', valeur: s.categorie ?? '—', encre: ENCRE.texte },
    { etiquette: 'Plage', valeur: plage(s), encre: ENCRE.texte },
    { etiquette: 'Durée', valeur: duree(s.debut_effectif, s.fin_effective), encre: ENCRE.texte },
    {
      etiquette: 'Étapes réglées',
      valeur: `${s.nb_etapes - s.reste} / ${s.nb_etapes}`,
      encre: s.reste > 0 ? ENCRE.attenue : ENCRE.ok,
    },
    {
      etiquette: 'Anomalies',
      // Zéro anomalie ne se célèbre pas : la nuit normale reste en gris pour que celles qui ne
      // le sont pas se voient.
      valeur: s.anomalies === 0 ? 'aucune' : String(s.anomalies),
      encre: s.anomalies === 0 ? ENCRE.attenue : ENCRE.alerte,
    },
  ];

  const colonnes = 4;
  const largeurCase = largeurUtile / colonnes;
  const hauteurCase = 11;
  const hauteur = hauteurCase * Math.ceil(cases.length / colonnes);

  pdf.setDrawColor(...ENCRE.filet);
  pdf.rect(MARGE, y, largeurUtile, hauteur);

  cases.forEach((c, i) => {
    const x = MARGE + (i % colonnes) * largeurCase;
    const haut = y + Math.floor(i / colonnes) * hauteurCase;
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(6.5);
    pdf.setTextColor(...ENCRE.attenue);
    pdf.text(c.etiquette.toUpperCase(), x + 3, haut + 4.2);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(9);
    pdf.setTextColor(...c.encre);
    pdf.text(pdf.splitTextToSize(c.valeur, largeurCase - 6)[0] ?? '', x + 3, haut + 8.8);
  });

  return y + hauteur + 6;
}

/** Le relevé des anomalies, juste sous la synthèse.
 *
 * Elles sont déjà dans le déroulé, mais noyées : deux lignes rouges sur vingt-huit, réparties sur
 * deux pages. Un supérieur qui reçoit ce rapport cherche d'abord ce qui s'est mal passé — le lui
 * faire chercher, c'est prendre le risque qu'il ne le trouve pas. Rien n'est affiché quand la nuit
 * s'est bien passée : un encadré vide ferait douter. */
function dessinerAnomalies(pdf: jsPDF, s: DetailEod, y: number, largeurUtile: number): number {
  const fautives = s.etapes.filter((e) => e.statut === 'Anomalie');
  if (fautives.length === 0) return y;

  const largeurTexte = largeurUtile - 10;
  // Même précaution que dans `cellules` : on découpe dans la police qui servira à tracer.
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(7.5);
  const blocs = fautives.map((e) => ({
    titre: `${e.section} · ${e.libelle}`,
    quand: e.nature === 'valeur' ? '' : `${heure(e.debut)} – ${heure(e.fin)}`,
    detail: pdf.splitTextToSize(e.notes ?? 'Sans explication consignée.', largeurTexte),
  }));

  const hauteur = 7 + blocs.reduce((t, b) => t + 4.4 + b.detail.length * 3.4 + 2.2, 0);

  pdf.setFillColor(252, 245, 245);
  pdf.rect(MARGE, y, largeurUtile, hauteur, 'F');
  pdf.setFillColor(...ENCRE.alerte);
  pdf.rect(MARGE, y, 1.2, hauteur, 'F');

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(7);
  pdf.setTextColor(...ENCRE.alerte);
  pdf.text(`ANOMALIES RELEVÉES (${fautives.length})`, MARGE + 5, y + 4.6);

  let curseur = y + 9.4;
  for (const b of blocs) {
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(7.5);
    pdf.setTextColor(...ENCRE.texte);
    pdf.text(pdf.splitTextToSize(b.titre, largeurTexte - 22)[0] ?? '', MARGE + 5, curseur);
    if (b.quand !== '') {
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(...ENCRE.attenue);
      pdf.text(b.quand, MARGE + largeurUtile - 4, curseur, { align: 'right' });
    }
    curseur += 4.4;
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7.5);
    pdf.setTextColor(...ENCRE.attenue);
    pdf.text(b.detail, MARGE + 5, curseur);
    curseur += b.detail.length * 3.4 + 2.2;
  }

  return y + hauteur + 6;
}

/** Rappel d'identité en haut des pages suivantes : une feuille détachée doit encore dire de quelle
 *  nuit elle parle, et de quel document elle vient. */
function dessinerRappel(pdf: jsPDF, s: DetailEod, largeurPage: number): number {
  const y = MARGE;
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(7.5);
  pdf.setTextColor(...ENCRE.attenue);
  pdf.text(`Rapport de fin de journée · ${jour(s.journee)}`, MARGE, y);
  pdf.text(s.reference, largeurPage - MARGE, y, { align: 'right' });
  pdf.setDrawColor(...ENCRE.filet);
  pdf.line(MARGE, y + 2, largeurPage - MARGE, y + 2);
  return y + 6;
}

/** Deux visas en bas du document. Un rapport de nuit se rend et se contrôle : sans emplacement
 *  prévu, il se signe en travers, dans la marge. */
function dessinerVisas(pdf: jsPDF, y: number, largeurUtile: number): void {
  const largeur = (largeurUtile - 10) / 2;
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(7);
  pdf.setTextColor(...ENCRE.attenue);
  const visas = [
    { titre: 'ÉTABLI PAR (OPÉRATEUR)', x: MARGE },
    { titre: 'VISA (RESPONSABLE PRODUCTION)', x: MARGE + largeur + 10 },
  ];
  for (const v of visas) {
    pdf.text(v.titre, v.x, y);
    pdf.setDrawColor(...ENCRE.filet);
    pdf.line(v.x, y + 13, v.x + largeur, y + 13);
  }
}

/**
 * Compose et télécharge le rapport d'une soirée.
 *
 * Les étapes sont prises telles que le serveur les rend : ce document doit montrer la nuit comme
 * elle s'est pointée, pas comme on la réordonnerait après coup.
 */
export async function exporterRapportEodPdf(soiree: DetailEod): Promise<void> {
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const largeurPage = pdf.internal.pageSize.getWidth();
  const hauteurPage = pdf.internal.pageSize.getHeight();
  const largeurUtile = largeurPage - 2 * MARGE;
  const basUtile = hauteurPage - PIED_H - 3; // 3 mm : une ligne ne doit pas toucher le filet du pied

  let y = await dessinerEnteteMarque(
    pdf,
    'Rapport de fin de journée',
    `Journée comptable du ${jour(soiree.journee)} · ${soiree.reference}`,
    largeurPage,
  );

  y = dessinerSynthese(pdf, soiree, y, largeurUtile);
  y = dessinerAnomalies(pdf, soiree, y, largeurUtile);

  /** Ouvre une page, y rappelle l'identité du document puis repose l'en-tête du tableau. */
  const pageSuivante = (): void => {
    pdf.addPage();
    y = dessinerRappel(pdf, soiree, largeurPage);
    y = dessinerEnteteTableau(pdf, y, largeurUtile);
  };

  y = dessinerEnteteTableau(pdf, y, largeurUtile);

  for (const groupe of grouperParSection(soiree.etapes)) {
    const reglees = groupe.etapes.filter(estReglee).length;
    const premiere = groupe.etapes[0];

    // Une bande de section seule en bas de page annonce des étapes qui commencent ailleurs : on
    // mesure la première ligne pour n'ouvrir la page qu'une fois, et au bon moment.
    const hPremiere = premiere === undefined ? 0 : hauteurLigne(cellules(pdf, premiere));
    if (y + H_BANDE_SECTION + hPremiere > basUtile) pageSuivante();

    y = dessinerBandeSection(pdf, groupe.titre, reglees, groupe.etapes.length, y, largeurUtile);

    for (const e of groupe.etapes) {
      const c = cellules(pdf, e);
      const h = hauteurLigne(c);
      if (y + h > basUtile) {
        pageSuivante();
        // Une section coupée redit son nom : sans cela, le lecteur de la page suivante voit des
        // étapes sans savoir à quelle phase de la nuit elles appartiennent — et ce document se
        // lit page par page, souvent imprimé et désolidarisé.
        y = dessinerBandeSection(
          pdf,
          `${groupe.titre} (suite)`,
          reglees,
          groupe.etapes.length,
          y,
          largeurUtile,
        );
      }
      dessinerLigne(pdf, e, c, y, largeurUtile);
      y += h;
    }
  }

  // Page nue si les visas ne tiennent pas : `pageSuivante` y poserait un en-tête de tableau qui
  // n'annoncerait aucune ligne.
  if (y + 22 > basUtile) {
    pdf.addPage();
    y = dessinerRappel(pdf, soiree, largeurPage);
  }
  dessinerVisas(pdf, y + 10, largeurUtile);

  dessinerPieds(pdf, largeurPage, hauteurPage);
  pdf.save(`${nomDeFichier(`rapport eod ${jour(soiree.journee)}`)}.pdf`);
}
