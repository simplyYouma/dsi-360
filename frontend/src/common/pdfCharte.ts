/** La charte des documents PDF de DSI 360 : logo, en-tête, pied de page, couleurs.
 *
 * Elle vit à part parce que deux exports très différents s'en servent — la capture de visuels
 * (`exportVisuels`) et le rapport composé du soir (`features/eod/rapportPdf`). Recopier l'en-tête
 * dans le second aurait suffi le jour même, puis les deux auraient divergé : un logo changé d'un
 * côté, une mention de pied oubliée de l'autre. Un document qui porte la marque de la banque ne
 * peut pas exister en deux versions.
 *
 * Ce module ne sait rien du contenu : il pose la marque, les autres composent dedans.
 */
import type { jsPDF } from 'jspdf';
// Le logo de la BANQUE, et non celui de la plateforme : un document qui sort d'ici se remet, se
// vise et s'archive au nom d'AFG Bank Mali — DSI 360 n'est que l'outil qui l'a produit, et le pied
// de page le dit déjà. L'export portait jusqu'ici le logo DSI 360 par défaut d'avoir eu l'autre.
import logoUrl from '@/assets/brand/logo-afgbank.png';

export const MARGE = 14; // mm
export const PIED_H = 12; // mm réservés au pied de page

type Encre = readonly [number, number, number];

/** Les couleurs de la charte, reprises telles quelles des tokens du thème clair (tokens.css).
 *
 * Toujours le thème clair : un PDF s'imprime et s'archive, il ne suit pas le thème de celui qui
 * l'exporte. Les reprendre des tokens plutôt que de les réinventer garantit qu'une anomalie a la
 * même couleur sur le papier qu'à l'écran — c'est la règle « la couleur réservée au sens ». */
export const ENCRE: Record<'texte' | 'attenue' | 'filet' | 'ok' | 'alerte', Encre> = {
  texte: [20, 22, 26], // --text     #14161a
  attenue: [107, 114, 128], // --text-muted   #6b7280
  filet: [230, 232, 236], // --border   #e6e8ec
  ok: [31, 157, 85], // --status-ok    #1f9d55
  alerte: [214, 69, 69], // --status-danger  #d64545
};

export function chargerImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resoudre, rejeter) => {
    const img = new Image();
    img.onload = () => resoudre(img);
    img.onerror = rejeter;
    img.src = url;
  });
}

/** Nom de fichier lisible et sans accent, préfixé par la plateforme. */
export function nomDeFichier(nom: string): string {
  const slug = nom
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return `dsi360-${slug || 'document'}`;
}

/**
 * En-tête de la première page : logo AFG Bank Mali, titre, sous-titre, date d'édition, filet.
 * Retourne l'ordonnée à partir de laquelle le contenu peut commencer.
 *
 * Le logo est chargé de façon défensive : si l'image manque, le document sort quand même, un peu
 * plus haut. Un rapport sans logo reste lisible ; une exception au milieu d'un export laisserait
 * l'opérateur sans rien, la nuit, au moment de rendre compte.
 */
export async function dessinerEnteteMarque(
  pdf: jsPDF,
  titre: string,
  sousTitre: string | null,
  largeurPage: number,
): Promise<number> {
  let bas = MARGE;
  try {
    const logo = await chargerImage(logoUrl);
    const h = 11; // mm — la hauteur d'un en-tête de courrier, pas d'une vignette

    pdf.addImage(logo, 'PNG', MARGE, MARGE, (logo.width / logo.height) * h, h);
    bas = MARGE + h;
  } catch {
    bas = MARGE + 6;
  }

  // L'émetteur, en face du logo : un document qui circule doit dire d'où il sort, pas seulement
  // au nom de qui. Le pied de page nomme l'outil ; l'en-tête nomme la direction.
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(7.5);
  pdf.setTextColor(...ENCRE.attenue);
  pdf.text("DIRECTION DES SYSTÈMES D'INFORMATION", largeurPage - MARGE, MARGE + 6.5, {
    align: 'right',
  });

  pdf.setTextColor(...ENCRE.texte);
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(15);
  pdf.text(titre, MARGE, bas + 8);

  let y = bas + 8;
  if (sousTitre !== null) {
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);
    pdf.setTextColor(...ENCRE.texte);
    pdf.text(sousTitre, MARGE, y + 6);
    y += 6;
  }

  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(9);
  pdf.setTextColor(...ENCRE.attenue);
  const date = new Date().toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
  pdf.text(`Édité le ${date}`, MARGE, y + 5);

  const filet = y + 9;
  pdf.setDrawColor(...ENCRE.filet);
  pdf.line(MARGE, filet, largeurPage - MARGE, filet);
  return filet + 6;
}

/** Pied de chaque page : la plateforme à gauche, la pagination à droite. */
export function dessinerPieds(pdf: jsPDF, largeurPage: number, hauteurPage: number): void {
  const total = pdf.getNumberOfPages();
  for (let n = 1; n <= total; n += 1) {
    pdf.setPage(n);
    const y = hauteurPage - 8;
    pdf.setDrawColor(...ENCRE.filet);
    pdf.line(MARGE, y - 4, largeurPage - MARGE, y - 4);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(...ENCRE.attenue);
    pdf.text('DSI 360 — Plateforme de pilotage de la DSI · AFG Bank Mali', MARGE, y);
    pdf.text(`Page ${n} / ${total}`, largeurPage - MARGE, y, { align: 'right' });
  }
}
