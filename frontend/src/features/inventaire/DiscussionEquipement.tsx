import { useCallback, useEffect, useState } from 'react';
import { useToast } from '@/design-system/primitives';
import { ComposeurDiscussion } from '@/common/ComposeurDiscussion';
import { LigneCommentaire } from '@/common/LigneCommentaire';
import { commentairesApi, type Commentaire } from '@/common/commentairesApi';
import { extraireMentions } from '@/common/useAgents';
import type { Agent } from '@/common/agentsApi';
import { useAuth } from '@/lib/auth';
import { ErreurApi, api } from '@/lib/api';
import fiche from '@/common/FicheTransition.module.css';

interface Props {
  equipementId: string | null;
  agents: Agent[];
}

/** Fil de discussion d'un équipement : même volet, mêmes règles que celui d'une activité.
 *
 *  Une panne récurrente, un déplacement, une décision de rebut se racontent ici — c'est la
 *  mémoire du matériel, que la fiche seule ne porte pas.
 */
export function DiscussionEquipement({ equipementId, agents }: Props): JSX.Element {
  const [commentaires, setCommentaires] = useState<Commentaire[]>([]);
  const [texte, setTexte] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const { moi } = useAuth();
  const { notifier } = useToast();

  const charger = useCallback(async (): Promise<void> => {
    if (equipementId === null) return;
    setCommentaires(await api.get<Commentaire[]>(`/commentaires/equipement/${equipementId}`));
  }, [equipementId]);

  useEffect(() => {
    setCommentaires([]);
    setTexte('');
    void charger();
  }, [charger]);

  // Les images restent réservées aux activités : rien ne se dépose sur un équipement.
  const envoyer = async (): Promise<void> => {
    if (equipementId === null || texte.trim() === '') return;
    setEnvoi(true);
    try {
      await api.post(`/commentaires/equipement/${equipementId}`, {
        texte: texte.trim(),
        mentions: extraireMentions(texte, agents),
      });
      setTexte('');
      await charger();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Envoi impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={fiche.panneauDiscussion}>
      <div className={fiche.panneauEntete}>
        <span className={fiche.panneauTitre}>Discussion interne (DSI)</span>
      </div>
      <div className={fiche.panneauFil}>
        {commentaires.length === 0 ? (
          <p className={fiche.commVide}>Aucun échange pour le moment.</p>
        ) : (
          <ul className={fiche.commListe}>
            {commentaires.map((c) => (
              <LigneCommentaire
                key={c.id}
                commentaire={c}
                moiId={moi?.id ?? null}
                agents={agents}
                onModifier={async (cid, t) => {
                  await commentairesApi.modifier(cid, t);
                  await charger();
                }}
                onSupprimer={async (cid) => {
                  await commentairesApi.supprimer(cid);
                  await charger();
                }}
              />
            ))}
          </ul>
        )}
      </div>
      <div className={fiche.panneauForm}>
        <ComposeurDiscussion
          valeur={texte}
          onChange={setTexte}
          agents={agents}
          placeholder="Ajouter un commentaire…  (@ pour mentionner)"
          envoi={envoi}
          onEnvoyer={envoyer}
        />
      </div>
    </div>
  );
}
