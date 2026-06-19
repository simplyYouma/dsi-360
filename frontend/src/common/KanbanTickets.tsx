import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Kanban, type ColonneKanban } from './Kanban';
import { couleurStatut } from './statuts';
import { chaineFiltres, type FiltresListe, type Incident } from '@/features/incidents/incidentsApi';
import styles from './Kanban.module.css';

interface Props {
  module: string;
  base: string;
  filtres: FiltresListe;
  onOuvrir: (id: string) => void;
}

/** Kanban d'un module (incidents/demandes…) : charge les tickets et les range par statut. */
export function KanbanTickets({ module, base, filtres, onOuvrir }: Props): JSX.Element {
  const [etats, setEtats] = useState<string[]>([]);
  const [items, setItems] = useState<Incident[]>([]);
  const [chargement, setChargement] = useState(true);

  useEffect(() => {
    void api.get<string[]>(`/referentiels/etats?module=${module}`).then(setEtats);
  }, [module]);
  useEffect(() => {
    setChargement(true);
    void api
      .get<Incident[]>(`${base}/kanban?${chaineFiltres(1, filtres)}`)
      .then(setItems)
      .finally(() => setChargement(false));
  }, [base, filtres]);

  if (chargement) return <p className={styles.info}>Chargement…</p>;

  const colonnes: ColonneKanban[] = etats.map((statut) => ({
    cle: statut,
    titre: statut,
    couleur: couleurStatut(statut),
    cartes: items
      .filter((i) => i.statut === statut)
      .map((i) => ({
        id: i.id,
        reference: i.reference,
        titre: i.titre,
        priorite: i.priorite,
        echeance: i.sla_resolution_le,
        debut: i.cree_le,
        statutSla: i.statut_sla,
        meta: i.gestionnaire,
        nbCommentaires: i.nb_commentaires,
      })),
  }));

  return <Kanban colonnes={colonnes} onOuvrir={onOuvrir} />;
}
