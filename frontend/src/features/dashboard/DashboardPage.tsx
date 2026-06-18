import { useEffect, useState } from 'react';
import { TriangleAlert, ShieldAlert, Timer, Inbox, FolderKanban, Flame } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
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

interface Segment {
  nom: string;
  valeur: number;
  couleur: string;
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
    { libelle: 'Incidents ouverts', valeur: String(c.incidents_ouverts), icone: TriangleAlert, couleur: 'var(--cat-1)', note: `${c.incidents_critiques} critique(s)`, tonNote: c.incidents_critiques > 0 ? 'danger' : undefined },
    { libelle: 'Incidents critiques', valeur: String(c.incidents_critiques), icone: ShieldAlert, couleur: 'var(--cat-4)', note: 'Priorité P1', tonNote: 'danger' },
    { libelle: 'Respect SLA', valeur: `${c.respect_sla} %`, icone: Timer, couleur: 'var(--cat-2)', note: c.respect_sla >= 90 ? 'Objectif tenu' : "Sous l'objectif", tonNote: c.respect_sla >= 90 ? 'ok' : 'warn' },
    { libelle: 'Demandes en cours', valeur: String(c.demandes_en_cours), icone: Inbox, couleur: 'var(--cat-7)', note: 'À traiter' },
    { libelle: 'Projets en retard', valeur: String(c.projets_en_retard), icone: FolderKanban, couleur: 'var(--cat-3)', note: c.projets_en_retard > 0 ? 'À surveiller' : 'Dans les temps', tonNote: c.projets_en_retard > 0 ? 'warn' : 'ok' },
    { libelle: 'Risques critiques', valeur: String(c.risques_critiques), icone: Flame, couleur: 'var(--cat-5)', note: 'Revue périodique' },
  ];
}

/** Donut épais à segments arrondis + total au centre + légende à mini-barres. */
function DonutAnneau({ data, unite }: { data: Segment[]; unite: string }): JSX.Element {
  const total = data.reduce((s, d) => s + d.valeur, 0);
  return (
    <div className={styles.donutBloc}>
      <div className={styles.donutGraphe}>
        <ResponsiveContainer width="100%" height={196}>
          <PieChart>
            <Pie
              data={total === 0 ? [{ nom: 'vide', valeur: 1, couleur: 'var(--bg-subtle)' }] : data}
              dataKey="valeur"
              nameKey="nom"
              innerRadius={66}
              outerRadius={92}
              cornerRadius={9}
              paddingAngle={total === 0 ? 0 : 4}
              startAngle={90}
              endAngle={-270}
              stroke="none"
            >
              {(total === 0 ? [{ couleur: 'var(--bg-subtle)' }] : data).map((d, i) => (
                <Cell key={i} fill={d.couleur} />
              ))}
            </Pie>
            {total > 0 && (
              <Tooltip
                contentStyle={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 10,
                  fontSize: 13,
                }}
              />
            )}
          </PieChart>
        </ResponsiveContainer>
        <div className={styles.donutCentre}>
          <span className={styles.donutTotal}>{total}</span>
          <span className={styles.donutUnite}>{unite}</span>
        </div>
      </div>
      <ul className={styles.legende}>
        {data.map((d) => {
          const pct = total === 0 ? 0 : Math.round((100 * d.valeur) / total);
          return (
            <li key={d.nom} className={styles.legendeItem}>
              <div className={styles.legendeTete}>
                <span className={styles.point} style={{ background: d.couleur }} />
                <span className={styles.legendeNom}>{d.nom}</span>
                <span className={styles.legendeVal}>{d.valeur}</span>
              </div>
              <div className={styles.track}>
                <div className={styles.trackPlein} style={{ width: `${pct}%`, background: d.couleur }} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Barre « capsule » segmentée (proportions) + légende chiffrée. */
function CapsuleSla({ data }: { data: Segment[] }): JSX.Element {
  const total = data.reduce((s, d) => s + d.valeur, 0);
  return (
    <div className={styles.slaBloc}>
      <div className={styles.capsule}>
        {total === 0 ? (
          <div className={styles.capsuleVide} />
        ) : (
          data
            .filter((d) => d.valeur > 0)
            .map((d) => (
              <div
                key={d.nom}
                className={styles.capsuleSeg}
                style={{ flexGrow: d.valeur, background: d.couleur }}
                title={`${d.nom} : ${d.valeur}`}
              />
            ))
        )}
      </div>
      <ul className={styles.slaLegende}>
        {data.map((d) => (
          <li key={d.nom}>
            <span className={styles.point} style={{ background: d.couleur }} />
            <span className={styles.legendeNom}>{d.nom}</span>
            <span className={styles.legendeVal}>{d.valeur}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DashboardPage(): JSX.Element {
  const [tableau, setTableau] = useState<TableauBord | null>(null);

  useEffect(() => {
    void dashboardApi.charger().then(setTableau);
  }, []);

  const cartes = tableau ? construireCartes(tableau) : [];
  const repartition: Segment[] = tableau
    ? tableau.repartition.map((r) => ({
        nom: MODULE_META[r.module]?.nom ?? r.module,
        valeur: r.valeur,
        couleur: MODULE_META[r.module]?.couleur ?? '#94a3b8',
      }))
    : [];
  const sla: Segment[] = tableau
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
          <DonutAnneau data={repartition} unite="activités" />
        </Card>
        <Card>
          <h2 className={styles.chartTitre}>Respect des échéances SLA</h2>
          <CapsuleSla data={sla} />
        </Card>
      </section>
    </div>
  );
}
