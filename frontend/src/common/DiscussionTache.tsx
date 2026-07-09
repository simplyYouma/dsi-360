import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquare } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { ComposeurDiscussion } from '@/common/ComposeurDiscussion';
import { cx } from '@/common/cx';
import { IndicateurDiscussion } from '@/common/IndicateurDiscussion';
import { LigneCommentaire } from '@/common/LigneCommentaire';
import { commentairesApi, type Commentaire } from '@/common/commentairesApi';
import { extraireMentions, useAgents } from '@/common/useAgents';
import fiche from './FicheTransition.module.css';
import styles from './DiscussionTache.module.css';

interface Props {
  activiteId: string;
  tacheId: string;
  /** Compteur initial (évite un appel réseau tant que le fil est replié). */
  nombre?: number;
  /** Messages non lus par l'utilisateur connecté (marque colorée). */
  nonVus?: number;
  /** Appelé dès que le fil est marqué lu : la carte/ligne retire sa marque sans rechargement. */
  onVu?: (tacheId: string) => void;
}

/** Fil de discussion d'une tâche, replié par défaut. Le bouton porte la marque de discussion :
 *  colorée avec le compteur de non-lus, discrète une fois tout lu. */
export function DiscussionTache({
  activiteId,
  tacheId,
  nombre = 0,
  nonVus = 0,
  onVu,
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [commentaires, setCommentaires] = useState<Commentaire[] | null>(null);
  const [texte, setTexte] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [nonVusLocaux, setNonVusLocaux] = useState(nonVus);
  const agents = useAgents();
  const { moi } = useAuth();

  useEffect(() => setNonVusLocaux(nonVus), [nonVus]);

  // `onVu` est souvent une lambda : on la garde dans une ref pour ne pas relancer l'effet.
  const onVuRef = useRef(onVu);
  onVuRef.current = onVu;

  const charger = useCallback(async (): Promise<void> => {
    setCommentaires(await commentairesApi.lister(activiteId, tacheId));
    // Marque le fil comme lu, puis retire la marque « nouveaux » sans recharger la page.
    // Les repères « nouveau » sur chaque message restent visibles ce tour-ci.
    await commentairesApi.marquerVues(activiteId, tacheId);
    setNonVusLocaux(0);
    onVuRef.current?.(tacheId);
  }, [activiteId, tacheId]);

  useEffect(() => {
    if (ouvert && commentaires === null) void charger();
  }, [ouvert, commentaires, charger]);

  const envoyer = async (images: File[]): Promise<void> => {
    if (texte.trim() === '' && images.length === 0) return;
    setEnvoi(true);
    try {
      const mentions = extraireMentions(texte, agents);
      if (images.length > 0) {
        await commentairesApi.ajouterAvecImages(activiteId, texte.trim(), images, tacheId, mentions);
      } else {
        await commentairesApi.ajouter(activiteId, texte.trim(), tacheId, mentions);
      }
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
        className={styles.bascule}
        onClick={() => setOuvert((o) => !o)}
        aria-expanded={ouvert}
      >
        {ouvert ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <MessageSquare size={13} />
        Discussion
        <span className={styles.marque}>
          <IndicateurDiscussion nombre={total} nonVus={nonVusLocaux} />
        </span>
      </button>
      {ouvert && (
        <div className={styles.corps}>
          {commentaires !== null && commentaires.length === 0 && (
            <p className={cx(fiche.commVide, styles.vide)}>Aucun échange sur cette tâche.</p>
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
          <ComposeurDiscussion
            valeur={texte}
            onChange={setTexte}
            agents={agents}
            placeholder="Commenter cette tâche…  (@ pour mentionner)"
            envoi={envoi}
            onEnvoyer={envoyer}
          />
        </div>
      )}
    </div>
  );
}
