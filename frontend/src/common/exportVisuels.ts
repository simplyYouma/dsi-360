import { jsPDF } from 'jspdf';
// html2canvas-pro (fork maintenu) : gère les couleurs CSS modernes — color-mix(), color(srgb …),
// oklch — que html2canvas 1.4.1 refuse (« unsupported color function »), ce qui faisait échouer
// l'export dès qu'un visuel touchait la charte (fonds en color-mix partout).
import html2canvas from 'html2canvas-pro';
import { MARGE, PIED_H, dessinerEnteteMarque, dessinerPieds, nomDeFichier } from './pdfCharte';

const ESPACE = 6; // mm entre deux visuels

/** Capture un seul visuel, en mode clair forcé, sans les boutons d'export. */
async function capturer(element: HTMLElement, echelle: number): Promise<HTMLCanvasElement> {
  return html2canvas(element, {
    scale: echelle,
    backgroundColor: '#ffffff',
    useCORS: true,
    // Les commandes d'export ne font pas partie du visuel.
    ignoreElements: (el) => el instanceof HTMLElement && el.dataset['exportIgnore'] !== undefined,
    // Les tokens CSS se résolvent en clair, quel que soit le thème à l'écran.
    onclone: (doc) => doc.documentElement.setAttribute('data-theme', 'light'),
  });
}

/** Exporte un visuel en PNG haute définition (3×), tel qu'il est à l'écran. */
export async function exporterVisuelPng(element: HTMLElement, nom: string): Promise<void> {
  const canvas = await capturer(element, 3);
  const lien = document.createElement('a');
  lien.download = `${nomDeFichier(nom)}.png`;
  lien.href = canvas.toDataURL('image/png');
  lien.click();
}

/**
 * Exporte les visuels d'une page dans un document A4 structuré.
 *
 * Chaque bloc `[data-visuel]` est capturé séparément, dans son état à l'écran, puis posé entier :
 * un visuel qui ne tient pas dans la page en ouvre une nouvelle — jamais de coupure au milieu.
 * Un visuel plus haut qu'une page est réduit pour y tenir.
 *
 * À réserver aux graphiques : ce qui sort d'ici est une IMAGE. Pour un tableau destiné à être lu,
 * cité ou recherché, composer le document en texte (cf. features/eod/rapportPdf).
 */
export async function exporterVisuelsPdf(
  conteneur: HTMLElement,
  titre: string,
  nomFichier: string,
): Promise<void> {
  const blocs = [...conteneur.querySelectorAll<HTMLElement>('[data-visuel]')].filter(
    (b) => b.offsetParent !== null, // les visuels des onglets inactifs n'existent pas à l'écran
  );
  if (blocs.length === 0) return;

  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const largeurPage = pdf.internal.pageSize.getWidth();
  const hauteurPage = pdf.internal.pageSize.getHeight();
  const largeur = largeurPage - 2 * MARGE;
  const basUtile = hauteurPage - PIED_H;

  let y = await dessinerEnteteMarque(pdf, titre, null, largeurPage);

  for (const bloc of blocs) {
    // Capture à 3× : à la largeur d'une page A4, 2× rendait le texte flou (résolution trop basse
    // une fois l'image posée). 3× donne ~380 dpi — net à l'impression comme à l'écran.
    const canvas = await capturer(bloc, 3);
    let imgL = largeur;
    let imgH = (canvas.height / canvas.width) * largeur;
    if (imgH > basUtile - MARGE) {
      // Plus haut qu'une page entière : on réduit, on ne coupe pas.
      imgH = basUtile - MARGE;
      imgL = (canvas.width / canvas.height) * imgH;
    }
    if (y + imgH > basUtile) {
      pdf.addPage();
      y = MARGE;
    }
    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', MARGE, y, imgL, imgH);
    y += imgH + ESPACE;
  }

  dessinerPieds(pdf, largeurPage, hauteurPage);
  pdf.save(nomFichier);
}
