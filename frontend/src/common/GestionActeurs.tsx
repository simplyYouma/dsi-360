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
}

/** Acteur secondaire d'une activité (contributeur, valideur) : un seul titulaire par rôle.
 *  Vide, le « + » désigne ; occupé, l'icône devient une réaffectation — nommer remplace. */
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
}: Props): JSX.Element {
  const [ajout, setAjout] = useState(false);
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
              title={acteurs.length > 0 ? 'Réaffecter' : placeholder}
              aria-label={acteurs.length > 0 ? 'Réaffecter' : placeholder}
            >
              {acteurs.length > 0 ? <Repeat2 size={14} /> : <Plus size={14} />}
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
