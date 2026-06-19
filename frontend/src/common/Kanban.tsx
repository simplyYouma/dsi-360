import { useState, type CSSProperties, type DragEvent } from 'react';
import { ZoomIn, ZoomOut } from 'lucide-react';
import { SablierSla } from './SablierSla';
import { AvatarPersonnage } from './AvatarPersonnage';
import { IndicateurDiscussion } from './IndicateurDiscussion';
import { BadgePriorite } from './statuts';
import { cx } from './cx';
import styles from './Kanban.module.css';

export interface CarteKanban {
  id: string;
  reference: string;
  titre: string;
  priorite: number | null;
  echeance: string | null;
  debut: string;
  statutSla: 'a_lheure' | 'approche' | 'depasse';
  meta: string | null; // demandeur ou gestionnaire (avatar)
  nbCommentaires: number;
}
export interface ColonneKanban {
  cle: string;
  titre: string;
  couleur: string;
  cartes: CarteKanban[];
}

interface Props {
  colonnes: ColonneKanban[];
  onOuvrir: (id: string) => void;
  /** Glisser-déposer : déplace une carte vers un statut cible (transition métier). */
  onDeplacer?: (id: string, statutCible: string) => void;
  /** Statuts cibles autorisés pour une carte donnée (transitions possibles). */
  ciblesValides?: (id: string) => Promise<string[]>;
}

const ZOOMS = [0.85, 1, 1.15, 1.3, 1.5];

/** Tableau Kanban présentationnel : colonnes par statut, cartes cliquables, zoom et
 *  glisser-déposer (les colonnes non autorisées sont estompées pendant le drag). */
export function Kanban({ colonnes, onOuvrir, onDeplacer, ciblesValides }: Props): JSX.Element {
  const [niveau, setNiveau] = useState(1);
  const zoom = ZOOMS[niveau] ?? 1;
  const [drag, setDrag] = useState<string | null>(null); // id de la carte tirée
  const [cibles, setCibles] = useState<Set<string>>(new Set()); // statuts acceptant le drop

  const dnd = onDeplacer !== undefined;

  const debuter = (e: DragEvent, id: string): void => {
    if (!dnd) return;
    e.dataTransfer.effectAllowed = 'move';
    setDrag(id);
    setCibles(new Set());
    if (ciblesValides) void ciblesValides(id).then((c) => setCibles(new Set(c)));
  };
  const finir = (): void => {
    setDrag(null);
    setCibles(new Set());
  };
  const deposer = (cle: string): void => {
    if (drag !== null && cibles.has(cle)) onDeplacer?.(drag, cle);
    finir();
  };

  return (
    <div className={styles.cadre}>
      <div className={styles.barre}>
        <button
          className={styles.zoomBtn}
          onClick={() => setNiveau((n) => Math.max(0, n - 1))}
          disabled={niveau === 0}
          title="Dézoomer"
        >
          <ZoomOut size={15} />
        </button>
        <span className={styles.zoomVal}>{Math.round(zoom * 100)} %</span>
        <button
          className={styles.zoomBtn}
          onClick={() => setNiveau((n) => Math.min(ZOOMS.length - 1, n + 1))}
          disabled={niveau === ZOOMS.length - 1}
          title="Zoomer"
        >
          <ZoomIn size={15} />
        </button>
      </div>

      <div className={styles.kanban} style={{ '--zoom': zoom } as CSSProperties}>
        {colonnes.map((col) => {
          const accepte = drag !== null && cibles.has(col.cle);
          const inerte = drag !== null && !cibles.has(col.cle);
          return (
            <section
              key={col.cle}
              className={cx(styles.colonne, accepte && styles.accepte, inerte && styles.inerte)}
              onDragOver={(e) => {
                if (accepte) e.preventDefault();
              }}
              onDrop={() => deposer(col.cle)}
            >
              <header className={styles.colTete}>
                <span className={styles.pastille} style={{ background: col.couleur }} />
                <span className={styles.colTitre}>{col.titre}</span>
                <span className={styles.colNb}>{col.cartes.length}</span>
              </header>
              <div className={styles.colCorps}>
                {col.cartes.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className={cx(styles.carte, drag === c.id && styles.tiree)}
                    draggable={dnd}
                    onDragStart={(e) => debuter(e, c.id)}
                    onDragEnd={finir}
                    onClick={() => onOuvrir(c.id)}
                  >
                    <span className={styles.accent} style={{ background: col.couleur }} />
                    <div className={styles.carteTete}>
                      <span className={styles.carteRef}>{c.reference}</span>
                      {c.priorite !== null && <BadgePriorite priorite={c.priorite} />}
                    </div>
                    <span className={styles.carteTitre} title={c.titre}>
                      {c.titre}
                    </span>
                    <div className={styles.carteBas}>
                      <SablierSla echeance={c.echeance} debut={c.debut} statut={c.statutSla} />
                      <span className={styles.carteMeta}>
                        <IndicateurDiscussion nombre={c.nbCommentaires} />
                        {c.meta !== null && (
                          <span title={c.meta}>
                            <AvatarPersonnage seed={c.meta} taille={20} />
                          </span>
                        )}
                      </span>
                    </div>
                  </button>
                ))}
                {col.cartes.length === 0 && <span className={styles.colVide}>Aucun</span>}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
