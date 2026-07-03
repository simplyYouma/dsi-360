import { useEffect, useRef, useState } from 'react';
import { TriangleAlert, ShieldAlert, Timer, Inbox, FolderKanban, Flame } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, AreaChart, Area, XAxis, YAxis } from 'recharts';
import { Card, Skeleton } from '@/design-system/primitives';
import { BoutonExportPdf } from '@/common/BoutonExportPdf';
import { infobulle } from '@/common/infobulle';
import { dashboardApi, type TableauBord } from './dashboardApi';
import styles from './DashboardPage.module.css';

type Cartes = TableauBord['cartes'];
type Ton = 'ok' | 'warn' | 'danger' | undefined;

interface MetaCarte {
  libelle: string;
  icone: LucideIcon;
  couleur: string;
  valeur: (c: Cartes) => string;
  note: (c: Cartes) => string;
  tonNote?: (c: Cartes) => Ton;
}

interface Segment {
  nom: string;
  valeur: number;
  couleur: string;
}

const META_CARTES: MetaCarte[] = [
  { libelle: 'Incidents ouverts', icone: TriangleAlert, couleur: 'var(--cat-1)', valeur: (c) => String(c.incidents_ouverts), note: (c) => `${c.incidents_critiques} critique(s)`, tonNote: (c) => (c.incidents_critiques > 0 ? 'danger' : undefined) },
  { libelle: 'Incidents critiques', icone: ShieldAlert, couleur: 'var(--cat-4)', valeur: (c) => String(c.incidents_critiques), note: () => 'Priorité P1', tonNote: () => 'danger' },
  { libelle: 'Respect SLA', icone: Timer, couleur: 'var(--cat-2)', valeur: (c) => `${c.respect_sla} %`, note: (c) => (c.respect_sla >= 90 ? 'Objectif tenu' : "Sous l'objectif"), tonNote: (c) => (c.respect_sla >= 90 ? 'ok' : 'warn') },
  { libelle: 'Demandes en cours', icone: Inbox, couleur: 'var(--cat-7)', valeur: (c) => String(c.demandes_en_cours), note: () => 'À traiter' },
  { libelle: 'Projets en retard', icone: FolderKanban, couleur: 'var(--cat-3)', valeur: (c) => String(c.projets_en_retard), note: (c) => (c.projets_en_retard > 0 ? 'À surveiller' : 'Dans les temps'), tonNote: (c) => (c.projets_en_retard > 0 ? 'warn' : 'ok') },
  { libelle: 'Risques critiques', icone: Flame, couleur: 'var(--cat-5)', valeur: (c) => String(c.risques_critiques), note: () => 'Revue périodique' },
];

const MODULE_META: Record<string, { nom: string; couleur: string }> = {
  incident: { nom: 'Incidents', couleur: '#4f6bed' },
  demande: { nom: 'Demandes', couleur: '#15a394' },
  projet: { nom: 'Projets', couleur: '#e0a341' },
  changement: { nom: 'Changements', couleur: '#e2557b' },
  audit: { nom: 'Audit', couleur: '#8a5cf6' },
  risque: { nom: 'Risques', couleur: '#2fa363' },
};

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
              <Tooltip {...infobulle} />
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

const AIRES = [
  { cle: 'a_lheure', nom: "À l'heure", couleur: '#1f9d55' },
  { cle: 'approche', nom: 'Approche', couleur: '#c77700' },
  { cle: 'depasse', nom: 'Dépassé', couleur: '#d64545' },
] as const;

/** Tendance des 3 états SLA en courbes d'aire lissées avec dégradés (par semaine). */
function TendanceSla({
  serie,
  courant,
}: {
  serie: TableauBord['serie'];
  courant: Segment[];
}): JSX.Element {
  return (
    <div className={styles.slaBloc}>
      {serie.length === 0 ? (
        <p className={styles.tendanceVide}>Tendance disponible dès les premières activités.</p>
      ) : (
        <ResponsiveContainer width="100%" height={210}>
          <AreaChart data={serie} margin={{ top: 8, right: 12, left: -22, bottom: 0 }}>
            <defs>
              {AIRES.map((a) => (
                <linearGradient key={a.cle} id={`grad-${a.cle}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={a.couleur} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={a.couleur} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <XAxis
              dataKey="periode"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: 'var(--text-muted)' }}
            />
            <YAxis hide allowDecimals={false} />
            <Tooltip {...infobulle} />
            {AIRES.map((a) => (
              <Area
                key={a.cle}
                type="monotone"
                dataKey={a.cle}
                name={a.nom}
                stroke={a.couleur}
                strokeWidth={2.5}
                fill={`url(#grad-${a.cle})`}
                dot={false}
                activeDot={{ r: 4 }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      )}
      <ul className={styles.slaLegende}>
        {courant.map((d) => (
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
  const contenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void dashboardApi.charger().then(setTableau);
  }, []);

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
      <header
        className={styles.entete}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 'var(--space-4)',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h1 className={styles.titre}>Tableau de bord</h1>
          <p className={styles.sous}>Vue d'ensemble des activités de la DSI — AFG Bank Mali.</p>
        </div>
        <BoutonExportPdf
          cible={contenuRef}
          titre="Tableau de bord exécutif"
          nomFichier="dsi360-tableau-de-bord.pdf"
        />
      </header>

      <div ref={contenuRef} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
      <section className={styles.grille}>
        {META_CARTES.map((m) => {
          const Icone = m.icone;
          return (
            <Card key={m.libelle} className={styles.kpi}>
              <div className={styles.kpiTete}>
                <span className={styles.kpiIcone} style={{ color: m.couleur }}>
                  <Icone size={18} />
                </span>
                <span className={styles.kpiLibelle}>{m.libelle}</span>
              </div>
              {tableau ? (
                <>
                  <div className={styles.kpiValeur}>{m.valeur(tableau.cartes)}</div>
                  <div className={styles.kpiNote} data-ton={m.tonNote?.(tableau.cartes)}>
                    {m.note(tableau.cartes)}
                  </div>
                </>
              ) : (
                <>
                  <Skeleton largeur="64px" hauteur="34px" />
                  <Skeleton largeur="96px" hauteur="12px" />
                </>
              )}
            </Card>
          );
        })}
      </section>

      <section className={styles.charts}>
        <Card>
          <h2 className={styles.chartTitre}>Répartition des activités</h2>
          {tableau ? (
            <DonutAnneau data={repartition} unite="activités" />
          ) : (
            <Skeleton hauteur="196px" radius="var(--radius-md)" />
          )}
        </Card>
        <Card>
          <h2 className={styles.chartTitre}>Respect des échéances SLA</h2>
          {tableau ? (
            <TendanceSla serie={tableau.serie} courant={sla} />
          ) : (
            <Skeleton hauteur="210px" radius="var(--radius-md)" />
          )}
        </Card>
      </section>
      </div>
    </div>
  );
}
