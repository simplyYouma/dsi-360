import { UserPlus } from 'lucide-react';
import styles from './CelluleActeur.module.css';

interface Props {
  /** Gestionnaire / chef de projet / responsable — le nom principal, ou null. */
  nom: string | null;
  /** Premier contributeur. Affiché en seconde ligne discrète s'il existe. */
  contributeur?: string | null;
  /** Combien ils sont en tout. Au-delà d'un, la cellule le dit : « Awa Touré +2 ». */
  nbContributeurs?: number;
  /** Libellé montré quand aucun responsable (« Non assigné », « — »…). */
  vide?: string;
}

/**
 * Cellule d'acteur d'une liste : le responsable, et — sous lui, en retrait — le contributeur
 * quand il y en a un. On voit qui suit le dossier sans ajouter de colonne ni allonger le tableau.
 *
 * Les contributeurs pouvant être plusieurs, n'en montrer qu'un sans le dire ferait mentir la
 * liste par omission : le « +N » rétablit la vérité sans prendre plus de place.
 */
export function CelluleActeur({
  nom,
  contributeur,
  nbContributeurs = 0,
  vide = 'Non assigné',
}: Props): JSX.Element {
  const autres = Math.max(0, nbContributeurs - 1);
  return (
    <div className={styles.cellule}>
      <span className={nom ? styles.nom : styles.vide}>{nom ?? vide}</span>
      {contributeur != null && contributeur !== '' && (
        <span
          className={styles.contrib}
          title={
            autres > 0
              ? `Contributeurs : ${contributeur} et ${autres} autre${autres > 1 ? 's' : ''}`
              : `Contributeur : ${contributeur}`
          }
        >
          <UserPlus size={12} aria-hidden="true" />
          {contributeur}
          {autres > 0 && <span className={styles.autres}>+{autres}</span>}
        </span>
      )}
    </div>
  );
}
