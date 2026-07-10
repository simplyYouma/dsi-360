import { useCallback, useState, type CSSProperties, type DragEvent } from 'react';
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from 'lucide-react';
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
  nbNonVus?: number;
  /** Étiquette optionnelle (ex. domaine/module) affichée sur la carte. */
  etiquette?: { texte: string; couleur: string };
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
  /** Espace de stockage pour mémoriser les colonnes repliées (un par tableau). */
  cleStockage?: string;
}

const ZOOMS = [0.85, 1, 1.15, 1.3, 1.5];

const SLA_COULEUR: Record<CarteKanban['statutSla'], string> = {
  a_lheure: 'var(--status-ok)',
  approche: 'var(--status-warn)',
  depasse: 'var(--status-danger)',
};

function lireReplie(cle: string): Set<string> {
  try {
    const brut = localStorage.getItem(`kanban-replie:${cle}`);
    return new Set(brut ? (JSON.parse(brut) as string[]) : []);
  } catch {
    return new Set();
  }
}

/** Fine barre de répartition SLA des cartes d'une colonne (à l'heure / proche / dépassé). */
function BarreSlaColonne({ cartes }: { cartes: CarteKanban[] }): JSX.Element | null {
  if (cartes.length === 0) return null;
  const compte = { a_lheure: 0, approche: 0, depasse: 0 };
  cartes.forEach((c) => (compte[c.statutSla] += 1));
  const segments = (Object.keys(compte) as CarteKanban['statutSla'][])
    .map((k) => ({ k, v: compte[k] }))
    .filter((s) => s.v > 0);
  return (
    <div
      className={styles.slaBarre}
      title={`À l'heure ${compte.a_lheure} · échéance proche ${compte.approche} · dépassé ${compte.depasse}`}
    >
      {segments.map((s) => (
        <span key={s.k} style={{ flexGrow: s.v, background: SLA_COULEUR[s.k] }} />
      ))}
    </div>
  );
}

/** Tableau Kanban présentationnel : colonnes par statut, cartes cliquables, zoom,
 *  glisser-déposer, colonnes repliables et en-têtes collants. */
export function Kanban({
  colonnes,
  onOuvrir,
  onDeplacer,
  ciblesValides,
  cleStockage = 'defaut',
}: Props): JSX.Element {
  const [niveau, setNiveau] = useState(1);
  const zoom = ZOOMS[niveau] ?? 1;
  const [drag, setDrag] = useState<string | null>(null); // id de la carte tirée
  const [cibles, setCibles] = useState<Set<string>>(new Set()); // statuts acceptant le drop
  const [replie, setReplie] = useState<Set<string>>(() => lireReplie(cleStockage));

  const dnd = onDeplacer !== undefined;

  const basculerRepli = useCallback(
    (cle: string): void => {
      setReplie((prev) => {
        const suivant = new Set(prev);
        if (suivant.has(cle)) suivant.delete(cle);
        else suivant.add(cle);
        try {
          localStorage.setItem(`kanban-replie:${cleStockage}`, JSON.stringify([...suivant]));
        } catch {
          /* stockage indisponible : on garde l'état en mémoire seulement. */
        }
        return suivant;
      });
    },
    [cleStockage],
  );

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
          if (replie.has(col.cle)) {
            return (
              <button
                key={col.cle}
                type="button"
                className={cx(styles.colonne, styles.colonneReplie)}
                onClick={() => basculerRepli(col.cle)}
                title="Déplier la colonne"
              >
                <ChevronRight size={15} className={styles.replieChevron} />
                <span className={styles.pastille} style={{ background: col.couleur }} />
                <span className={styles.colTitreV}>{col.titre}</span>
                <span className={styles.colNb}>{col.cartes.length}</span>
              </button>
            );
          }
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
                <div className={styles.colTeteHaut}>
                  <span className={styles.pastille} style={{ background: col.couleur }} />
                  <span className={styles.colTitre}>{col.titre}</span>
                  <span className={styles.colNb}>{col.cartes.length}</span>
                  <button
                    type="button"
                    className={styles.replierBtn}
                    onClick={() => basculerRepli(col.cle)}
                    title="Replier la colonne"
                  >
                    <ChevronLeft size={15} />
                  </button>
                </div>
                <BarreSlaColonne cartes={col.cartes} />
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
                    <div className={styles.carteTete}>
                      <span className={styles.carteRef}>{c.reference}</span>
                      {c.priorite !== null && <BadgePriorite priorite={c.priorite} />}
                    </div>
                    <span className={styles.carteTitre} title={c.titre}>
                      {c.titre}
                    </span>
                    {c.etiquette && (
                      <span className={styles.carteEtiquette}>
                        <span
                          className={styles.etiquettePoint}
                          style={{ background: c.etiquette.couleur }}
                        />
                        {c.etiquette.texte}
                      </span>
                    )}
                    <div className={styles.carteBas}>
                      <SablierSla echeance={c.echeance} debut={c.debut} statut={c.statutSla} />
                      <span className={styles.carteMeta}>
                        <IndicateurDiscussion nombre={c.nbCommentaires} nonVus={c.nbNonVus ?? 0} />
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
