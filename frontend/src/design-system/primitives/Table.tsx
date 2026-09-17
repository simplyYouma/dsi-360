import { useMemo, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import {
  ChevronDown,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Check,
  Trash2,
} from 'lucide-react';
import { cx } from '@/common/cx';
import { Skeleton } from './Skeleton';
import styles from './Table.module.css';

export interface SelectionTable {
  selectionnes: Set<string>;
  onBasculer: (id: string) => void;
  onTout: (ids: string[], tout: boolean) => void;
}

function Case({
  coche,
  onClick,
}: {
  coche: boolean;
  onClick: (e: MouseEvent) => void;
}): JSX.Element {
  return (
    <button
      type="button"
      className={coche ? styles.caseCochee : styles.case}
      onClick={onClick}
      aria-label="Sélectionner"
    >
      {coche && <Check size={13} />}
    </button>
  );
}

export interface Colonne<T> {
  cle: string;
  entete: string;
  /** Rendu de la cellule (sinon valeur brute). */
  rendu?: (ligne: T) => ReactNode;
  /** Clé de tri (active le tri sur la colonne). */
  valeur?: (ligne: T) => string | number;
  aligne?: 'droite' | 'centre';
  largeur?: string;
  /** Tronque le contenu avec « … » (le détail reste visible au clic / en infobulle). */
  tronque?: boolean;
}

/** Suppression d'une ligne, offerte par le tableau lui-même.
 *
 * Elle vit ici et non dans chaque page : le geste le plus destructeur de l'application doit avoir
 * partout la même place, la même discrétion et le même poids visuel. Neuf listes qui le dessinent
 * chacune à sa façon, c'est neuf occasions de le confondre avec autre chose.
 *
 * Le tableau ne décide de rien : la page dit S'IL est offert (l'administrateur seul, en pratique),
 * et confirme avant d'agir. */
export interface SuppressionTable<T> {
  onSupprimer: (ligne: T) => void;
  /** Ce que l'infobulle annonce — nommer la ligne évite d'effacer la voisine. */
  titre?: (ligne: T) => string;
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
  selection?: SelectionTable;
  /** Classe CSS additionnelle par ligne (ex. mise en évidence d'un SLA dépassé). */
  classeLigne?: (ligne: T) => string | undefined;
  /** Colonne de suppression en fin de ligne. Non fournie — ou `undefined` pour qui n'administre
   *  pas : aucune colonne, aucune place perdue. */
  suppression?: SuppressionTable<T> | undefined;
}

// Largeur exacte de la colonne de sélection (cf. Table.module.css) : décalage de la colonne figée.
const LARGEUR_SELECTION = 44;

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
  selection,
  classeLigne,
  suppression,
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
  const idsPage = lignesTriees.map(cleLigne);
  const toutCoche =
    selection !== undefined &&
    idsPage.length > 0 &&
    idsPage.every((id) => selection.selectionnes.has(id));
  const nbColonnes = colonnes.length + (selection ? 1 : 0) + (suppression ? 1 : 0);

  return (
    <div className={styles.cadre}>
      <div className={styles.zone}>
        <table className={styles.table}>
          <thead>
            <tr>
              {selection && (
                <th className={cx(styles.selCol, styles.figee)} style={{ left: 0 }}>
                  <Case coche={toutCoche} onClick={() => selection.onTout(idsPage, !toutCoche)} />
                </th>
              )}
              {colonnes.map((c, i) => {
                const actif = tri?.cle === c.cle;
                // La première colonne (souvent la référence) reste visible au défilement.
                const figee = i === 0;
                const styleEntete: Record<string, string | number> = {};
                if (c.largeur !== undefined) styleEntete.width = c.largeur;
                if (figee) styleEntete.left = selection ? LARGEUR_SELECTION : 0;
                return (
                  <th
                    key={c.cle}
                    style={styleEntete}
                    className={cx(
                      c.aligne === 'droite' && styles.droite,
                      c.aligne === 'centre' && styles.centre,
                      c.valeur !== undefined && styles.triable,
                      figee && styles.figee,
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
              {suppression && <th className={styles.supprCol} aria-label="Supprimer" />}
            </tr>
          </thead>
          <tbody>
            {chargement ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={`squelette-${i}`}>
                  {colonnes.map((c) => (
                    <td key={c.cle}>
                      <Skeleton largeur="68%" />
                    </td>
                  ))}
                  {suppression && <td className={styles.supprCol} />}
                </tr>
              ))
            ) : lignesTriees.length === 0 ? (
              <tr>
                <td colSpan={nbColonnes} className={styles.message}>
                  {vide ?? 'Aucun élément.'}
                </td>
              </tr>
            ) : (
              lignesTriees.map((ligne) => {
                const id = cleLigne(ligne);
                const coche = selection?.selectionnes.has(id) ?? false;
                return (
                  <tr
                    key={id}
                    className={cx(
                      onLigne && styles.cliquable,
                      coche && styles.ligneCochee,
                      classeLigne?.(ligne),
                    )}
                    onClick={onLigne ? () => onLigne(ligne) : undefined}
                  >
                    {selection && (
                      <td className={cx(styles.selCol, styles.figee)} style={{ left: 0 }}>
                        <Case
                          coche={coche}
                          onClick={(e) => {
                            e.stopPropagation();
                            selection.onBasculer(id);
                          }}
                        />
                      </td>
                    )}
                    {colonnes.map((c, i) => {
                      const figee = i === 0;
                      return (
                        <td
                          key={c.cle}
                          style={figee ? { left: selection ? LARGEUR_SELECTION : 0 } : undefined}
                          className={cx(
                            c.aligne === 'droite' && styles.droite,
                            c.aligne === 'centre' && styles.centre,
                            c.tronque && styles.tronque,
                            figee && styles.figee,
                          )}
                        >
                          {c.rendu
                            ? c.rendu(ligne)
                            : String((ligne as Record<string, unknown>)[c.cle] ?? '')}
                        </td>
                      );
                    })}
                    {suppression && (
                      <td className={styles.supprCol}>
                        <button
                          type="button"
                          className={styles.supprimer}
                          title={suppression.titre?.(ligne) ?? 'Supprimer'}
                          aria-label={suppression.titre?.(ligne) ?? 'Supprimer'}
                          onClick={(e) => {
                            // Sans cela, effacer une ligne ouvrirait d'abord sa fiche.
                            e.stopPropagation();
                            suppression.onSupprimer(ligne);
                          }}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })
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
