import { useEffect, useState } from 'react';
import { Link2 } from 'lucide-react';
import { api } from '@/lib/api';
import styles from './ApercuLien.module.css';

interface Apercu {
  url: string;
  titre: string | null;
  description: string | null;
  image: string | null;
  site: string | null;
}

// Cache de module : une URL vue dans plusieurs commentaires n'est demandée qu'une fois par session.
const cache = new Map<string, Apercu>();

/** Vignette d'aperçu d'un lien, façon messagerie : image, titre, description, domaine. Discrète —
 *  n'affiche rien tant qu'on n'a pas au moins un titre (pas de carte vide sur un lien muet). */
export function ApercuLien({ url }: { url: string }): JSX.Element | null {
  const [apercu, setApercu] = useState<Apercu | null>(cache.get(url) ?? null);

  useEffect(() => {
    const enCache = cache.get(url);
    if (enCache) {
      setApercu(enCache);
      return;
    }
    let vivant = true;
    void api
      .get<Apercu>(`/apercu-lien?url=${encodeURIComponent(url)}`)
      .then((a) => {
        cache.set(url, a);
        if (vivant) setApercu(a);
      })
      .catch(() => undefined);
    return () => {
      vivant = false;
    };
  }, [url]);

  if (apercu === null || apercu.titre === null) return null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={styles.carte}>
      {apercu.image !== null && (
        <span
          className={styles.image}
          style={{ backgroundImage: `url("${apercu.image}")` }}
          aria-hidden="true"
        />
      )}
      <span className={styles.corps}>
        <span className={styles.site}>
          <Link2 size={12} />
          {apercu.site ?? new URL(url).hostname}
        </span>
        <span className={styles.titre}>{apercu.titre}</span>
        {apercu.description !== null && (
          <span className={styles.description}>{apercu.description}</span>
        )}
      </span>
    </a>
  );
}
