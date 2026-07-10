import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, House } from 'lucide-react';
import { NAVIGATION } from './navigation';
import styles from './FilAriane.module.css';

/** Fil d'Ariane : Accueil › <Module> [› <sous-page>] selon la route courante. */
export function FilAriane(): JSX.Element {
  const { pathname } = useLocation();
  if (pathname === '/') {
    return (
      <nav className={styles.fil} aria-label="Fil d'Ariane">
        <span className={styles.courant}>
          <House size={15} aria-hidden="true" />
          Accueil
        </span>
      </nav>
    );
  }

  const segments = pathname.split('/').filter(Boolean);
  const base = `/${segments[0] ?? ''}`;
  const entree =
    NAVIGATION.find((e) => e.chemin === pathname) ?? NAVIGATION.find((e) => e.chemin === base);
  const libelleModule = entree?.libelle ?? 'Page';
  // Sous-page éventuelle (création ou fiche détail).
  const sousPage = segments.length > 1 ? (segments[1] === 'nouveau' ? 'Nouveau' : 'Fiche') : null;

  return (
    <nav className={styles.fil} aria-label="Fil d'Ariane">
      <Link to="/" className={styles.lien}>
        <House size={15} aria-hidden="true" />
        Accueil
      </Link>
      <ChevronRight size={15} className={styles.sep} aria-hidden="true" />
      {sousPage === null ? (
        <span className={styles.courant}>{libelleModule}</span>
      ) : (
        <>
          <Link to={base} className={styles.lien}>
            {libelleModule}
          </Link>
          <ChevronRight size={15} className={styles.sep} aria-hidden="true" />
          <span className={styles.courant}>{sousPage}</span>
        </>
      )}
    </nav>
  );
}
