import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { AvatarPersonnage } from './AvatarPersonnage';
import { SablierSla } from './SablierSla';
import { BadgePriorite, couleurStatut } from './statuts';
import { chaineFiltres, type FiltresListe, type Incident } from '@/features/incidents/incidentsApi';
import styles from './KanbanTickets.module.css';

interface Props {
  module: string;
  base: string;
  filtres: FiltresListe;
  onOuvrir: (id: string) => void;
}

/** Vue Kanban : une colonne par statut du cycle de vie, cartes cliquables. */
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

  return (
    <div className={styles.kanban}>
      {etats.map((statut) => {
        const cartes = items.filter((i) => i.statut === statut);
        const couleur = couleurStatut(statut);
        return (
          <div key={statut} className={styles.colonne}>
            <div className={styles.colTete} style={{ borderTopColor: couleur }}>
              <span className={styles.colTitre}>{statut}</span>
              <span className={styles.colNb}>{cartes.length}</span>
            </div>
            <div className={styles.colCorps}>
              {cartes.map((c) => (
                <button key={c.id} type="button" className={styles.carte} onClick={() => onOuvrir(c.id)}>
                  <div className={styles.carteTete}>
                    <span className={styles.carteRef}>{c.reference}</span>
                    <BadgePriorite priorite={c.priorite} />
                  </div>
                  <span className={styles.carteTitre} title={c.titre}>
                    {c.titre}
                  </span>
                  <div className={styles.carteBas}>
                    <SablierSla echeance={c.sla_resolution_le} debut={c.cree_le} statut={c.statut_sla} />
                    {c.gestionnaire !== null && (
                      <span className={styles.carteGest} title={c.gestionnaire}>
                        <AvatarPersonnage seed={c.gestionnaire} taille={20} />
                      </span>
                    )}
                  </div>
                </button>
              ))}
              {cartes.length === 0 && <span className={styles.colVide}>—</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
