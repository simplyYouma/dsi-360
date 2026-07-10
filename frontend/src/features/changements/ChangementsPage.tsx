import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { Button, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { FiltreTickets } from '@/common/FiltreTickets';
import { BadgeStatut } from '@/common/statuts';
import type { FiltresListe } from '@/features/incidents/incidentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { SablierSla } from '@/common/SablierSla';
import { changementsApi, type Changement } from './changementsApi';

const PRIORITE_COULEUR: Record<number, string> = {
  1: 'var(--status-danger)',
  2: 'var(--cat-3)',
  3: 'var(--cat-7)',
  4: 'var(--cat-1)',
  5: 'var(--text-muted)',
};

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

const COLONNES: Colonne<Changement>[] = [
  { cle: 'reference', entete: 'Référence', valeur: (c) => c.reference, largeur: '150px' },
  {
    cle: 'titre',
    entete: 'Objet',
    tronque: true,
    rendu: (c) => <strong title={c.titre}>{c.titre}</strong>,
    valeur: (c) => c.titre,
  },
  {
    cle: 'categorie',
    entete: 'Type',
    rendu: (c) =>
      c.categorie ? <StatusBadge couleur="var(--cat-5)">{c.categorie}</StatusBadge> : '—',
  },
  {
    cle: 'priorite',
    entete: 'Priorité',
    valeur: (c) => c.priorite,
    rendu: (c) => (
      <StatusBadge couleur={PRIORITE_COULEUR[c.priorite] ?? 'var(--text-muted)'}>
        P{c.priorite}
      </StatusBadge>
    ),
  },
  { cle: 'statut', entete: 'Statut', rendu: (c) => <BadgeStatut statut={c.statut} /> },
  {
    cle: 'responsable',
    entete: 'Responsable',
    rendu: (c) => (c.responsable ? `${c.responsable.prenom} ${c.responsable.nom}` : '—'),
  },
  {
    cle: 'sla',
    entete: 'Échéance SLA',
    valeur: (c) => c.sla_resolution_le ?? '',
    rendu: (c) => (
      <SablierSla
        echeance={c.sla_resolution_le}
        debut={c.cree_le}
        statut={c.statut_sla ?? 'a_lheure'}
      />
    ),
  },
  {
    cle: 'cree_le',
    entete: 'Créé le',
    valeur: (c) => c.cree_le,
    rendu: (c) => formaterDate(c.cree_le),
  },
];

export function ChangementsPage(): JSX.Element {
  const navigate = useNavigate();
  const [changements, setChangements] = useState<Changement[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await changementsApi.lister(p, filtres);
        setChangements(data.elements);
        setTotal(data.total);
      } finally {
        setChargement(false);
      }
    },
    [filtres],
  );

  useEffect(() => {
    void charger(page);
  }, [charger, page]);

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Changements</h1>
          <p className={styles.sous}>Demandes de changement (RFC) — workflow CAB / ECAB.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/changements" />
          <Button onClick={() => navigate('/changements/nouveau')}>
            <Plus size={16} />
            Nouveau changement
          </Button>
        </div>
      </header>

      <FiltreTickets
        module="changement"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

      <Table
        colonnes={COLONNES}
        lignes={changements}
        cleLigne={(c) => c.id}
        chargement={chargement}
        vide="Aucun changement pour le moment."
        onLigne={(c) => navigate(`/changements/${c.id}`)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />
    </div>
  );
}
