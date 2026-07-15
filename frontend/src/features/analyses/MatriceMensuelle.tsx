import { Fragment } from 'react';
import { CheckCircle2, CircleDot, XCircle, AlertTriangle, FileText } from 'lucide-react';
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
      <span className={styles.carteNom} style={{ color: s.accent }}>
        {s.libelle}
      </span>
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

/** Couleur sémantique d'un cas du tableau par gestionnaire (la couleur porte le sens). */
const CAS_COULEUR = {
  incidents: 'var(--cat-1)',
  demandes: 'var(--secondary)',
  ouverts: 'var(--status-warn)',
  fermes: 'var(--status-ok)',
} as const;

/** Valeur d'un cas, teintée de sa couleur ; tiret discret quand nul. */
function Cas({ v, couleur }: { v: number; couleur: string }): JSX.Element {
  if (!v) return <span className={styles.discret}>—</span>;
  return (
    <span
      className={styles.cas}
      style={{ color: couleur, background: `color-mix(in srgb, ${couleur} 12%, transparent)` }}
    >
      {v}
    </span>
  );
}

/** Répartition d'un filtre d'état vers la sous-ligne correspondante du tableau DSI/DBS. */
const STATUT_LIGNE: Record<string, keyof CelluleEntite> = {
  ouvert: 'ouverts',
  ferme: 'fermes',
  rejete: 'rejetes',
};
const STATUT_TEXTE: Record<string, string> = {
  ouvert: 'ouverts',
  ferme: 'fermés',
  rejete: 'rejetés',
};

interface MatriceProps {
  data: AnalysesMensuelles | null;
  /** Filtre d'état actif (ouvert|ferme|rejete) : ne montre que la sous-ligne concernée. */
  statut?: string | null;
}

