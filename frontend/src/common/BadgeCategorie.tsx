import styles from './BadgeCategorie.module.css';

/** Palette catégorielle de la charte : elle distingue, elle ne juge pas.
 *  Aucune de ces teintes ne veut dire « bon » ou « mauvais » — les statuts gardent ça pour eux. */
const TEINTES = [
  'var(--cat-1)',
  'var(--cat-2)',
  'var(--cat-3)',
  'var(--cat-4)',
  'var(--cat-5)',
  'var(--cat-6)',
  'var(--cat-7)',
  'var(--cat-8)',
];

/** Teinte d'un libellé : tirée de son nom, donc **stable**.
 *
 *  Un vrai tirage au sort donnerait une couleur différente à chaque rendu, et « Migration » ne
 *  serait jamais deux fois de la même teinte — la couleur ne servirait plus à reconnaître, juste
 *  à décorer. Ici deux projets du même type se repèrent d'un coup d'œil dans la liste. */
export function teinteCategorie(libelle: string): string {
  let somme = 0;
  for (let i = 0; i < libelle.length; i += 1) somme = (somme * 31 + libelle.charCodeAt(i)) % 100_003;
  return TEINTES[somme % TEINTES.length] as string;
}

/** Badge d'une valeur de référentiel (type de projet, catégorie…) : pastille teintée et sobre. */
export function BadgeCategorie({ libelle }: { libelle: string | null }): JSX.Element {
  if (libelle === null || libelle === '') {
    return <span className={styles.vide}>—</span>;
  }
  const teinte = teinteCategorie(libelle);
  return (
    <span
      className={styles.badge}
      style={{
        color: teinte,
        background: `color-mix(in srgb, ${teinte} 12%, transparent)`,
        borderColor: `color-mix(in srgb, ${teinte} 35%, transparent)`,
      }}
      title={libelle}
    >
      {libelle}
    </span>
  );
}
