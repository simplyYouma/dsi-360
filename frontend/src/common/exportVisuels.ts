import { jsPDF } from 'jspdf';
// html2canvas-pro (fork maintenu) : gère les couleurs CSS modernes — color-mix(), color(srgb …),
// oklch — que html2canvas 1.4.1 refuse (« unsupported color function »), ce qui faisait échouer
// l'export dès qu'un visuel touchait la charte (fonds en color-mix partout).
import html2canvas from 'html2canvas-pro';
import logoUrl from '@/assets/brand/logo1.png';

const MARGE = 14; // mm
const PIED_H = 12; // mm réservés au pied de page
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

function nomDeFichier(nom: string): string {
  const slug = nom
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return `dsi360-${slug || 'visuel'}`;
}

/** Exporte un visuel en PNG haute définition (3×), tel qu'il est à l'écran. */
export async function exporterVisuelPng(element: HTMLElement, nom: string): Promise<void> {
  const canvas = await capturer(element, 3);
  const lien = document.createElement('a');
  lien.download = `${nomDeFichier(nom)}.png`;
  lien.href = canvas.toDataURL('image/png');
  lien.click();
}

function chargerImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resoudre, rejeter) => {
    const img = new Image();
    img.onload = () => resoudre(img);
    img.onerror = rejeter;
    img.src = url;
  });
}

/** En-tête de la première page : logo, titre, horodatage, filet. Retourne le y disponible. */
async function dessinerEntete(pdf: jsPDF, titre: string, largeurPage: number): Promise<number> {
  let bas = MARGE;
  try {
    const logo = await chargerImage(logoUrl);
    const h = 9;
    pdf.addImage(logo, 'PNG', MARGE, MARGE, (logo.width / logo.height) * h, h);
    bas = MARGE + h;
  } catch {
    bas = MARGE + 6;
  }
  pdf.setTextColor(22, 24, 29);
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(15);
  pdf.text(titre, MARGE, bas + 8);
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(9);
  pdf.setTextColor(120, 128, 140);
  const date = new Date().toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
  pdf.text(`Édité le ${date}`, MARGE, bas + 13);
  const y = bas + 17;
  pdf.setDrawColor(224, 227, 231);
  pdf.line(MARGE, y, largeurPage - MARGE, y);
  return y + ESPACE;
}

/** Pied de chaque page : la plateforme à gauche, la pagination à droite. */
function dessinerPieds(pdf: jsPDF, largeurPage: number, hauteurPage: number): void {
  const total = pdf.getNumberOfPages();
  for (let n = 1; n <= total; n += 1) {
    pdf.setPage(n);
    const y = hauteurPage - 8;
    pdf.setDrawColor(224, 227, 231);
    pdf.line(MARGE, y - 4, largeurPage - MARGE, y - 4);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(120, 128, 140);
    pdf.text('DSI 360 — Plateforme de pilotage de la DSI · AFG Bank Mali', MARGE, y);
    pdf.text(`Page ${n} / ${total}`, largeurPage - MARGE, y, { align: 'right' });
  }
}

/**
 * Exporte les visuels d'une page dans un document A4 structuré.
 *
 * Chaque bloc `[data-visuel]` est capturé séparément, dans son état à l'écran, puis posé entier :
 * un visuel qui ne tient pas dans la page en ouvre une nouvelle — jamais de coupure au milieu.
 * Un visuel plus haut qu'une page est réduit pour y tenir.
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

  let y = await dessinerEntete(pdf, titre, largeurPage);

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