/** Les trois tableaux croisés dans le style maison — volumétrie/SLA et DSI vs DBS, par période. */
export function MatriceMensuelle({ data, statut }: MatriceProps): JSX.Element {
  if (data === null || data.mois.length === 0) {
    return <p className={styles.vide}>Aucune donnée importée sur la période.</p>;
  }
  const { mois, priorites, total_priorites, entites, niveaux, granularite } = data;
  const ligneFiltree = statut ? STATUT_LIGNE[statut] : undefined;
  const pas = PAR_PAS[granularite];
  // Colonnes d'état du tableau par gestionnaire : un filtre d'état ne garde que la colonne concernée
  // (rejeté n'a ni ouverts ni fermés → aucune colonne d'état).
  const colsEtat = (
    [
      { cle: 'ouverts', libelle: 'Ouverts' },
      { cle: 'fermes', libelle: 'Fermés' },
    ] as const
  ).filter((c) => statut == null || STATUT_LIGNE[statut] === c.cle);
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

  const toutesLignes: {
    cle: keyof CelluleEntite;
    libelle: string;
    icone: JSX.Element;
    groupe: 'statut' | 'nature';
  }[] = [
    { cle: 'fermes', libelle: 'Fermés', icone: <CheckCircle2 size={13} />, groupe: 'statut' },
    { cle: 'ouverts', libelle: 'Ouverts', icone: <CircleDot size={13} />, groupe: 'statut' },
    { cle: 'rejetes', libelle: 'Rejetés', icone: <XCircle size={13} />, groupe: 'statut' },
    {
      cle: 'incidents',
      libelle: 'Incidents',
      icone: <AlertTriangle size={13} />,
      groupe: 'nature',
    },
    { cle: 'demandes', libelle: 'Demandes', icone: <FileText size={13} />, groupe: 'nature' },
  ];
  const sousLignes = toutesLignes.filter(
    (sl) => ligneFiltree === undefined || sl.cle === ligneFiltree,
  );

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
                  {sousLignes.map((sl, idx) => {
                    const debutNature =
                      sl.groupe === 'nature' && sousLignes[idx - 1]?.groupe !== 'nature';
                    return (
                      <tr
                        key={`${e.cle}-${sl.cle}`}
                        className={debutNature ? styles.debutGroupe : undefined}
                      >
                        <td className={`${styles.figee} ${styles.sousLigne}`}>
                          <span className={styles.slIcone}>{sl.icone}</span>
                          {sl.libelle}
                        </td>
                        {e.cellules.map((c) => (
                          <td key={c.mois} className={styles.discret}>
                            {c[sl.cle] || '—'}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---- 3. Répartition par gestionnaire ---- */}
      <Card data-visuel="Répartition par gestionnaire">
        <BoutonExportPng nom="Répartition par gestionnaire" />
        <h2 className={styles.titre}>Répartition par gestionnaire</h2>
        <p className={styles.sous}>
          Les 5 gestionnaires les plus actifs (incidents et demandes)
          {ligneFiltree !== undefined ? `, état : ${STATUT_TEXTE[statut ?? ''] ?? ''}` : ''}.
        </p>
        <div className={styles.zone}>
          <table className={styles.matrice}>
            <thead>
              <tr>
                <th className={styles.figee}>Gestionnaire</th>
                <th>Incidents</th>
                <th>Demandes</th>
                <th>Total</th>
                {colsEtat.map((c) => (
                  <th key={c.cle}>{c.libelle}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {niveaux.slice(0, 5).map((n) => (
                <tr key={n.cle}>
                  <td className={styles.figee}>{n.libelle}</td>
                  <td>
                    <Cas v={n.incidents} couleur={CAS_COULEUR.incidents} />
                  </td>
                  <td>
                    <Cas v={n.demandes} couleur={CAS_COULEUR.demandes} />
                  </td>
                  <td>
                    <span className={styles.volume}>{n.total || '—'}</span>
                  </td>
                  {colsEtat.map((c) => (
                    <td key={c.cle}>
                      <Cas v={n[c.cle]} couleur={CAS_COULEUR[c.cle]} />
                    </td>
                  ))}
                </tr>
              ))}
              {niveaux.length === 0 && (
                <tr>
                  <td className={styles.figee}>—</td>
                  <td colSpan={3 + colsEtat.length} className={styles.discret}>
                    Aucun gestionnaire sur la période.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---- 4. Part fermés / ouverts par gestionnaire ---- */}
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
                    { libelle: 'Fermés', champ: 'fermes' as const },
                    { champ: 'ouverts' as const, libelle: 'Ouverts' },
                  ] as const
                ).map((g) => (
                  <Fragment key={g.champ}>
                    {/* Ligne globale : le total des deux entités (base des pourcentages).
                        Fermés en rouge, ouverts en vert — la couleur porte l'état. */}
                    <tr
                      className={styles.ligneTotale}
                      style={{
                        background: `color-mix(in srgb, ${
                          g.champ === 'fermes' ? 'var(--status-danger)' : 'var(--status-ok)'
                        } 12%, transparent)`,
                      }}
                    >
                      <td className={styles.figee}>{g.libelle} · Ensemble</td>
                      {dsi.cellules.map((c, i) => {
                        const tout = c[g.champ] + (dbs.cellules[i]?.[g.champ] ?? 0);
                        return (
                          <td key={c.mois}>
                            <span className={styles.volume}>{tout || '—'}</span>
                          </td>
                        );
                      })}
                    </tr>
                    {(
                      [
                        { nom: 'DSI', ent: dsi, autre: dbs },
                        { nom: 'DBS', ent: dbs, autre: dsi },
                      ] as const
                    ).map((r) => (
                      <tr key={`${g.champ}-${r.nom}`}>
                        <td className={`${styles.figee} ${styles.sousLigne}`}>{r.nom}</td>
                        {r.ent.cellules.map((c, i) => {
                          const part = c[g.champ];
                          const tout = part + (r.autre.cellules[i]?.[g.champ] ?? 0);
                          const p = pct(part, tout);
                          return (
                            <td key={c.mois} className={styles.discret}>
                              {p === null ? '—' : `${p}%`}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
