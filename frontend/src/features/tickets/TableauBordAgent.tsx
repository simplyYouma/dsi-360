import { Inbox, AlertTriangle, CheckCircle2, Gauge, Timer } from 'lucide-react';
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import { BoutonExportPng } from '@/common/BoutonExportPng';
import { infobulle } from '@/common/infobulle';
import { LIBELLE_MODULE } from '@/common/routesModule';
import styles from './MesTickets.module.css';
import type { MesStats } from './mesTicketsApi';

const PRIORITE_COULEUR: Record<string, string> = {
  P1: 'var(--status-danger)',
  P2: '#e0683c',
  P3: 'var(--status-warn)',
  P4: 'var(--cat-1)',
  P5: 'var(--text-muted)',
};
const MODULE_COULEUR: Record<string, string> = {
  incident: 'var(--cat-1)',
  demande: 'var(--cat-2)',
  changement: 'var(--cat-4)',
  audit: 'var(--cat-5)',
  cybersecurite: 'var(--cat-4)',
  gouvernance: 'var(--cat-6)',
};

function couleurTaux(taux: number): string {
  return taux >= 90
    ? 'var(--status-ok)'
    : taux >= 75
      ? 'var(--status-warn)'
      : 'var(--status-danger)';
}

/** Jauge circulaire (SVG) — % de respect SLA personnel. Sans résolution, rien à noter : « — ». */
function Jauge({ taux, mesure }: { taux: number; mesure: boolean }): JSX.Element {
  const r = 34;
  const circ = 2 * Math.PI * r;
  const couleur = mesure ? couleurTaux(taux) : 'var(--bg-subtle)';
  return (
    <svg viewBox="0 0 88 88" className={styles.jaugeSvg}>
      <circle cx="44" cy="44" r={r} fill="none" stroke="var(--bg-subtle)" strokeWidth="9" />
      <circle
        cx="44"
        cy="44"
        r={r}
        fill="none"
        stroke={couleur}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={mesure ? circ * (1 - taux / 100) : circ}
        transform="rotate(-90 44 44)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="44" y="42" textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--text)">
        {mesure ? `${taux}%` : '—'}
      </text>
      <text x="44" y="57" textAnchor="middle" fontSize="9" fill="var(--text-muted)">
        respect SLA
      </text>
    </svg>
  );
}

