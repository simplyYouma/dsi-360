import { useState } from 'react';
import { Plus, Repeat2, X } from 'lucide-react';
import { SelecteurListe } from '@/common/SelecteurListe';
import styles from './GestionActeurs.module.css';

export interface Acteur {
  id: string;
  prenom: string;
  nom: string;
  email: string;
  decision?: string | null;
}

interface OptionAgent {
  id: string;
  nom: string;
}

interface Props {
  acteurs: Acteur[];
  agents: OptionAgent[];
  /** Identifiants à exclure des options d'ajout (ex. gestionnaire + déjà présents). */
  exclureIds?: string[];
  onAjouter: (id: string) => void;
  onRetirer: (id: string) => void;
  placeholder: string;
  disabled?: boolean;
  /** Acteurs qui tranchent (valideurs) : affiche « En attente » tant qu'ils n'ont pas décidé. */
  avecDecision?: boolean;
  /** Seul l'administrateur désigne : les autres voient la liste, sans ajout ni retrait. */
  lectureSeule?: boolean;
  /** Plusieurs titulaires possibles (contributeurs). Le « + » reste un ajout, jamais un
   *  remplacement. Faux pour les valideurs, qui restent uniques. */
  plusieurs?: boolean;
}

/** Acteur secondaire d'une activité.
 *
 *  Deux régimes, et l'icône dit lequel :
 *  - **contributeurs** (`plusieurs`) : le « + » AJOUTE. Ils sont plusieurs depuis le 07/09/2026 —
 *    un dossier mobilise couramment plusieurs appuis.
 *  - **valideurs** : un seul titulaire. Vide, le « + » désigne ; occupé, l'icône devient une
 *    réaffectation — nommer remplace, et la décision du prédécesseur ne l'engage pas. */
export function GestionActeurs({
  acteurs,
  agents,
  exclureIds = [],
  onAjouter,
  onRetirer,
  placeholder,
  disabled = false,
  avecDecision = false,
  lectureSeule = false,
  plusieurs = false,
}: Props): JSX.Element {
  const [ajout, setAjout] = useState(false);
  // Le geste n'est un remplacement que sur un rôle à titulaire unique déjà pourvu.
  const remplace = !plusieurs && acteurs.length > 0;
  const exclus = new Set([...exclureIds, ...acteurs.map((a) => a.id)]);
  const options = agents
    .filter((a) => !exclus.has(a.id))
    .map((a) => ({ valeur: a.id, libelle: a.nom }));

  return (
    <div className={styles.bloc}>
      <ul className={styles.liste}>
        {acteurs.map((a) => (
          <li key={a.id} className={styles.item}>
            <span>
              {a.prenom} {a.nom}
            </span>
            {a.decision === 'APPROUVE' && <span className={styles.approuve}>Approuvé</span>}
            {a.decision === 'REJETE' && <span className={styles.rejete}>Rejeté</span>}
            {avecDecision && !a.decision && <span className={styles.attente}>En attente</span>}
            {!lectureSeule && (
              <button
                type="button"
                className={styles.retirer}
                disabled={disabled}
                onClick={() => onRetirer(a.id)}
                aria-label={`Retirer ${a.prenom} ${a.nom}`}
              >
                <X size={13} />
              </button>
            )}
          </li>
        ))}
        {acteurs.length === 0 && lectureSeule && <li className={styles.item}>—</li>}
        {!ajout && !lectureSeule && (
          <li>
            <button
              type="button"
              className={styles.ajouter}
              disabled={disabled || options.length === 0}
              onClick={() => setAjout(true)}
              title={remplace ? 'Réaffecter' : placeholder}
              aria-label={remplace ? 'Réaffecter' : placeholder}
            >
              {remplace ? <Repeat2 size={14} /> : <Plus size={14} />}
            </button>
          </li>
        )}
      </ul>

      {ajout && (
        <div className={styles.zoneAjout}>
          <SelecteurListe
            options={options}
            valeur={null}
            onChange={(v) => {
              if (v !== null) onAjouter(v);
              setAjout(false);
            }}
            permettreVide={false}
            placeholder={placeholder}
          />
          <button
            type="button"
            className={styles.annuler}
            onClick={() => setAjout(false)}
            aria-label="Annuler l’ajout"
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
