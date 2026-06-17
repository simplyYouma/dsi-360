import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { PanelLeft, Search, Bell, Moon, Sun, LogOut } from 'lucide-react';
import { useTheme } from '@/design-system/ThemeProvider';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import { cx } from '@/common/cx';
import logo from '@/assets/brand/logo-dsi360.svg';
import { SECTIONS } from './navigation';
import { FilAriane } from './FilAriane';
import styles from './AppShell.module.css';

const CLE_REPLI = 'dsi360.sidebar.replie';
// Graine d'avatar = identité de l'utilisateur connecté (provisoire avant l'authentification).
const SEED_UTILISATEUR = 'fatou.yattara@afgbank.ml';

/** Shell applicatif premium : sidebar repliable (sections) + topbar. Contenu via <Outlet/>. */
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
          <img src={logo} alt="DSI 360" className={styles.logo} />
          <button
            className={styles.pli}
            onClick={basculerSidebar}
            aria-label={replie ? 'Déplier le menu' : 'Replier le menu'}
          >
            <PanelLeft size={18} />
          </button>
        </div>

        <nav className={styles.nav}>
          {SECTIONS.map((section) => (
            <div key={section.titre} className={styles.section}>
              <span className={styles.sectionTitre}>{section.titre}</span>
              {section.entrees.map(({ chemin, libelle, icone: Icone }) => (
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
          ))}
        </nav>

        <div className={styles.pied}>
          <div className={styles.profil}>
            <AvatarPersonnage seed={SEED_UTILISATEUR} taille={36} />
            <span className={styles.profilInfos}>
              <span className={styles.profilNom}>Fatou Y.</span>
              <span className={styles.profilRole}>Administrateur</span>
            </span>
          </div>
          <button className={styles.deconnexion} title="Déconnexion" aria-label="Déconnexion">
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
            <button className={styles.iconeBtn} aria-label="Notifications">
              <Bell size={20} />
            </button>
            <AvatarPersonnage seed={SEED_UTILISATEUR} taille={36} />
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
