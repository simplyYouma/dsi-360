import type { ReactNode } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/lib/auth';
import { LoginPage } from '@/features/auth/LoginPage';
import { ChangerMotDePasse } from '@/features/auth/ChangerMotDePasse';
import { AppShell } from '@/features/shell/AppShell';
import { PagePlaceholder } from '@/features/shell/PagePlaceholder';
import { NonAutorise } from '@/features/shell/NonAutorise';
import { DashboardPage } from '@/features/dashboard/DashboardPage';
import { IncidentsPage } from '@/features/incidents/IncidentsPage';
import { DemandesPage } from '@/features/demandes/DemandesPage';
import { ProjetsPage } from '@/features/projets/ProjetsPage';
import { ChangementsPage } from '@/features/changements/ChangementsPage';
import { AuditPage } from '@/features/audit/AuditPage';
import { RisquesPage } from '@/features/risques/RisquesPage';
import { PageActiviteCategorie } from '@/common/PageActiviteCategorie';
import { AdministrationPage } from '@/features/administration/AdministrationPage';
import { NAVIGATION, cleAcces } from '@/features/shell/navigation';

/** Pages réelles déjà implémentées (les autres routes affichent un écran « à venir »). */
const PAGES: Record<string, JSX.Element> = {
  '/incidents': <IncidentsPage />,
  '/demandes': <DemandesPage />,
  '/projets': <ProjetsPage />,
  '/changements': <ChangementsPage />,
  '/audit': <AuditPage />,
  '/risques': <RisquesPage />,
  '/cybersecurite': (
    <PageActiviteCategorie
      titre="Cybersécurité"
      sous="Habilitations sensibles, comptes admin, vulnérabilités, correctifs, MFA, IAM."
      base="/cybersecurite"
      module="cybersecurite"
      labelObjet="Élément"
      labelCategorie="Type"
      labelNouveau="Nouvel élément"
      couleurCategorie="var(--cat-4)"
    />
  ),
  '/gouvernance': (
    <PageActiviteCategorie
      titre="Gouvernance DSI"
      sous="COPIL, comités, décisions DG, engagements et plans d'actions."
      base="/gouvernance"
      module="gouvernance"
      labelObjet="Sujet"
      labelCategorie="Type"
      labelNouveau="Nouveau point"
      couleurCategorie="var(--cat-6)"
    />
  ),
  '/administration': <AdministrationPage />,
};

/** Garde de route : n'affiche le contenu que si l'utilisateur a l'accès requis. */
function RequiertAcces({ cle, children }: { cle: string; children: ReactNode }): JSX.Element {
  const { moi } = useAuth();
  if (moi !== null && !moi.acces.includes(cle)) return <NonAutorise />;
  return <>{children}</>;
}

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
  if (moi.doit_changer_mdp) return <ChangerMotDePasse />;

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          {NAVIGATION.filter((e) => e.chemin !== '/').map((e) => (
            <Route
              key={e.chemin}
              path={e.chemin}
              element={
                <RequiertAcces cle={cleAcces(e.chemin)}>
                  {PAGES[e.chemin] ?? <PagePlaceholder />}
                </RequiertAcces>
              }
            />
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
