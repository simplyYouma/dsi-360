import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cx } from '@/common/cx';
import styles from './Modale.module.css';

interface ModaleProps {
  ouverte: boolean;
  onFermer: () => void;
  titre: string;
  children: ReactNode;
  /** Contenu du pied (boutons d'action), aligné à droite. */
  pied?: ReactNode;
  /** Largeur maximale en px (défaut 560). */
  largeur?: number;
  /** Colonne latérale fixe à droite (ex. fil de discussion), avec son propre défilement. */
  panneau?: ReactNode;
  /** Largeur de la colonne latérale en px (défaut 380). */
  largeurPanneau?: number;
  /** Colonne latérale fixe à GAUCHE (ex. explorateur de pièces jointes), avec son propre
   *  défilement. Ce qui s'y trouve se consulte en parallèle du dossier, sans le faire défiler. */
  panneauGauche?: ReactNode;
  /** Largeur de la colonne de gauche en px (défaut 250). */
  largeurPanneauGauche?: number;
  /** Étiquettes flottantes collées au bord gauche, comme des stickers (ex. constats). */
  etiquettes?: ReactNode;
}

/**
 * Modale premium : grand rayon, ombre flottante, bouton fermer circulaire en haut à droite.
 * Ferme via le X, la touche Échap ou un clic sur le fond. Verrouille le défilement de la page.
 */
export function Modale({
  ouverte,
  onFermer,
  titre,
  children,
  pied,
  largeur = 560,
  panneau,
  largeurPanneau = 380,
  panneauGauche,
  largeurPanneauGauche = 250,
  etiquettes,
}: ModaleProps): JSX.Element | null {
  useEffect(() => {
    if (!ouverte) return;
    const surTouche = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onFermer();
    };
    document.addEventListener('keydown', surTouche);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', surTouche);
      document.body.style.overflow = overflow;
    };
  }, [ouverte, onFermer]);

  if (!ouverte) return null;

  return createPortal(
    <div className={styles.overlay} onMouseDown={onFermer}>
      <div
        className={styles.modale}
        style={{
          maxWidth:
            largeur +
            (panneau !== undefined ? largeurPanneau : 0) +
            (panneauGauche !== undefined ? largeurPanneauGauche : 0),
        }}
        role="dialog"
        aria-modal="true"
        aria-label={titre}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button className={styles.fermer} onClick={onFermer} aria-label="Fermer">
          <X size={20} />
        </button>
        {etiquettes !== undefined && <div className={styles.etiquettes}>{etiquettes}</div>}
        <div className={styles.grille}>
          {panneauGauche !== undefined && (
            <aside className={styles.panneauGauche} style={{ flexBasis: largeurPanneauGauche }}>
              {panneauGauche}
            </aside>
          )}
          <div className={styles.principal}>
            <h2 className={styles.titre}>{titre}</h2>
            <div className={styles.corps}>{children}</div>
            {pied !== undefined && <div className={cx(styles.pied)}>{pied}</div>}
          </div>
          {panneau !== undefined && (
            <aside className={styles.panneau} style={{ flexBasis: largeurPanneau }}>
              {panneau}
            </aside>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
