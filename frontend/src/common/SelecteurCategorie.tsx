import { useState } from 'react';
import { Plus, X, Check } from 'lucide-react';
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
  /** Module — requis pour la gestion inline (ajout/suppression). */
  module?: string;
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
  desactive = false,
  titreDesactive,
}: Props): JSX.Element | null {
  const { notifier } = useToast();
  const [ajout, setAjout] = useState(false);
  const [nouveau, setNouveau] = useState('');
  const [enCours, setEnCours] = useState(false);
  const gestion = gerable === true && module !== undefined;

  if (categories.length === 0 && !gestion) return null;

  const ajouter = async (): Promise<void> => {
    const libelle = nouveau.trim();
    if (libelle === '' || module === undefined) return;
    setEnCours(true);
    try {
      const creee = await categoriesApi.creer(module, libelle);
      setNouveau('');
      setAjout(false);
      onModifie?.();
      onChange(creee.id);
      notifier('Catégorie ajoutée', 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Ajout impossible.', 'erreur');
    } finally {
      setEnCours(false);
    }
  };

  const supprimer = async (id: string): Promise<void> => {
    setEnCours(true);
    try {
      await categoriesApi.supprimer(id);
      if (valeur === id) onChange(null);
      onModifie?.();
      notifier('Catégorie supprimée', 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Suppression impossible.', 'erreur');
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className={styles.chips} role="listbox" aria-label="Catégorie">
      {categories.map((c) => {
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
            {gestion && (
              <button
                type="button"
                className={styles.suppr}
                disabled={enCours}
                aria-label={`Supprimer la catégorie ${c.libelle}`}
                title="Supprimer"
                onClick={() => void supprimer(c.id)}
              >
                <X size={12} />
              </button>
            )}
          </span>
        );
      })}

      {gestion &&
        (ajout ? (
          <span className={styles.ajoutForm}>
            <input
              autoFocus
              className={styles.ajoutInput}
              value={nouveau}
              onChange={(e) => setNouveau(e.target.value)}
              placeholder="Nouvelle catégorie"
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
              aria-label="Valider la catégorie"
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
            title="Ajouter une catégorie"
          >
            <Plus size={14} />
            Ajouter
          </button>
        ))}
    </div>
  );
}
