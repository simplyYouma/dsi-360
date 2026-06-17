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

export interface SectionNav {
  titre: string;
  entrees: EntreeNav[];
}

/** Navigation groupée en sections élégantes (les 9 modules du cahier + administration). */
export const SECTIONS: SectionNav[] = [
  {
    titre: 'Pilotage',
    entrees: [{ chemin: '/', libelle: 'Tableau de bord', icone: LayoutDashboard, phase: 'P1' }],
  },
  {
    titre: 'Activités',
    entrees: [
      { chemin: '/incidents', libelle: 'Incidents', icone: TriangleAlert, phase: 'P1' },
      { chemin: '/demandes', libelle: 'Demandes', icone: Inbox, phase: 'P1' },
      { chemin: '/projets', libelle: 'Projets', icone: FolderKanban, phase: 'P1' },
      { chemin: '/changements', libelle: 'Changements', icone: GitPullRequestArrow, phase: 'P2' },
    ],
  },
  {
    titre: 'Maîtrise & conformité',
    entrees: [
      { chemin: '/audit', libelle: 'Audit & Recommandations', icone: ClipboardCheck, phase: 'P2' },
      { chemin: '/risques', libelle: 'Risques IT', icone: ShieldAlert, phase: 'P2' },
      { chemin: '/cybersecurite', libelle: 'Cybersécurité', icone: Lock, phase: 'P3' },
    ],
  },
  {
    titre: 'Gouvernance',
    entrees: [{ chemin: '/gouvernance', libelle: 'Gouvernance DSI', icone: Landmark, phase: 'P3' }],
  },
  {
    titre: 'Système',
    entrees: [{ chemin: '/administration', libelle: 'Administration', icone: Settings, phase: 'P1' }],
  },
];

/** Liste à plat (routage + recherche de libellé pour le fil d'Ariane). */
export const NAVIGATION: EntreeNav[] = SECTIONS.flatMap((s) => s.entrees);

/** Clé d'accès (RBAC) correspondant à un chemin : '/' -> 'tableau-de-bord', '/incidents' -> 'incidents'. */
export function cleAcces(chemin: string): string {
  return chemin === '/' ? 'tableau-de-bord' : chemin.slice(1);
}
