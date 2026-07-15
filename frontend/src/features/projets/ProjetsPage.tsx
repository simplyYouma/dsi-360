import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { Button, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { BandeauStats } from '@/common/BandeauStats';
import { SablierSla } from '@/common/SablierSla';
import { BadgeStatut } from '@/common/statuts';
import { BarreAvancement } from '@/common/BarreAvancement';
import { CelluleActeur } from '@/common/CelluleActeur';
import { FiltreTickets } from '@/common/FiltreTickets';
import type { FiltresListe } from '@/features/incidents/incidentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { projetsApi, type Projet } from './projetsApi';

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function formaterBudget(v: number | null): string {
  if (v === null) return '—';
  return new Intl.NumberFormat('fr-FR', { notation: 'compact', maximumFractionDigits: 1 }).format(
    v,
  );
}

const COLONNES: Colonne<Projet>[] = [
  { cle: 'reference', entete: 'Référence', valeur: (p) => p.reference, largeur: '150px' },
  {
    cle: 'titre',
    entete: 'Projet',
    tronque: true,
    rendu: (p) => <strong title={p.titre}>{p.titre}</strong>,
    valeur: (p) => p.titre,
  },
  {
    cle: 'statut',
    entete: 'Statut',
    valeur: (p) => p.statut,
    rendu: (p) => <BadgeStatut statut={p.statut} />,
  },
  {
    cle: 'chef',
    entete: 'Chef de projet',
    valeur: (p) => (p.chef ? `${p.chef.prenom} ${p.chef.nom}` : ''),
    rendu: (p) => (
      <CelluleActeur
        nom={p.chef ? `${p.chef.prenom} ${p.chef.nom}` : null}
        contributeur={p.contributeur}
        vide="—"
      />
    ),
  },
  {
    cle: 'avancement',
    entete: 'Avancement',
    valeur: (p) => p.avancement,
    rendu: (p) => <BarreAvancement valeur={p.avancement} compact />,
  },
  {
    cle: 'budget',
    entete: 'Budget (FCFA)',
    aligne: 'droite',
    valeur: (p) => p.budget ?? 0,
    rendu: (p) => <span className="tabular">{formaterBudget(p.budget)}</span>,
  },
  {
    cle: 'date_fin',
    entete: 'Échéance',
    valeur: (p) => p.date_fin ?? '',
    rendu: (p) =>
      p.date_fin ? (
        <SablierSla echeance={p.date_fin} debut={p.cree_le} />
      ) : (
        <span style={{ color: 'var(--text-muted)' }}>—</span>
      ),
  },
  {
    cle: 'cree_le',
    entete: 'Créé le',
    valeur: (p) => p.cree_le,
    rendu: (p) => formaterDate(p.cree_le),
  },
];

export function ProjetsPage(): JSX.Element {
  const navigate = useNavigate();
  const [projets, setProjets] = useState<Projet[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await projetsApi.lister(p, filtres);
        setProjets(data.elements);
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
          <h1 className={styles.titre}>Projets</h1>
          <p className={styles.sous}>Suivi des projets de la DSI : planning, budget, avancement.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/projets" />
          <Button onClick={() => navigate('/projets/nouveau')}>
            <Plus size={16} />
            Nouveau projet
          </Button>
        </div>
      </header>

      <BandeauStats base="/projets" signal={total} />

      <FiltreTickets
        module="projet"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

      <Table
        colonnes={COLONNES}
        lignes={projets}
        cleLigne={(p) => p.id}
        chargement={chargement}
        vide="Aucun projet pour le moment."
        onLigne={(p) => navigate(`/projets/${p.id}`)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />
    </div>
  );
}
