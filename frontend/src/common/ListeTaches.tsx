import { useEffect, useRef, useState, type ReactNode } from 'react';
import { GripVertical, Plus } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { SelecteurDate } from '@/common/SelecteurDate';
import { SelecteurListe } from '@/common/SelecteurListe';
import { cx } from '@/common/cx';
import {
  COULEUR_STATUT_TACHE,
  STATUTS_TACHE,
  type MajTache,
  type NouvelleTache,
  type StatutTache,
  type Tache,
} from '@/common/tacheTypes';
import styles from './ListeTaches.module.css';

interface OptionAgent {
  valeur: string;
  libelle: string;
}

interface Props {
  taches: Tache[];
  agents: OptionAgent[];
  onAjouter: (corps: NouvelleTache) => Promise<void>;
  onMaj: (id: string, corps: MajTache) => Promise<void>;
  onSupprimer: (id: string) => Promise<void>;
  /** Persiste le nouvel ordre (glisser-déposer). Sans lui, la poignée n'apparaît pas. */
  onReordonner?: (ids: string[]) => Promise<void>;
  /** Contenu additionnel par tâche, en pied de carte (ex. discussion). */
  renduEnfant?: (tache: Tache) => ReactNode;
  /** Contenu rattaché au titre, en tête de carte (ex. liens utiles). */
  renduSousTitre?: (tache: Tache) => ReactNode;
  /** Acteur de travail (admin, gestionnaire, contributeur) : organise les tâches. */
  peutTravailler?: boolean;
  /** Identifiant de l'utilisateur : l'assigné d'une tâche en change le statut, rien d'autre. */
  moiId?: string | null;
}

const RESERVE_AUX_ACTEURS =
  'Réservé au gestionnaire, aux contributeurs et à l’administrateur.';

/** Pastille d'état d'échéance d'une tâche non terminée : dépassée (rouge) / proche (ambre). */
function EtatEcheance({ tache }: { tache: Tache }): JSX.Element | null {
  if (tache.echeance === null || tache.statut === 'Terminée') return null;
  const jours = Math.ceil(
    (new Date(tache.echeance).setHours(23, 59, 59, 999) - Date.now()) / 86_400_000,
  );
  if (jours < 0) return <span className={styles.pilRetard}>Échéance dépassée</span>;
  if (jours === 0) return <span className={styles.pilProche}>Échéance aujourd’hui</span>;
  if (jours <= 3) return <span className={styles.pilProche}>Échéance dans {jours} j</span>;
  return null;
}

