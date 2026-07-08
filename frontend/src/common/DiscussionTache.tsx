import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquare, Send } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { ChampMention } from '@/common/ChampMention';
import { commentairesApi, type Commentaire } from '@/common/commentairesApi';
import { extraireMentions, useAgents } from '@/common/useAgents';
import { TexteMentions } from '@/common/TexteMentions';
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

  const charger = useCallback(async (): Promise<void> => {
    setCommentaires(await commentairesApi.lister(activiteId, tacheId));
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
            <p className={fiche.commVide}>Aucun échange sur cette tâche.</p>
          )}
          {commentaires !== null && commentaires.length > 0 && (
            <ul className={fiche.commListe}>
              {commentaires.map((c) => (
                <li key={c.id} className={fiche.commItem}>
                  <div className={fiche.commTete}>
                    <span className={fiche.commAuteur}>{c.auteur}</span>
                    <span className={fiche.commDate}>
                      {new Date(c.cree_le).toLocaleString('fr-FR', {
                        day: '2-digit',
                        month: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                  <p className={fiche.commTexte}>
                    <TexteMentions texte={c.texte} agents={agents} />
                  </p>
                </li>
              ))}
            </ul>
          )}
          <div className={fiche.commForm}>
            <ChampMention
              className={fiche.commInput}
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
