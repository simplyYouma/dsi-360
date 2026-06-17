import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { PanelLeft, Search, Bell, Moon, Sun, LogOut } from 'lucide-react';
import { useTheme } from '@/design-system/ThemeProvider';
import { cx } from '@/common/cx';
import { NAVIGATION } from './navigation';
import styles from './AppShell.module.css';

const CLE_REPLI = 'dsi360.sidebar.replie';

/** Shell applicatif premium : sidebar repliable + topbar. Contenu via <Outlet/>. */
export function AppShell(): JSX.Element {
  const { theme, basculer } = useTheme();
  const [replie, setReplie] = useState(() => localStorage.getItem(CLE_REPLI) === '1');

  const basculerSidebar = (): void => {
    setReplie((r) => {
      localStorage.setItem(CLE_REPLI, r ? '0' : '1');
      return !r;
    });
  };

  return (
    <div className={cx(styles.shell, replie && styles.replie)}>
      <aside className={styles.sidebar}>
        <div className={styles.marque}>
          <span className={styles.logo}>D</span>
          {!replie && <span className={styles.marqueTexte}>DSI 360</span>}
        </div>

        <nav className={styles.nav}>
          {NAVIGATION.map(({ chemin, libelle, icone: Icone }) => (
            <NavLink
              key={chemin}
              to={chemin}
              end={chemin === '/'}
              className={({ isActive }) => cx(styles.lien, isActive && styles.actif)}
              title={libelle}
            >
              <Icone size={20} className={styles.lienIcone} aria-hidden="true" />
              {!replie && <span className={styles.lienTexte}>{libelle}</span>}
            </NavLink>
          ))}
        </nav>

        <div className={styles.pied}>
          <div className={styles.profil}>
            <span className={styles.avatar}>FY</span>
            {!replie && (
              <span className={styles.profilInfos}>
                <span className={styles.profilNom}>Fatou Y.</span>
                <span className={styles.profilRole}>Administrateur</span>
              </span>
            )}
          </div>
          <button className={styles.deconnexion} title="Déconnexion" aria-label="Déconnexion">
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      <div className={styles.principal}>
        <header className={styles.topbar}>
          <button className={styles.iconeBtn} onClick={basculerSidebar} aria-label="Replier le menu">
            <PanelLeft size={20} />
          </button>

          <label className={styles.recherche}>
            <Search size={18} />
            <input placeholder="Rechercher une activité, une référence…" />
          </label>

          <div className={styles.actions}>
            <button className={styles.iconeBtn} onClick={basculer} aria-label="Changer de thème">
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            <button className={styles.iconeBtn} aria-label="Notifications">
              <Bell size={20} />
            </button>
            <span className={styles.avatar}>FY</span>
          </div>
        </header>

        <main className={styles.contenu}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
