import { Fragment } from 'react';
import { CheckCircle2, CircleDot, AlertTriangle, FileText } from 'lucide-react';
import { Card } from '@/design-system/primitives';
import { BoutonExportPng } from '@/common/BoutonExportPng';
import type { AnalysesMensuelles, CelluleEntite, Granularite, LigneEntite } from './analysesApi';
import styles from './MatriceMensuelle.module.css';

/** Formulation du pas de temps, selon la granularité choisie par le filtre. */
const PAR_PAS: Record<Granularite, string> = {
  heure: 'par heure',
  jour: 'par jour',
  semaine: 'par semaine',
  mois: 'par mois',
  annee: 'par année',
};

/** Couleur du taux de respect SLA (vert bon, ambre moyen, rouge faible ; gris si non mesurable). */
function couleurTaux(taux: number | null): string {
  if (taux === null) return 'var(--text-muted)';
  if (taux >= 75) return 'var(--status-ok)';
  if (taux >= 40) return 'var(--status-warn)';
  return 'var(--status-danger)';
}

/** Cible SLA lisible : minutes → heures (ou jours) comme dans le rapport source. */
function cibleLisible(minutes: number | null): string {
  if (minutes === null) return '';
  if (minutes % 1440 === 0) return `${minutes / 1440} j`;
  if (minutes % 60 === 0) return `${minutes / 60} h`;
  return `${minutes} min`;
}

function pct(part: number, tout: number): number | null {
  return tout > 0 ? Math.round((part * 100) / tout) : null;
}

interface Synthese {
  libelle: string;
  accent: string;
  total: number;
  fermes: number;
  ouverts: number;
  incidents: number;
  demandes: number;
}

/** Pastille du taux SLA : la couleur du sens, sur un fond très léger de la même teinte. */
function PastilleSla({ taux }: { taux: number | null }): JSX.Element {
  const c = couleurTaux(taux);
  return (
    <span
      className={styles.pastille}
      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
    >
      {taux === null ? '—' : `${taux}%`}
    </span>
  );
}

/** Carte de synthèse d'une entité : dégradé, total en évidence, indicateurs en badges. */
function CarteSynthese({ s }: { s: Synthese }): JSX.Element {
  const badges = [
    { icone: <CheckCircle2 size={14} />, valeur: s.fermes, libelle: 'fermés' },
    { icone: <CircleDot size={14} />, valeur: s.ouverts, libelle: 'ouverts' },
    { icone: <AlertTriangle size={14} />, valeur: s.incidents, libelle: 'incidents' },
    { icone: <FileText size={14} />, valeur: s.demandes, libelle: 'demandes' },
  ];
  return (
    <div
      className={styles.carte}
      style={{
        background: `linear-gradient(135deg, color-mix(in srgb, ${s.accent} 16%, var(--surface)), var(--surface) 70%)`,
        borderColor: `color-mix(in srgb, ${s.accent} 35%, var(--border))`,
      }}
    >
      <div className={styles.carteTete}>
        <span className={styles.cartePoint} style={{ background: s.accent }} />
        <span className={styles.carteNom}>{s.libelle}</span>
      </div>
      <span className={styles.carteTotal}>{s.total}</span>
      <div className={styles.badges}>
        {badges.map((b) => (
          <span key={b.libelle} className={styles.badge}>
            <span className={styles.badgeIcone} style={{ color: s.accent }}>
              {b.icone}
            </span>
            <strong>{b.valeur}</strong> {b.libelle}
          </span>
        ))}
      </div>
    </div>
  );
}

function synthese(e: LigneEntite | undefined, libelle: string, accent: string): Synthese {
  return {
    libelle,
    accent,
    total: e?.total ?? 0,
    fermes: e?.fermes ?? 0,
    ouverts: e?.ouverts ?? 0,
    incidents: e?.incidents ?? 0,
    demandes: e?.demandes ?? 0,
  };
}

