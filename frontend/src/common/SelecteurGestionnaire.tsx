import { useEffect, useState } from 'react';
import { SelecteurListe } from './SelecteurListe';
import { chargerAgents, type Agent } from './agentsApi';
import styles from './SelecteurGestionnaire.module.css';

interface Props {
  valeur: string | null;
  onChange: (id: string | null) => void;
  /** Clé d'accès du module : n'affiche que les agents qui peuvent ouvrir cette activité. */
  module?: string | undefined;
}

/** Champ « Gestionnaire » (responsable DSI) autonome : libellé + sélecteur d'agents. Se masque
 *  s'il n'y a pas d'agents (ou pas d'accès). Partagé entre création et édition pour un comportement
 *  identique partout. */
export function SelecteurGestionnaire({ valeur, onChange, module }: Props): JSX.Element | null {
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    void chargerAgents(module)
      .then(setAgents)
      .catch(() => setAgents([]));
  }, [module]);

  if (agents.length === 0) return null;
  return (
    <div className={styles.champ}>
      <span className={styles.label}>Gestionnaire</span>
      <SelecteurListe
        options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
        valeur={valeur}
        onChange={onChange}
        permettreVide
        libelleVide="Non assigné"
        placeholder="Assigner à un agent DSI…"
      />
    </div>
  );
}
