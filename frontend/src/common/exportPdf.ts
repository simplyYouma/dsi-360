import { jsPDF } from 'jspdf';
import html2canvas from 'html2canvas';
import logoUrl from '@/assets/brand/logo1.png';

const MARGE = 12; // mm

function chargerImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resoudre, rejeter) => {
    const img = new Image();
    img.onload = () => resoudre(img);
    img.onerror = rejeter;
    img.src = url;
  });
}

/** En-tête du document (logo + titre + horodatage + filet). Retourne la hauteur consommée (mm). */
async function dessinerEntete(pdf: jsPDF, titre: string, largeurPage: number): Promise<number> {
  let bas = MARGE;
  try {
    const logo = await chargerImage(logoUrl);
    const h = 9;
    const l = (logo.width / logo.height) * h;
    pdf.addImage(logo, 'PNG', MARGE, MARGE, l, h);
    bas = MARGE + h;
  } catch {
    bas = MARGE + 6;
  }
  pdf.setTextColor(22, 24, 29);
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(15);
  pdf.text(titre, MARGE, bas + 7);
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
  pdf.text(`DSI 360 — AFG Bank Mali · Édité le ${date}`, MARGE, bas + 12);
  const y = bas + 16;
  pdf.setDrawColor(224, 227, 231);
  pdf.line(MARGE, y, largeurPage - MARGE, y);
  return y + 4 - MARGE; // hauteur totale de l'en-tête sous la marge haute
}

/**
 * Exporte les visuels d'un élément dans un PDF structuré (en-tête logo + titre + date), en
 * **mode clair** quel que soit le thème à l'écran, en reprenant exactement les visuels rendus.
 */
export async function exporterVisuelsPdf(
  element: HTMLElement,
  titre: string,
  nomFichier: string,
): Promise<void> {
  const canvas = await html2canvas(element, {
    scale: 2,
    backgroundColor: '#ffffff',
    useCORS: true,
    // Force le thème clair sur le clone capturé (les tokens CSS se résolvent en clair).
    onclone: (doc) => doc.documentElement.setAttribute('data-theme', 'light'),
  });

  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const largeurPage = pdf.internal.pageSize.getWidth();
  const hauteurPage = pdf.internal.pageSize.getHeight();
  const largeur = largeurPage - 2 * MARGE;

  const enteteH = await dessinerEntete(pdf, titre, largeurPage);
  const image = canvas.toDataURL('image/png');
  const imgH = (canvas.height / canvas.width) * largeur;

  // 1re page : image sous l'en-tête ; pages suivantes : image décalée (pagination d'image longue).
  let y = MARGE + enteteH;
  pdf.addImage(image, 'PNG', MARGE, y, largeur, imgH);
  let reste = imgH - (hauteurPage - y - MARGE);
  while (reste > 0) {
    pdf.addPage();
    y = MARGE - (imgH - reste);
    pdf.addImage(image, 'PNG', MARGE, y, largeur, imgH);
    reste -= hauteurPage - 2 * MARGE;
  }

  pdf.save(nomFichier);
}
