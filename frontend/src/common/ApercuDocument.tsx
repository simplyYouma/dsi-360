import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Download, ZoomIn, ZoomOut, RotateCw } from 'lucide-react';
import styles from './ApercuDocument.module.css';

interface Props {
  url: string;
  type: string;
  nom: string;
  onFermer: () => void;
  onTelecharger?: () => void;
}

const ECHELLE_MIN = 0.25;
const ECHELLE_MAX = 4;
const PAS = 0.25;

/** Aperçu plein écran d'un document (image / PDF) sans quitter la fiche. Overlay dédié : sa touche
 *  Échap est captée en amont pour ne fermer que l'aperçu (pas la modale en dessous). Zoom + rotation
 *  pour les images. */
export function ApercuDocument({ url, type, nom, onFermer, onTelecharger }: Props): JSX.Element {
  const [echelle, setEchelle] = useState(1);
  const [rotation, setRotation] = useState(0);

  const estImage = type.startsWith('image/');
  const estPdf = type === 'application/pdf';

  // Réinitialise zoom/rotation à chaque nouveau document.
  useEffect(() => {
    setEchelle(1);
    setRotation(0);
  }, [url]);

  useEffect(() => {
    const surTouche = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.stopImmediatePropagation();
        onFermer();
      }
    };
    document.addEventListener('keydown', surTouche, true); // capture : passe avant la modale
    return () => document.removeEventListener('keydown', surTouche, true);
  }, [onFermer]);

  return createPortal(
    <div className={styles.overlay} onMouseDown={onFermer}>
      <div className={styles.boite} onMouseDown={(e) => e.stopPropagation()}>
        <header className={styles.tete}>
          <span className={styles.nom} title={nom}>
            {nom}
          </span>
          <div className={styles.actions}>
            {estImage && (
              <>
                <button
                  type="button"
                  className={styles.bouton}
                  onClick={() => setEchelle((e) => Math.max(ECHELLE_MIN, +(e - PAS).toFixed(2)))}
                  disabled={echelle <= ECHELLE_MIN}
                  aria-label="Dézoomer"
                  title="Dézoomer"
                >
                  <ZoomOut size={18} />
                </button>
                <span className={styles.zoom}>{Math.round(echelle * 100)} %</span>
                <button
                  type="button"
                  className={styles.bouton}
                  onClick={() => setEchelle((e) => Math.min(ECHELLE_MAX, +(e + PAS).toFixed(2)))}
                  disabled={echelle >= ECHELLE_MAX}
                  aria-label="Zoomer"
                  title="Zoomer"
                >
                  <ZoomIn size={18} />
                </button>
                <button
                  type="button"
                  className={styles.bouton}
                  onClick={() => setRotation((r) => (r + 90) % 360)}
                  aria-label="Pivoter"
                  title="Pivoter"
                >
                  <RotateCw size={18} />
                </button>
                <span className={styles.separateur} />
              </>
            )}
            {onTelecharger && (
              <button
                type="button"
                className={styles.bouton}
                onClick={onTelecharger}
                aria-label="Télécharger"
                title="Télécharger"
              >
                <Download size={18} />
              </button>
            )}
            <button
              type="button"
              className={styles.bouton}
              onClick={onFermer}
              aria-label="Fermer"
              title="Fermer"
            >
              <X size={18} />
            </button>
          </div>
        </header>
        <div className={styles.corps}>
          {estImage ? (
            <img
              src={url}
              alt={nom}
              className={styles.image}
              style={{ transform: `rotate(${rotation}deg) scale(${echelle})` }}
            />
          ) : estPdf ? (
            <iframe src={url} title={nom} className={styles.cadre} />
          ) : (
            <div className={styles.nonApercu}>
              <p>Aperçu non disponible pour ce type de fichier.</p>
              {onTelecharger && (
                <button type="button" className={styles.telecharger} onClick={onTelecharger}>
                  <Download size={16} /> Télécharger
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
