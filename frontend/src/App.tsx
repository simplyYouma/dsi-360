import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/lib/auth';
import { LoginPage } from '@/features/auth/LoginPage';
import { AppShell } from '@/features/shell/AppShell';
import { PagePlaceholder } from '@/features/shell/PagePlaceholder';
import { DashboardPage } from '@/features/dashboard/DashboardPage';
import { NAVIGATION } from '@/features/shell/navigation';

/** Aiguillage selon l'état d'authentification (garde de routes). */
function Racine(): JSX.Element {
  const { statut, moi } = useAuth();

  if (statut === 'chargement') {
    return (
      <div
        style={{
          minHeight: '100dvh',
          display: 'grid',
          placeItems: 'center',
          color: 'var(--text-muted)',
        }}
      >
        Chargement…
      </div>
    );
  }
  if (moi === null) return <LoginPage />;

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          {NAVIGATION.filter((e) => e.chemin !== '/').map((e) => (
            <Route key={e.chemin} path={e.chemin} element={<PagePlaceholder />} />
          ))}
          <Route path="*" element={<PagePlaceholder />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export function App(): JSX.Element {
  return (
    <AuthProvider>
      <Racine />
    </AuthProvider>
  );
}
