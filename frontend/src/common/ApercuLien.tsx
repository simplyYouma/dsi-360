import { useEffect, useState } from 'react';
import { Link2 } from 'lucide-react';
import { api, recupererBlob } from '@/lib/api';
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
  // La vignette ne se charge pas depuis le site lié : elle transite par l'API, avec le jeton.
  // Le navigateur ne révèle donc rien au site — un lien collé ne peut pas servir de mouchard —
  // et la politique de sécurité de la page reste stricte.
  const [vignette, setVignette] = useState<string | null>(null);

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

  const distante = apercu?.image ?? null;
  useEffect(() => {
    if (distante === null) return;
    let vivant = true;
    let objet: string | null = null;
    void recupererBlob(`/apercu-lien/image?url=${encodeURIComponent(distante)}`)
      .then((blob) => {
        if (!vivant) return;
        objet = URL.createObjectURL(blob);
        setVignette(objet);
      })
      // Vignette indisponible : la carte reste, sans image. Jamais d'image brisée.
      .catch(() => undefined);
    return () => {
      vivant = false;
      if (objet !== null) URL.revokeObjectURL(objet);
      setVignette(null);
    };
  }, [distante]);

  if (apercu === null || apercu.titre === null) return null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={styles.carte}>
      {vignette !== null && (
        <span
          className={styles.image}
          style={{ backgroundImage: `url("${vignette}")` }}
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
