import {
  Building2,
  CircleCheck,
  CircleSlash,
  Cloud,
  Hammer,
  Link2,
  Unlink,
  type LucideIcon,
} from 'lucide-react';
import { api } from '@/lib/api';

/** Une personne qui répond d'une application : un compte de l'annuaire, ou un nom écrit à la main
 *  (prestataire, support éditeur, personne sans compte). */
export interface ResponsableApplication {
  utilisateur_id: string | null;
  nom: string;
}

export interface Application {
  id: string;
  /** Référence système (« APP-00001 »), générée par la plateforme — jamais saisie. */
  reference: string;
  nom: string;
  /** Le métier que l'application sert (« Banque mobile »). */
  processus_metier: string | null;
  version: string | null;
  editeur: string | null;
  hebergement: string | null;
  interfacage: string | null;
  statut: string;
  /** Qui l'administre, et qui prend le relais. Plusieurs par rôle : une application se tient
   *  rarement à une seule personne. */
  administrateurs: ResponsableApplication[];
  administrateurs_secours: ResponsableApplication[];
  nb_comptes_actifs: number | null;
}

export interface EvenementApplication {
  action: string;
  horodatage: string;
  acteur: string | null;
  /** Ce qui a changé, en clair (« administrateur : Awa Touré → Mady Wague »). */
  detail: string | null;
}

export interface ApplicationDetail extends Application {
  /** Dernières actions journalisées, plus récentes d'abord. */
  historique: EvenementApplication[];
  fonctionnalites: string | null;
  editeur_id: string | null;
  proprietaire: string | null;
  pays_donnees: string | null;
  date_debut: string | null;
  date_fin: string | null;
  lien: string | null;
  serveur_application: string | null;
  serveur_base: string | null;
  port: string | null;
  source: string;
  cree_le: string;
  maj_le: string;
}

export interface StatsApplications {
  total: number;
  actives: number;
  retirees: number;
  internes: number;
  externes: number;
  interfacees: number;
  /** Plus personne ne répond de cette application : le premier trou à combler. */
  sans_administrateur: number;
  /** Un seul administrateur, sans relais : le risque de continuité qu'on ne voit jamais venir. */
  sans_secours: number;
}

export interface ReferentielItem {
  id: string;
  libelle: string;
  actif: boolean;
}

export interface FiltresApplications {
  q?: string | null;
  editeur_id?: string | null;
  hebergement?: string | null;
  statut?: string | null;
  interfacage?: string | null;
  /** Un nom d'administrateur, ou `AUCUN` pour « personne ne s'en occupe ». */
  administrateur?: string | null;
}

/** Ce que l'écran envoie pour désigner une personne : un compte, ou un nom libre. */
export interface ResponsableSaisie {
  utilisateur_id?: string | null;
  nom?: string | null;
}

export interface NouvelleApplication {
  nom: string;
  processus_metier?: string | null;
  fonctionnalites?: string | null;
  version?: string | null;
  editeur_id?: string | null;
  hebergement?: string | null;
  pays_donnees?: string | null;
  interfacage?: string | null;
  statut?: string;
  proprietaire?: string | null;
  date_debut?: string | null;
  date_fin?: string | null;
  nb_comptes_actifs?: number | null;
  lien?: string | null;
  serveur_application?: string | null;
  serveur_base?: string | null;
  port?: string | null;
  /** Listes complètes : ce qui n'y figure plus est retiré. */
  administrateurs?: ResponsableSaisie[];
  administrateurs_secours?: ResponsableSaisie[];
}

export type MajApplication = Partial<NouvelleApplication>;

/** Où tournent les données : chez nous, ou chez un tiers. */
export const HEBERGEMENTS = [
  { valeur: 'INTERNE', libelle: 'Interne' },
  { valeur: 'EXTERNE', libelle: 'Externe' },
] as const;

/** Cycle de vie d'une application. Volontairement court : ce n'est pas un workflow. */
export const STATUTS = [
  { valeur: 'EN_SERVICE', libelle: 'En service' },
  { valeur: 'EN_PROJET', libelle: 'En projet' },
  { valeur: 'ARRETE', libelle: 'Arrêtée' },
] as const;

