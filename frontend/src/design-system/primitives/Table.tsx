import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { ChevronDown, ChevronsUpDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { cx } from '@/common/cx';
import styles from './Table.module.css';

export interface Colonne<T> {
  cle: string;
  entete: string;
  /** Rendu de la cellule (sinon valeur brute). */
  rendu?: (ligne: T) => ReactNode;
  /** Clé de tri (active le tri sur la colonne). */
  valeur?: (ligne: T) => string | number;
  aligne?: 'droite' | 'centre';
  largeur?: string;
}

export interface Pagination {
  page: number;
  total: number;
  taille: number;
  onPage: (page: number) => void;
}

interface TableProps<T> {
  colonnes: Colonne<T>[];
  lignes: T[];
  cleLigne: (ligne: T) => string;
  vide?: ReactNode;
  chargement?: boolean;
  onLigne?: (ligne: T) => void;
  pagination?: Pagination;
}

function pagesAffichees(courante: number, nb: number): (number | '…')[] {
  if (nb <= 7) return Array.from({ length: nb }, (_, i) => i + 1);
  const set = new Set([1, nb, courante, courante - 1, courante + 1]);
  const tri = [...set].filter((p) => p >= 1 && p <= nb).sort((a, b) => a - b);
  const sortie: (number | '…')[] = [];
  let prec = 0;
  for (const p of tri) {
    if (p - prec > 1) sortie.push('…');
    sortie.push(p);
    prec = p;
  }
  return sortie;
}

/** Tableau commun : en-tête figé, survol doux, tri par colonne, état vide, pagination numérotée. */
export function Table<T>({
  colonnes,
  lignes,
  cleLigne,
  vide,
  chargement = false,
  onLigne,
  pagination,
}: TableProps<T>): JSX.Element {
  const [tri, setTri] = useState<{ cle: string; sens: 1 | -1 } | null>(null);

  const lignesTriees = useMemo(() => {
    if (tri === null) return lignes;
    const col = colonnes.find((c) => c.cle === tri.cle);
    const valeur = col?.valeur;
    if (valeur === undefined) return lignes;
    return [...lignes].sort((a, b) => {
      const va = valeur(a);
      const vb = valeur(b);
      if (va < vb) return -tri.sens;
      if (va > vb) return tri.sens;
      return 0;
    });
  }, [lignes, tri, colonnes]);

  const basculerTri = (col: Colonne<T>): void => {
    if (col.valeur === undefined) return;
    setTri((t) =>
      t !== null && t.cle === col.cle
        ? { cle: col.cle, sens: t.sens === 1 ? -1 : 1 }
        : { cle: col.cle, sens: 1 },
    );
  };

  const nbPages = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.taille)) : 1;

  return (
    <div className={styles.cadre}>
      <div className={styles.zone}>
        <table className={styles.table}>
          <thead>
            <tr>
              {colonnes.map((c) => {
                const actif = tri?.cle === c.cle;
                return (
                  <th
                    key={c.cle}
                    style={c.largeur !== undefined ? { width: c.largeur } : undefined}
                    className={cx(
                      c.aligne === 'droite' && styles.droite,
                      c.aligne === 'centre' && styles.centre,
                      c.valeur !== undefined && styles.triable,
                    )}
                    onClick={() => basculerTri(c)}
                  >
                    <span className={styles.enteteContenu}>
                      {c.entete}
                      {c.valeur !== undefined &&
                        (actif ? (
                          <ChevronDown
                            size={14}
                            className={cx(styles.caret, tri?.sens === -1 && styles.caretInverse)}
                          />
                        ) : (
                          <ChevronsUpDown size={14} className={styles.caretInactif} />
                        ))}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {chargement ? (
              <tr>
                <td colSpan={colonnes.length} className={styles.message}>
                  Chargement…
                </td>
              </tr>
            ) : lignesTriees.length === 0 ? (
              <tr>
                <td colSpan={colonnes.length} className={styles.message}>
                  {vide ?? 'Aucun élément.'}
                </td>
              </tr>
            ) : (
              lignesTriees.map((ligne) => (
                <tr
                  key={cleLigne(ligne)}
                  className={onLigne ? styles.cliquable : undefined}
                  onClick={onLigne ? () => onLigne(ligne) : undefined}
                >
                  {colonnes.map((c) => (
                    <td
                      key={c.cle}
                      className={cx(
                        c.aligne === 'droite' && styles.droite,
                        c.aligne === 'centre' && styles.centre,
                      )}
                    >
                      {c.rendu ? c.rendu(ligne) : String((ligne as Record<string, unknown>)[c.cle] ?? '')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination && nbPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageNav}
            disabled={pagination.page <= 1}
            onClick={() => pagination.onPage(pagination.page - 1)}
            aria-label="Page précédente"
          >
            <ChevronLeft size={16} />
          </button>
          {pagesAffichees(pagination.page, nbPages).map((p, i) =>
            p === '…' ? (
              <span key={`e${i}`} className={styles.ellipse}>
                …
              </span>
            ) : (
              <button
                key={p}
                className={p === pagination.page ? styles.pageActive : styles.page}
                onClick={() => pagination.onPage(p)}
              >
                {p}
              </button>
            ),
          )}
          <button
            className={styles.pageNav}
            disabled={pagination.page >= nbPages}
            onClick={() => pagination.onPage(pagination.page + 1)}
            aria-label="Page suivante"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
