import { useState, type ReactNode } from 'react';
import { Button, Modale } from '@/design-system/primitives';

/** Une action à confirmer : titre, message, libellé du bouton, et ce qu'on fait si l'on confirme. */
export interface DemandeConfirmation {
  titre: string;
  message: ReactNode;
  libelleConfirmer: string;
  /** `danger` (rouge) pour une action clôturante ou définitive ; `primaire` sinon. */
  variante?: 'primaire' | 'danger';
  action: () => void | Promise<void>;
}

interface Props {
  /** La demande en cours, ou `null` quand aucune confirmation n'est ouverte. */
  demande: DemandeConfirmation | null;
  onFermer: () => void;
}

/** Modale de confirmation générique : aucune action sensible ne s'exécute sans un clic explicite.
 *  Pilotée par une `demande` (état de l'appelant) plutôt que par un bouton, pour couvrir aussi bien
 *  une décision de valideur qu'une transition clôturante. */
export function ModaleConfirmation({ demande, onFermer }: Props): JSX.Element {
  const [envoi, setEnvoi] = useState(false);

  const confirmer = async (): Promise<void> => {
    if (demande === null) return;
    setEnvoi(true);
    try {
      await demande.action();
      onFermer();
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Modale
      ouverte={demande !== null}
      onFermer={onFermer}
      titre={demande?.titre ?? ''}
      pied={
        <>
          <Button variante="secondaire" onClick={onFermer} disabled={envoi}>
            Annuler
          </Button>
          <Button
            variante={demande?.variante ?? 'primaire'}
            onClick={() => void confirmer()}
            disabled={envoi}
          >
            {envoi ? 'En cours…' : (demande?.libelleConfirmer ?? 'Confirmer')}
          </Button>
        </>
      }
    >
      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text)' }}>{demande?.message}</div>
    </Modale>
  );
}
