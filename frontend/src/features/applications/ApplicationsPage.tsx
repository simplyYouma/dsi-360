import { useCallback, useEffect, useState } from 'react';
import { Plus, Search, X, type LucideIcon } from 'lucide-react';
import { Button, Table, useToast, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { SelecteurListe } from '@/common/SelecteurListe';
import { useFicheUrl } from '@/common/useFicheUrl';
import { useAuth } from '@/lib/auth';
import { api, ErreurApi } from '@/lib/api';
import styles from '@/features/incidents/IncidentsPage.module.css';
import filtres from '@/common/FiltreTickets.module.css';
import local from '@/features/inventaire/Inventaire.module.css';
import propre from './Applications.module.css';
import { FicheApplication } from './FicheApplication';
import { ModaleApplication } from './ModaleApplication';
import {
  applicationsApi,
  COULEUR_HEBERGEMENT,
  COULEUR_STATUT,
  HEBERGEMENTS,
  ICONE_HEBERGEMENT,
  ICONE_INTERFACAGE,
  ICONE_STATUT,
  INTERFACAGES,
  LIBELLE_HEBERGEMENT,
  LIBELLE_INTERFACAGE,
  LIBELLE_STATUT,
  SANS_ADMINISTRATEUR,
  type Application,
  type FiltresApplications,
  type ReferentielItem,
  type ResponsableApplication,
  type StatsApplications,
} from './applicationsApi';

/** Couleur stable d'un éditeur : la même étiquette garde toujours la même teinte (hash →
 *  palette catégorielle). On repère ainsi ses dépendances d'un coup d'œil, sans que la couleur
 *  ne change d'une page à l'autre. */
const _PALETTE_EDITEUR = [
  'var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)',
  'var(--cat-5)', 'var(--cat-6)', 'var(--cat-7)', 'var(--cat-8)',
];
export function couleurEditeur(libelle: string): string {
  let h = 0;
  for (let i = 0; i < libelle.length; i++) h = (h * 31 + libelle.charCodeAt(i)) >>> 0;
  return _PALETTE_EDITEUR[h % _PALETTE_EDITEUR.length] ?? 'var(--cat-1)';
}

/** Les personnes qui répondent, en une cellule : la première nommée, puis le compte des autres.
 *  Aligner trois noms bout à bout étirait la colonne sans rien apprendre — le détail est en fiche. */
function Personnes({ liste }: { liste: ResponsableApplication[] }): JSX.Element {
  if (liste.length === 0) {
    // Personne de désigné : ce n'est pas une case vide, c'est un trou de suivi.
    return <span className={propre.personne0}>Personne</span>;
  }
  const [premiere, ...reste] = liste;
  return (
    <span className={propre.personnes} title={liste.map((p) => p.nom).join(' · ')}>
      <span className={propre.personnePremiere}>{premiere?.nom}</span>
      {reste.length > 0 && <span className={propre.personneReste}>+{reste.length}</span>}
    </span>
  );
}

/** Une valeur codée : l'icône porte le sens, le mot le confirme. Une forme se lit plus vite
 *  qu'un point coloré, et reste lisible pour qui distingue mal les couleurs. */
function Marqueur({
  valeur,
  libelles,
  icones,
  couleurs,
}: {
  valeur: string | null;
  libelles: Record<string, string>;
  icones: Record<string, LucideIcon>;
  couleurs?: Record<string, string>;
}): JSX.Element {
  if (valeur === null) return <span className={local.vide}>—</span>;
  const Icone = icones[valeur];
  return (
    <span className={propre.marqueur} style={{ color: couleurs?.[valeur] ?? 'var(--text)' }}>
      {Icone !== undefined && <Icone size={14} />}
      {libelles[valeur] ?? valeur}
    </span>
  );
}

/** Les vues suivent le statut — seule source de vérité sur l'état d'une application. */
const VUES: { cle: string; libelle: string; statut: string | null }[] = [
  { cle: 'service', libelle: 'En service', statut: 'EN_SERVICE' },
  { cle: 'projet', libelle: 'En projet', statut: 'EN_PROJET' },
  { cle: 'arretees', libelle: 'Arrêtées', statut: 'ARRETE' },
  { cle: 'tous', libelle: 'Toutes', statut: null },
];

export function ApplicationsPage(): JSX.Element {
  const [items, setItems] = useState<Application[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [stats, setStats] = useState<StatsApplications | null>(null);
  const [editeurs, setEditeurs] = useState<ReferentielItem[]>([]);
  const [f, setF] = useState<FiltresApplications>({ statut: 'EN_SERVICE' });
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const { moi } = useAuth();
  const { notifier } = useToast();
  const estAdmin = moi?.profil === 'ADMIN';

  const charger = useCallback(async (): Promise<void> => {
    setChargement(true);
    try {
      const data = await applicationsApi.lister(page, f);
      setItems(data.elements);
      setTotal(data.total);
    } finally {
      setChargement(false);
    }
  }, [page, f]);

  const chargerStats = useCallback((): void => {
    void api
      .get<StatsApplications>('/applications/stats')
      .then(setStats)
      .catch(() => undefined);
  }, []);

  const chargerEditeurs = useCallback((): void => {
    void applicationsApi.editeurs().then(setEditeurs);
  }, []);

  useEffect(() => {
    void charger();
  }, [charger]);
  useEffect(() => chargerStats(), [chargerStats, total]);
  useEffect(() => chargerEditeurs(), [chargerEditeurs]);

  const colonnes: Colonne<Application>[] = [
    {
      cle: 'reference',
      entete: 'Réf',
      largeur: '110px',
      valeur: (a) => a.reference,
      // Référence système, générée par la plateforme : le repère stable de l'application.
      rendu: (a) => <span className={local.technique}>{a.reference}</span>,
    },
    {
      // Le nom porte le métier servi juste en dessous : deux informations qui se lisent ensemble,
      // et une colonne de moins à faire tenir dans la largeur.
      cle: 'nom',
      entete: 'Application',
      largeur: '230px',
      tronque: true,
      valeur: (a) => a.nom,
      rendu: (a) => (
        <span className={propre.nomCellule}>
          <span className={propre.nomPrincipal} title={a.nom}>
            {a.nom}
          </span>
          {a.processus_metier !== null && (
            <span className={propre.nomMetier} title={a.processus_metier}>
              {a.processus_metier}
            </span>
          )}
        </span>
      ),
    },
    {
      cle: 'editeur',
      entete: 'Éditeur',
      largeur: '160px',
      valeur: (a) => a.editeur ?? '',
      rendu: (a) =>
        a.editeur !== null ? (
          <span
            className={local.typeBadge}
            style={{ background: couleurEditeur(a.editeur), color: 'var(--on-accent)' }}
            title={a.editeur}
          >
            <span className={propre.tronque}>{a.editeur}</span>
          </span>
        ) : (
          <span className={local.vide}>—</span>
        ),
    },
    {
      cle: 'hebergement',
      entete: 'Hébergement',
      largeur: '130px',
      valeur: (a) => a.hebergement ?? '',
      rendu: (a) => (
        <Marqueur
          valeur={a.hebergement}
          libelles={LIBELLE_HEBERGEMENT}
          icones={ICONE_HEBERGEMENT}
          couleurs={COULEUR_HEBERGEMENT}
        />
      ),
    },
    {
      cle: 'interfacage',
      entete: 'Interfaçage',
      largeur: '140px',
      valeur: (a) => a.interfacage ?? '',
      rendu: (a) => (
        <Marqueur
          valeur={a.interfacage}
          libelles={LIBELLE_INTERFACAGE}
          icones={ICONE_INTERFACAGE}
        />
      ),
    },
    {
      cle: 'administrateurs',
      entete: 'Administrateurs',
      largeur: '135px',
      valeur: (a) => a.administrateurs[0]?.nom ?? '',
      rendu: (a) => <Personnes liste={a.administrateurs} />,
    },
    {
      cle: 'administrateurs_secours',
      entete: 'Relais',
      largeur: '135px',
      valeur: (a) => a.administrateurs_secours[0]?.nom ?? '',
      rendu: (a) => <Personnes liste={a.administrateurs_secours} />,
    },
    {
      cle: 'statut',
      entete: 'Statut',
      largeur: '125px',
      valeur: (a) => a.statut,
      rendu: (a) => (
        <Marqueur
          valeur={a.statut}
          libelles={LIBELLE_STATUT}
          icones={ICONE_STATUT}
          couleurs={COULEUR_STATUT}
        />
      ),
    },
  ];

  const vue = VUES.find((v) => v.statut === (f.statut ?? null))?.cle ?? 'tous';
  const filtreActif = Boolean(
    f.q || f.editeur_id || f.hebergement || f.interfacage || f.administrateur,
  );

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Applications</h1>
          <p className={styles.sous}>
            Inventaire applicatif : ce qui tourne, de qui l'on dépend, et qui en répond.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/applications" />
          {estAdmin && (
            <Button onClick={() => setModale(true)}>
              <Plus size={16} />
              Nouvelle application
            </Button>
          )}
        </div>
      </header>

      {stats !== null && (
        <div className={local.compteurs}>
          <span className={local.compteur}>
            <b>{stats.total}</b>
            <span>Total</span>
          </span>
          <span className={local.compteur}>
            <b>{stats.actives}</b>
            <span>En service</span>
          </span>
          <span className={local.compteur}>
            <b>{stats.retirees}</b>
            <span>Arrêtées</span>
          </span>
          <span className={local.compteur}>
            <b>{stats.internes}</b>
            <span>Hébergées chez nous</span>
          </span>
          <span className={local.compteur}>
            <b>{stats.externes}</b>
            <span>Hébergées chez un tiers</span>
          </span>
        </div>
      )}

      {/* Les trous de suivi, cliquables : c'est de là que part le travail de mise à jour.
          Une application sans responsable, ou sans relais, est un risque — pas un détail. */}
      {stats !== null && (
        <div className={local.compteurs}>
          <button
            type="button"
            className={
              f.administrateur === SANS_ADMINISTRATEUR
                ? local.compteurActif
                : stats.sans_administrateur > 0
                  ? local.compteurAlerteClic
                  : local.compteurClic
            }
            onClick={() => {
              setPage(1);
              setF({
                ...f,
                administrateur:
                  f.administrateur === SANS_ADMINISTRATEUR ? null : SANS_ADMINISTRATEUR,
              });
            }}
            title="Aucun administrateur désigné : plus personne n'en répond"
          >
            <b
              style={{
                color:
                  stats.sans_administrateur > 0 ? 'var(--status-danger)' : 'var(--text-muted)',
              }}
            >
              {stats.sans_administrateur}
            </b>
            <span>Sans administrateur</span>
          </button>
          <span className={local.compteur} title="Un seul administrateur, aucun relais désigné">
            <b style={{ color: stats.sans_secours > 0 ? 'var(--status-warn)' : 'var(--text-muted)' }}>
              {stats.sans_secours}
            </b>
            <span>Sans relais</span>
          </span>
          <span className={local.compteur}>
            <b>{stats.interfacees}</b>
            <span>Interfacées</span>
          </span>
        </div>
      )}

      <div className={filtres.barre}>
        <label className={filtres.recherche}>
          <Search size={16} />
          <input
            value={f.q ?? ''}
            onChange={(e) => {
              setPage(1);
              setF({ ...f, q: e.target.value });
            }}
            placeholder="Rechercher (nom, éditeur, métier, administrateur)…"
          />
        </label>

        <div className={filtres.segments}>
          {VUES.map((v) => (
            <button
              key={v.cle}
              type="button"
              className={vue === v.cle ? filtres.segmentOn : filtres.segment}
              onClick={() => {
                setPage(1);
                setF({ ...f, statut: v.statut });
              }}
            >
              {v.libelle}
            </button>
          ))}
        </div>

        <div className={filtres.filtre}>
          <SelecteurListe
            options={editeurs.map((e) => ({ valeur: e.id, libelle: e.libelle }))}
            valeur={f.editeur_id ?? null}
            onChange={(v) => {
              setPage(1);
              setF({ ...f, editeur_id: v });
            }}
            placeholder="Tous les éditeurs"
            permettreVide
            libelleVide="Tous les éditeurs"
          />
        </div>
        <div className={filtres.filtre}>
          <SelecteurListe
            options={HEBERGEMENTS.map((h) => ({ valeur: h.valeur, libelle: h.libelle }))}
            valeur={f.hebergement ?? null}
            onChange={(v) => {
              setPage(1);
              setF({ ...f, hebergement: v });
            }}
            placeholder="Tous hébergements"
            permettreVide
            libelleVide="Tous hébergements"
            couleurs={COULEUR_HEBERGEMENT}
            icones={ICONE_HEBERGEMENT}
          />
        </div>
        <div className={filtres.filtre}>
          <SelecteurListe
            options={INTERFACAGES.map((i) => ({ valeur: i.valeur, libelle: i.libelle }))}
            valeur={f.interfacage ?? null}
            onChange={(v) => {
              setPage(1);
              setF({ ...f, interfacage: v });
            }}
            placeholder="Interfaçage"
            permettreVide
            libelleVide="Tout interfaçage"
            icones={ICONE_INTERFACAGE}
          />
        </div>
        {filtreActif && (
          <button
            type="button"
            className={filtres.reset}
            onClick={() => {
              setPage(1);
              setF({ statut: f.statut ?? null });
            }}
          >
            <X size={14} />
            Réinitialiser
          </button>
        )}
      </div>

      <Table
        colonnes={colonnes}
        lignes={items}
        cleLigne={(a) => a.id}
        chargement={chargement}
        vide="Aucune application pour le moment."
        onLigne={(a) => setFicheId(a.id)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <FicheApplication
        id={ficheId}
        editeurs={editeurs}
        onFermer={() => setFicheId(null)}
        onChange={() => {
          void charger();
          chargerStats();
        }}
        onEditeurs={chargerEditeurs}
      />

      <ModaleApplication
        ouverte={modale}
        gerable={estAdmin}
        editeurs={editeurs}
        onEditeurs={chargerEditeurs}
        onFermer={() => setModale(false)}
        onCree={(cree) => {
          setModale(false);
          notifier(`${cree.nom} ajoutée à l'inventaire applicatif.`, 'succes');
          void charger();
          chargerStats();
        }}
        onErreur={(e) =>
          notifier(e instanceof ErreurApi ? e.message : 'Création impossible.', 'erreur')
        }
      />
    </div>
  );
}
