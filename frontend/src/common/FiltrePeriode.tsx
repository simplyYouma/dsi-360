import { SelecteurDate } from './SelecteurDate';
import { estPerso, type Periode } from './periode';
import styles from './FiltrePeriode.module.css';

const PRESETS: { libelle: string; jours: number | null }[] = [
  { libelle: '7 j', jours: 7 },
  { libelle: '30 j', jours: 30 },
  { libelle: '90 j', jours: 90 },
  { libelle: 'Tout', jours: null },
];

/** Année civile en cours : du 1ᵉʳ janvier à aujourd'hui (plage de dates, pas un preset en jours). */
function anneeEnCours(): { du: string; au: string } {
  const maintenant = new Date();
  const jour = (d: Date): string =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { du: `${maintenant.getFullYear()}-01-01`, au: jour(maintenant) };
}

interface Props {
  valeur: Periode;
  onChange: (p: Periode) => void;
}

/** Filtre de période réutilisable : presets (7/30/90/Année/Tout) + plage de dates au calendrier. */
export function FiltrePeriode({ valeur, onChange }: Props): JSX.Element {
  const perso = estPerso(valeur);
  const annee = anneeEnCours();
  const anneeActive = valeur.du === annee.du && valeur.au === annee.au;
  return (
    <div className={styles.filtre}>
      <div className={styles.presets}>
        {PRESETS.map((p) => (
          <button
            key={p.libelle}
            className={!perso && valeur.jours === p.jours ? styles.presetOn : styles.preset}
            onClick={() => onChange({ jours: p.jours, du: null, au: null })}
          >
            {p.libelle}
          </button>
        ))}
        <button
          className={anneeActive ? styles.presetOn : styles.preset}
          onClick={() => onChange({ jours: null, du: annee.du, au: annee.au })}
        >
          Année
        </button>
      </div>
      <div className={styles.dates}>
        <SelecteurDate
          valeur={valeur.du}
          onChange={(du) => onChange({ jours: null, du, au: valeur.au })}
          placeholder="Du…"
        />
        <span className={styles.tiret} aria-hidden="true">
          →
        </span>
        <SelecteurDate
          valeur={valeur.au}
          onChange={(au) => onChange({ jours: null, du: valeur.du, au })}
          placeholder="Au…"
        />
      </div>
    </div>
  );
}
