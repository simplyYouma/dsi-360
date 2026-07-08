import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Link2, Plus } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import styles from './LiensTache.module.css';

export interface LienItem {
  id: string;
  libelle: string;
  url: string;
  cree_le: string;
}

interface Props {
  charger: () => Promise<LienItem[]>;
  creer: (libelle: string, url: string) => Promise<unknown>;
  supprimer: (lienId: string) => Promise<void>;
}

/** Liens utiles d'une tâche, repliés par défaut : ajout et affichage discrets. */
export function LiensTache({ charger, creer, supprimer }: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [liens, setLiens] = useState<LienItem[] | null>(null);
  const [libelle, setLibelle] = useState('');
  const [url, setUrl] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const recharger = useCallback(async (): Promise<void> => {
    setLiens(await charger());
  }, [charger]);

  useEffect(() => {
    if (ouvert && liens === null) void recharger();
  }, [ouvert, liens, recharger]);

  const ajouter = async (): Promise<void> => {
    if (libelle.trim().length < 2 || url.trim().length < 4) return;
    setEnvoi(true);
    try {
      await creer(libelle.trim(), url.trim());
      setLibelle('');
      setUrl('');
      await recharger();
    } finally {
      setEnvoi(false);
    }
  };

  const total = liens?.length ?? 0;

  return (
    <div>
      <button
        type="button"
        className={styles.bascule}
        onClick={() => setOuvert((o) => !o)}
        aria-expanded={ouvert}
      >
        {ouvert ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <Link2 size={13} />
        Liens{liens !== null && total > 0 ? ` (${total})` : ''}
      </button>
      {ouvert && (
        <div className={styles.zone}>
          {liens !== null && liens.length > 0 && (
            <ul className={styles.liste}>
              {liens.map((l) => (
                <li key={l.id} className={styles.item}>
                  <Link2 size={12} aria-hidden="true" />
                  <a href={l.url} target="_blank" rel="noreferrer" title={l.url}>
                    {l.libelle}
                  </a>
                  <BoutonSupprimer
                    cible={`le lien « ${l.libelle} »`}
                    onSupprimer={() => supprimer(l.id)}
                    className={styles.suppr}
                    taille={13}
                  />
                </li>
              ))}
            </ul>
          )}
          <div className={styles.form}>
            <input
              className={styles.champ}
              value={libelle}
              onChange={(e) => setLibelle(e.target.value)}
              placeholder="Libellé"
            />
            <input
              className={styles.champ}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
              onKeyDown={(e) => {
                if (e.key === 'Enter') void ajouter();
              }}
            />
            <Button
              variante="secondaire"
              onClick={() => void ajouter()}
              disabled={envoi || libelle.trim().length < 2 || url.trim().length < 4}
            >
              <Plus size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
