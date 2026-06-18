import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Ouvre la fiche dont l'identifiant est passé en `?fiche=…` (lien profond depuis la
 * recherche globale ou une notification), puis retire le paramètre pour ne pas la
 * rouvrir au rendu suivant. La page reste maître de sa propre logique d'ouverture.
 */
export function useFicheUrl(ouvrir: (id: string) => void): void {
  const [params, setParams] = useSearchParams();
  const fiche = params.get('fiche');
  useEffect(() => {
    if (fiche === null) return;
    ouvrir(fiche);
    const suite = new URLSearchParams(params);
    suite.delete('fiche');
    setParams(suite, { replace: true });
    // ouvrir/params/setParams stables ; on ne réagit qu'au changement de l'id ciblé.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fiche]);
}
