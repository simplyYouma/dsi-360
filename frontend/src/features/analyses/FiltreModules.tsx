import styles from './FiltreModules.module.css';

/** Les modules d'activité analysables, dans l'ordre où on les lit ailleurs dans l'application.
 *  La clé est celle que porte `core.activite.module` — c'est elle que le serveur attend. */
export const MODULES_ANALYSE: { cle: string; libelle: string }[] = [
  { cle: 'incident', libelle: 'Incidents' },
  { cle: 'demande', libelle: 'Demandes' },
  { cle: 'projet', libelle: 'Projets' },
  { cle: 'changement', libelle: 'Changements' },
  { cle: 'audit', libelle: 'Audit' },
  { cle: 'risque', libelle: 'Risques' },
  { cle: 'cybersecurite', libelle: 'Cybersécurité' },
  { cle: 'gouvernance', libelle: 'Gouvernance' },
];

interface Props {
  valeur: string[];
  onChange: (modules: string[]) => void;
}

/** Choix des modules regardés : rien de coché = tout est regardé.
 *
 *  Des pastilles à cocher plutôt qu'une liste déroulante : sur un tableau de bord, ce qu'on
 *  regarde doit se lire sans ouvrir quoi que ce soit — et se corriger d'un clic.
 */
export function FiltreModules({ valeur, onChange }: Props): JSX.Element {
  const basculer = (cle: string): void => {
    onChange(valeur.includes(cle) ? valeur.filter((m) => m !== cle) : [...valeur, cle]);
  };

  return (
    <div className={styles.barre}>
      <span className={styles.intitule}>Modules</span>
      {MODULES_ANALYSE.map((m) => {
        const retenu = valeur.includes(m.cle);
        return (
          <button
            key={m.cle}
            type="button"
            className={retenu ? styles.puceOn : styles.puce}
            onClick={() => basculer(m.cle)}
            aria-pressed={retenu}
          >
            {m.libelle}
          </button>
        );
      })}
      {/* Aucun bouton « Tous » permanent : sans sélection, tout est déjà regardé. Le retour à la
          vue complète n'apparaît donc que lorsqu'il y a quelque chose à annuler. */}
      {valeur.length > 0 && (
        <button type="button" className={styles.tout} onClick={() => onChange([])}>
          Tout afficher
        </button>
      )}
    </div>
  );
}
