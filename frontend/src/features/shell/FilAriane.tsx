import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, House } from 'lucide-react';
import { NAVIGATION } from './navigation';
import styles from './FilAriane.module.css';

/** Fil d'Ariane : Accueil › <Module> selon la route courante. */
export function FilAriane(): JSX.Element {
  const { pathname } = useLocation();
  const entree = NAVIGATION.find((e) => e.chemin === pathname);
  const courant = entree?.libelle ?? 'Page';
  const surAccueil = pathname === '/';

  return (
    <nav className={styles.fil} aria-label="Fil d'Ariane">
      <Link to="/" className={styles.lien}>
        <House size={15} aria-hidden="true" />
        Accueil
      </Link>
      {!surAccueil && (
        <>
          <ChevronRight size={15} className={styles.sep} aria-hidden="true" />
          <span className={styles.courant}>{courant}</span>
        </>
      )}
    </nav>
  );
}
