import { useState } from 'react';
import { Plus, UserRound, X } from 'lucide-react';
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
  /** Ce qu'on attend ici, en une ligne (ex. « Le relais, s'il existe »). */
  indication?: string;
}

/** Les personnes qui répondent d'une application : autant qu'il en faut, prises dans l'annuaire
 *  ou écrites à la main.
 *
 *  Les deux voies coexistent parce que la réalité les impose : un agent de la maison se désigne
 *  par son compte — la fiche suit alors son nom s'il change — mais l'interlocuteur est souvent un
 *  prestataire ou une adresse de support, qui n'aura jamais de compte ici. Interdire l'un ou
 *  l'autre reviendrait à laisser la case vide, c'est-à-dire à ne plus savoir qui appeler.
 */
export function ChampResponsables({
  valeur,
  agents,
  onChange,
  desactive = false,
  titreDesactive,
  indication,
}: Props): JSX.Element {
  const [libre, setLibre] = useState('');

  const dejaPris = new Set(
    valeur.map((p) => (p.utilisateur_id ?? p.nom.trim().toLowerCase())),
  );

  const ajouterCompte = (id: string | null): void => {
    if (id === null) return;
    const agent = agents.find((a) => a.id === id);
    if (agent === undefined || dejaPris.has(id)) return;
    onChange([...valeur, { utilisateur_id: id, nom: agent.nom }]);
  };

  const ajouterLibre = (): void => {
    const nom = libre.trim();
    if (nom === '' || dejaPris.has(nom.toLowerCase())) {
      setLibre('');
      return;
    }
    onChange([...valeur, { utilisateur_id: null, nom }]);
    setLibre('');
  };

  const retirer = (index: number): void => {
    onChange(valeur.filter((_, i) => i !== index));
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
                  onClick={() => retirer(i)}
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

      {!desactive && (
        <div className={styles.ajout}>
          <div className={styles.selecteur}>
            <SelecteurListe
              options={agents
                .filter((a) => !dejaPris.has(a.id))
                .map((a) => ({ valeur: a.id, libelle: a.nom }))}
              valeur={null}
              onChange={ajouterCompte}
              placeholder="Choisir dans l’annuaire…"
            />
          </div>
          <div className={styles.libre}>
            <input
              value={libre}
              onChange={(e) => setLibre(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  ajouterLibre();
                }
              }}
              placeholder={indication ?? 'ou saisir un nom…'}
              maxLength={160}
            />
            <button
              type="button"
              className={styles.ajouter}
              onClick={ajouterLibre}
              disabled={libre.trim() === ''}
            >
              <Plus size={14} />
              Ajouter
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
