import { useState } from 'react';
import { Link2, Plus } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import styles from './LiensActivite.module.css';

export interface LienSaisi {
  libelle: string;
  url: string;
}

interface Props {
  valeur: LienSaisi[];
  onChange: (liens: LienSaisi[]) => void;
}

const LIBELLE_MINI = 2;
const URL_MINI = 8; // « https:// »

/** Saisie de liens utiles dans une modale de création : la liste vit en local ; l'appelant la
 *  persiste après création de l'activité (POST `${base}/${id}/liens`). Aucun composant natif. */
export function SaisieLiens({ valeur, onChange }: Props): JSX.Element {
  const [libelle, setLibelle] = useState('');
  const [url, setUrl] = useState('');

  const valide = libelle.trim().length >= LIBELLE_MINI && url.trim().length >= URL_MINI;

  const ajouter = (): void => {
    if (!valide) return;
    onChange([...valeur, { libelle: libelle.trim(), url: url.trim() }]);
    setLibelle('');
    setUrl('');
  };

  return (
    <div className={styles.liens}>
      {valeur.map((l, i) => (
        <div key={`${l.url}-${i}`} className={styles.lien}>
          <Link2 size={14} className={styles.icone} />
          <span className={styles.libelle} title={l.url}>
            {l.libelle}
          </span>
          <BoutonSupprimer
            cible={`le lien « ${l.libelle} »`}
            onSupprimer={() => onChange(valeur.filter((_, j) => j !== i))}
            className={styles.action}
            taille={14}
          />
        </div>
      ))}
      <div className={styles.ajout}>
        <input
          className={styles.champ}
          value={libelle}
          onChange={(e) => setLibelle(e.target.value)}
          placeholder="Libellé du lien…"
          aria-label="Libellé du lien"
        />
        <input
          className={styles.champ}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          aria-label="Adresse du lien"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              ajouter();
            }
          }}
        />
        <Button type="button" onClick={ajouter} disabled={!valide}>
          <Plus size={15} />
        </Button>
      </div>
    </div>
  );
}

/** Persiste les liens saisis sur une activité fraîchement créée. Best-effort, silencieux. */
export async function persisterLiens(
  poster: (l: LienSaisi) => Promise<unknown>,
  liens: LienSaisi[],
): Promise<void> {
  for (const l of liens) {
    try {
      await poster(l);
    } catch {
      // On n'échoue pas la création pour un lien : l'activité existe déjà.
    }
  }
}
