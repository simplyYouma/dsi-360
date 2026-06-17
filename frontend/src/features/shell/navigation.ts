import {
  LayoutDashboard,
  TriangleAlert,
  Inbox,
  FolderKanban,
  GitPullRequestArrow,
  ClipboardCheck,
  ShieldAlert,
  Lock,
  Landmark,
  Settings,
  type LucideIcon,
} from 'lucide-react';

export interface EntreeNav {
  chemin: string;
  libelle: string;
  icone: LucideIcon;
  phase: 'P1' | 'P2' | 'P3';
}

/** Navigation principale = les 9 modules du cahier + administration. */
export const NAVIGATION: EntreeNav[] = [
  { chemin: '/', libelle: 'Tableau de bord', icone: LayoutDashboard, phase: 'P1' },
  { chemin: '/incidents', libelle: 'Incidents', icone: TriangleAlert, phase: 'P1' },
  { chemin: '/demandes', libelle: 'Demandes', icone: Inbox, phase: 'P1' },
  { chemin: '/projets', libelle: 'Projets', icone: FolderKanban, phase: 'P1' },
  { chemin: '/changements', libelle: 'Changements', icone: GitPullRequestArrow, phase: 'P2' },
  { chemin: '/audit', libelle: 'Audit & Recommandations', icone: ClipboardCheck, phase: 'P2' },
  { chemin: '/risques', libelle: 'Risques IT', icone: ShieldAlert, phase: 'P2' },
  { chemin: '/cybersecurite', libelle: 'Cybersécurité', icone: Lock, phase: 'P3' },
  { chemin: '/gouvernance', libelle: 'Gouvernance DSI', icone: Landmark, phase: 'P3' },
  { chemin: '/administration', libelle: 'Administration', icone: Settings, phase: 'P1' },
];