/** Anneau (donut) de la file ouverte par état SLA. */
function AnneauSla({ stats }: { stats: MesStats }): JSX.Element {
  const data = [
    { nom: "À l'heure", valeur: stats.a_lheure, couleur: 'var(--status-ok)' },
    { nom: 'Échéance proche', valeur: stats.approche, couleur: 'var(--status-warn)' },
    { nom: 'Dépassé', valeur: stats.en_retard, couleur: 'var(--status-danger)' },
  ];
  const total = data.reduce((s, d) => s + d.valeur, 0);
  return (
    <div className={styles.anneauBloc}>
      <div className={styles.anneauGraphe}>
        <ResponsiveContainer width="100%" height={150}>
          <PieChart>
            <Pie
              data={total === 0 ? [{ nom: 'vide', valeur: 1, couleur: 'var(--bg-subtle)' }] : data}
              dataKey="valeur"
              nameKey="nom"
              innerRadius={48}
              outerRadius={68}
              cornerRadius={7}
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
        <div className={styles.anneauCentre}>
          <span className={styles.anneauTotal}>{total}</span>
          <span className={styles.anneauUnite}>avec SLA</span>
        </div>
      </div>
      {total === 0 ? (
        <p className={styles.vide}>Aucun ticket ouvert ne porte d'échéance SLA.</p>
      ) : (
        <ul className={styles.legende}>
          {data.map((d) => (
            <li key={d.nom}>
              <span className={styles.pastille} style={{ background: d.couleur }} />
              <span className={styles.legendeNom}>{d.nom}</span>
              <span className={styles.legendeVal}>{d.valeur}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Barres horizontales (priorité ou module). */
function Barres({
  data,
  couleurs,
  libelle,
}: {
  data: { libelle: string; valeur: number }[];
  couleurs: Record<string, string>;
  libelle?: (cle: string) => string;
}): JSX.Element {
  const max = Math.max(1, ...data.map((d) => d.valeur));
  if (data.every((d) => d.valeur === 0)) return <p className={styles.vide}>Aucun ticket ouvert.</p>;
  return (
    <ul className={styles.barres}>
      {data.map((d) => (
        <li key={d.libelle} className={styles.barreLigne}>
          <span className={styles.barreNom}>{libelle ? libelle(d.libelle) : d.libelle}</span>
          <div className={styles.barreTrack}>
            <div
              className={styles.barrePlein}
              style={{
                width: `${(100 * d.valeur) / max}%`,
                background: couleurs[d.libelle] ?? 'var(--cat-1)',
              }}
            />
          </div>
          <span className={styles.barreVal}>{d.valeur}</span>
        </li>
      ))}
    </ul>
  );
}

const KPIS = (
  s: MesStats,
): { cle: string; icone: typeof Inbox; valeur: string; libelle: string; couleur: string }[] => [
  {
    cle: 'ouverts',
    icone: Inbox,
    valeur: String(s.ouverts),
    libelle: 'À traiter',
    couleur: 'var(--text)',
  },
  {
    cle: 'retard',
    icone: AlertTriangle,
    valeur: String(s.en_retard),
    libelle: 'SLA dépassé',
    couleur: 'var(--status-danger)',
  },
  {
    cle: 'resolus',
    icone: CheckCircle2,
    valeur: String(s.resolus_periode),
    libelle: 'Résolus',
    couleur: 'var(--status-ok)',
  },
  {
    cle: 'sla',
    icone: Gauge,
    valeur: s.resolus_periode > 0 || s.respect_sla > 0 ? `${s.respect_sla} %` : '—',
    libelle: 'Respect SLA',
    couleur:
      s.resolus_periode > 0 || s.respect_sla > 0 ? couleurTaux(s.respect_sla) : 'var(--text-muted)',
  },
  {
    cle: 'mttr',
    icone: Timer,
    valeur: s.mttr_jours === null ? '—' : `${s.mttr_jours} j`,
    libelle: 'Délai moyen',
    couleur: 'var(--cat-4)',
  },
];

export function TableauBordAgent({ stats }: { stats: MesStats }): JSX.Element {
  return (
    <>
      <section className={styles.profil} data-visuel="Agent">
        <AvatarPersonnage seed={stats.agent.nom} taille={56} />
        <div className={styles.profilTxt}>
          <span className={styles.profilNom}>{stats.agent.nom}</span>
          <span className={styles.profilMeta}>
            {stats.agent.profil}
            {stats.agent.direction !== null && ` · ${stats.agent.direction}`}
          </span>
        </div>
        {stats.plus_ancien_jours !== null && (
          <div className={styles.profilAncien}>
            <span className={styles.profilAncienVal}>{stats.plus_ancien_jours} j</span>
            <span className={styles.profilAncienLib}>ticket le plus ancien</span>
          </div>
        )}
      </section>

      <section className={styles.kpis} data-visuel="Mes indicateurs">
        {KPIS(stats).map((k) => {
          const Icone = k.icone;
          return (
            <div key={k.cle} className={styles.kpi}>
              <span className={styles.kpiIcone} style={{ color: k.couleur }}>
                <Icone size={18} />
              </span>
              <span className={styles.kpiValeur} style={{ color: k.couleur }}>
                {k.valeur}
              </span>
              <span className={styles.kpiLibelle}>{k.libelle}</span>
            </div>
          );
        })}
      </section>

      <section className={styles.dash}>
        <div className={styles.carte} data-visuel="Mes tâches">
          <BoutonExportPng nom="Mes tâches" />
          <h2 className={styles.carteTitre}>Mes tâches</h2>
          <p className={styles.carteSous}>Vos tâches assignées (projets, changements).</p>
          <div className={styles.tachesResume}>
            <div className={styles.tacheStat}>
              <span className={styles.tacheVal}>{stats.taches.a_faire}</span>
              <span className={styles.tacheLib}>À faire</span>
            </div>
            <div className={styles.tacheStat}>
              <span className={styles.tacheVal} style={{ color: 'var(--cat-1)' }}>
                {stats.taches.en_cours}
              </span>
              <span className={styles.tacheLib}>En cours</span>
            </div>
            <div className={styles.tacheStat}>
              <span
                className={styles.tacheVal}
                style={{
                  color: stats.taches.en_retard > 0 ? 'var(--status-danger)' : 'var(--text)',
                }}
              >
                {stats.taches.en_retard}
              </span>
              <span className={styles.tacheLib}>En retard</span>
            </div>
          </div>
        </div>
        <div className={styles.carte} data-visuel="Respect du SLA">
          <BoutonExportPng nom="Respect du SLA" />
          <h2 className={styles.carteTitre}>Respect du SLA</h2>
          <p className={styles.carteSous}>Résolus dans la cible, sur la période.</p>
          <div className={styles.jaugeWrap}>
            <Jauge
              taux={stats.respect_sla}
              mesure={stats.resolus_periode > 0 || stats.respect_sla > 0}
            />
            <span className={styles.jaugeNote}>
              {stats.resolus_periode === 0
                ? 'Aucun ticket résolu sur la période'
                : `${stats.resolus_periode} résolu${stats.resolus_periode > 1 ? 's' : ''} sur la période`}
            </span>
          </div>
        </div>

        <div className={styles.carte} data-visuel="File par échéance">
          <BoutonExportPng nom="File par échéance" />
          <h2 className={styles.carteTitre}>File par échéance</h2>
          <p className={styles.carteSous}>Où en sont vos tickets ouverts.</p>
          <AnneauSla stats={stats} />
        </div>

        <div className={styles.carte} data-visuel="Par priorité">
          <BoutonExportPng nom="Par priorité" />
          <h2 className={styles.carteTitre}>Par priorité</h2>
          <p className={styles.carteSous}>Tickets ouverts, P1 critique → P5.</p>
          <Barres data={stats.par_priorite} couleurs={PRIORITE_COULEUR} />
        </div>

        <div className={styles.carte} data-visuel="Par domaine">
          <BoutonExportPng nom="Par domaine" />
          <h2 className={styles.carteTitre}>Par domaine</h2>
          <p className={styles.carteSous}>Répartition de votre charge.</p>
          <Barres
            data={stats.par_module}
            couleurs={MODULE_COULEUR}
            libelle={(c) => LIBELLE_MODULE[c] ?? c}
          />
        </div>

        <div className={`${styles.carte} ${styles.carteLarge}`} data-visuel="Rythme de résolution">
          <BoutonExportPng nom="Rythme de résolution" />
          <h2 className={styles.carteTitre}>Rythme de résolution</h2>
          <p className={styles.carteSous}>Tickets que vous avez résolus, sur la période.</p>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={stats.tendance} margin={{ top: 8, right: 8, left: -28, bottom: 0 }}>
              <defs>
                <linearGradient id="grad-mes-resolus" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--status-ok)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--status-ok)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="jour"
                tickLine={false}
                axisLine={false}
                interval={1}
                tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
              />
              <Tooltip {...infobulle} cursor={{ stroke: 'var(--border)', strokeWidth: 1 }} />
              <Area
                type="monotone"
                dataKey="resolus"
                name="Résolus"
                stroke="var(--status-ok)"
                strokeWidth={2.5}
                fill="url(#grad-mes-resolus)"
                dot={false}
                activeDot={{ r: 4 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>
    </>
  );
}
