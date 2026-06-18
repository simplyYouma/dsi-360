import { useEffect, useState } from 'react';
import { Activity, Gauge, Timer, AlertTriangle, type LucideIcon } from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  RadialBarChart,
  RadialBar,
  ComposedChart,
  Area,
  Line,
} from 'recharts';
import { Card } from '@/design-system/primitives';
import { infobulle } from '@/common/infobulle';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import styles from './Analyses.module.css';
import { analysesApi, type Analyses } from './analysesApi';

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
const PALETTE = ['#4f6bed', '#15a394', '#e0a341', '#e2557b', '#8a5cf6', '#2fa363', '#3aa0c9', '#e07a3c'];

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
  { cle: 'ouvertes', libelle: 'Activités ouvertes', icone: Activity, couleur: '#4f6bed', format: (v) => String(v), note: 'Hors clôturées' },
  { cle: 'respect_sla', libelle: 'Respect du SLA', icone: Gauge, couleur: '#15a394', format: (v) => `${v} %`, note: 'Sur échéances en cours' },
  { cle: 'mttr_jours', libelle: 'Délai moyen de résolution', icone: Timer, couleur: '#8a5cf6', format: (v) => `${v} j`, note: '90 derniers jours' },
  { cle: 'en_retard', libelle: 'Échéances dépassées', icone: AlertTriangle, couleur: '#d64545', format: (v) => String(v), note: 'À traiter en priorité' },
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
                <div className={styles.trackPlein} style={{ width: `${pct}%`, background: d.couleur }} />
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
                        n > 0
                          ? couleur
                          : `color-mix(in srgb, ${couleur} 14%, transparent)`,
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

// ---------------------------------------------------------------- Page

export function AnalysesPage(): JSX.Element {
  const [a, setA] = useState<Analyses | null>(null);

  useEffect(() => {
    void analysesApi.charger().then(setA);
  }, []);

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
  const responsables = (a?.par_responsable ?? []).map((r, i) => ({
    libelle: r.libelle,
    valeur: r.valeur,
    couleur: PALETTE[i % PALETTE.length] ?? '#4f6bed',
  }));

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Analyses</h1>
          <p className={incidents.sous}>
            Pilotage transverse : performance SLA, charge, priorités et exposition au risque.
          </p>
        </div>
      </header>

      <section className={styles.kpiRow}>
        {KPIS.map((k) => {
          const Icone = k.icone;
          return (
            <Card key={k.cle} className={styles.kpiCarte}>
              <span className={styles.kpiIcone} style={{ color: k.couleur, background: `color-mix(in srgb, ${k.couleur} 14%, transparent)` }}>
                <Icone size={20} />
              </span>
              <span className={styles.kpiValeur}>{a ? k.format(a.kpis[k.cle]) : '—'}</span>
              <span className={styles.kpiLibelle}>{k.libelle}</span>
              <span className={styles.kpiNote}>{k.note}</span>
            </Card>
          );
        })}
      </section>

      <section className={styles.grille}>
        <Card className={styles.span2}>
          <h2 className={styles.chartTitre}>Tendance — créations vs résolutions</h2>
          <p className={styles.chartSous}>Volume hebdomadaire sur les 8 dernières semaines.</p>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={a?.tendance ?? []} margin={{ top: 10, right: 12, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="grad-crees" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4f6bed" stopOpacity={0.32} />
                  <stop offset="100%" stopColor="#4f6bed" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="periode" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: 'var(--text-muted)' }} />
              <YAxis hide allowDecimals={false} />
              <Tooltip {...infobulle} />
              <Area type="monotone" dataKey="crees" name="Créées" stroke="#4f6bed" strokeWidth={2.5} fill="url(#grad-crees)" dot={false} activeDot={{ r: 4 }} />
              <Line type="monotone" dataKey="resolus" name="Résolues" stroke="#1f9d55" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
          <ul className={styles.miniLegende}>
            <li><span className={styles.tiret} style={{ background: '#4f6bed' }} />Créées</li>
            <li><span className={styles.tiret} style={{ background: '#1f9d55' }} />Résolues</li>
          </ul>
        </Card>

        <Card>
          <h2 className={styles.chartTitre}>Répartition par module</h2>
          <DonutModules data={modules} />
        </Card>

        <Card>
          <h2 className={styles.chartTitre}>Performance SLA par module</h2>
          <p className={styles.chartSous}>À l'heure, en approche et dépassé.</p>
          <ResponsiveContainer width="100%" height={Math.max(180, slaModules.length * 38)}>
            <BarChart layout="vertical" data={slaModules} margin={{ top: 0, right: 12, left: 8, bottom: 0 }} barCategoryGap={10}>
              <XAxis type="number" hide allowDecimals={false} />
              <YAxis type="category" dataKey="nom" width={104} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: 'var(--text-muted)' }} />
              <Tooltip {...infobulle} cursor={{ fill: 'var(--bg-subtle)' }} />
              {SLA_SEGMENTS.map((s, i) => (
                <Bar
                  key={s.cle}
                  dataKey={s.cle}
                  name={s.nom}
                  stackId="sla"
                  fill={s.couleur}
                  radius={i === SLA_SEGMENTS.length - 1 ? [0, 6, 6, 0] : [0, 0, 0, 0]}
                  barSize={18}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <ul className={styles.miniLegende}>
            {SLA_SEGMENTS.map((s) => (
              <li key={s.cle}><span className={styles.tiret} style={{ background: s.couleur }} />{s.nom}</li>
            ))}
          </ul>
        </Card>

        <Card>
          <h2 className={styles.chartTitre}>Répartition par priorité</h2>
          <div className={styles.radialBloc}>
            <ResponsiveContainer width="100%" height={210}>
              <RadialBarChart innerRadius="28%" outerRadius="100%" data={priorites} startAngle={90} endAngle={-270}>
                <RadialBar dataKey="valeur" cornerRadius={6} background={{ fill: 'var(--bg-subtle)' }}>
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
                  <span className={styles.pastillePrio} style={{ background: p.fill }}>{p.name}</span>
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
          <h2 className={styles.chartTitre}>Charge par responsable</h2>
          {responsables.length === 0 ? (
            <p className={styles.vide}>Aucune donnée.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(160, responsables.length * 40)}>
              <BarChart layout="vertical" data={responsables} margin={{ top: 0, right: 28, left: 8, bottom: 0 }}>
                <XAxis type="number" hide allowDecimals={false} />
                <YAxis type="category" dataKey="libelle" width={150} tickLine={false} axisLine={false} tick={{ fontSize: 13, fill: 'var(--text-muted)' }} />
                <Tooltip {...infobulle} cursor={{ fill: 'var(--bg-subtle)' }} />
                <Bar dataKey="valeur" radius={[0, 8, 8, 0]} barSize={18} label={{ position: 'right', fill: 'var(--text-muted)', fontSize: 12 }}>
                  {responsables.map((r) => (
                    <Cell key={r.libelle} fill={r.couleur} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </section>
    </div>
  );
}
