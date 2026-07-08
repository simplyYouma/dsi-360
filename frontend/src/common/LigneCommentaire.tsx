import { useEffect, useRef, useState } from 'react';
import { Check, Eye, Pencil, X } from 'lucide-react';
import { Button, Modale } from '@/design-system/primitives';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { cx } from '@/common/cx';
import { ChampMention } from '@/common/ChampMention';
import { TexteMentions } from '@/common/TexteMentions';
import { commentairesApi, type Commentaire, type LecteurCommentaire } from '@/common/commentairesApi';
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
  const [lecteurs, setLecteurs] = useState<LecteurCommentaire[] | null>(null);
  const editRef = useRef<HTMLDivElement>(null);
  const estAuteur = moiId !== null && c.auteur_id === moiId;
  const nonVu = !estAuteur && !c.vu;

  // À l'ouverture de l'édition, on amène le formulaire (et ses boutons) dans la vue.
  useEffect(() => {
    if (edition) editRef.current?.scrollIntoView({ block: 'nearest' });
  }, [edition]);

  const ouvrirLecteurs = (): void => {
    setLecteurs([]);
    void commentairesApi.lecteurs(c.id).then(setLecteurs);
  };

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
    <li className={cx(fiche.commItem, nonVu && styles.nonVu)}>
      <div className={fiche.commTete}>
        <span className={fiche.commAuteur}>
          {c.auteur}
          {nonVu && <span className={styles.nouveau}>nouveau</span>}
        </span>
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
        <div ref={editRef} className={styles.edition}>
          <ChampMention
            valeur={texte}
            onChange={setTexte}
            agents={agents}
            rows={2}
            onEnvoyer={() => void enregistrer()}
          />
          <div className={styles.editActions}>
            <button
              type="button"
              className={styles.editIcon}
              title="Enregistrer"
              aria-label="Enregistrer la modification"
              onClick={() => void enregistrer()}
              disabled={envoi || texte.trim() === ''}
            >
              <Check size={16} />
            </button>
            <button
              type="button"
              className={cx(styles.editIcon, styles.editAnnuler)}
              title="Annuler"
              aria-label="Annuler la modification"
              onClick={() => setEdition(false)}
              disabled={envoi}
            >
              <X size={16} />
            </button>
          </div>
        </div>
      ) : (
        <p className={fiche.commTexte}>
          <TexteMentions texte={c.texte} agents={agents} />
        </p>
      )}
      {/* Vues : sur ses propres messages, discret, cliquable pour voir qui a lu. */}
      {estAuteur && !edition && c.nb_vues > 0 && (
        <button type="button" className={styles.vues} onClick={ouvrirLecteurs} title="Voir les vues">
          <Eye size={12} />
          {c.nb_vues}
        </button>
      )}
      <Modale
        ouverte={lecteurs !== null}
        onFermer={() => setLecteurs(null)}
        titre="Vu par"
        largeur={360}
        pied={
          <Button variante="secondaire" onClick={() => setLecteurs(null)}>
            Fermer
          </Button>
        }
      >
        {lecteurs !== null && lecteurs.length === 0 ? (
          <p className={styles.videLecteurs}>Personne n’a encore vu ce message.</p>
        ) : (
          <ul className={styles.lecteurs}>
            {(lecteurs ?? []).map((l, i) => (
              <li key={i}>
                <span>{l.nom}</span>
                <span className={styles.lecteurDate}>
                  {new Date(l.vu_le).toLocaleString('fr-FR', {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Modale>
    </li>
  );
}
