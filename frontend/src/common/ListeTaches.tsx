import { useState, type ReactNode } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { SelecteurDate } from '@/common/SelecteurDate';
import { SelecteurListe } from '@/common/SelecteurListe';
import { cx } from '@/common/cx';
import {
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
  /** Contenu additionnel par tâche (ex. pièces jointes). */
  renduEnfant?: (tache: Tache) => ReactNode;
}

/** Liste de tâches réutilisable (projets, changements) : ajout, statut, assigné, échéance. */
export function ListeTaches({
  taches,
  agents,
  onAjouter,
  onMaj,
  onSupprimer,
  renduEnfant,
}: Props): JSX.Element {
  const [titre, setTitre] = useState('');
  const [assigne, setAssigne] = useState<string | null>(null);
  const [echeance, setEcheance] = useState('');
  const [envoi, setEnvoi] = useState(false);

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

  return (
    <div className={styles.taches}>
      {taches.length === 0 && <p className={styles.vide}>Aucune tâche pour le moment.</p>}
      {taches.map((t) => (
        <div key={t.id} className={styles.tache}>
          <div className={cx(styles.tacheTitre, t.statut === 'Terminée' && styles.faite)}>
            {t.titre}
          </div>
          <button
            type="button"
            className={styles.tacheSuppr}
            aria-label={`Supprimer ${t.titre}`}
            onClick={() => void onSupprimer(t.id)}
          >
            <Trash2 size={15} />
          </button>
          <div className={styles.tacheChamps}>
            <div className={styles.tacheChamp}>
              <SelecteurListe
                options={STATUTS_TACHE.map((s) => ({ valeur: s, libelle: s }))}
                valeur={t.statut}
                onChange={(v) => v !== null && void onMaj(t.id, { statut: v as StatutTache })}
                placeholder="Statut"
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
              />
            </div>
            <div className={styles.tacheChamp}>
              <SelecteurDate
                valeur={t.echeance}
                onChange={(v) => void onMaj(t.id, { echeance: v })}
                placeholder="Échéance"
              />
            </div>
          </div>
          {renduEnfant && <div className={styles.enfant}>{renduEnfant(t)}</div>}
        </div>
      ))}

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
    </div>
  );
}
