import { useCallback, useEffect, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Button, Modale, StatusBadge } from '@/design-system/primitives';
import { api, ErreurApi } from '@/lib/api';

interface Detail {
  reference: string;
  titre: string;
  statut: string;
  description: string | null;
  transitions_possibles: string[];
}

interface FicheTransitionProps {
  /** Base de l'API (ex. "/changements"). */
  base: string;
  /** Identifiant de l'activité ouverte, ou null si la fiche est fermée. */
  id: string | null;
  onFermer: () => void;
  /** Appelé après une transition réussie (pour rafraîchir la liste). */
  onChange: () => void;
}

/** Fiche d'une activité : informations + boutons de transition d'état (machine à états serveur). */
export function FicheTransition({ base, id, onFermer, onChange }: FicheTransitionProps): JSX.Element {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async (): Promise<void> => {
    if (id === null) return;
    setDetail(null);
    setErreur(null);
    setDetail(await api.get<Detail>(`${base}/${id}`));
  }, [base, id]);

  useEffect(() => {
    void charger();
  }, [charger]);

  const transitionner = async (vers: string): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const maj = await api.post<Detail>(`${base}/${id}/transition`, { vers });
      setDetail(maj);
      onChange();
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Transition impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Modale
      ouverte={id !== null}
      onFermer={onFermer}
      titre={detail ? detail.reference : 'Fiche'}
      pied={
        <Button variante="secondaire" onClick={onFermer}>
          Fermer
        </Button>
      }
    >
      {detail === null ? (
        <p style={{ color: 'var(--text-muted)' }}>Chargement…</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <strong style={{ fontSize: 'var(--text-base)' }}>{detail.titre}</strong>
            <StatusBadge>{detail.statut}</StatusBadge>
          </div>
          {detail.description !== null && detail.description !== '' && (
            <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
              {detail.description}
            </p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>Faire évoluer vers</span>
            {detail.transitions_possibles.length === 0 ? (
              <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
                Aucune transition disponible (état final).
              </span>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                {detail.transitions_possibles.map((vers) => (
                  <Button
                    key={vers}
                    variante="secondaire"
                    disabled={envoi}
                    onClick={() => void transitionner(vers)}
                  >
                    <ArrowRight size={15} />
                    {vers}
                  </Button>
                ))}
              </div>
            )}
          </div>

          {erreur !== null && (
            <p style={{ color: 'var(--status-danger)', fontSize: 'var(--text-sm)' }}>{erreur}</p>
          )}
        </div>
      )}
    </Modale>
  );
}
