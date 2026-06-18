import { useEffect, useState } from 'react';
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
  CartesianGrid,
} from 'recharts';
import { Card } from '@/design-system/primitives';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import { infobulle } from '@/common/infobulle';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import styles from './Analyses.module.css';
import {
  analysesApi,
  type Analyses,
  type GestionnaireEval,
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
const PALETTE = ['#4f6bed', '#15a394', '#e0a341', '#e2557b', '#8a5cf6', '#2fa363', '#3aa0c9', '#e07a3c'];

type CleOnglet = 'apercu' | 'priorites' | 'equipe';
const ONGLETS: { cle: CleOnglet; libelle: string }[] = [
  { cle: 'apercu', libelle: "Vue d'ensemble" },
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

// ---------------------------------------------------------------- Jauge circulaire (SVG)

function couleurTaux(taux: number): string {
  return taux >= 90 ? 'var(--status-ok)' : taux >= 75 ? 'var(--status-warn)' : 'var(--status-danger)';
}

function Jauge({ taux, label, detail }: { taux: number; label: string; detail: string }): JSX.Element {
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
              const intensite = v === 0 ? 0 : Math.round((20 + 80 * (v / max)));
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

// ---------------------------------------------------------------- Page

export function AnalysesPage(): JSX.Element {
  const [a, setA] = useState<Analyses | null>(null);
  const [evals, setEvals] = useState<GestionnaireEval[]>([]);
  const [jours, setJours] = useState<number | null>(null);
  const [onglet, setOnglet] = useState<CleOnglet>('apercu');

  useEffect(() => {
    void analysesApi.charger(jours).then(setA);
  }, [jours]);
  useEffect(() => {
    void analysesApi.gestionnaires().then(setEvals);
  }, []);

  const volMax = Math.max(1, ...evals.map((e) => e.volume));

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
  const chargeMax = Math.max(1, ...responsables.map((r) => r.valeur));

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Analyses</h1>
          <p className={incidents.sous}>
            Pilotage transverse : performance SLA, charge, priorités et exposition au risque.
          </p>
        </div>
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
            <ComposedChart data={a?.tendance ?? []} margin={{ top: 10, right: 12, left: -20, bottom: 0 }}>
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
              <XAxis dataKey="periode" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: 'var(--text-muted)' }} />
              <YAxis hide allowDecimals={false} />
              <Tooltip {...infobulle} cursor={{ stroke: 'var(--border)', strokeWidth: 1 }} />
              <Area type="monotone" dataKey="crees" name="Créées" stroke="#4f6bed" strokeWidth={2.5} fill="url(#grad-crees)" dot={false} activeDot={{ r: 4 }} />
              <Area type="monotone" dataKey="resolus" name="Résolues" stroke="#1f9d55" strokeWidth={2.5} fill="url(#grad-resolus)" dot={false} activeDot={{ r: 4 }} />
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

        <Card className={styles.span2}>
          <h2 className={styles.chartTitre}>Carte d'activité</h2>
          <p className={styles.chartSous}>
            Volume de tickets créés par jour de semaine et heure — repère les pics de charge.
          </p>
          <HeatmapActivite points={a?.activite ?? []} />
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
              <li key={s.cle}><span className={styles.tiret} style={{ background: s.couleur }} />{s.nom}</li>
            ))}
          </ul>
        </Card>
        </section>
      )}

      {onglet === 'priorites' && (
        <section className={styles.grille}>
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
          <h2 className={styles.chartTitre}>Respect du SLA par priorité</h2>
          <p className={styles.chartSous}>
            Part des tickets résolus dans la cible (P1 4 h · P2 8 h · P3 24 h · P4 72 h · P5 120 h) —
            durées réelles.
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
        <section className={styles.grille}>
        <Card className={styles.span2}>
          <h2 className={styles.chartTitre}>Charge par responsable</h2>
          {responsables.length === 0 ? (
            <p className={styles.vide}>Aucune donnée.</p>
          ) : (
            <ul className={styles.charge}>
              {responsables.map((r) => (
                <li key={r.libelle} className={styles.chargeLigne}>
                  <AvatarPersonnage seed={r.libelle} taille={30} />
                  <div className={styles.chargeCorps}>
                    <div className={styles.chargeTete}>
                      <span className={styles.chargeNom}>{r.libelle}</span>
                      <span className={styles.chargeVal}>{r.valeur}</span>
                    </div>
                    <div className={styles.chargeBarre}>
                      <div
                        className={styles.chargePlein}
                        style={{ width: `${Math.round((r.valeur * 100) / chargeMax)}%`, background: r.couleur }}
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className={styles.span2}>
          <h2 className={styles.chartTitre}>Évaluation des gestionnaires</h2>
          <p className={styles.chartSous}>
            Volume traité, délai moyen de résolution (jours) et de prise en charge (heures) —
            mesures réelles issues du ticketing.
          </p>
          {evals.length === 0 ? (
            <p className={styles.vide}>Aucune donnée d’évaluation.</p>
          ) : (
            <ul className={styles.eval}>
              {evals.map((g, i) => {
                const pct = Math.round((g.volume * 100) / volMax);
                const taux = g.volume > 0 ? Math.round((g.resolus * 100) / g.volume) : 0;
                return (
                  <li key={g.gestionnaire} className={styles.evalLigne}>
                    <span className={styles.evalRang}>{i + 1}</span>
                    <AvatarPersonnage seed={g.gestionnaire} taille={34} />
                    <div className={styles.evalCorps}>
                      <div className={styles.evalTete}>
                        <span className={styles.evalNom}>{g.gestionnaire}</span>
                        <span className={styles.evalVol}>{g.volume} tickets</span>
                      </div>
                      <div className={styles.evalBarre}>
                        <div className={styles.evalPlein} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                    <div className={styles.evalMets}>
                      <span className={styles.metric}>
                        <b>{g.mttr_jours ?? '—'}</b> j MTTR
                      </span>
                      <span className={styles.metric}>
                        <b>{g.prise_en_charge_h ?? '—'}</b> h prise
                      </span>
                      <span className={styles.metric}>
                        <b>{taux}%</b> résolus
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
        </section>
      )}
    </div>
  );
}
