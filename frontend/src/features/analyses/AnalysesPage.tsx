import { useEffect, useRef, useState } from 'react';
import { Activity, Gauge, Timer, AlertTriangle, type LucideIcon } from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  RadialBarChart,
  RadialBar,
  ComposedChart,
  Area,
  Bar,
  Line,
  CartesianGrid,
  ScatterChart,
  Scatter,
  ZAxis,
} from 'recharts';
import { Card } from '@/design-system/primitives';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import { SelecteurListe } from '@/common/SelecteurListe';
import { BoutonExportPdf } from '@/common/BoutonExportPdf';
import { infobulle } from '@/common/infobulle';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import styles from './Analyses.module.css';
import {
  analysesApi,
  type Analyses,
  type GestionnaireEval,
  type GestionnaireDetail,
  type PointActivite,
} from './analysesApi';

const MODULE_LABEL: Record<string, string> = {
  incident: 'Incidents',
  demande: 'Demandes',
  projet: 'Projets',
  changement: 'Changements',
  audit: 'Audit',
  risque: 'Risques',
  cybersecurite: 'Cybersécurité',
  gouvernance: 'Gouvernance',
};
const MODULE_COULEUR: Record<string, string> = {
  incident: '#4f6bed',
  demande: '#15a394',
  projet: '#e0a341',
  changement: '#e2557b',
  audit: '#8a5cf6',
  risque: '#2fa363',
  cybersecurite: '#3aa0c9',
  gouvernance: '#e07a3c',
};
const PRIORITE_COULEUR: Record<string, string> = {
  P1: '#d64545',
  P2: '#e0683c',
  P3: '#e0a341',
  P4: '#4f6bed',
  P5: '#8a93a6',
};
const SLA_SEGMENTS = [
  { cle: 'a_lheure', nom: "À l'heure", couleur: '#1f9d55' },
  { cle: 'approche', nom: 'Approche', couleur: '#c77700' },
  { cle: 'depasse', nom: 'Dépassé', couleur: '#d64545' },
] as const;

type CleOnglet = 'apercu' | 'flux' | 'priorites' | 'equipe';
const ONGLETS: { cle: CleOnglet; libelle: string }[] = [
  { cle: 'apercu', libelle: "Vue d'ensemble" },
  { cle: 'flux', libelle: 'Flux & qualité' },
  { cle: 'priorites', libelle: 'Risques & priorités' },
  { cle: 'equipe', libelle: 'Équipe & gestionnaires' },
];
const PERIODES: { libelle: string; jours: number | null }[] = [
  { libelle: '7 j', jours: 7 },
  { libelle: '30 j', jours: 30 },
  { libelle: '90 j', jours: 90 },
  { libelle: 'Tout', jours: null },
];

// ---------------------------------------------------------------- KPI

interface MetaKpi {
  cle: keyof Analyses['kpis'];
  libelle: string;
  icone: LucideIcon;
  couleur: string;
  format: (v: number) => string;
  note: string;
}
const KPIS: MetaKpi[] = [
  {
    cle: 'ouvertes',
    libelle: 'Activités ouvertes',
    icone: Activity,
    couleur: '#4f6bed',
    format: (v) => String(v),
    note: 'Hors clôturées',
  },
  {
    cle: 'respect_sla',
    libelle: 'Respect du SLA',
    icone: Gauge,
    couleur: '#15a394',
    format: (v) => `${v} %`,
    note: 'Sur échéances en cours',
  },
  {
    cle: 'mttr_jours',
    libelle: 'Délai moyen de résolution',
    icone: Timer,
    couleur: '#8a5cf6',
    format: (v) => `${v} j`,
    note: '90 derniers jours',
  },
  {
    cle: 'en_retard',
    libelle: 'Échéances dépassées',
    icone: AlertTriangle,
    couleur: '#d64545',
    format: (v) => String(v),
    note: 'À traiter en priorité',
  },
];

// ---------------------------------------------------------------- Donut module

