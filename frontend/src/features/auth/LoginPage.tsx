import { useState } from 'react';
import type { FormEvent } from 'react';
import { Eye, EyeOff, LogIn } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { useAuth } from '@/lib/auth';
import { ErreurApi } from '@/lib/api';
import logo from '@/assets/brand/logo-dsi360.svg';
import styles from './LoginPage.module.css';

/** Écran de connexion (mode LOCAL ; l'OIDC Entra ID s'ajoutera ici). */
export function LoginPage(): JSX.Element {
  const { connecter } = useAuth();
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [visible, setVisible] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

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
          : "Connexion impossible. Réessayez.",
      );
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.page}>
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
      </form>
    </div>
  );
}
