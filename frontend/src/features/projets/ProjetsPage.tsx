import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { Button, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
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

function Avancement({ valeur }: { valeur: number }): JSX.Element {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', minWidth: 130 }}>
      <div
        style={{
          flex: 1,
          height: 6,
          background: 'var(--bg-subtle)',
          borderRadius: 'var(--radius-pill)',
        }}
      >
        <div
          style={{
            width: `${valeur}%`,
            height: '100%',
            background: 'var(--secondary)',
            borderRadius: 'var(--radius-pill)',
          }}
        />
      </div>
      <span className="tabular" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
        {valeur}%
      </span>
    </div>
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
  { cle: 'statut', entete: 'Statut', rendu: (p) => <StatusBadge>{p.statut}</StatusBadge> },
  {
    cle: 'chef',
    entete: 'Chef de projet',
    rendu: (p) => (p.chef ? `${p.chef.prenom} ${p.chef.nom}` : '—'),
  },
  {
    cle: 'avancement',
    entete: 'Avancement',
    valeur: (p) => p.avancement,
    rendu: (p) => <Avancement valeur={p.avancement} />,
  },
  {
    cle: 'budget',
    entete: 'Budget (FCFA)',
    aligne: 'droite',
    valeur: (p) => p.budget ?? 0,
    rendu: (p) => <span className="tabular">{formaterBudget(p.budget)}</span>,
  },
  { cle: 'date_fin', entete: 'Échéance', rendu: (p) => p.date_fin ?? '—' },
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
