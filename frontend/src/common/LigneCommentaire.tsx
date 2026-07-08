import { useState } from 'react';
import { Pencil } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { ChampMention } from '@/common/ChampMention';
import { TexteMentions } from '@/common/TexteMentions';
import type { Commentaire } from '@/common/commentairesApi';
import type { AgentRef } from '@/common/useAgents';
import fiche from './FicheTransition.module.css';
import styles from './LigneCommentaire.module.css';

interface Props {
  commentaire: Commentaire;
  moiId: string | null;
  agents: AgentRef[];
  onModifier: (id: number, texte: string) => Promise<void>;
  onSupprimer: (id: number) => Promise<void>;
}

/** Un commentaire de discussion : affichage, marque « modifié », édition/suppression par l'auteur. */
export function LigneCommentaire({
  commentaire: c,
  moiId,
  agents,
  onModifier,
  onSupprimer,
}: Props): JSX.Element {
  const [edition, setEdition] = useState(false);
  const [texte, setTexte] = useState(c.texte);
  const [envoi, setEnvoi] = useState(false);
  const estAuteur = moiId !== null && c.auteur_id === moiId;

  const enregistrer = async (): Promise<void> => {
    if (texte.trim() === '' || texte.trim() === c.texte) {
      setEdition(false);
      return;
    }
    setEnvoi(true);
    try {
      await onModifier(c.id, texte.trim());
      setEdition(false);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <li className={fiche.commItem}>
      <div className={fiche.commTete}>
        <span className={fiche.commAuteur}>{c.auteur}</span>
        <span className={fiche.commDate}>
          {new Date(c.cree_le).toLocaleString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })}
          {c.edite && <span className={styles.modifie}> · modifié</span>}
        </span>
        {estAuteur && !edition && (
          <span className={styles.actions}>
            <button
              type="button"
              className={styles.action}
              title="Modifier"
              aria-label="Modifier le commentaire"
              onClick={() => {
                setTexte(c.texte);
                setEdition(true);
              }}
            >
              <Pencil size={13} />
            </button>
            <BoutonSupprimer
              cible="ce commentaire"
              onSupprimer={() => onSupprimer(c.id)}
              className={styles.action}
              taille={13}
            />
          </span>
        )}
      </div>
      {edition ? (
        <div className={styles.edition}>
          <ChampMention valeur={texte} onChange={setTexte} agents={agents} rows={2} />
          <div className={styles.boutons}>
            <Button variante="secondaire" onClick={() => setEdition(false)} disabled={envoi}>
              Annuler
            </Button>
            <Button onClick={() => void enregistrer()} disabled={envoi || texte.trim() === ''}>
              {envoi ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </div>
      ) : (
        <p className={fiche.commTexte}>
          <TexteMentions texte={c.texte} agents={agents} />
        </p>
      )}
    </li>
  );
}
