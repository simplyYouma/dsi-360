import { useState } from 'react';
import { Plus, X, Check, MoreHorizontal } from 'lucide-react';
import { useToast } from '@/design-system/primitives';
import { ErreurApi } from '@/lib/api';
import { cx } from './cx';
import { categoriesApi } from './categoriesApi';
import styles from './SelecteurCategorie.module.css';

export interface OptionCategorie {
  id: string;
  libelle: string;
  /** Code technique (ex. type de changement) — sert au mappage de couleur optionnel. */
  code?: string;
}

interface Props {
  categories: OptionCategorie[];
  valeur: string | null;
  onChange: (id: string | null) => void;
  /** Couleur sémantique par code (ex. types de changement). Optionnel : sinon rendu neutre. */
  couleurs?: Record<string, string>;
  /** Module — requis pour la gestion inline des catégories (ajout/suppression). */
  module?: string;
  /** Ajout sur mesure : fournir cette fonction branche le sélecteur sur un autre référentiel
   *  (emplacements, départements…) plutôt que sur les catégories. */
  onAjouter?: (libelle: string) => Promise<OptionCategorie>;
  /** Suppression sur mesure. Sans elle, la croix ne s'affiche pas : on ne propose pas une
   *  action qu'on ne sait pas exécuter. */
  onSupprimer?: (id: string) => Promise<void>;
  /** Nom de la chose, pour les libellés (« Ajouter un emplacement », « Emplacement ajouté »). */
  entite?: string;
  /** Autorise l'ajout/suppression inline (réservé aux profils Administration). */
  gerable?: boolean;
  /** Recharge la liste des catégories après ajout/suppression. */
  onModifie?: () => void;
  /** Grisé : la sélection reste lisible, on ne peut plus la changer. */
  desactive?: boolean;
  /** Raison du grisage, en infobulle. */
  titreDesactive?: string;
}

/** Sélecteur de catégorie en pastilles (chips). Cliquer sélectionne / désélectionne (facultatif).
 *  Avec `gerable` + `module`, un Administrateur peut ajouter/supprimer une catégorie sans quitter
 *  la modale. Partagé entre modules pour garantir la cohérence des formulaires. */
