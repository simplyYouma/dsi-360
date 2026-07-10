import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Button, Modale } from '@/design-system/primitives';

interface Props {
  /** Ce qui va être supprimé, lisible : « la tâche “Documenter” », « ce lien »… */
  cible: string;
  onSupprimer: () => void | Promise<void>;
  /** Classe du bouton icône (réutilise le style de l'appelant). */
  className?: string | undefined;
  taille?: number;
}

/** Suppression JAMAIS automatique : icône corbeille -> confirmation explicite avant d'agir. */
export function BoutonSupprimer({
  cible,
  onSupprimer,
  className,
  taille = 15,
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [envoi, setEnvoi] = useState(false);

  const confirmer = async (): Promise<void> => {
    setEnvoi(true);
    try {
      await onSupprimer();
      setOuvert(false);
    } finally {
      setEnvoi(false);
    }
  };

  const [survol, setSurvol] = useState(false);

  return (
    <>
      <button
        type="button"
        className={className}
        title="Supprimer"
        aria-label={`Supprimer ${cible}`}
        // Survol rouge garanti quel que soit le style de l'appelant (inline > classe).
        style={survol ? { color: 'var(--status-danger)' } : undefined}
        onMouseEnter={() => setSurvol(true)}
        onMouseLeave={() => setSurvol(false)}
        onFocus={() => setSurvol(true)}
        onBlur={() => setSurvol(false)}
        onClick={() => setOuvert(true)}
      >
        <Trash2 size={taille} />
      </button>
      <Modale
        ouverte={ouvert}
        onFermer={() => setOuvert(false)}
        titre="Confirmer la suppression"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setOuvert(false)} disabled={envoi}>
              Annuler
            </Button>
            <Button variante="danger" onClick={() => void confirmer()} disabled={envoi}>
              {envoi ? 'Suppression…' : 'Supprimer'}
            </Button>
          </>
        }
      >
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text)' }}>
          Supprimer {cible} ? Cette action est définitive.
        </p>
      </Modale>
    </>
  );
}
