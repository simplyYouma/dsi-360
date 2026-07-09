import { useEffect, useState } from 'react';
import { Users, X } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { SelecteurListe } from './SelecteurListe';
import { chargerAgents, type Agent } from './agentsApi';
import styles from './DispatchBar.module.css';

interface Props {
  count: number;
  onAssigner: (responsableId: string | null) => Promise<void>;
  onEffacer: () => void;
  /** Clé d'accès du module : seuls ses agents peuvent recevoir ces tickets. */
  module: string;
}

/** Barre de dispatch en lot : assigne les tickets sélectionnés à un gestionnaire DSI. */
export function DispatchBar({ count, onAssigner, onEffacer, module }: Props): JSX.Element {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agent, setAgent] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    void chargerAgents(module).then(setAgents);
  }, [module]);

  const assigner = async (): Promise<void> => {
    setEnvoi(true);
    try {
      await onAssigner(agent);
      setAgent(null);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.barre}>
      <span className={styles.compte}>
        <Users size={16} />
        {count} sélectionné{count > 1 ? 's' : ''}
      </span>
      <div className={styles.select}>
        <SelecteurListe
          options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
          valeur={agent}
          onChange={setAgent}
          placeholder="Assigner à…"
        />
      </div>
      <Button disabled={agent === null || envoi} onClick={() => void assigner()}>
        {envoi ? 'Assignation…' : 'Assigner'}
      </Button>
      <button type="button" className={styles.effacer} onClick={onEffacer} aria-label="Effacer la sélection">
        <X size={16} />
      </button>
    </div>
  );
}
