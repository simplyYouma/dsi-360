import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquare, Send } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { useAuth } from '@/lib/auth';
import { ChampMention } from '@/common/ChampMention';
import { LigneCommentaire } from '@/common/LigneCommentaire';
import { commentairesApi, type Commentaire } from '@/common/commentairesApi';
import { extraireMentions, useAgents } from '@/common/useAgents';
import fiche from './FicheTransition.module.css';

interface Props {
  activiteId: string;
  tacheId: string;
  /** Compteur initial (évite un appel réseau tant que le fil est replié). */
  nombre?: number;
}

/** Fil de discussion d'une tâche, replié par défaut (bouton avec compteur). */
export function DiscussionTache({ activiteId, tacheId, nombre = 0 }: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [commentaires, setCommentaires] = useState<Commentaire[] | null>(null);
  const [texte, setTexte] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const agents = useAgents();
  const { moi } = useAuth();

  const charger = useCallback(async (): Promise<void> => {
    setCommentaires(await commentairesApi.lister(activiteId, tacheId));
    // Marque le fil comme lu (sans recharger : les repères « nouveau » restent visibles ce tour).
    void commentairesApi.marquerVues(activiteId, tacheId);
  }, [activiteId, tacheId]);

  useEffect(() => {
    if (ouvert && commentaires === null) void charger();
  }, [ouvert, commentaires, charger]);

  const envoyer = async (): Promise<void> => {
    if (texte.trim() === '') return;
    setEnvoi(true);
    try {
      await commentairesApi.ajouter(
        activiteId,
        texte.trim(),
        tacheId,
        extraireMentions(texte, agents),
      );
      setTexte('');
      await charger();
    } finally {
      setEnvoi(false);
    }
  };

  const total = commentaires?.length ?? nombre;

  return (
    <div>
      <button
        type="button"
        onClick={() => setOuvert((o) => !o)}
        aria-expanded={ouvert}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 'var(--space-1)',
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          color: 'var(--text-muted)',
          fontSize: 'var(--text-xs)',
        }}
      >
        {ouvert ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <MessageSquare size={13} />
        Discussion{total > 0 ? ` (${total})` : ''}
      </button>
      {ouvert && (
        <div style={{ marginTop: 'var(--space-2)' }}>
          {commentaires !== null && commentaires.length === 0 && (
            <p className={fiche.commVide} style={{ marginBottom: 'var(--space-3)' }}>
              Aucun échange sur cette tâche.
            </p>
          )}
          {commentaires !== null && commentaires.length > 0 && (
            <ul className={fiche.commListe}>
              {commentaires.map((c) => (
                <LigneCommentaire
                  key={c.id}
                  commentaire={c}
                  moiId={moi?.id ?? null}
                  agents={agents}
                  onModifier={async (id, t) => {
                    await commentairesApi.modifier(id, t);
                    await charger();
                  }}
                  onSupprimer={async (id) => {
                    await commentairesApi.supprimer(id);
                    await charger();
                  }}
                />
              ))}
            </ul>
          )}
          <div className={fiche.commForm}>
            <ChampMention
              valeur={texte}
              onChange={setTexte}
              agents={agents}
              placeholder="Commenter cette tâche…  (@ pour mentionner)"
              onEnvoyer={() => void envoyer()}
            />
            <Button onClick={() => void envoyer()} disabled={envoi || texte.trim() === ''}>
              <Send size={14} />
              {envoi ? 'Envoi…' : 'Commenter'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
