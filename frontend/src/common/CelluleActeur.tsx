import { UserPlus } from 'lucide-react';
import styles from './CelluleActeur.module.css';

interface Props {
  /** Gestionnaire / chef de projet / responsable — le nom principal, ou null. */
  nom: string | null;
  /** Contributeur (au plus un). Affiché en seconde ligne discrète s'il existe. */
  contributeur?: string | null;
  /** Libellé montré quand aucun responsable (« Non assigné », « — »…). */
  vide?: string;
}

/**
 * Cellule d'acteur d'une liste : le responsable, et — sous lui, en retrait — le contributeur
 * quand il y en a un. On voit qui suit le dossier sans ajouter de colonne ni allonger le tableau.
 */
export function CelluleActeur({ nom, contributeur, vide = 'Non assigné' }: Props): JSX.Element {
  return (
    <div className={styles.cellule}>
      <span className={nom ? styles.nom : styles.vide}>{nom ?? vide}</span>
      {contributeur != null && contributeur !== '' && (
        <span className={styles.contrib} title={`Contributeur : ${contributeur}`}>
          <UserPlus size={12} aria-hidden="true" />
          {contributeur}
        </span>
      )}
    </div>
  );
}
