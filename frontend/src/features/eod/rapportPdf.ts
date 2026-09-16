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

/** Ligne d'en-tête du tableau, redessinée en haut de chaque page : un tableau qui continue sans
 *  ses titres oblige le lecteur à remonter d'une page pour savoir ce qu'il lit. */
function dessinerEnteteTableau(pdf: jsPDF, y: number, largeurUtile: number): number {
  const hauteur = 6;
  pdf.setFillColor(248, 249, 251);
  pdf.rect(MARGE, y, largeurUtile, hauteur, 'F');
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(7);
  pdf.setTextColor(...ENCRE.attenue);
  const xs = abscisses();
  COLONNES.forEach((c, i) => {
    pdf.text(c.titre.toUpperCase(), (xs[i] ?? MARGE) + PAD, y + 4);
  });
  pdf.setDrawColor(...ENCRE.filet);
  pdf.line(MARGE, y + hauteur, MARGE + largeurUtile, y + hauteur);
  return y + hauteur;
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
    {
      etiquette: 'Plage',
      valeur: `${s.debut_effectif === null ? '—' : heure(s.debut_effectif)} → ${
        s.fin_effective === null ? '…' : heure(s.fin_effective)
      }`,
      encre: ENCRE.texte,
    },
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

  const colonnes = 3;
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
    pdf.setFontSize(9.5);
    pdf.setTextColor(...c.encre);
    pdf.text(c.valeur, x + 3, haut + 8.8);
  });

  return y + hauteur + 7;
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
  const basUtile = hauteurPage - PIED_H;

  let y = await dessinerEnteteMarque(
    pdf,
    'Rapport de fin de journée',
    `Journée comptable du ${jour(soiree.journee)} · ${soiree.reference}`,
    largeurPage,
  );

  y = dessinerSynthese(pdf, soiree, y, largeurUtile);

  /** Ouvre une page et y repose l'en-tête du tableau. */
  const pageSuivante = (): void => {
    pdf.addPage();
    y = dessinerEnteteTableau(pdf, MARGE, largeurUtile);
  };

  for (const groupe of grouperParSection(soiree.etapes)) {
    const reglees = groupe.etapes.filter(estReglee).length;

    // Un titre de section seul en bas de page annonce un tableau qui commence ailleurs.
    if (y + 7 + 6 + 8 > basUtile) pageSuivante();

    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(8);
    pdf.setTextColor(...ENCRE.texte);
    pdf.text(groupe.titre.toUpperCase(), MARGE, y + 4);
    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(...ENCRE.attenue);
    pdf.text(`${reglees} / ${groupe.etapes.length} réglées`, MARGE + largeurUtile, y + 4, {
      align: 'right',
    });
    y += 7;

    y = dessinerEnteteTableau(pdf, y, largeurUtile);

    for (const e of groupe.etapes) {
      const c = cellules(pdf, e);
      const h = hauteurLigne(c);
      if (y + h > basUtile) pageSuivante();
      dessinerLigne(pdf, e, c, y, largeurUtile);
      y += h;
    }
    y += 6;
  }

  if (y + 20 > basUtile) pageSuivante();
  dessinerVisas(pdf, y + 4, largeurUtile);

  dessinerPieds(pdf, largeurPage, hauteurPage);
  pdf.save(`${nomDeFichier(`rapport eod ${jour(soiree.journee)}`)}.pdf`);
}
