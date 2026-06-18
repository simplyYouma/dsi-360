import { useState } from 'react';
import type { FormEvent } from 'react';
import { Eye, EyeOff, KeyRound } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/design-system/ThemeProvider';
import { api, ErreurApi } from '@/lib/api';
import logoClair from '@/assets/brand/logo1.svg';
import logoSombre from '@/assets/brand/logo1-blanc.svg';
import styles from './LoginPage.module.css';

/** Changement de mot de passe imposé (1re connexion) ou volontaire. */
export function ChangerMotDePasse(): JSX.Element {
  const { deconnecter, rafraichir } = useAuth();
  const { theme } = useTheme();
  const logo = theme === 'dark' ? logoSombre : logoClair;

  const [ancien, setAncien] = useState('');
  const [nouveau, setNouveau] = useState('');
  const [confirme, setConfirme] = useState('');
  const [visible, setVisible] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const soumettre = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setErreur(null);
    if (nouveau.length < 8) {
      setErreur('Le nouveau mot de passe doit faire au moins 8 caractères.');
      return;
    }
    if (nouveau !== confirme) {
      setErreur('La confirmation ne correspond pas.');
      return;
    }
    setEnvoi(true);
    try {
      await api.post('/auth/mot-de-passe', { ancien, nouveau });
      await rafraichir();
    } catch (err) {
      setErreur(
        err instanceof ErreurApi && err.statut === 400
          ? 'Ancien mot de passe incorrect.'
          : 'Modification impossible.',
      );
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.page}>
      <form className={styles.carte} onSubmit={soumettre}>
        <img src={logo} alt="DSI 360" className={styles.logo} />
        <h1 className={styles.titre}>Nouveau mot de passe</h1>
        <p className={styles.sous}>
          Pour votre sécurité, définissez un nouveau mot de passe avant de continuer.
        </p>

        <label className={styles.champ}>
          <span className={styles.label}>Mot de passe actuel</span>
          <div className={styles.motDePasse}>
            <input
              type={visible ? 'text' : 'password'}
              value={ancien}
              onChange={(e) => setAncien(e.target.value)}
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              className={styles.oeil}
              onClick={() => setVisible((v) => !v)}
              aria-label={visible ? 'Masquer' : 'Afficher'}
            >
              {visible ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>

        <label className={styles.champ}>
          <span className={styles.label}>Nouveau mot de passe</span>
          <input
            type={visible ? 'text' : 'password'}
            value={nouveau}
            onChange={(e) => setNouveau(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>

        <label className={styles.champ}>
          <span className={styles.label}>Confirmer</span>
          <input
            type={visible ? 'text' : 'password'}
            value={confirme}
            onChange={(e) => setConfirme(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>

        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}

        <Button type="submit" pleineLargeur disabled={envoi}>
          <KeyRound size={16} />
          {envoi ? 'Enregistrement…' : 'Valider'}
        </Button>
        <Button type="button" variante="fantome" pleineLargeur onClick={() => void deconnecter()}>
          Se déconnecter
        </Button>
      </form>
    </div>
  );
}
