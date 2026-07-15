import { Fragment } from 'react';
import { Card } from '@/design-system/primitives';
import { BoutonExportPng } from '@/common/BoutonExportPng';
import type { AnalysesMensuelles, CelluleEntite } from './analysesApi';
import styles from './MatriceMensuelle.module.css';

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

/** Les trois tableaux croisés par mois, dans le style maison — volumétrie/SLA et DSI vs DBS. */
export function MatriceMensuelle({ data }: { data: AnalysesMensuelles | null }): JSX.Element {
  if (data === null || data.mois.length === 0) {
    return <p className={styles.vide}>Aucune donnée importée sur la période.</p>;
  }
  const { mois, priorites, total_priorites, entites } = data;
  const dsi = entites.find((e) => e.cle === 'DSI');
  const dbs = entites.find((e) => e.cle === 'DBS');

  // Sous-lignes de la répartition DSI/DBS (mêmes clés que CelluleEntite).
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
        <p className={styles.sous}>Nombre de tickets par priorité et respect des SLA, par mois.</p>
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
                    <span className={styles.taux} style={{ color: couleurTaux(c.sla_taux) }}>
                      {c.sla_taux === null ? '—' : `${c.sla_taux}%`}
                    </span>
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
                      <span className={styles.taux} style={{ color: couleurTaux(c.sla_taux) }}>
                        {c.sla_taux === null ? '—' : `${c.sla_taux}%`}
                      </span>
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
        <p className={styles.sous}>Volume traité par entité, ventilé par mois et par nature.</p>
        <div className={styles.tuiles}>
          {entites.map((e) => (
            <div key={e.cle} className={styles.tuile}>
              <span className={styles.tuileNom}>{e.libelle}</span>
              <span className={styles.tuileTotal}>{e.total}</span>
              <span className={styles.tuileDetail}>
                {e.fermes} fermés · {e.ouverts} ouverts
              </span>
              <span className={styles.tuileDetail}>
                {e.incidents} incidents · {e.demandes} demandes
              </span>
            </div>
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
                  {sousLignes.map((s) => (
                    <tr key={`${e.cle}-${s.cle}`}>
                      <td className={`${styles.figee} ${styles.sousLigne}`}>{s.libelle}</td>
                      {e.cellules.map((c) => (
                        <td key={c.mois} className={styles.discret}>
                          {c[s.cle] || '—'}
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
            Répartition DSI / DBS des tickets fermés puis ouverts, mois par mois.
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
