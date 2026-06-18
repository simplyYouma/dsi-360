import { useEffect, useState } from 'react';
import { TriangleAlert, ShieldAlert, Timer, Inbox, FolderKanban, Flame } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Card } from '@/design-system/primitives';
import { dashboardApi, type TableauBord } from './dashboardApi';
import styles from './DashboardPage.module.css';

interface Carte {
  libelle: string;
  valeur: string;
  icone: LucideIcon;
  couleur: string;
  note: string;
  tonNote?: 'ok' | 'warn' | 'danger' | undefined;
}

const MODULE_META: Record<string, { nom: string; couleur: string }> = {
  incident: { nom: 'Incidents', couleur: '#4f6bed' },
  demande: { nom: 'Demandes', couleur: '#15a394' },
  projet: { nom: 'Projets', couleur: '#e0a341' },
  changement: { nom: 'Changements', couleur: '#e2557b' },
  audit: { nom: 'Audit', couleur: '#8a5cf6' },
  risque: { nom: 'Risques', couleur: '#2fa363' },
};

function construireCartes(t: TableauBord): Carte[] {
  const c = t.cartes;
  return [
    {
      libelle: 'Incidents ouverts',
      valeur: String(c.incidents_ouverts),
      icone: TriangleAlert,
      couleur: 'var(--cat-1)',
      note: `${c.incidents_critiques} critique(s)`,
      tonNote: c.incidents_critiques > 0 ? 'danger' : undefined,
    },
    {
      libelle: 'Incidents critiques',
      valeur: String(c.incidents_critiques),
      icone: ShieldAlert,
      couleur: 'var(--cat-4)',
      note: 'Priorité P1',
      tonNote: 'danger',
    },
    {
      libelle: 'Respect SLA',
      valeur: `${c.respect_sla} %`,
      icone: Timer,
      couleur: 'var(--cat-2)',
      note: c.respect_sla >= 90 ? 'Objectif tenu' : "Sous l'objectif",
      tonNote: c.respect_sla >= 90 ? 'ok' : 'warn',
    },
    {
      libelle: 'Demandes en cours',
      valeur: String(c.demandes_en_cours),
      icone: Inbox,
      couleur: 'var(--cat-7)',
      note: 'À traiter',
    },
    {
      libelle: 'Projets en retard',
      valeur: String(c.projets_en_retard),
      icone: FolderKanban,
      couleur: 'var(--cat-3)',
      note: c.projets_en_retard > 0 ? 'À surveiller' : 'Dans les temps',
      tonNote: c.projets_en_retard > 0 ? 'warn' : 'ok',
    },
    {
      libelle: 'Risques critiques',
      valeur: String(c.risques_critiques),
      icone: Flame,
      couleur: 'var(--cat-5)',
      note: 'Revue périodique',
    },
  ];
}

function Donut({
  data,
}: {
  data: { nom: string; valeur: number; couleur: string }[];
}): JSX.Element {
  const total = data.reduce((s, d) => s + d.valeur, 0);
  if (total === 0) return <p className={styles.chartVide}>Aucune donnée.</p>;
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data}
          dataKey="valeur"
          nameKey="nom"
          innerRadius={62}
          outerRadius={92}
          paddingAngle={2}
          stroke="none"
        >
          {data.map((d) => (
            <Cell key={d.nom} fill={d.couleur} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            fontSize: 13,
            color: 'var(--text)',
          }}
        />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 13 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function DashboardPage(): JSX.Element {
  const [tableau, setTableau] = useState<TableauBord | null>(null);

  useEffect(() => {
    void dashboardApi.charger().then(setTableau);
  }, []);

  const cartes = tableau ? construireCartes(tableau) : [];
  const repartition = tableau
    ? tableau.repartition.map((r) => ({
        nom: MODULE_META[r.module]?.nom ?? r.module,
        valeur: r.valeur,
        couleur: MODULE_META[r.module]?.couleur ?? '#94a3b8',
      }))
    : [];
  const sla = tableau
    ? [
        { nom: "À l'heure", valeur: tableau.sla.a_lheure, couleur: '#1f9d55' },
        { nom: 'Approche', valeur: tableau.sla.approche, couleur: '#c77700' },
        { nom: 'Dépassé', valeur: tableau.sla.depasse, couleur: '#d64545' },
      ]
    : [];

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <h1 className={styles.titre}>Tableau de bord</h1>
        <p className={styles.sous}>Vue d'ensemble des activités de la DSI — AFG Bank Mali.</p>
      </header>

      <section className={styles.grille}>
        {cartes.map(({ libelle, valeur, icone: Icone, couleur, note, tonNote }) => (
          <Card key={libelle} className={styles.kpi}>
            <div className={styles.kpiTete}>
              <span className={styles.kpiIcone} style={{ color: couleur }}>
                <Icone size={18} />
              </span>
              <span className={styles.kpiLibelle}>{libelle}</span>
            </div>
            <div className={styles.kpiValeur}>{tableau ? valeur : '—'}</div>
            <div className={styles.kpiNote} data-ton={tonNote}>
              {tableau ? note : ' '}
            </div>
          </Card>
        ))}
      </section>

      <section className={styles.charts}>
        <Card>
          <h2 className={styles.chartTitre}>Répartition des activités</h2>
          <Donut data={repartition} />
        </Card>
        <Card>
          <h2 className={styles.chartTitre}>Respect des échéances SLA</h2>
          <Donut data={sla} />
        </Card>
      </section>
    </div>
  );
}