interface Segment {
  nom: string;
  valeur: number;
  couleur: string;
}
function DonutModules({ data }: { data: Segment[] }): JSX.Element {
  const total = data.reduce((s, d) => s + d.valeur, 0);
  return (
    <div className={styles.donutBloc}>
      <div className={styles.donutGraphe}>
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={total === 0 ? [{ nom: 'vide', valeur: 1, couleur: 'var(--bg-subtle)' }] : data}
              dataKey="valeur"
              nameKey="nom"
              innerRadius={64}
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
          <span className={styles.donutUnite}>activités</span>
        </div>
      </div>
      <ul className={styles.legende}>
        {data.map((d) => {
          const pct = total === 0 ? 0 : Math.round((100 * d.valeur) / total);
          return (
            <li key={d.nom} className={styles.legendeItem}>
              <div className={styles.legendeTete}>
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

// ---------------------------------------------------------------- Matrice des risques

const CRITICITE_BANDE = (c: number): string => {
  // c = probabilité × impact (1..25). Dégradé vert -> ambre -> rouge.
  const ratio = (c - 1) / 24;
  const hue = 135 * (1 - ratio);
  return `hsl(${hue.toFixed(0)} 62% 45%)`;
};

function MatriceRisques({ cases }: { cases: Analyses['matrice_risques'] }): JSX.Element {
  const carte = new Map<string, number>();
  cases.forEach((c) => carte.set(`${c.probabilite}-${c.impact}`, c.valeur));
  const niveaux = [5, 4, 3, 2, 1]; // probabilité décroissante en lignes (haut = forte)
  const impacts = [1, 2, 3, 4, 5];
  return (
    <div className={styles.hm}>
      <span className={styles.hmAxeY}>Probabilité</span>
      <div className={styles.hmCorps}>
        <div className={styles.hmGrille}>
          {niveaux.map((p) => (
            <div key={p} className={styles.hmLigne}>
              <span className={styles.hmRowLabel}>{p}</span>
              {impacts.map((i) => {
                const n = carte.get(`${p}-${i}`) ?? 0;
                const couleur = CRITICITE_BANDE(p * i);
                return (
                  <div
                    key={i}
                    className={styles.hmCell}
                    style={{
                      background:
                        n > 0 ? couleur : `color-mix(in srgb, ${couleur} 14%, transparent)`,
                      color: n > 0 ? '#fff' : 'transparent',
                    }}
                    title={`Probabilité ${p} × Impact ${i} — ${n} risque(s)`}
                  >
                    {n > 0 ? n : ''}
                  </div>
                );
              })}
            </div>
          ))}
          <div className={styles.hmLigne}>
            <span className={styles.hmRowLabel} />
            {impacts.map((i) => (
              <span key={i} className={styles.hmColLabel}>
                {i}
              </span>
            ))}
          </div>
        </div>
        <span className={styles.hmAxeX}>Impact</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Jauge circulaire (SVG)

function couleurTaux(taux: number): string {
  return taux >= 90
    ? 'var(--status-ok)'
    : taux >= 75
      ? 'var(--status-warn)'
      : 'var(--status-danger)';
}

// Délai moyen de résolution : vert si rapide, ambre, rouge si lent.
function couleurMttr(jours: number | null): string {
  if (jours === null) return 'var(--cat-1)';
  return jours <= 5 ? '#1f9d55' : jours <= 20 ? '#c77700' : '#d64545';
}

interface BulleData {
  x: number;
  y: number;
  z: number;
  id: string;
  nom: string;
  couleur: string;
  suivis: number;
}

function BulleTooltip({
  active,
  payload,
}: {
  active?: boolean | undefined;
  payload?: ReadonlyArray<{ payload?: BulleData }> | undefined;
}): JSX.Element | null {
  const point = payload?.[0]?.payload;
  if (active !== true || point === undefined) return null;
  return (
    <div className={styles.bulleTip}>
      <strong>{point.nom}</strong>
      <span>
        {point.x} traités · {point.y} j de délai · {point.z} en charge
        {point.suivis > 0 && ` · ${point.suivis} suivi(s)`}
      </span>
    </div>
  );
}

function Jauge({
  taux,
  label,
  detail,
}: {
  taux: number;
  label: string;
  detail: string;
}): JSX.Element {
  const r = 32;
  const circ = 2 * Math.PI * r;
  const couleur = couleurTaux(taux);
  return (
    <div className={styles.jauge}>
      <svg viewBox="0 0 80 80" className={styles.jaugeSvg}>
        <circle cx="40" cy="40" r={r} fill="none" stroke="var(--bg-subtle)" strokeWidth="8" />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke={couleur}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - taux / 100)}
          transform="rotate(-90 40 40)"
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
        <text x="40" y="38" textAnchor="middle" fontSize="17" fontWeight="600" fill="var(--text)">
          {taux}%
        </text>
        <text x="40" y="53" textAnchor="middle" fontSize="9" fill="var(--text-muted)">
          {label}
        </text>
      </svg>
      <span className={styles.jaugeDetail}>{detail}</span>
    </div>
  );
}

// ---------------------------------------------------------------- Carte d'activité (heatmap calendrier)

const JOURS_SEMAINE = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

function HeatmapActivite({ points }: { points: PointActivite[] }): JSX.Element {
  const carte = new Map<string, number>();
  let max = 1;
  for (const p of points) {
    carte.set(`${p.jour}-${p.heure}`, p.valeur);
    if (p.valeur > max) max = p.valeur;
  }
  return (
    <div className={styles.heat}>
      {JOURS_SEMAINE.map((nom, ji) => (
        <div key={nom} className={styles.heatLigne}>
          <span className={styles.heatJour}>{nom}</span>
          <div className={styles.heatCells}>
            {Array.from({ length: 24 }, (_, h) => {
              const v = carte.get(`${ji + 1}-${h}`) ?? 0;
              const intensite = v === 0 ? 0 : Math.round(20 + 80 * (v / max));
              return (
                <span
                  key={h}
                  className={styles.heatCell}
                  title={`${nom} ${h}h — ${v} ticket(s)`}
                  style={{
                    background:
                      v === 0
                        ? 'var(--bg-subtle)'
                        : `color-mix(in srgb, var(--secondary) ${intensite}%, transparent)`,
                  }}
                />
              );
            })}
          </div>
        </div>
      ))}
      <div className={styles.heatAxe}>
        <span />
        <div className={styles.heatHeures}>
          <span>0 h</span>
          <span>6 h</span>
          <span>12 h</span>
          <span>18 h</span>
          <span>23 h</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Flux & qualité

/** Durée lisible : les séjours d'un ticket se comptent en heures autant qu'en jours. */
function formaterJours(jours: number): string {
  if (jours >= 1) return `${jours} j`;
  const heures = Math.round(jours * 24);
  return heures >= 1 ? `${heures} h` : '< 1 h';
}

/** Barres horizontales des séjours moyens par statut, module par module. */
function DureesStatuts({ durees }: { durees: Analyses['durees_statuts'] }): JSX.Element {
  const lignes = [...durees].sort((a, b) => b.jours - a.jours).slice(0, 10);
  const max = Math.max(...lignes.map((d) => d.jours), 0.01);
  if (lignes.length === 0) return <p className={styles.vide}>Aucun parcours journalisé.</p>;
  return (
    <ul className={styles.stack}>
      {lignes.map((d) => (
        <li key={`${d.module}-${d.statut}`} className={styles.stackLigne}>
          <span className={styles.stackNom} title={MODULE_LABEL[d.module] ?? d.module}>
            <span
              className={styles.pointModule}
              style={{ background: MODULE_COULEUR[d.module] ?? '#8a93a6' }}
            />
            {d.statut}
          </span>
          <div className={styles.stackBarre}>
            <span
              className={styles.stackSeg}
              style={{
                width: `${Math.max(2, (100 * d.jours) / max)}%`,
                background: MODULE_COULEUR[d.module] ?? '#8a93a6',
              }}
              title={`${MODULE_LABEL[d.module] ?? d.module} · ${d.passages} passage(s)`}
            />
          </div>
          <span className={styles.stackTot}>{formaterJours(d.jours)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Vieillissement du stock ouvert : plus c'est vieux, plus la couleur insiste. */
const TONS_AGE = ['#1f9d55', '#c77700', '#e0683c', '#d64545'];

function Vieillissement({ tranches }: { tranches: Analyses['vieillissement'] }): JSX.Element {
  const max = Math.max(...tranches.map((v) => v.valeur), 1);
  return (
    <div className={styles.ages}>
      {tranches.map((v, i) => (
        <div key={v.libelle} className={styles.age}>
          <span className={styles.ageValeur}>{v.valeur}</span>
          <div className={styles.ageColonne}>
            <div
              className={styles.agePlein}
              style={{
                height: `${Math.max(4, (100 * v.valeur) / max)}%`,
                background: TONS_AGE[i] ?? '#8a93a6',
              }}
            />
          </div>
          <span className={styles.ageLibelle}>{v.libelle}</span>
        </div>
      ))}
    </div>
  );
}

/** Part DSI / DBS des tickets importés : une seule barre, deux camps. */
function PartDbs({ dbs }: { dbs: Analyses['dbs'] }): JSX.Element {
  const total = dbs.dsi + dbs.dbs;
  const partDbs = total === 0 ? 0 : Math.round((100 * dbs.dbs) / total);
  return (
    <div className={styles.dbsBloc}>
      <div className={styles.dbsBarre}>
        <span className={styles.dbsSegDsi} style={{ width: `${100 - partDbs}%` }} />
        <span className={styles.dbsSegDbs} style={{ width: `${partDbs}%` }} />
      </div>
      <ul className={styles.miniLegende}>
        <li>
          <span className={styles.tiret} style={{ background: 'var(--secondary)' }} />
          DSI · {dbs.dsi}
        </li>
        <li>
          <span className={styles.tiret} style={{ background: '#c77700' }} />
          DBS · {dbs.dbs} ({partDbs} %)
        </li>
      </ul>
      <p className={styles.dbsNote}>
        {dbs.dbs_ouverts === 0
          ? 'Aucun ticket ouvert chez DBS.'
          : `${dbs.dbs_ouverts} ticket(s) encore ouvert(s) chez DBS` +
            (dbs.dbs_age_jours !== null
              ? `, depuis ${Math.round(dbs.dbs_age_jours)} j en moyenne.`
              : '.')}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- Page

export function AnalysesPage(): JSX.Element {
  const [a, setA] = useState<Analyses | null>(null);
  const [evals, setEvals] = useState<GestionnaireEval[]>([]);
  const [jours, setJours] = useState<number | null>(null);
  const [onglet, setOnglet] = useState<CleOnglet>('apercu');
  const [gestSel, setGestSel] = useState<string | null>(null);
  const [gestDetail, setGestDetail] = useState<GestionnaireDetail | null>(null);
  const contenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void analysesApi.charger(jours).then(setA);
  }, [jours]);
  useEffect(() => {
    void analysesApi.gestionnaires(jours).then(setEvals);
  }, [jours]);
  useEffect(() => {
    if (gestSel === null) {
      setGestDetail(null);
      return;
    }
    setGestDetail(null);
    void analysesApi.gestionnaire(gestSel, jours).then(setGestDetail);
  }, [gestSel, jours]);

  const modules: Segment[] = (a?.par_module ?? []).map((m) => ({
    nom: MODULE_LABEL[m.libelle] ?? m.libelle,
    valeur: m.valeur,
    couleur: MODULE_COULEUR[m.libelle] ?? '#94a3b8',
  }));
  const slaModules = (a?.sla_par_module ?? []).map((s) => ({
    nom: MODULE_LABEL[s.module] ?? s.module,
    a_lheure: s.a_lheure,
    approche: s.approche,
    depasse: s.depasse,
  }));
  const priorites = (a?.par_priorite ?? []).map((p) => ({
    name: p.libelle,
    valeur: p.valeur,
    fill: PRIORITE_COULEUR[p.libelle] ?? '#8a93a6',
  }));
  const bulles: BulleData[] = evals.map((e) => ({
    x: e.volume,
    y: e.mttr_jours ?? 0,
    z: Math.max(1, e.charge ?? 0),
    id: e.id,
    nom: e.gestionnaire,
    couleur: couleurMttr(e.mttr_jours),
    suivis: e.suivis,
  }));
  const detailTaux =
    gestDetail && gestDetail.volume > 0
      ? Math.round((gestDetail.resolus * 100) / gestDetail.volume)
      : 0;

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Analyses</h1>
          <p className={incidents.sous}>
            Pilotage transverse : performance SLA, charge, priorités et exposition au risque.
          </p>
        </div>
        <div className={styles.actionsAnalyse}>
          <div className={styles.periodes}>
            {PERIODES.map((p) => (
              <button
                key={p.libelle}
                className={jours === p.jours ? styles.periodeOn : styles.periode}
                onClick={() => setJours(p.jours)}
              >
                {p.libelle}
              </button>
            ))}
          </div>
          <BoutonExportPdf
            cible={contenuRef}
            titre="Analyses DSI"
            nomFichier="dsi360-analyses.pdf"
          />
        </div>
      </header>

      <div
        ref={contenuRef}
        style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}
      >
        <section className={styles.kpiRow}>
          {KPIS.map((k) => {
            const Icone = k.icone;
            return (
              <Card key={k.cle} className={styles.kpiCarte}>
                <span
                  className={styles.kpiIcone}
                  style={{
                    color: k.couleur,
                    background: `color-mix(in srgb, ${k.couleur} 14%, transparent)`,
                  }}
                >
                  <Icone size={20} />
                </span>
                <span className={styles.kpiValeur}>{a ? k.format(a.kpis[k.cle]) : '—'}</span>
                <span className={styles.kpiLibelle}>{k.libelle}</span>
                <span className={styles.kpiNote}>{k.note}</span>
              </Card>
            );
          })}
        </section>

        <div className={styles.onglets}>
          {ONGLETS.map((o) => (
            <button
              key={o.cle}
              className={onglet === o.cle ? styles.ongletOn : styles.onglet}
              onClick={() => setOnglet(o.cle)}
            >
              {o.libelle}
            </button>
          ))}
        </div>

        {onglet === 'apercu' && (
          <section className={styles.grille}>
            <Card className={styles.span2}>
              <h2 className={styles.chartTitre}>Tendance — créations vs résolutions</h2>
              <p className={styles.chartSous}>Volume hebdomadaire sur les 8 dernières semaines.</p>
              <ResponsiveContainer width="100%" height={240}>
                <ComposedChart
                  data={a?.tendance ?? []}
                  margin={{ top: 10, right: 12, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="grad-crees" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4f6bed" stopOpacity={0.32} />
                      <stop offset="100%" stopColor="#4f6bed" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="grad-resolus" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#1f9d55" stopOpacity={0.26} />
                      <stop offset="100%" stopColor="#1f9d55" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} strokeDasharray="4 4" stroke="var(--border)" />
                  <XAxis
                    dataKey="periode"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 12, fill: 'var(--text-muted)' }}
                  />
                  <YAxis hide allowDecimals={false} />
                  <Tooltip {...infobulle} cursor={{ stroke: 'var(--border)', strokeWidth: 1 }} />
                  <Area
                    type="monotone"
                    dataKey="crees"
                    name="Créées"
                    stroke="#4f6bed"
                    strokeWidth={2.5}
                    fill="url(#grad-crees)"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="resolus"
                    name="Résolues"
                    stroke="#1f9d55"
                    strokeWidth={2.5}
                    fill="url(#grad-resolus)"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
              <ul className={styles.miniLegende}>
                <li>
                  <span className={styles.tiret} style={{ background: '#4f6bed' }} />
                  Créées
                </li>
                <li>
                  <span className={styles.tiret} style={{ background: '#1f9d55' }} />
                  Résolues
                </li>
              </ul>
            </Card>

            <Card>
              <h2 className={styles.chartTitre}>Répartition par module</h2>
              <DonutModules data={modules} />
            </Card>

            <Card>
              <h2 className={styles.chartTitre}>Performance SLA par module</h2>
              <p className={styles.chartSous}>Répartition à l'heure · approche · dépassé.</p>
              <ul className={styles.stack}>
                {slaModules.map((m) => {
                  const tot = Math.max(1, m.a_lheure + m.approche + m.depasse);
                  return (
                    <li key={m.nom} className={styles.stackLigne}>
                      <span className={styles.stackNom}>{m.nom}</span>
                      <div className={styles.stackBarre}>
                        {SLA_SEGMENTS.map((s) => {
                          const v = m[s.cle];
                          if (v === 0) return null;
                          return (
                            <span
                              key={s.cle}
                              className={styles.stackSeg}
                              title={`${s.nom} : ${v}`}
                              style={{ width: `${(100 * v) / tot}%`, background: s.couleur }}
                            />
                          );
                        })}
                      </div>
                      <span className={styles.stackTot}>{m.a_lheure + m.approche + m.depasse}</span>
                    </li>
                  );
                })}
              </ul>
              <ul className={styles.miniLegende}>
                {SLA_SEGMENTS.map((s) => (
                  <li key={s.cle}>
                    <span className={styles.tiret} style={{ background: s.couleur }} />
                    {s.nom}
                  </li>
                ))}
              </ul>
            </Card>

            <Card className={styles.span2}>
              <h2 className={styles.chartTitre}>Carte d'activité</h2>
              <p className={styles.chartSous}>
                Volume de tickets créés par jour de semaine et heure — repère les pics de charge.
              </p>
              <HeatmapActivite points={a?.activite ?? []} />
            </Card>
          </section>
        )}

        {onglet === 'flux' && (
          <section className={styles.grille}>
            <Card>
              <h2 className={styles.chartTitre}>Où le temps se perd</h2>
              <p className={styles.chartSous}>
                Séjour moyen dans chaque statut, reconstitué du journal — les goulots se voient.
              </p>
              <DureesStatuts durees={a?.durees_statuts ?? []} />
            </Card>

            <Card>
              <h2 className={styles.chartTitre}>Vieillissement du stock ouvert</h2>
              <p className={styles.chartSous}>
                Ancienneté des activités non clôturées — le vieux stock est le plus coûteux.
              </p>
              <Vieillissement tranches={a?.vieillissement ?? []} />
            </Card>

            <Card className={styles.span2}>
              <h2 className={styles.chartTitre}>Ce qui casse le plus</h2>
              <p className={styles.chartSous}>
                Pareto des catégories : volumes décroissants, part cumulée en surimpression.
              </p>
              {(a?.pareto_categories ?? []).length === 0 ? (
                <p className={styles.vide}>Aucune catégorie renseignée.</p>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <ComposedChart
                    data={a?.pareto_categories ?? []}
                    margin={{ top: 10, right: 8, left: -18, bottom: 0 }}
                  >
                    <CartesianGrid vertical={false} strokeDasharray="4 4" stroke="var(--border)" />
                    <XAxis
                      dataKey="libelle"
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
                      interval={0}
                      angle={-18}
                      textAnchor="end"
                      height={52}
                    />
                    <YAxis yAxisId="v" hide allowDecimals={false} />
                    <YAxis yAxisId="pct" hide domain={[0, 100]} />
                    <Tooltip {...infobulle} />
                    <Bar
                      yAxisId="v"
                      dataKey="valeur"
                      name="Volume"
                      fill="var(--secondary)"
                      radius={[6, 6, 0, 0]}
                      maxBarSize={38}
                    />
                    <Line
                      yAxisId="pct"
                      type="monotone"
                      dataKey="cumul_pct"
                      name="Cumul (%)"
                      stroke="#c77700"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card>
              <h2 className={styles.chartTitre}>Résolutions qui n'ont pas tenu</h2>
              <p className={styles.chartSous}>
                Tickets rouverts après résolution — le taux dit la qualité, pas la vitesse.
              </p>
              <ul className={styles.stack}>
                {(a?.reouvertures ?? []).map((r) => (
                  <li key={r.libelle} className={styles.stackLigne}>
                    <span className={styles.stackNom}>{MODULE_LABEL[r.libelle] ?? r.libelle}</span>
                    <div className={styles.stackBarre}>
                      {r.taux > 0 && (
                        <span
                          className={styles.stackSeg}
                          style={{ width: `${Math.max(3, r.taux)}%`, background: '#d64545' }}
                          title={`${r.rouverts} rouvert(s) / ${r.resolus} résolu(s)`}
                        />
                      )}
                    </div>
                    <span
                      className={styles.stackTot}
                      style={{ color: r.taux > 10 ? '#d64545' : 'var(--text-muted)' }}
                    >
                      {r.taux} %
                    </span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <h2 className={styles.chartTitre}>Tickets restés chez DBS</h2>
              <p className={styles.chartSous}>
                Gestionnaire hors DSI = transféré (ADR-0005). Ce volume nous échappe.
              </p>
              <PartDbs dbs={a?.dbs ?? { dsi: 0, dbs: 0, dbs_ouverts: 0, dbs_age_jours: null }} />
            </Card>

            <Card className={styles.span2}>
              <h2 className={styles.chartTitre}>Prise en charge — la première promesse</h2>
              <p className={styles.chartSous}>
                Part des tickets pris en charge dans la cible de leur priorité (durées réelles).
              </p>
              {(a?.pec_par_priorite ?? []).length === 0 ? (
                <p className={styles.vide}>Aucune durée de prise en charge mesurée.</p>
              ) : (
                <div className={styles.jauges}>
                  {(a?.pec_par_priorite ?? []).map((p) => (
                    <Jauge
                      key={p.priorite}
                      taux={p.taux}
                      label={p.priorite}
                      detail={`${p.dans_delai}/${p.total}`}
                    />
                  ))}
                </div>
              )}
            </Card>
          </section>
        )}

        {onglet === 'priorites' && (
          <section className={styles.grille}>
            <Card>
              <h2 className={styles.chartTitre}>Répartition par priorité</h2>
              <p className={styles.chartSous}>
                Activités ouvertes par niveau de priorité (P1 critique → P5 faible).
              </p>
              <div className={styles.radialBloc}>
                <ResponsiveContainer width="100%" height={300}>
                  <RadialBarChart
                    innerRadius="32%"
                    outerRadius="100%"
                    data={priorites}
                    startAngle={90}
                    endAngle={-270}
                  >
                    <RadialBar
                      dataKey="valeur"
                      cornerRadius={6}
                      background={{ fill: 'var(--bg-subtle)' }}
                    >
                      {priorites.map((p) => (
                        <Cell key={p.name} fill={p.fill} />
                      ))}
                    </RadialBar>
                    <Tooltip {...infobulle} />
                  </RadialBarChart>
                </ResponsiveContainer>
                <ul className={styles.radialLegende}>
                  {priorites.map((p) => (
                    <li key={p.name}>
                      <span className={styles.pastillePrio} style={{ background: p.fill }}>
                        {p.name}
                      </span>
                      <span className={styles.legendeVal}>{p.valeur}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </Card>

            <Card>
              <h2 className={styles.chartTitre}>Matrice des risques</h2>
              <p className={styles.chartSous}>Probabilité × impact — intensité = criticité.</p>
              <MatriceRisques cases={a?.matrice_risques ?? []} />
            </Card>

            <Card className={styles.span2}>
              <h2 className={styles.chartTitre}>Respect du SLA par priorité</h2>
              <p className={styles.chartSous}>
                Part des tickets résolus dans la cible (P1 4 h · P2 8 h · P3 24 h · P4 72 h · P5 120
                h) — durées réelles.
              </p>
              {(a?.sla_par_priorite ?? []).length === 0 ? (
                <p className={styles.vide}>Aucune donnée de résolution.</p>
              ) : (
                <div className={styles.jauges}>
                  {(a?.sla_par_priorite ?? []).map((p) => (
                    <Jauge
                      key={p.priorite}
                      taux={p.taux}
                      label={p.priorite}
                      detail={`${p.dans_delai}/${p.total}`}
                    />
                  ))}
                </div>
              )}
            </Card>
          </section>
        )}

        {onglet === 'equipe' && (
          <>
            <div className={styles.barreGest}>
              <span className={styles.barreGestLib}>Gestionnaire</span>
              <div className={styles.barreGestSelect}>
                <SelecteurListe
                  options={evals.map((e) => ({ valeur: e.id, libelle: e.gestionnaire }))}
                  valeur={gestSel}
                  onChange={setGestSel}
                  placeholder="Tous les gestionnaires"
                  permettreVide
                  libelleVide="Tous les gestionnaires"
                />
              </div>
            </div>

            {gestSel === null ? (
              <section className={styles.grille}>
                <Card className={styles.span2}>
                  <h2 className={styles.chartTitre}>Cartographie des gestionnaires</h2>
                  <p className={styles.chartSous}>
                    Une bulle par agent — abscisse : volume traité · ordonnée : délai moyen (jours)
                    · taille : charge ouverte. Cliquez une bulle pour le détail.
                  </p>
                  {bulles.length === 0 ? (
                    <p className={styles.vide}>Aucune donnée.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={360}>
                      <ScatterChart margin={{ top: 12, right: 24, bottom: 24, left: 4 }}>
                        <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
                        <XAxis
                          type="number"
                          dataKey="x"
                          name="Volume"
                          tick={{ fontSize: 12, fill: 'var(--text-muted)' }}
                          axisLine={false}
                          tickLine={false}
                          label={{
                            value: 'Volume traité',
                            position: 'insideBottom',
                            offset: -10,
                            fill: 'var(--text-muted)',
                            fontSize: 12,
                          }}
                        />
                        <YAxis
                          type="number"
                          dataKey="y"
                          name="Délai (j)"
                          tick={{ fontSize: 12, fill: 'var(--text-muted)' }}
                          axisLine={false}
                          tickLine={false}
                          label={{
                            value: 'Délai moyen (j)',
                            angle: -90,
                            position: 'insideLeft',
                            fill: 'var(--text-muted)',
                            fontSize: 12,
                          }}
                        />
                        <ZAxis type="number" dataKey="z" range={[120, 900]} name="Charge" />
                        <Tooltip
                          {...infobulle}
                          cursor={{ strokeDasharray: '3 3' }}
                          content={BulleTooltip}
                        />
                        <Scatter
                          data={bulles}
                          onClick={(e: unknown) => {
                            const o = e as { id?: string; payload?: { id?: string } };
                            const id = o.id ?? o.payload?.id;
                            if (id !== undefined) setGestSel(id);
                          }}
                        >
                          {bulles.map((b) => (
                            <Cell
                              key={b.id}
                              fill={b.couleur}
                              fillOpacity={0.75}
                              stroke={b.couleur}
                            />
                          ))}
                        </Scatter>
                      </ScatterChart>
                    </ResponsiveContainer>
                  )}
                  <ul className={styles.miniLegende}>
                    <li>
                      <span className={styles.tiret} style={{ background: '#1f9d55' }} />≤ 5 j
                    </li>
                    <li>
                      <span className={styles.tiret} style={{ background: '#c77700' }} />≤ 20 j
                    </li>
                    <li>
                      <span className={styles.tiret} style={{ background: '#d64545' }} />
                      &gt; 20 j
                    </li>
                  </ul>
                </Card>
              </section>
            ) : (
              <section className={styles.grille}>
                <Card className={styles.span2}>
                  <div className={styles.gestTete}>
                    <AvatarPersonnage seed={gestDetail?.gestionnaire ?? gestSel} taille={44} />
                    <div>
                      <h2 className={styles.chartTitre}>{gestDetail?.gestionnaire ?? '…'}</h2>
                      <p className={styles.chartSous}>État et charge du gestionnaire</p>
                    </div>
                  </div>
                  <div className={styles.gestKpis}>
                    <div className={styles.gestKpi}>
                      <span className={styles.gestVal}>{gestDetail?.volume ?? '—'}</span>
                      <span className={styles.gestLib}>Volume traité</span>
                    </div>
                    <div className={styles.gestKpi}>
                      <span className={styles.gestVal} style={{ color: 'var(--cat-1)' }}>
                        {gestDetail?.charge ?? '—'}
                      </span>
                      <span className={styles.gestLib}>Charge ouverte</span>
                    </div>
                    <div className={styles.gestKpi}>
                      <span
                        className={styles.gestVal}
                        style={{ color: couleurMttr(gestDetail?.mttr_jours ?? null) }}
                      >
                        {gestDetail?.mttr_jours ?? '—'} j
                      </span>
                      <span className={styles.gestLib}>Délai moyen</span>
                    </div>
                    <div className={styles.gestKpi}>
                      <span className={styles.gestVal} style={{ color: couleurTaux(detailTaux) }}>
                        {detailTaux}%
                      </span>
                      <span className={styles.gestLib}>Taux résolution</span>
                    </div>
                    <div className={styles.gestKpi}>
                      <span className={styles.gestVal}>{gestDetail?.suivis ?? '—'}</span>
                      <span className={styles.gestLib}>Suivis (contributeur)</span>
                    </div>
                  </div>
                </Card>

                <Card className={styles.span2}>
                  <h2 className={styles.chartTitre}>Charge horodatée</h2>
                  <p className={styles.chartSous}>
                    Tickets pris en charge par jour de semaine et heure — rythme de travail de
                    l'agent.
                  </p>
                  <HeatmapActivite points={gestDetail?.activite ?? []} />
                </Card>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
