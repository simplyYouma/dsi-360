import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/design-system/primitives';
import { BoutonExportPng } from '@/common/BoutonExportPng';
import { infobulle } from '@/common/infobulle';
import { inventaireApi, type AnalysesParc } from '@/features/inventaire/inventaireApi';
import compteurs from '@/features/inventaire/Inventaire.module.css';
import styles from './Analyses.module.css';

/** Montant compact : les milliards et millions se lisent mieux que douze chiffres. */
function montantCourt(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Md`;
  if (v >= 1e6) return `${(v / 1e6).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} M`;
  return Math.round(v).toLocaleString('fr-FR');
}

/** Vert → rouge avec l'âge : la couleur dit l'obsolescence, pas la décoration. */
const TONS_AGE: Record<string, string> = {
  'Moins de 3 ans': '#1f9d55',
  '3 à 6 ans': '#c77700',
  'Plus de 6 ans': '#d64545',
  'Sans date': '#8a93a6',
};

/** Le parc matériel en chiffres (lot 4) : localisation, valeur au bilan, obsolescence. */
export function ParcOnglet(): JSX.Element {
  const [parc, setParc] = useState<AnalysesParc | null>(null);
  const [erreur, setErreur] = useState(false);

  useEffect(() => {
    void inventaireApi
      .analyses()
      .then(setParc)
      .catch(() => setErreur(true));
  }, []);

  if (erreur) {
    return <p className={styles.chartSous}>Analyses du parc indisponibles pour ce profil.</p>;
  }
  if (parc === null) {
    return <p className={styles.chartSous}>Chargement…</p>;
  }

  const donneesEmplacement = parc.par_emplacement.map((t) => ({
    ...t,
    // Recharts tronque mal les longs libellés : on les borne nous-mêmes.
    nom: t.libelle.length > 22 ? `${t.libelle.slice(0, 21)}…` : t.libelle,
  }));
  const donneesDepartement = parc.par_departement.map((t) => ({
    ...t,
    nom: t.libelle.length > 22 ? `${t.libelle.slice(0, 21)}…` : t.libelle,
  }));

  return (
    <>
      {/* Les chiffres de tête : ce que vaut le parc, et ce qu'il en reste au bilan. */}
      <div className={compteurs.compteurs} style={{ marginBottom: 'var(--space-4)' }}>
        <span className={compteurs.compteur}>
          <b>{parc.parc_actif}</b>
          <span>Équipements en service</span>
        </span>
        <span className={compteurs.compteurValeur}>
          <b>{montantCourt(parc.valeur_acquisition)}</b>
          <span>Valeur d'acquisition (FCFA)</span>
        </span>
        <span className={compteurs.compteurValeur}>
          <b>{montantCourt(parc.valeur_nette)}</b>
          <span>Valeur nette comptable (FCFA)</span>
        </span>
        <span className={parc.totalement_amortis > 0 ? compteurs.compteurAlerte : compteurs.compteur}>
          <b>{parc.totalement_amortis}</b>
          <span>Totalement amortis</span>
        </span>
        {parc.sans_donnee_comptable > 0 && (
          <span className={compteurs.compteurAlerte}>
            <b>{parc.sans_donnee_comptable}</b>
            <span>Sans données comptables</span>
          </span>
        )}
      </div>

      <section className={styles.grille}>
        <Card data-visuel="Parc par emplacement">
          <BoutonExportPng nom="Parc par emplacement" />
          <h2 className={styles.chartTitre}>Où est le matériel</h2>
          <p className={styles.chartSous}>Équipements en service par emplacement.</p>
          <ResponsiveContainer width="100%" height={Math.max(180, donneesEmplacement.length * 30)}>
            <BarChart
              data={donneesEmplacement}
              layout="vertical"
              margin={{ top: 4, right: 24, left: 8, bottom: 0 }}
            >
              <CartesianGrid horizontal={false} strokeDasharray="4 4" stroke="var(--border)" />
              <XAxis type="number" hide allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="nom"
                width={150}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: 'var(--text-muted)' }}
              />
              <Tooltip {...infobulle} cursor={{ fill: 'var(--bg-subtle)' }} />
              <Bar
                dataKey="nombre"
                name="Équipements"
                fill="#4f6bed"
                radius={[0, 4, 4, 0]}
                barSize={14}
              />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card data-visuel="Valeur par département">
          <BoutonExportPng nom="Valeur par département" />
          <h2 className={styles.chartTitre}>Valeur au bilan par département</h2>
          <p className={styles.chartSous}>
            Ce que le matériel a coûté, et ce qu'il vaut encore (VNC).
          </p>
          <ResponsiveContainer width="100%" height={Math.max(180, donneesDepartement.length * 34)}>
            <BarChart
              data={donneesDepartement}
              layout="vertical"
              margin={{ top: 4, right: 24, left: 8, bottom: 0 }}
            >
              <CartesianGrid horizontal={false} strokeDasharray="4 4" stroke="var(--border)" />
              <XAxis type="number" hide tickFormatter={montantCourt} />
              <YAxis
                type="category"
                dataKey="nom"
                width={150}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: 'var(--text-muted)' }}
              />
              <Tooltip
                {...infobulle}
                cursor={{ fill: 'var(--bg-subtle)' }}
                formatter={(v: number) => `${montantCourt(v)} FCFA`}
              />
              <Bar
                dataKey="valeur_acquisition"
                name="Acquisition"
                fill="#4f6bed"
                radius={[0, 4, 4, 0]}
                barSize={9}
              />
              <Bar
                dataKey="valeur_nette"
                name="Valeur nette"
                fill="#1f9d55"
                radius={[0, 4, 4, 0]}
                barSize={9}
              />
            </BarChart>
          </ResponsiveContainer>
          <ul className={styles.miniLegende}>
            <li>
              <span className={styles.tiret} style={{ background: '#4f6bed' }} />
              Acquisition
            </li>
            <li>
              <span className={styles.tiret} style={{ background: '#1f9d55' }} />
              Valeur nette
            </li>
          </ul>
        </Card>

        <Card className={styles.span2} data-visuel="Âge du parc">
          <BoutonExportPng nom="Âge du parc" />
          <h2 className={styles.chartTitre}>Âge du parc</h2>
          <p className={styles.chartSous}>
            Plus un matériel vieillit, plus il approche de la fin d'amortissement — c'est la
            carte de l'obsolescence.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={parc.par_age} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
              <CartesianGrid vertical={false} strokeDasharray="4 4" stroke="var(--border)" />
              <XAxis
                dataKey="libelle"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: 'var(--text-muted)' }}
              />
              <YAxis hide allowDecimals={false} />
              <Tooltip {...infobulle} cursor={{ fill: 'var(--bg-subtle)' }} />
              <Bar dataKey="nombre" name="Équipements" radius={[4, 4, 0, 0]} barSize={44}>
                {parc.par_age.map((t) => (
                  <Cell key={t.libelle} fill={TONS_AGE[t.libelle] ?? '#8a93a6'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </section>
    </>
  );
}
