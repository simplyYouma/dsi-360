import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { api } from '@/lib/api';
import { SelecteurListe, type OptionListe } from './SelecteurListe';
import type { FiltresListe } from '@/features/incidents/incidentsApi';
import styles from './FiltreTickets.module.css';

interface Agent {
  id: string;
  nom: string;
  profil: string;
}

const NON_ASSIGNE = '__non_assigne__';

interface Props {
  module: string;
  valeur: FiltresListe;
  onChange: (f: FiltresListe) => void;
}

/** Barre de filtres de dispatch : statut, gestionnaire, non assignés. */
export function FiltreTickets({ module, valeur, onChange }: Props): JSX.Element {
  const [etats, setEtats] = useState<string[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    void api.get<string[]>(`/referentiels/etats?module=${module}`).then(setEtats);
  }, [module]);
  useEffect(() => {
    void api.get<Agent[]>('/referentiels/agents').then(setAgents);
  }, []);

  const optionsGest: OptionListe[] = [
    { valeur: NON_ASSIGNE, libelle: 'Non assignés' },
    ...agents.map((a) => ({ valeur: a.id, libelle: a.nom })),
  ];
  const gestValeur = valeur.non_assigne ? NON_ASSIGNE : valeur.responsable_id ?? null;
  const actif = Boolean(valeur.statut || valeur.responsable_id || valeur.non_assigne);

  return (
    <div className={styles.barre}>
      <div className={styles.filtre}>
        <SelecteurListe
          options={etats.map((e) => ({ valeur: e, libelle: e }))}
          valeur={valeur.statut ?? null}
          onChange={(v) => onChange({ ...valeur, statut: v })}
          placeholder="Tous les statuts"
          permettreVide
          libelleVide="Tous les statuts"
        />
      </div>
      <div className={styles.filtre}>
        <SelecteurListe
          options={optionsGest}
          valeur={gestValeur}
          onChange={(v) =>
            onChange({
              ...valeur,
              responsable_id: v === NON_ASSIGNE ? null : v,
              non_assigne: v === NON_ASSIGNE,
            })
          }
          placeholder="Tous les gestionnaires"
          permettreVide
          libelleVide="Tous les gestionnaires"
        />
      </div>
      {actif && (
        <button type="button" className={styles.reset} onClick={() => onChange({})}>
          <X size={14} />
          Réinitialiser
        </button>
      )}
    </div>
  );
}
