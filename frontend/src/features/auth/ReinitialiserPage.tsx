import { useState } from 'react';
import type { FormEvent } from 'react';
import { Eye, EyeOff, ShieldCheck } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { ErreurApi } from '@/lib/api';
import logo from '@/assets/brand/logo1.svg';
import fond from '@/assets/fond-login.png';
import styles from './LoginPage.module.css';
import { authApi } from './authApi';

const STYLE_FOND = {
  backgroundImage: `linear-gradient(color-mix(in srgb, var(--bg) 80%, transparent), color-mix(in srgb, var(--bg) 88%, transparent)), url(${fond})`,
  backgroundSize: 'cover',
  backgroundPosition: 'center',
};

/** Réinitialisation du mot de passe via le lien reçu par e-mail (jeton en paramètre d'URL). */
export function ReinitialiserPage(): JSX.Element {
  const jeton = new URLSearchParams(window.location.search).get('jeton') ?? '';
  const [nouveau, setNouveau] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [visible, setVisible] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [fait, setFait] = useState(false);

  const soumettre = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setErreur(null);
    if (nouveau.length < 8) {
      setErreur('Le mot de passe doit contenir au moins 8 caractères.');
      return;
    }
    if (nouveau !== confirmation) {
      setErreur('Les deux mots de passe ne correspondent pas.');
      return;
    }
    setEnvoi(true);
    try {
      await authApi.reinitialiser(jeton, nouveau);
      setFait(true);
    } catch (err) {
      const base = err instanceof ErreurApi ? err.message : 'Réinitialisation impossible. Réessayez.';
      const expire = /expir|invalide/i.test(base);
      setErreur(
        expire
          ? `${base} Demandez un nouveau lien à votre administrateur.`
          : base,
      );
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.page} style={STYLE_FOND}>
      <form className={styles.carte} onSubmit={(e) => void soumettre(e)}>
        <img src={logo} alt="DSI 360" className={styles.logo} />
        {fait ? (
          <>
            <ShieldCheck size={34} style={{ color: 'var(--status-ok)' }} />
            <h1 className={styles.titre}>Mot de passe modifié</h1>
            <p className={styles.sous}>Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.</p>
            <Button type="button" pleineLargeur onClick={() => (window.location.href = '/')}>
              Se connecter
            </Button>
          </>
        ) : jeton === '' ? (
          <>
            <h1 className={styles.titre}>Lien invalide</h1>
            <p className={styles.sous}>Ce lien de réinitialisation est incomplet ou expiré.</p>
            <Button type="button" pleineLargeur onClick={() => (window.location.href = '/')}>
              Retour à la connexion
            </Button>
          </>
        ) : (
          <>
            <h1 className={styles.titre}>Nouveau mot de passe</h1>
            <p className={styles.sous}>Choisissez un mot de passe (8 caractères minimum).</p>
            <label className={styles.champ}>
              <span className={styles.label}>Nouveau mot de passe</span>
              <div className={styles.motDePasse}>
                <input
                  type={visible ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={nouveau}
                  onChange={(e) => setNouveau(e.target.value)}
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
              <span className={styles.label}>Confirmer</span>
              <input
                type={visible ? 'text' : 'password'}
                autoComplete="new-password"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                required
              />
            </label>
            {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
            <Button type="submit" pleineLargeur disabled={envoi}>
              {envoi ? 'Validation…' : 'Réinitialiser'}
            </Button>
          </>
        )}
      </form>
    </div>
  );
}
