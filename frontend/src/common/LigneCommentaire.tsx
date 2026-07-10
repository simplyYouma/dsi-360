import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, CheckCheck, Pencil, X } from 'lucide-react';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { ImagesCommentaire } from '@/common/ImagesCommentaire';
import { cx } from '@/common/cx';
import { ChampMention } from '@/common/ChampMention';
import { TexteMentions } from '@/common/TexteMentions';
import {
  commentairesApi,
  type Commentaire,
  type LecteurCommentaire,
} from '@/common/commentairesApi';
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
  // La liste des lecteurs est demandée au serveur ; le compteur, lui, datait du chargement du fil.
  // Les deux doivent dire la même chose : dès qu'on connaît les noms, on compte les noms.
  const [nbVuesFrais, setNbVuesFrais] = useState<number | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const editRef = useRef<HTMLDivElement>(null);
  const accuseRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const estAuteur = moiId !== null && c.auteur_id === moiId;
  const nonVu = !estAuteur && !c.vu;
  const nbVues = nbVuesFrais ?? c.nb_vues;
  const lu = nbVues > 0;

  // À l'ouverture de l'édition, on amène le formulaire (et ses boutons) dans la vue.
  useEffect(() => {
    if (edition) editRef.current?.scrollIntoView({ block: 'nearest' });
  }, [edition]);

  // Popover discret ancré sous l'accusé (aucune modale) : on l'ouvre, on charge, on ferme au clic
  // extérieur ou au défilement. Pas d'Échap : la fiche l'écoute déjà et se fermerait avec.
  const LARGEUR_POP = 240;
  const ouvrirLecteurs = (): void => {
    if (lecteurs !== null) {
      setLecteurs(null);
      return;
    }
    const r = accuseRef.current?.getBoundingClientRect();
    if (r === undefined) return;
    setPos({
      top: r.bottom + 6,
      left: Math.max(6, Math.min(r.right - LARGEUR_POP, window.innerWidth - LARGEUR_POP - 6)),
    });
    setLecteurs([]);
    void commentairesApi.lecteurs(c.id).then((liste) => {
      setLecteurs(liste);
      setNbVuesFrais(liste.length);
    });
  };

  useEffect(() => {
    if (lecteurs === null) return;
    const dedans = (n: Node): boolean =>
      (accuseRef.current?.contains(n) ?? false) || (popRef.current?.contains(n) ?? false);
    const surClic = (e: MouseEvent): void => {
      if (!dedans(e.target as Node)) setLecteurs(null);
    };
    const surScroll = (e: Event): void => {
      if (!dedans(e.target as Node)) setLecteurs(null);
    };
    document.addEventListener('mousedown', surClic);
    window.addEventListener('scroll', surScroll, true);
    return () => {
      document.removeEventListener('mousedown', surClic);
      window.removeEventListener('scroll', surScroll, true);
    };
  }, [lecteurs]);

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
        {/* Accusé de lecture visible par tous (façon groupe de messagerie) : une coche = envoyé,
            deux coches vertes = vu par au moins une personne. */}
        {!edition && (
          <button
            ref={accuseRef}
            type="button"
            className={cx(styles.accuse, lu && styles.accuseLu)}
            onClick={ouvrirLecteurs}
            title={
              lu ? `Vu par ${nbVues} personne${nbVues > 1 ? 's' : ''}` : 'Envoyé — pas encore lu'
            }
            aria-label={lu ? 'Voir qui a lu ce message' : 'Message pas encore lu'}
          >
            {lu ? <CheckCheck size={15} /> : <Check size={15} />}
            {lu && <span className={styles.accuseNb}>{nbVues}</span>}
          </button>
        )}
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
        <>
          {c.texte !== '' && (
            <p className={fiche.commTexte}>
              <TexteMentions texte={c.texte} agents={agents} />
            </p>
          )}
          <ImagesCommentaire commentaireId={c.id} images={c.images} />
        </>
      )}
      {lecteurs !== null &&
        pos !== null &&
        createPortal(
          <div
            ref={popRef}
            className={styles.popLecteurs}
            style={{ position: 'fixed', top: pos.top, left: pos.left, width: LARGEUR_POP }}
            role="dialog"
            aria-label="Vu par"
          >
            <span className={styles.popTitre}>Vu par</span>
            {lecteurs.length === 0 ? (
              <p className={styles.videLecteurs}>Personne n’a encore vu ce message.</p>
            ) : (
              <ul className={styles.lecteurs}>
                {lecteurs.map((l, i) => (
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
          </div>,
          document.body,
        )}
    </li>
  );
}
