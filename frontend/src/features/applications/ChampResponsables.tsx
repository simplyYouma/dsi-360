import { useState } from 'react';
import { Check, UserPlus, UserRound, X } from 'lucide-react';
import { SelecteurListe } from '@/common/SelecteurListe';
import type { Agent } from '@/common/agentsApi';
import styles from './ChampResponsables.module.css';
import type { ResponsableApplication } from './applicationsApi';

interface Props {
  valeur: ResponsableApplication[];
  agents: Agent[];
  onChange: (personnes: ResponsableApplication[]) => void;
  /** Grisé : la liste reste lisible, l'ajout et le retrait sont fermés. */
  desactive?: boolean;
  titreDesactive?: string | undefined;
  /** Ce qu'on attend ici (ex. « le relais »), repris dans l'invite de saisie. */
  indication?: string;
}

/** Les personnes qui répondent d'une application : autant qu'il en faut, prises dans l'annuaire
 *  ou écrites à la main.
 *
 *  Les deux voies coexistent parce que la réalité les impose : un agent de la maison se désigne
 *  par son compte — la fiche suit alors son nom s'il change — mais l'interlocuteur est souvent un
 *  prestataire ou une adresse de support, qui n'aura jamais de compte ici.
 *
 *  La saisie libre vit **dans la liste**, en pied de son menu, et non dans un champ voisin : le
 *  geste appartient là où l'on cherche quelqu'un. Un second champ à côté obligeait à le repérer,
 *  et laissait croire à deux réglages distincts.
 */
export function ChampResponsables({
  valeur,
  agents,
  onChange,
  desactive = false,
  titreDesactive,
  indication,
}: Props): JSX.Element {
  const [saisie, setSaisie] = useState(false);
  const [nom, setNom] = useState('');

  const dejaPris = new Set(valeur.map((p) => p.utilisateur_id ?? p.nom.trim().toLowerCase()));

  const ajouterCompte = (id: string | null): void => {
    if (id === null) return;
    const agent = agents.find((a) => a.id === id);
    if (agent === undefined || dejaPris.has(id)) return;
    onChange([...valeur, { utilisateur_id: id, nom: agent.nom }]);
  };

  const validerSaisie = (): void => {
    const propre = nom.trim();
    setSaisie(false);
    setNom('');
    if (propre === '' || dejaPris.has(propre.toLowerCase())) return;
    onChange([...valeur, { utilisateur_id: null, nom: propre }]);
  };

  const annulerSaisie = (): void => {
    setSaisie(false);
    setNom('');
  };

  return (
    <div className={styles.bloc} title={desactive ? titreDesactive : undefined}>
      {valeur.length > 0 ? (
        <ul className={styles.jetons}>
          {valeur.map((p, i) => (
            <li key={`${p.utilisateur_id ?? p.nom}-${i}`} className={styles.jeton}>
              {/* Un compte de l'annuaire porte sa marque : on voit d'un coup d'œil qui est
                  rattaché et qui n'est qu'un nom. */}
              <span
                className={p.utilisateur_id !== null ? styles.marqueCompte : styles.marque}
                title={p.utilisateur_id !== null ? 'Compte de l’annuaire' : 'Nom saisi'}
              >
                <UserRound size={13} />
              </span>
              <span className={styles.nom} title={p.nom}>
                {p.nom}
              </span>
              {!desactive && (
                <button
                  type="button"
                  className={styles.retirer}
                  onClick={() => onChange(valeur.filter((_, j) => j !== i))}
                  aria-label={`Retirer ${p.nom}`}
                >
                  <X size={12} />
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <span className={styles.vide}>Personne de désigné</span>
      )}

      {!desactive &&
        (saisie ? (
          <span className={styles.saisie}>
            <input
              autoFocus
              value={nom}
              placeholder={indication ?? 'Nom (prestataire, support…)'}
              onChange={(e) => setNom(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') validerSaisie();
                if (e.key === 'Escape') annulerSaisie();
              }}
              maxLength={160}
            />
            <button
              type="button"
              className={styles.ok}
              onClick={validerSaisie}
              aria-label="Valider le nom"
            >
              <Check size={14} />
            </button>
            <button
              type="button"
              className={styles.annuler}
              onClick={annulerSaisie}
              aria-label="Annuler"
            >
              <X size={14} />
            </button>
          </span>
        ) : (
          <SelecteurListe
            options={agents
              .filter((a) => !dejaPris.has(a.id))
              .map((a) => ({ valeur: a.id, libelle: a.nom }))}
            valeur={null}
            onChange={ajouterCompte}
            placeholder="Ajouter une personne…"
            action={{
              libelle: 'Saisir un nom (prestataire, support…)',
              icone: UserPlus,
              onClick: () => setSaisie(true),
            }}
          />
        ))}
    </div>
  );
}