/** Les trois tableaux croisés dans le style maison — volumétrie/SLA et DSI vs DBS, par période. */
export function MatriceMensuelle({ data }: { data: AnalysesMensuelles | null }): JSX.Element {
  if (data === null || data.mois.length === 0) {
    return <p className={styles.vide}>Aucune donnée importée sur la période.</p>;
  }
  const { mois, priorites, total_priorites, entites, granularite } = data;
  const pas = PAR_PAS[granularite];
  const dsi = entites.find((e) => e.cle === 'DSI');
  const dbs = entites.find((e) => e.cle === 'DBS');

  const cartes: Synthese[] = [
    synthese(dsi, 'DSI AFG', 'var(--secondary)'),
    synthese(dbs, 'DBS', 'var(--cat-3)'),
    {
      libelle: 'Ensemble',
      accent: 'var(--status-ok)',
      total: (dsi?.total ?? 0) + (dbs?.total ?? 0),
      fermes: (dsi?.fermes ?? 0) + (dbs?.fermes ?? 0),
      ouverts: (dsi?.ouverts ?? 0) + (dbs?.ouverts ?? 0),
      incidents: (dsi?.incidents ?? 0) + (dbs?.incidents ?? 0),
      demandes: (dsi?.demandes ?? 0) + (dbs?.demandes ?? 0),
    },
  ];

  const sousLignes: { cle: keyof CelluleEntite; libelle: string }[] = [
    { cle: 'fermes', libelle: 'Fermés' },
    { cle: 'ouverts', libelle: 'Ouverts' },
    { cle: 'rejetes', libelle: 'Rejetés' },
    { cle: 'incidents', libelle: 'Incidents' },
    { cle: 'demandes', libelle: 'Demandes' },
  ];

  return (
    <div className={styles.pile}>
      {/* ---- 1. Volumétrie par priorité & conformité SLA ---- */}
      <Card data-visuel="Volumétrie par priorité & conformité SLA">
        <BoutonExportPng nom="Volumétrie par priorité & conformité SLA" />
        <h2 className={styles.titre}>Volumétrie par priorité &amp; conformité SLA</h2>
        <p className={styles.sous}>Nombre de tickets par priorité et respect des SLA, {pas}.</p>
        <div className={styles.zone}>
          <table className={styles.matrice}>
            <thead>
              <tr>
                <th className={styles.figee}>Priorité</th>
                {mois.map((m) => (
                  <th key={m.cle}>{m.libelle}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className={styles.ligneTotale}>
                <td className={styles.figee}>Toutes</td>
                {total_priorites.map((c) => (
                  <td key={c.mois}>
                    <span className={styles.volume}>{c.total}</span>
                    <PastilleSla taux={c.sla_taux} />
                  </td>
                ))}
              </tr>
              {priorites.map((p) => (
                <tr key={p.priorite}>
                  <td className={styles.figee}>
                    <strong>P{p.priorite}</strong>
                    {p.cible_minutes !== null && (
                      <span className={styles.cible}> · {cibleLisible(p.cible_minutes)}</span>
                    )}
                  </td>
                  {p.cellules.map((c) => (
                    <td key={c.mois}>
                      <span className={styles.volume}>{c.total || '—'}</span>
                      {c.total > 0 && <PastilleSla taux={c.sla_taux} />}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---- 2. Répartition DSI vs DBS ---- */}
      <Card data-visuel="Répartition DSI vs DBS">
        <BoutonExportPng nom="Répartition DSI vs DBS" />
        <h2 className={styles.titre}>Répartition DSI vs DBS</h2>
        <p className={styles.sous}>Volume traité par entité, ventilé {pas} et par nature.</p>
        <div className={styles.cartes}>
          {cartes.map((s) => (
            <CarteSynthese key={s.libelle} s={s} />
          ))}
        </div>
        <div className={styles.zone}>
          <table className={styles.matrice}>
            <thead>
              <tr>
                <th className={styles.figee}>Entité</th>
                {mois.map((m) => (
                  <th key={m.cle}>{m.libelle}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entites.map((e) => (
                <Fragment key={e.cle}>
                  <tr className={styles.ligneTotale}>
                    <td className={styles.figee}>{e.libelle}</td>
                    {e.cellules.map((c) => (
                      <td key={c.mois}>
                        <span className={styles.volume}>{c.total || '—'}</span>
                      </td>
                    ))}
                  </tr>
                  {sousLignes.map((sl) => (
                    <tr key={`${e.cle}-${sl.cle}`}>
                      <td className={`${styles.figee} ${styles.sousLigne}`}>{sl.libelle}</td>
                      {e.cellules.map((c) => (
                        <td key={c.mois} className={styles.discret}>
                          {c[sl.cle] || '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---- 3. Part fermés / ouverts par gestionnaire ---- */}
      {dsi && dbs && (
        <Card data-visuel="Part par statut et gestionnaire">
          <BoutonExportPng nom="Part par statut et gestionnaire" />
          <h2 className={styles.titre}>Part par statut &amp; gestionnaire</h2>
          <p className={styles.sous}>
            Répartition DSI / DBS des tickets fermés puis ouverts, {pas}.
          </p>
          <div className={styles.zone}>
            <table className={styles.matrice}>
              <thead>
                <tr>
                  <th className={styles.figee}>Répartition</th>
                  {mois.map((m) => (
                    <th key={m.cle}>{m.libelle}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    { libelle: 'Fermés · DSI', champ: 'fermes' as const, ent: dsi, autre: dbs },
                    { libelle: 'Fermés · DBS', champ: 'fermes' as const, ent: dbs, autre: dsi },
                    { libelle: 'Ouverts · DSI', champ: 'ouverts' as const, ent: dsi, autre: dbs },
                    { libelle: 'Ouverts · DBS', champ: 'ouverts' as const, ent: dbs, autre: dsi },
                  ] as const
                ).map((r) => (
                  <tr key={r.libelle}>
                    <td className={styles.figee}>{r.libelle}</td>
                    {r.ent.cellules.map((c, i) => {
                      const part = c[r.champ];
                      const tout = part + (r.autre.cellules[i]?.[r.champ] ?? 0);
                      const p = pct(part, tout);
                      return (
                        <td key={c.mois} className={styles.discret}>
                          {p === null ? '—' : `${p}%`}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
