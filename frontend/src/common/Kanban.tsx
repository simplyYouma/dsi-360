import { useState, type CSSProperties } from 'react';
import { ZoomIn, ZoomOut } from 'lucide-react';
import { SablierSla } from './SablierSla';
import { AvatarPersonnage } from './AvatarPersonnage';
import { IndicateurDiscussion } from './IndicateurDiscussion';
import { BadgePriorite } from './statuts';
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

const ZOOMS = [0.85, 1, 1.15, 1.3, 1.5];

/** Tableau Kanban présentationnel : colonnes par statut, cartes cliquables, zoom intégré. */
export function Kanban({
  colonnes,
  onOuvrir,
}: {
  colonnes: ColonneKanban[];
  onOuvrir: (id: string) => void;
}): JSX.Element {
  const [niveau, setNiveau] = useState(1); // index dans ZOOMS
  const zoom = ZOOMS[niveau] ?? 1;

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
        {colonnes.map((col) => (
          <section key={col.cle} className={styles.colonne}>
            <header className={styles.colTete}>
              <span className={styles.pastille} style={{ background: col.couleur }} />
              <span className={styles.colTitre}>{col.titre}</span>
              <span className={styles.colNb}>{col.cartes.length}</span>
            </header>
            <div className={styles.colCorps}>
              {col.cartes.map((c) => (
                <button key={c.id} type="button" className={styles.carte} onClick={() => onOuvrir(c.id)}>
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
        ))}
      </div>
    </div>
  );
}
