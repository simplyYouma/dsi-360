import { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
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
const ETATS_VUE: { cle: string; libelle: string }[] = [
  { cle: 'en_cours', libelle: 'En cours' },
  // Ce qui a dépassé son échéance SLA et n'est toujours pas résolu : la file à traiter d'abord.
  { cle: 'en_retard', libelle: 'En retard' },
  { cle: 'termines', libelle: 'Terminés' },
  { cle: 'tous', libelle: 'Tous' },
];

interface Props {
  module: string;
  valeur: FiltresListe;
  onChange: (f: FiltresListe) => void;
}

/** Barre de recherche + filtres : recherche texte, état (en cours/terminés/tous),
 *  statut précis, gestionnaire (dont non assignés). */
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
  const gestValeur = valeur.non_assigne ? NON_ASSIGNE : (valeur.responsable_id ?? null);
  const vue = valeur.etat ?? 'tous';
  const actif = Boolean(
    valeur.statut || valeur.responsable_id || valeur.non_assigne || (valeur.q && valeur.q !== ''),
  );

  return (
    <div className={styles.barre}>
      <label className={styles.recherche}>
        <Search size={16} />
        <input
          value={valeur.q ?? ''}
          onChange={(e) => onChange({ ...valeur, q: e.target.value })}
          placeholder="Rechercher (référence, objet)…"
        />
      </label>

      <div className={styles.segments}>
        {ETATS_VUE.map((v) => (
          <button
            key={v.cle}
            type="button"
            className={vue === v.cle ? styles.segmentOn : styles.segment}
            onClick={() => onChange({ ...valeur, etat: v.cle === 'tous' ? null : v.cle })}
          >
            {v.libelle}
          </button>
        ))}
      </div>

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
        <button
          type="button"
          className={styles.reset}
          onClick={() => onChange({ etat: valeur.etat ?? null })}
        >
          <X size={14} />
          Réinitialiser
        </button>
      )}
    </div>
  );
}
