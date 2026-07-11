import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TriangleAlert, ShieldAlert, Timer, Inbox, FolderKanban, Flame } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  AreaChart,
  Area,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, Skeleton } from '@/design-system/primitives';
import { cx } from '@/common/cx';
import { BadgePriorite, BadgeStatut } from '@/common/statuts';
import { lienActivite } from '@/common/routesModule';
import { BoutonExportPdf } from '@/common/BoutonExportPdf';
import { BoutonExportPng } from '@/common/BoutonExportPng';
import { FiltrePeriode } from '@/common/FiltrePeriode';
import { PERIODE_TOUT, type Periode } from '@/common/periode';
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
  /** Un chiffre alarmant doit mener aux dossiers qui le composent. */
  route: string;
  /** Série hebdomadaire miniature (créations sur 8 semaines). */
  spark?: (t: TableauBord) => number[];
}

interface Segment {
  nom: string;
  valeur: number;
  couleur: string;
}

const META_CARTES: MetaCarte[] = [
  {
    libelle: 'Incidents ouverts',
    route: '/incidents',
    spark: (t) => t.creations_hebdo['incident'] ?? [],
    icone: TriangleAlert,
    couleur: 'var(--cat-1)',
    valeur: (c) => String(c.incidents_ouverts),
    note: (c) => `${c.incidents_critiques} critique(s)`,
    tonNote: (c) => (c.incidents_critiques > 0 ? 'danger' : undefined),
  },
  {
    libelle: 'Incidents critiques',
    route: '/incidents',
    icone: ShieldAlert,
    couleur: 'var(--cat-4)',
    valeur: (c) => String(c.incidents_critiques),
    note: () => 'Priorité P1',
    tonNote: () => 'danger',
  },
  {
    libelle: 'Respect SLA',
    route: '/analyses',
    icone: Timer,
    couleur: 'var(--cat-2)',
    valeur: (c) => `${c.respect_sla} %`,
    note: (c) => (c.respect_sla >= 90 ? 'Objectif tenu' : "Sous l'objectif"),
    tonNote: (c) => (c.respect_sla >= 90 ? 'ok' : 'warn'),
  },
  {
    libelle: 'Demandes en cours',
    route: '/demandes',
    spark: (t) => t.creations_hebdo['demande'] ?? [],
    icone: Inbox,
    couleur: 'var(--cat-7)',
    valeur: (c) => String(c.demandes_en_cours),
    note: () => 'À traiter',
  },
  {
    libelle: 'Projets en retard',
    route: '/projets',
    icone: FolderKanban,
    couleur: 'var(--cat-3)',
    valeur: (c) => String(c.projets_en_retard),
    note: (c) => (c.projets_en_retard > 0 ? 'À surveiller' : 'Dans les temps'),
    tonNote: (c) => (c.projets_en_retard > 0 ? 'warn' : 'ok'),
  },
  {
    libelle: 'Risques critiques',
    route: '/risques',
    icone: Flame,
    couleur: 'var(--cat-5)',
    valeur: (c) => String(c.risques_critiques),
    note: (c) => `Sur ${c.risques_ouverts} ouvert(s)`,
    tonNote: (c) => (c.risques_critiques > 0 ? 'danger' : 'ok'),
  },
];

const MODULE_META: Record<string, { nom: string; couleur: string }> = {
  incident: { nom: 'Incidents', couleur: '#4f6bed' },
  demande: { nom: 'Demandes', couleur: '#15a394' },
  projet: { nom: 'Projets', couleur: '#e0a341' },
  changement: { nom: 'Changements', couleur: '#e2557b' },
  audit: { nom: 'Audit', couleur: '#8a5cf6' },
  risque: { nom: 'Risques', couleur: '#2fa363' },
};

const TON_COULEUR: Record<Exclude<Ton, undefined>, string> = {
  ok: 'var(--status-ok)',
  warn: 'var(--status-warn)',
  danger: 'var(--status-danger)',
};

/**
 * Un signal = une jauge radiale (anneau). L'arc encode la PART, le grand chiffre au centre
 * donne le compte, la couleur dit l'état. Le sens ne repose jamais sur la couleur seule : un
 * libellé l'accompagne toujours.
 */
function JaugeSignal({
  valeur,
  ton,
  titre,
  detail,
  pct,
}: {
  valeur: number;
  ton: Ton;
  titre: string;
  detail: string;
  pct: number | null;
}): JSX.Element {
  const couleur = TON_COULEUR[ton ?? 'ok'];
  const r = 22;
  const c = 2 * Math.PI * r;
  const rempli = pct === null ? 0 : Math.min(1, pct / 100);
  return (
    <li className={styles.signal}>
      <svg viewBox="0 0 60 60" className={styles.signalArc} aria-hidden="true">
        {/* Anneau : rail complet gris, part remplie en couleur d'état, départ en haut. */}
        <circle cx="30" cy="30" r={r} fill="none" stroke="var(--bg-subtle)" strokeWidth="6" />
        {pct !== null && rempli > 0 && (
          <circle
            cx="30"
            cy="30"
            r={r}
            fill="none"
            stroke={couleur}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - rempli)}
            transform="rotate(-90 30 30)"
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
        )}
        <text
          x="30"
          y="30"
          textAnchor="middle"
          dominantBaseline="central"
          className={styles.signalNombre}
          fill={couleur}
        >
          {valeur}
        </text>
      </svg>
      <span className={styles.signalCorps}>
        <span className={styles.signalTitre}>{titre}</span>
        <span className={styles.signalDetail}>{detail}</span>
      </span>
    </li>
  );
}

