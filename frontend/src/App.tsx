import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppShell } from '@/features/shell/AppShell';
import { PagePlaceholder } from '@/features/shell/PagePlaceholder';
import { DashboardPage } from '@/features/dashboard/DashboardPage';
import { NAVIGATION } from '@/features/shell/navigation';

/** Racine : routeur + shell premium. L'authentification arrivera au lot P1-0 (garde de routes). */
export function App(): JSX.Element {
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
