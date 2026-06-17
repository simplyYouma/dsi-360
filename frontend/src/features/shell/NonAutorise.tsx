import { Link } from 'react-router-dom';
import { ShieldOff } from 'lucide-react';

/** Affichée quand l'utilisateur n'a pas l'accès requis pour un module. */
export function NonAutorise(): JSX.Element {
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-4)',
        textAlign: 'center',
        color: 'var(--text-muted)',
      }}
    >
      <ShieldOff size={40} aria-hidden="true" />
      <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 600, color: 'var(--text)' }}>
        Accès non autorisé
      </h1>
      <p style={{ maxWidth: '44ch' }}>
        Votre profil ne donne pas accès à ce module. Si c'est une erreur, contactez un administrateur.
      </p>
      <Link to="/" style={{ color: 'var(--accent)', fontWeight: 500 }}>
        Retour au tableau de bord
      </Link>
    </div>
  );
}
