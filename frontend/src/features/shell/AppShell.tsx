import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Search, Moon, Sun, LogOut } from 'lucide-react';
import { useTheme } from '@/design-system/ThemeProvider';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import { useAuth } from '@/lib/auth';
import { cx } from '@/common/cx';
import logoClair from '@/assets/brand/logo1.svg';
import logoSombre from '@/assets/brand/logo1-blanc.svg';
import { SECTIONS, cleAcces } from './navigation';
import { FilAriane } from './FilAriane';
import { Notifications } from './Notifications';
import styles from './AppShell.module.css';

const CLE_REPLI = 'dsi360.sidebar.replie';

/** Icône de pli : panneau dont la partie gauche est pleine (ouvert) ou vide (replié). */
function IconePli({ ouvert }: { ouvert: boolean }): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <line x1="9" y1="4" x2="9" y2="20" />
      {ouvert && (
        <path
          d="M5.5 4 H9 V20 H5.5 A2.5 2.5 0 0 1 3 17.5 V6.5 A2.5 2.5 0 0 1 5.5 4 Z"
          fill="currentColor"
          stroke="none"
        />
      )}
    </svg>
  );
}

/** Shell applicatif premium : sidebar repliable (sections) + topbar. Contenu via <Outlet/>. */
export function AppShell(): JSX.Element | null {
  const { theme, basculer } = useTheme();
  const { moi, deconnecter } = useAuth();
  const [replie, setReplie] = useState(() => localStorage.getItem(CLE_REPLI) === '1');

  const basculerSidebar = (): void => {
    setReplie((r) => {
      localStorage.setItem(CLE_REPLI, r ? '0' : '1');
      return !r;
    });
  };

  if (moi === null) return null; // le shell n'est rendu qu'authentifié (garde dans App)

  const logo = theme === 'dark' ? logoSombre : logoClair;

  return (
    <div className={cx(styles.shell, replie && styles.replie)}>
      <aside className={styles.sidebar}>
        <div className={styles.marque}>
          <img src={logo} alt="DSI 360" className={styles.logo} />
          <button
            className={styles.pli}
            onClick={basculerSidebar}
            aria-label={replie ? 'Déplier le menu' : 'Replier le menu'}
          >
            <IconePli ouvert={!replie} />
          </button>
        </div>

        <nav className={styles.nav}>
          {SECTIONS.map((section) => {
            const entrees = section.entrees.filter((e) => moi.acces.includes(cleAcces(e.chemin)));
            if (entrees.length === 0) return null;
            return (
            <div key={section.titre} className={styles.section}>
              <span className={styles.sectionTitre}>{section.titre}</span>
              {entrees.map(({ chemin, libelle, icone: Icone }) => (
                <NavLink
                  key={chemin}
                  to={chemin}
                  end={chemin === '/'}
                  className={({ isActive }) => cx(styles.lien, isActive && styles.actif)}
                  title={libelle}
                >
                  <Icone size={19} className={styles.lienIcone} aria-hidden="true" />
                  <span className={styles.lienTexte}>{libelle}</span>
                </NavLink>
              ))}
            </div>
            );
          })}
        </nav>

        <div className={styles.pied}>
          <div className={styles.profil}>
            <AvatarPersonnage seed={moi.email} taille={36} />
            <span className={styles.profilInfos}>
              <span className={styles.profilNom}>
                {moi.prenom} {moi.nom}
              </span>
              <span className={styles.profilRole}>{moi.profil_libelle}</span>
            </span>
          </div>
          <button
            className={styles.deconnexion}
            onClick={() => void deconnecter()}
            title="Déconnexion"
            aria-label="Déconnexion"
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      <div className={styles.principal}>
        <header className={styles.topbar}>
          <label className={styles.recherche}>
            <Search size={18} />
            <input placeholder="Rechercher une activité, une référence…" />
          </label>

          <div className={styles.actions}>
            <button className={styles.iconeBtn} onClick={basculer} aria-label="Changer de thème">
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            <Notifications />
            <AvatarPersonnage seed={moi.email} taille={36} />
          </div>
        </header>

        <main className={styles.contenu}>
          <FilAriane />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
