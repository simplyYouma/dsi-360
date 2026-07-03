import { useState } from 'react';
import type { FormEvent } from 'react';
import { Eye, EyeOff, LogIn, Moon, Sun, ArrowLeft, MailCheck } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/design-system/ThemeProvider';
import { ErreurApi } from '@/lib/api';
import logoClair from '@/assets/brand/logo1.svg';
import logoSombre from '@/assets/brand/logo1-blanc.svg';
import fond from '@/assets/fond-login.png';
import styles from './LoginPage.module.css';
import { authApi } from './authApi';

// Voile semi-transparent (couleur de fond du thème) superposé à l'image : rend bien en clair et sombre.
const STYLE_FOND = {
  backgroundImage: `linear-gradient(color-mix(in srgb, var(--bg) 80%, transparent), color-mix(in srgb, var(--bg) 88%, transparent)), url(${fond})`,
  backgroundSize: 'cover',
  backgroundPosition: 'center',
};

/** Écran de connexion (mode LOCAL ; l'OIDC Entra ID s'ajoutera ici). */
export function LoginPage(): JSX.Element {
  const { connecter } = useAuth();
  const { theme, basculer } = useTheme();
  const logo = theme === 'dark' ? logoSombre : logoClair;
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [visible, setVisible] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [oubli, setOubli] = useState(false);
  const [oubliEnvoye, setOubliEnvoye] = useState(false);

  const soumettre = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      await connecter(email.trim(), motDePasse);
    } catch (err) {
      setErreur(
        err instanceof ErreurApi && err.statut === 401
          ? 'Identifiants invalides.'
          : 'Connexion impossible. Réessayez.',
      );
      setEnvoi(false);
    }
  };

  const soumettreOubli = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      await authApi.motDePasseOublie(email.trim());
      setOubliEnvoye(true);
    } catch {
      // Réponse volontairement neutre : on n'indique jamais si le compte existe.
      setOubliEnvoye(true);
    } finally {
      setEnvoi(false);
    }
  };

  const revenirLogin = (): void => {
    setOubli(false);
    setOubliEnvoye(false);
    setErreur(null);
  };

  return (
    <div className={styles.page} style={STYLE_FOND}>
      <button type="button" className={styles.theme} onClick={basculer} aria-label="Changer de thème">
        {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
      </button>

      {oubli ? (
        <form className={styles.carte} onSubmit={(e) => void soumettreOubli(e)}>
          <img src={logo} alt="DSI 360" className={styles.logo} />
          {oubliEnvoye ? (
            <>
              <MailCheck size={34} style={{ color: 'var(--status-ok)' }} />
              <h1 className={styles.titre}>Vérifiez votre e-mail</h1>
              <p className={styles.sous}>
                Si un compte est associé à cette adresse, un lien de réinitialisation vient d'être
                envoyé. Le lien expire après 30 minutes.
              </p>
              <button type="button" className={styles.lienOubli} onClick={revenirLogin}>
                <ArrowLeft size={14} /> Retour à la connexion
              </button>
            </>
          ) : (
            <>
              <h1 className={styles.titre}>Mot de passe oublié</h1>
              <p className={styles.sous}>
                Saisissez votre adresse e-mail : nous vous enverrons un lien de réinitialisation.
              </p>
              <label className={styles.champ}>
                <span className={styles.label}>Adresse e-mail</span>
                <input
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="prenom.nom@afgbank.ml"
                  required
                />
              </label>
              {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
              <Button type="submit" pleineLargeur disabled={envoi}>
                {envoi ? 'Envoi…' : 'Envoyer le lien'}
              </Button>
              <button type="button" className={styles.lienOubli} onClick={revenirLogin}>
                <ArrowLeft size={14} /> Retour à la connexion
              </button>
            </>
          )}
        </form>
      ) : (
        <form className={styles.carte} onSubmit={soumettre}>
          <img src={logo} alt="DSI 360" className={styles.logo} />
          <h1 className={styles.titre}>Connexion</h1>
          <p className={styles.sous}>Plateforme de pilotage de la DSI — AFG Bank Mali.</p>

          <label className={styles.champ}>
            <span className={styles.label}>Adresse e-mail</span>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="prenom.nom@afgbank.ml"
              required
            />
          </label>

          <label className={styles.champ}>
            <span className={styles.label}>Mot de passe</span>
            <div className={styles.motDePasse}>
              <input
                type={visible ? 'text' : 'password'}
                autoComplete="current-password"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
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

          {erreur !== null && <p className={styles.erreur}>{erreur}</p>}

          <Button type="submit" pleineLargeur disabled={envoi}>
            <LogIn size={16} />
            {envoi ? 'Connexion…' : 'Se connecter'}
          </Button>
          <button type="button" className={styles.lienOubli} onClick={() => setOubli(true)}>
            Mot de passe oublié ?
          </button>
        </form>
      )}
    </div>
  );
}