export const INTERFACAGES = [
  { valeur: 'OUI', libelle: 'Interfacée' },
  { valeur: 'NON', libelle: 'Non interfacée' },
] as const;

export const LIBELLE_HEBERGEMENT: Record<string, string> = {
  INTERNE: 'Interne',
  EXTERNE: 'Externe',
};

/** Une forme se lit plus vite qu'un point coloré, et reste lisible pour qui distingue mal les
 *  couleurs : un bâtiment pour ce qui tourne chez nous, un nuage pour ce qui est chez un tiers. */
export const ICONE_HEBERGEMENT: Record<string, LucideIcon> = {
  INTERNE: Building2,
  EXTERNE: Cloud,
};

/** Interfacée ou non : deux maillons liés, ou rompus. */
export const ICONE_INTERFACAGE: Record<string, LucideIcon> = {
  OUI: Link2,
  NON: Unlink,
};

export const LIBELLE_INTERFACAGE: Record<string, string> = {
  OUI: 'Interfacée',
  NON: 'Non interfacée',
};

/** Cycle de vie : ce qui tourne, ce qui se construit, ce qui s'est arrêté. */
export const ICONE_STATUT: Record<string, LucideIcon> = {
  EN_SERVICE: CircleCheck,
  EN_PROJET: Hammer,
  ARRETE: CircleSlash,
};

export const LIBELLE_STATUT: Record<string, string> = {
  EN_SERVICE: 'En service',
  EN_PROJET: 'En projet',
  ARRETE: 'Arrêtée',
};

/** La couleur porte le sens : externe = ce qui sort de nos murs, arrêtée = ce qui ne tourne plus. */
export const COULEUR_HEBERGEMENT: Record<string, string> = {
  INTERNE: 'var(--status-ok)',
  EXTERNE: 'var(--status-warn)',
};

export const COULEUR_STATUT: Record<string, string> = {
  EN_SERVICE: 'var(--status-ok)',
  EN_PROJET: 'var(--cat-3)',
  ARRETE: 'var(--text-muted)',
};

export interface TrancheApplications {
  libelle: string;
  nombre: number;
}

export interface AnalysesApplications {
  total: number;
  par_editeur: TrancheApplications[];
  par_hebergement: TrancheApplications[];
  par_statut: TrancheApplications[];
  par_administrateur: TrancheApplications[];
  /** Ce qui n'a pas de relais désigné : la continuité qui tient à une personne. */
  sans_secours: TrancheApplications[];
}

/** Filtre « personne ne s'en occupe » : un mot-clé, pas un nom. */
export const SANS_ADMINISTRATEUR = 'AUCUN';

function chaineFiltres(page: number, f?: FiltresApplications): string {
  const p = new URLSearchParams({ page: String(page) });
  if (f?.q && f.q.trim() !== '') p.set('q', f.q.trim());
  if (f?.editeur_id) p.set('editeur_id', f.editeur_id);
  if (f?.hebergement) p.set('hebergement', f.hebergement);
  if (f?.statut) p.set('statut', f.statut);
  if (f?.interfacage) p.set('interfacage', f.interfacage);
  if (f?.administrateur) p.set('administrateur', f.administrateur);
  return p.toString();
}

export const applicationsApi = {
  lister: (
    page: number,
    f?: FiltresApplications,
  ): Promise<{ elements: Application[]; total: number }> =>
    api.get(`/applications?${chaineFiltres(page, f)}`),
  detail: (id: string): Promise<ApplicationDetail> => api.get(`/applications/${id}`),
  creer: (corps: NouvelleApplication): Promise<ApplicationDetail> =>
    api.post('/applications', corps),
  modifier: (id: string, corps: MajApplication): Promise<ApplicationDetail> =>
    api.patch(`/applications/${id}`, corps),
  supprimer: (id: string): Promise<void> => api.del(`/applications/${id}`),
  editeurs: (): Promise<ReferentielItem[]> => api.get('/applications/referentiels/editeurs'),
  ajouterEditeur: (libelle: string): Promise<ReferentielItem> =>
    api.post('/applications/referentiels/editeurs', { libelle }),
  supprimerEditeur: (id: string): Promise<void> =>
    api.del(`/applications/referentiels/editeurs/${id}`),
  analyses: (): Promise<AnalysesApplications> => api.get('/applications/analyses'),
};