/** Miniature de tendance : huit semaines de créations, tracées sans axes — le geste suffit. */
function Sparkline({ points, couleur }: { points: number[]; couleur: string }): JSX.Element | null {
  if (points.length < 2 || points.every((v) => v === 0)) return null;
  const max = Math.max(...points, 1);
  const L = 84;
  const H = 22;
  const pas = L / (points.length - 1);
  const y = (v: number): number => H - 2 - (v / max) * (H - 4);
  const d = points.map(
    (v, i) => `${i === 0 ? 'M' : 'L'}${(i * pas).toFixed(1)} ${y(v).toFixed(1)}`,
  );
  return (
    <svg viewBox={`0 0 ${L} ${H}`} width={L} height={H} className={styles.spark} aria-hidden="true">
      <path d={d.join(' ')} fill="none" stroke={couleur} strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx={L} cy={y(points[points.length - 1] ?? 0)} r="2" fill={couleur} />
    </svg>
  );
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
            {total > 0 && <Tooltip {...infobulle} />}
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
                <div
                  className={styles.trackPlein}
                  style={{ width: `${pct}%`, background: d.couleur }}
                />
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

/** Part entière, bornée, sans division par zéro. */
function pctDe(part: number, tout: number): number {
  return tout > 0 ? Math.min(100, Math.round((100 * part) / tout)) : 0;
}

export function DashboardPage(): JSX.Element {
  const [tableau, setTableau] = useState<TableauBord | null>(null);
  const [periode, setPeriode] = useState<Periode>(PERIODE_TOUT);
  const contenuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const ouvrir = (module: string, id: string): void => {
    const lien = lienActivite(module, id);
    if (lien !== null) navigate(lien);
  };

  useEffect(() => {
    void dashboardApi.charger(periode).then(setTableau);
  }, [periode]);

  const repartition: Segment[] = tableau
    ? tableau.repartition.map((r) => ({
        nom: MODULE_META[r.module]?.nom ?? r.module,
        valeur: r.valeur,
        couleur: MODULE_META[r.module]?.couleur ?? '#94a3b8',
      }))
    : [];
  const ticketsOuverts = tableau
    ? tableau.repartition
        .filter((r) => r.module === 'incident' || r.module === 'demande')
        .reduce((s, r) => s + r.valeur, 0)
    : 0;
  const sla: Segment[] = tableau
    ? [
        { nom: "À l'heure", valeur: tableau.sla.a_lheure, couleur: '#1f9d55' },
        { nom: 'Approche', valeur: tableau.sla.approche, couleur: '#c77700' },
        { nom: 'Dépassé', valeur: tableau.sla.depasse, couleur: '#d64545' },
      ]
    : [];

  return (
    <div className={styles.page}>
      <header className={styles.enteteBarre}>
        <div className={styles.entete}>
          <h1 className={styles.titre}>Tableau de bord</h1>
          <p className={styles.sous}>Vue d'ensemble des activités de la DSI — AFG Bank Mali.</p>
        </div>
        <div className={styles.actions}>
          <FiltrePeriode valeur={periode} onChange={setPeriode} />
          <BoutonExportPdf
            cible={contenuRef}
            titre="Tableau de bord exécutif"
            nomFichier="dsi360-tableau-de-bord.pdf"
          />
        </div>
      </header>

      <div
        ref={contenuRef}
        style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}
      >
        <section
          className={styles.grille}
          data-visuel="Indicateurs clés"
          style={{ position: 'relative' }}
        >
          <BoutonExportPng nom="Indicateurs clés" />
          {META_CARTES.map((m) => {
            const Icone = m.icone;
            const spark = tableau && m.spark ? m.spark(tableau) : [];
            return (
              <Card
                key={m.libelle}
                className={cx(styles.kpi, styles.kpiCliquable)}
                onClick={() => navigate(m.route)}
                role="link"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && navigate(m.route)}
              >
                <div className={styles.kpiTete}>
                  <span className={styles.kpiIcone} style={{ color: m.couleur }}>
                    <Icone size={18} />
                  </span>
                  <span className={styles.kpiLibelle}>{m.libelle}</span>
                </div>
                {tableau ? (
                  <>
                    <div className={styles.kpiValeurLigne}>
                      <span className={styles.kpiValeur}>{m.valeur(tableau.cartes)}</span>
                      <Sparkline points={spark} couleur={m.couleur} />
                    </div>
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

        <section className={styles.rangee}>
          <Card className={styles.aTraiter} data-visuel="À traiter en premier">
            <BoutonExportPng nom="À traiter en premier" />
            <h2 className={styles.chartTitre}>À traiter en premier</h2>
            <p className={styles.chartSous}>
              Les échéances les plus proches — ou déjà dépassées. Cliquez pour ouvrir.
            </p>
            {tableau === null ? (
              <Skeleton hauteur="180px" radius="var(--radius-md)" />
            ) : tableau.a_traiter.length === 0 ? (
              <p className={styles.vide}>Aucune échéance en cours : rien ne presse.</p>
            ) : (
              <ul className={styles.urgences}>
                {(() => {
                  // La barre compare les lignes entre elles : sa longueur ∝ jours de retard,
                  // rapportés au pire de la liste. On classe, on ne juxtapose pas.
                  const jours = (iso: string): number =>
                    (Date.now() - new Date(iso).getTime()) / 86_400_000;
                  const pire = Math.max(
                    1,
                    ...tableau.a_traiter.map((u) => Math.abs(jours(u.sla_resolution_le))),
                  );
                  return tableau.a_traiter.map((u) => {
                    const dj = jours(u.sla_resolution_le);
                    const retard = dj > 0;
                    const largeur = Math.max(4, (100 * Math.abs(dj)) / pire);
                    const couleur = retard ? 'var(--status-danger)' : 'var(--status-warn)';
                    return (
                      <li key={u.id}>
                        <button
                          type="button"
                          className={styles.urgence}
                          onClick={() => ouvrir(u.module, u.id)}
                        >
                          <span className={styles.urgenceTete}>
                            <span className={styles.urgenceRef}>{u.reference}</span>
                            <span className={styles.urgenceTitre} title={u.titre}>
                              {u.titre}
                            </span>
                            {u.priorite !== null && <BadgePriorite priorite={u.priorite} />}
                            <BadgeStatut statut={u.statut} />
                          </span>
                          <span className={styles.urgenceMesure}>
                            <span className={styles.urgenceRail}>
                              <span
                                className={styles.urgencePlein}
                                style={{ width: `${largeur}%`, background: couleur }}
                              />
                            </span>
                            <span className={styles.urgenceDelai} style={{ color: couleur }}>
                              {retard
                                ? `${Math.round(Math.abs(dj))} j de retard`
                                : `dans ${Math.max(1, Math.round(Math.abs(dj)))} j`}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  });
                })()}
              </ul>
            )}
          </Card>

          <Card data-visuel="Signaux">
            <BoutonExportPng nom="Signaux" />
            <h2 className={styles.chartTitre}>Signaux</h2>
            <p className={styles.chartSous}>Ce qui mérite un œil, au-delà des volumes.</p>
            {tableau === null ? (
              <Skeleton hauteur="180px" radius="var(--radius-md)" />
            ) : (
              <ul className={styles.signaux}>
                <JaugeSignal
                  valeur={tableau.dbs_ouverts}
                  ton={tableau.dbs_ouverts > 0 ? 'warn' : 'ok'}
                  titre="Tickets chez DBS"
                  detail={
                    tableau.dbs_ouverts === 0
                      ? 'Rien parti chez DBS.'
                      : `${pctDe(tableau.dbs_ouverts, ticketsOuverts)} % des ouverts` +
                        (tableau.dbs_age_jours !== null
                          ? ` · ${Math.round(tableau.dbs_age_jours)} j en moyenne`
                          : '')
                  }
                  pct={pctDe(tableau.dbs_ouverts, ticketsOuverts)}
                />
                <JaugeSignal
                  valeur={tableau.rouverts_30j}
                  ton={tableau.rouverts_30j > 0 ? 'warn' : 'ok'}
                  titre="Réouvertures (30 j)"
                  detail={
                    tableau.resolus_30j === 0
                      ? 'Aucune résolution récente.'
                      : `${pctDe(tableau.rouverts_30j, tableau.resolus_30j)} % des résolutions ont rouvert`
                  }
                  pct={
                    tableau.resolus_30j === 0
                      ? null
                      : pctDe(tableau.rouverts_30j, tableau.resolus_30j)
                  }
                />
                <JaugeSignal
                  valeur={tableau.sla.depasse}
                  ton={tableau.sla.depasse > 0 ? 'danger' : 'ok'}
                  titre="Échéances dépassées"
                  detail={`${pctDe(
                    tableau.sla.depasse,
                    tableau.sla.a_lheure + tableau.sla.approche + tableau.sla.depasse,
                  )} % des échéances en cours`}
                  pct={pctDe(
                    tableau.sla.depasse,
                    tableau.sla.a_lheure + tableau.sla.approche + tableau.sla.depasse,
                  )}
                />
              </ul>
            )}
          </Card>
        </section>

        <section className={styles.charts}>
          <Card data-visuel="Répartition des activités">
            <BoutonExportPng nom="Répartition des activités" />
            <h2 className={styles.chartTitre}>Répartition des activités</h2>
            {tableau ? (
              <DonutAnneau data={repartition} unite="activités" />
            ) : (
              <Skeleton hauteur="196px" radius="var(--radius-md)" />
            )}
          </Card>
          <Card data-visuel="Respect des échéances SLA">
            <BoutonExportPng nom="Respect des échéances SLA" />
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
