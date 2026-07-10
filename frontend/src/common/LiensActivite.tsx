import { useCallback, useEffect, useState } from 'react';
import { Link2, Plus } from 'lucide-react';
import { Button, useToast } from '@/design-system/primitives';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { ErreurApi } from '@/lib/api';
import styles from './LiensActivite.module.css';

export interface LienItem {
  id: string;
  libelle: string;
  url: string;
}

interface Props {
  charger: () => Promise<LienItem[]>;
  creer: (libelle: string, url: string) => Promise<LienItem>;
  supprimer: (lienId: string) => Promise<void>;
  /** Sans droit de travail : les liens restent consultables, l'ajout et le retrait disparaissent. */
  modifiable?: boolean;
}

const LIBELLE_MINI = 2;
const URL_MINI = 8; // « https:// »

/** Liens utiles d'une activité (espace documentaire, wiki, dossier réseau…).
 *
 *  Rattachés au sujet, jamais à une tâche : un lien survit à l'étape qui l'a fait naître.
 *  Partagé par les projets et les changements. */
export function LiensActivite({ charger, creer, supprimer, modifiable = true }: Props): JSX.Element {
  const [liens, setLiens] = useState<LienItem[]>([]);
  const [libelle, setLibelle] = useState('');
  const [url, setUrl] = useState('');
  const { notifier } = useToast();

  const recharger = useCallback((): void => {
    void charger().then(setLiens);
    // `charger` est recréée à chaque rendu par l'appelant : on ne la met pas en dépendance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => recharger(), [recharger]);

  const valide = libelle.trim().length >= LIBELLE_MINI && url.trim().length >= URL_MINI;

  const ajouter = async (): Promise<void> => {
    if (!valide) return;
    try {
      await creer(libelle.trim(), url.trim());
      setLibelle('');
      setUrl('');
      recharger();
    } catch (e) {
      notifier(
        e instanceof ErreurApi ? e.message : 'Ajout impossible — adresse http(s):// attendue.',
        'erreur',
      );
    }
  };

  const retirer = async (id: string): Promise<void> => {
    await supprimer(id);
    recharger();
  };

  return (
    <div className={styles.liens}>
      {liens.length === 0 && <p className={styles.vide}>Aucun lien pour le moment.</p>}
      {liens.map((l) => (
        <div key={l.id} className={styles.lien}>
          <Link2 size={14} className={styles.icone} />
          <a
            href={l.url}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.libelle}
            title={l.url}
          >
            {l.libelle}
          </a>
          {modifiable && (
            <BoutonSupprimer
              cible={`le lien « ${l.libelle} »`}
              onSupprimer={() => retirer(l.id)}
              className={styles.action}
              taille={14}
            />
          )}
        </div>
      ))}

      {modifiable && (
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
              if (e.key === 'Enter') void ajouter();
            }}
          />
          <Button onClick={() => void ajouter()} disabled={!valide}>
            <Plus size={15} />
          </Button>
        </div>
      )}
    </div>
  );
}