export function SelecteurCategorie({
  categories,
  valeur,
  onChange,
  couleurs,
  module,
  gerable,
  onModifie,
  onAjouter,
  onSupprimer,
  entite = 'catégorie',
  desactive = false,
  titreDesactive,
}: Props): JSX.Element | null {
  const { notifier } = useToast();
  const [ajout, setAjout] = useState(false);
  const [nouveau, setNouveau] = useState('');
  const [enCours, setEnCours] = useState(false);
  const [tout, setTout] = useState(false);
  const gestion = gerable === true && (module !== undefined || onAjouter !== undefined);
  // Le référentiel d'inventaire s'alimente à l'import : on n'y propose pas la suppression, qui
  // détacherait des équipements sans le dire. La croix ne paraît que si l'on sait supprimer.
  const supprimable = gestion && (onSupprimer !== undefined || module !== undefined);

  if (categories.length === 0 && !gestion) return null;

  // On ne déroule que les trois premières : une longue liste encombre la fiche. La sélection
  // reste toujours visible (on la fait remonter), et « … » révèle le reste à la demande.
  const LIMITE = 3;
  const trop = !tout && categories.length > LIMITE + 1;
  let visibles = categories;
  if (trop) {
    const tete = categories.slice(0, LIMITE);
    const choisie = categories.find((c) => c.id === valeur);
    visibles =
      choisie !== undefined && !tete.some((c) => c.id === choisie.id)
        ? [choisie, ...tete.slice(0, LIMITE - 1)]
        : tete;
  }
  const restant = categories.length - visibles.length;

  const ajouter = async (): Promise<void> => {
    const libelle = nouveau.trim();
    if (libelle === '') return;
    setEnCours(true);
    try {
      const creee =
        onAjouter !== undefined
          ? await onAjouter(libelle)
          : module !== undefined
            ? await categoriesApi.creer(module, libelle)
            : null;
      if (creee === null) return;
      setNouveau('');
      setAjout(false);
      onModifie?.();
      onChange(creee.id);
      notifier(`${entite[0]?.toUpperCase()}${entite.slice(1)} ajouté(e)`, 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Ajout impossible.', 'erreur');
    } finally {
      setEnCours(false);
    }
  };

  const supprimer = async (id: string): Promise<void> => {
    setEnCours(true);
    try {
      if (onSupprimer !== undefined) await onSupprimer(id);
      else await categoriesApi.supprimer(id);
      if (valeur === id) onChange(null);
      onModifie?.();
      notifier(`${entite[0]?.toUpperCase()}${entite.slice(1)} supprimé(e)`, 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Suppression impossible.', 'erreur');
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className={styles.chips} role="listbox" aria-label={entite}>
      {visibles.map((c) => {
        const actif = c.id === valeur;
        const coul = c.code !== undefined && couleurs !== undefined ? couleurs[c.code] : undefined;
        const style =
          coul === undefined
            ? undefined
            : actif
              ? { background: coul, color: '#fff', borderColor: coul }
              : { color: coul, borderColor: `color-mix(in srgb, ${coul} 35%, var(--border))` };
        return (
          <span key={c.id} className={styles.chipWrap}>
            <button
              type="button"
              role="option"
              aria-selected={actif}
              className={cx(
                styles.chip,
                actif && coul === undefined && styles.chipActif,
                gestion && styles.chipGerable,
              )}
              style={style}
              onClick={() => onChange(actif ? null : c.id)}
              disabled={desactive}
              title={desactive ? titreDesactive : undefined}
            >
              {c.libelle}
            </button>
            {supprimable && (
              <button
                type="button"
                className={styles.suppr}
                disabled={enCours}
                aria-label={`Supprimer : ${c.libelle}`}
                title="Supprimer"
                onClick={() => void supprimer(c.id)}
              >
                <X size={12} />
              </button>
            )}
          </span>
        );
      })}

      {trop && (
        <button
          type="button"
          className={styles.plus}
          onClick={() => setTout(true)}
          title={`Voir ${restant} de plus`}
          aria-label={`Voir ${restant} de plus`}
        >
          <MoreHorizontal size={14} />
          <span className={styles.plusNb}>{restant}</span>
        </button>
      )}
      {tout && categories.length > LIMITE + 1 && (
        <button
          type="button"
          className={styles.plus}
          onClick={() => setTout(false)}
          title="Réduire la liste"
          aria-label="Réduire la liste"
        >
          Réduire
        </button>
      )}

      {gestion &&
        (ajout ? (
          <span className={styles.ajoutForm}>
            <input
              autoFocus
              className={styles.ajoutInput}
              value={nouveau}
              onChange={(e) => setNouveau(e.target.value)}
              placeholder={`Nouvel élément — ${entite}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void ajouter();
                } else if (e.key === 'Escape') {
                  setAjout(false);
                  setNouveau('');
                }
              }}
            />
            <button
              type="button"
              className={styles.ajoutOk}
              disabled={enCours || nouveau.trim() === ''}
              onClick={() => void ajouter()}
              aria-label="Valider"
            >
              <Check size={14} />
            </button>
            <button
              type="button"
              className={styles.ajoutAnnuler}
              onClick={() => {
                setAjout(false);
                setNouveau('');
              }}
              aria-label="Annuler"
            >
              <X size={14} />
            </button>
          </span>
        ) : (
          <button
            type="button"
            className={styles.ajoutBtn}
            onClick={() => setAjout(true)}
            title={`Ajouter — ${entite}`}
          >
            <Plus size={14} />
            Ajouter
          </button>
        ))}
    </div>
  );
}