/** Liste de tâches réutilisable (projets, changements) : ajout, statut, assigné, échéance. */
export function ListeTaches({
  taches,
  agents,
  onAjouter,
  onMaj,
  onSupprimer,
  onReordonner,
  renduEnfant,
  renduSousTitre,
  peutTravailler = true,
  moiId = null,
}: Props): JSX.Element {
  const [titre, setTitre] = useState('');
  const [assigne, setAssigne] = useState<string | null>(null);
  const [echeance, setEcheance] = useState('');
  const [envoi, setEnvoi] = useState(false);

  // Ordre local pour un réordonnancement fluide (glisser-déposer), synchronisé avec les props.
  const [local, setLocal] = useState<Tache[]>(taches);
  const localRef = useRef<Tache[]>(taches);
  const drag = useRef<number | null>(null);
  const [saisiPar, setSaisiPar] = useState<string | null>(null);
  useEffect(() => {
    setLocal(taches);
    localRef.current = taches;
  }, [taches]);

  const deplacer = (de: number, vers: number): void => {
    setLocal((liste) => {
      const copie = [...liste];
      const [item] = copie.splice(de, 1);
      if (item) copie.splice(vers, 0, item);
      localRef.current = copie;
      return copie;
    });
  };

  const persisterOrdre = (): void => {
    setSaisiPar(null);
    if (drag.current === null) return;
    drag.current = null;
    if (onReordonner) void onReordonner(localRef.current.map((t) => t.id));
  };

  const ajouter = async (): Promise<void> => {
    if (titre.trim().length < 2) return;
    setEnvoi(true);
    try {
      await onAjouter({ titre: titre.trim(), assigne_id: assigne, echeance: echeance || null });
      setTitre('');
      setAssigne(null);
      setEcheance('');
    } finally {
      setEnvoi(false);
    }
  };

  const reordonnable = onReordonner !== undefined && peutTravailler;

  return (
    <div className={styles.taches}>
      {local.length === 0 && <p className={styles.vide}>Aucune tâche pour le moment.</p>}
      {local.map((t, index) => (
        <div
          key={t.id}
          className={cx(styles.tache, saisiPar === t.id && styles.tacheSaisie)}
          draggable={reordonnable && saisiPar === t.id}
          onDragStart={() => {
            drag.current = index;
          }}
          onDragOver={(e) => {
            if (drag.current === null) return;
            e.preventDefault();
            if (drag.current !== index) {
              deplacer(drag.current, index);
              drag.current = index;
            }
          }}
          onDragEnd={persisterOrdre}
        >
          <div className={styles.tacheTete}>
            {reordonnable && (
              <button
                type="button"
                className={styles.poignee}
                title="Glisser pour réordonner"
                aria-label="Réordonner la tâche"
                // La poignée arme le glisser (le reste de la carte reste cliquable).
                onMouseDown={() => setSaisiPar(t.id)}
                onMouseUp={() => setSaisiPar(null)}
              >
                <GripVertical size={15} />
              </button>
            )}
            <div className={styles.tacheTitreBloc}>
              <span className={cx(styles.tacheTitre, t.statut === 'Terminée' && styles.faite)}>
                {t.titre}
                <EtatEcheance tache={t} />
              </span>
              {renduSousTitre && (
                <div className={styles.tacheSousTitre}>{renduSousTitre(t)}</div>
              )}
            </div>
          </div>
          {peutTravailler && (
            <BoutonSupprimer
              cible={`la tâche « ${t.titre} »`}
              onSupprimer={() => onSupprimer(t.id)}
              className={styles.tacheSuppr}
            />
          )}
          <div className={styles.tacheChamps}>
            <div className={styles.tacheChamp}>
              {/* Son porteur rend compte de l'avancement : c'est le seul champ qu'il change. */}
              <SelecteurListe
                options={STATUTS_TACHE.map((s) => ({ valeur: s, libelle: s }))}
                valeur={t.statut}
                onChange={(v) => v !== null && void onMaj(t.id, { statut: v as StatutTache })}
                placeholder="Statut"
                couleurs={COULEUR_STATUT_TACHE}
                desactive={!peutTravailler && t.assigne_id !== moiId}
                titreDesactive="Seul l’assigné de cette tâche en change le statut."
              />
            </div>
            <div className={styles.tacheChamp}>
              <SelecteurListe
                options={agents}
                valeur={t.assigne_id}
                onChange={(v) => void onMaj(t.id, { assigne_id: v })}
                placeholder="Assigner…"
                permettreVide
                libelleVide="Non assigné"
                desactive={!peutTravailler}
                titreDesactive={RESERVE_AUX_ACTEURS}
              />
            </div>
            <div className={styles.tacheChamp}>
              <SelecteurDate
                valeur={t.echeance}
                onChange={(v) => void onMaj(t.id, { echeance: v })}
                placeholder="Échéance"
                remplissageEcheance={t.statut !== 'Terminée'}
                desactive={!peutTravailler}
                titreDesactive={RESERVE_AUX_ACTEURS}
              />
            </div>
          </div>
          {renduEnfant && <div className={styles.enfant}>{renduEnfant(t)}</div>}
        </div>
      ))}

      {/* Créer une tâche, c'est distribuer du travail : réservé aux acteurs. */}
      {peutTravailler && (
        <div className={styles.ajout}>
          <input
            className={styles.ajoutTitre}
            value={titre}
            onChange={(e) => setTitre(e.target.value)}
            placeholder="Nouvelle tâche…"
            onKeyDown={(e) => {
              if (e.key === 'Enter') void ajouter();
            }}
          />
          <div className={styles.tacheChamp}>
            <SelecteurListe
              options={agents}
              valeur={assigne}
              onChange={setAssigne}
              placeholder="Assigner…"
              permettreVide
              libelleVide="Non assigné"
            />
          </div>
          <div className={styles.tacheChamp}>
            <SelecteurDate
              valeur={echeance || null}
              onChange={(v) => setEcheance(v ?? '')}
              placeholder="Échéance"
            />
          </div>
          <Button onClick={() => void ajouter()} disabled={envoi || titre.trim().length < 2}>
            <Plus size={15} /> Ajouter
          </Button>
        </div>
      )}
    </div>
  );
}
