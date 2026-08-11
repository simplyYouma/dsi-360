import { useCallback, useEffect, useState } from 'react';
import { Plus, Search, X } from 'lucide-react';
import { Button, Table, useToast, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { SelecteurListe } from '@/common/SelecteurListe';
import { useFicheUrl } from '@/common/useFicheUrl';
import { useAuth } from '@/lib/auth';
import { api, ErreurApi } from '@/lib/api';
import styles from '@/features/incidents/IncidentsPage.module.css';
import filtres from '@/common/FiltreTickets.module.css';
import local from '@/features/inventaire/Inventaire.module.css';
import { FicheApplication } from './FicheApplication';
import { ModaleApplication } from './ModaleApplication';
import {
  applicationsApi,
  COULEUR_HEBERGEMENT,
  COULEUR_STATUT,
  HEBERGEMENTS,
  INTERFACAGES,
  LIBELLE_HEBERGEMENT,
  LIBELLE_STATUT,
  SANS_ADMINISTRATEUR,
  STATUTS,
  type Application,
  type FiltresApplications,
  type ReferentielItem,
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

const VUES: { cle: string; libelle: string; actif: boolean | null }[] = [
  { cle: 'service', libelle: 'En service', actif: true },
  { cle: 'retirees', libelle: 'Retirées', actif: false },
  { cle: 'tous', libelle: 'Toutes', actif: null },
];

export function ApplicationsPage(): JSX.Element {
  const [items, setItems] = useState<Application[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [stats, setStats] = useState<StatsApplications | null>(null);
  const [editeurs, setEditeurs] = useState<ReferentielItem[]>([]);
  const [f, setF] = useState<FiltresApplications>({ actif: true });
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
      cle: 'nom',
      entete: 'Application',
      tronque: true,
      valeur: (a) => a.nom,
      rendu: (a) => <strong title={a.nom}>{a.nom}</strong>,
    },
    {
      cle: 'processus_metier',
      entete: 'Processus métier',
      tronque: true,
      valeur: (a) => a.processus_metier ?? '',
      rendu: (a) =>
        a.processus_metier !== null ? (
          <span title={a.processus_metier}>{a.processus_metier}</span>
        ) : (
          <span className={local.vide}>—</span>
        ),
    },
    {
      cle: 'editeur',
      entete: 'Éditeur',
      valeur: (a) => a.editeur ?? '',
      rendu: (a) =>
        a.editeur !== null ? (
          <span
            className={local.typeBadge}
            style={{ background: couleurEditeur(a.editeur), color: 'var(--on-accent)' }}
            title={a.editeur}
          >
            {a.editeur}
          </span>
        ) : (
          <span className={local.vide}>—</span>
        ),
    },
    {
      cle: 'hebergement',
      entete: 'Hébergement',
      largeur: '150px',
      valeur: (a) => a.hebergement ?? '',
      // La couleur porte le sens : ce qui est externe sort de nos murs.
      rendu: (a) =>
        a.hebergement !== null ? (
          <span style={{ color: COULEUR_HEBERGEMENT[a.hebergement] ?? 'var(--text)' }}>
            {LIBELLE_HEBERGEMENT[a.hebergement] ?? a.hebergement}
          </span>
        ) : (
          <span className={local.vide}>—</span>
        ),
    },
    {
      cle: 'administrateur',
      entete: 'Administrateur',
      valeur: (a) => a.administrateur ?? '',
      // Sans administrateur, plus personne ne répond de l'application : on ne le tait pas.
      rendu: (a) =>
        a.administrateur !== null ? (
          <span title={a.administrateur_secours ?? undefined}>{a.administrateur}</span>
        ) : (
          <span className={local.brut}>Personne</span>
        ),
    },
    {
      cle: 'statut',
      entete: 'Statut',
      largeur: '120px',
      valeur: (a) => a.statut,
      rendu: (a) => (
        <span style={{ color: COULEUR_STATUT[a.statut] ?? 'var(--text)' }}>
          {LIBELLE_STATUT[a.statut] ?? a.statut}
        </span>
      ),
    },
  ];

  const vue = VUES.find((v) => v.actif === (f.actif ?? null))?.cle ?? 'tous';
  const filtreActif = Boolean(
    f.q || f.editeur_id || f.hebergement || f.statut || f.interfacage || f.administrateur,
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
            <span>Retirées</span>
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
                actif: true,
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
                setF({ ...f, actif: v.actif });
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
          />
        </div>
        <div className={filtres.filtre}>
          <SelecteurListe
            options={STATUTS.map((s) => ({ valeur: s.valeur, libelle: s.libelle }))}
            valeur={f.statut ?? null}
            onChange={(v) => {
              setPage(1);
              setF({ ...f, statut: v });
            }}
            placeholder="Tous les statuts"
            permettreVide
            libelleVide="Tous les statuts"
            couleurs={COULEUR_STATUT}
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
          />
        </div>
        {filtreActif && (
          <button
            type="button"
            className={filtres.reset}
            onClick={() => {
              setPage(1);
              setF({ actif: f.actif ?? null });
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
