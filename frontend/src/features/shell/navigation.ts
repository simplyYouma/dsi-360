import {
  AppWindow,
  Boxes,
  ChartColumnBig,
  ClipboardCheck,
  FolderKanban,
  GitPullRequestArrow,
  Inbox,
  Landmark,
  LayoutDashboard,
  MoonStar,
  ListChecks,
  Lock,
  Settings,
  ShieldAlert,
  TriangleAlert,
  UploadCloud,
  type LucideIcon,
} from 'lucide-react';

export interface EntreeNav {
  chemin: string;
  libelle: string;
  icone: LucideIcon;
  phase: 'P1' | 'P2' | 'P3';
  /** Réservé aux profils transverses (DSI / Administration) plutôt qu'à un accès module. */
  transverse?: boolean;
  /** Toujours visible (toute personne authentifiée), sans contrôle d'accès module. */
  toujours?: boolean;
  /** Retirée du menu ET du routage, sans rien supprimer : l'écran, son API, ses données et ses
   *  droits restent en place. Le chemin retombe alors sur la page « Module à venir », qui dit à
   *  quelle phase il appartient — plutôt qu'un écran vide ou une erreur.
   *
   *  C'est un interrupteur, pas une suppression : remettre le module en service se fait en
   *  retirant cette ligne, sans rien réécrire. L'entrée reste ici pour que le catalogue des
   *  modules dise la vérité — le fil d'Ariane et la page d'attente y lisent encore son libellé. */
  masque?: boolean;
}

export interface SectionNav {
  titre: string;
  entrees: EntreeNav[];
}

/** Navigation groupée en sections élégantes (les 9 modules du cahier + administration). */
export const SECTIONS: SectionNav[] = [
  {
    titre: 'Mon espace',
    entrees: [
      {
        chemin: '/mes-tickets',
        libelle: 'Mes tickets',
        icone: ListChecks,
        phase: 'P1',
        toujours: true,
      },
    ],
  },
  {
    titre: 'Pilotage',
    entrees: [
      { chemin: '/', libelle: 'Tableau de bord', icone: LayoutDashboard, phase: 'P1' },
      { chemin: '/analyses', libelle: 'Analyses', icone: ChartColumnBig, phase: 'P1' },
    ],
  },
  {
    titre: 'Activités',
    entrees: [
      { chemin: '/incidents', libelle: 'Incidents', icone: TriangleAlert, phase: 'P1' },
      { chemin: '/demandes', libelle: 'Demandes', icone: Inbox, phase: 'P1' },
      { chemin: '/projets', libelle: 'Projets', icone: FolderKanban, phase: 'P1' },
      { chemin: '/changements', libelle: 'Changements', icone: GitPullRequestArrow, phase: 'P2' },
      // La production quotidienne : la soirée de clôture du core banking.
      { chemin: '/eod', libelle: 'EOD', icone: MoonStar, phase: 'P1' },
    ],
  },
  {
    titre: 'Maîtrise & conformité',
    entrees: [
      { chemin: '/audit', libelle: 'Audit & Recommandations', icone: ClipboardCheck, phase: 'P2' },
      // Masqués : les deux écrans existent et fonctionnent, mais ne sont pas ouverts aux agents.
      { chemin: '/risques', libelle: 'Risques IT', icone: ShieldAlert, phase: 'P2', masque: true },
      {
        chemin: '/cybersecurite',
        libelle: 'Cybersécurité',
        icone: Lock,
        phase: 'P3',
        masque: true,
      },
    ],
  },
  {
    titre: 'Patrimoine',
    entrees: [
      { chemin: '/inventaire', libelle: 'Inventaire', icone: Boxes, phase: 'P2' },
      { chemin: '/applications', libelle: 'Applications', icone: AppWindow, phase: 'P2' },
    ],
  },
  {
    titre: 'Gouvernance',
    entrees: [{ chemin: '/gouvernance', libelle: 'Gouvernance', icone: Landmark, phase: 'P3' }],
  },
  {
    titre: 'Système',
    entrees: [
      // Accès module « import » distribué depuis la matrice, comme les autres.
      { chemin: '/import', libelle: 'Import quotidien', icone: UploadCloud, phase: 'P1' },
      { chemin: '/administration', libelle: 'Administration', icone: Settings, phase: 'P1' },
    ],
  },
];

/** Liste à plat (routage + recherche de libellé pour le fil d'Ariane). */
export const NAVIGATION: EntreeNav[] = SECTIONS.flatMap((s) => s.entrees);

/** Clé d'accès (RBAC) correspondant à un chemin : '/' -> 'tableau-de-bord', '/incidents' -> 'incidents'. */
export function cleAcces(chemin: string): string {
  return chemin === '/' ? 'tableau-de-bord' : chemin.slice(1);
}
