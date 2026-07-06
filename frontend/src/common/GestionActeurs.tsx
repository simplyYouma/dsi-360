import { X } from 'lucide-react';
import { SelecteurListe } from '@/common/SelecteurListe';
import styles from './GestionActeurs.module.css';

export interface Acteur {
  id: string;
  prenom: string;
  nom: string;
  email: string;
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
}

/** Gestion d'acteurs secondaires d'une activité (contributeurs, valideurs) : liste + ajout. */
export function GestionActeurs({
  acteurs,
  agents,
  exclureIds = [],
  onAjouter,
  onRetirer,
  placeholder,
  disabled = false,
}: Props): JSX.Element {
  const exclus = new Set([...exclureIds, ...acteurs.map((a) => a.id)]);
  return (
    <div>
      {acteurs.length > 0 && (
        <ul className={styles.liste}>
          {acteurs.map((a) => (
            <li key={a.id} className={styles.item}>
              <span>
                {a.prenom} {a.nom}
              </span>
              <button
                type="button"
                className={styles.retirer}
                disabled={disabled}
                onClick={() => onRetirer(a.id)}
                aria-label={`Retirer ${a.prenom} ${a.nom}`}
              >
                <X size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <SelecteurListe
        options={agents.filter((a) => !exclus.has(a.id)).map((a) => ({ valeur: a.id, libelle: a.nom }))}
        valeur={null}
        onChange={(v) => v !== null && onAjouter(v)}
        permettreVide={false}
        placeholder={placeholder}
      />
    </div>
  );
}
