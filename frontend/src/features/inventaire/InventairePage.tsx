import { useCallback, useEffect, useState } from 'react';
import { Plus, Search, X } from 'lucide-react';
import { Button, Table, useToast, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { SelecteurListe } from '@/common/SelecteurListe';
import { useFicheUrl } from '@/common/useFicheUrl';
import { useAuth } from '@/lib/auth';
import { ErreurApi } from '@/lib/api';
import styles from '@/features/incidents/IncidentsPage.module.css';
import filtres from '@/common/FiltreTickets.module.css';
import { FicheEquipement } from './FicheEquipement';
import { ModaleEquipement } from './ModaleEquipement';
import local from './Inventaire.module.css';
import {
  inventaireApi,
  type Equipement,
  type FiltresInventaire,
  type ReferentielItem,
  type StatsInventaire,
} from './inventaireApi';
import { api } from '@/lib/api';

/** Montant en francs CFA, séparé par milliers. Sans décimales : elles n'apportent rien ici. */
export function formaterMontant(valeur: number | null): string {
  if (valeur === null) return '—';
  return Math.round(valeur).toLocaleString('fr-FR');
}

function formaterDate(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Part amortie : barre discrète, rouge quand le matériel ne vaut plus rien au bilan. */
function Amortissement({ pct }: { pct: number | null }): JSX.Element {
  if (pct === null) return <span className={local.vide}>—</span>;
  const couleur = pct >= 100 ? 'var(--status-danger)' : 'var(--secondary)';
  return (
    <span className={local.amorti} title={`${pct} % amorti`}>
      <span className={local.amortiPiste}>
        <span
          className={local.amortiPlein}
          style={{ width: `${Math.min(100, pct)}%`, background: couleur }}
        />
      </span>
      <span className={local.amortiTexte}>{pct} %</span>
    </span>
  );
}

const VUES: { cle: string; libelle: string; actif: boolean | null }[] = [
  { cle: 'service', libelle: 'En service', actif: true },
  { cle: 'sortis', libelle: 'Sortis du parc', actif: false },
  { cle: 'tous', libelle: 'Tous', actif: null },
];

export function InventairePage(): JSX.Element {
  const [items, setItems] = useState<Equipement[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [stats, setStats] = useState<StatsInventaire | null>(null);
  const [emplacements, setEmplacements] = useState<ReferentielItem[]>([]);
  const [departements, setDepartements] = useState<ReferentielItem[]>([]);
  const [f, setF] = useState<FiltresInventaire>({ actif: true });
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const { moi } = useAuth();
  const { notifier } = useToast();
  const estAdmin = moi?.profil === 'ADMIN';

  const charger = useCallback(async (): Promise<void> => {
    setChargement(true);
    try {
      const data = await inventaireApi.lister(page, f);
      setItems(data.elements);
      setTotal(data.total);
    } finally {
      setChargement(false);
    }
  }, [page, f]);

  const chargerStats = useCallback((): void => {
    void api
      .get<StatsInventaire>('/inventaire/stats')
      .then(setStats)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void charger();
  }, [charger]);
  useEffect(() => chargerStats(), [chargerStats, total]);
  const chargerReferentiels = useCallback((): void => {
    void inventaireApi.referentiel('emplacements').then(setEmplacements);
    void inventaireApi.referentiel('departements').then(setDepartements);
  }, []);
  useEffect(() => chargerReferentiels(), [chargerReferentiels]);

  const colonnes: Colonne<Equipement>[] = [
    {
      cle: 'code_immo',
      entete: 'Code immo',
      largeur: '130px',
      valeur: (e) => e.code_immo ?? '',
      rendu: (e) => <span className="tabular">{e.code_immo ?? '—'}</span>,
    },
    {
      cle: 'designation',
      entete: 'Désignation',
      tronque: true,
      valeur: (e) => e.designation,
      rendu: (e) => <strong title={e.designation}>{e.designation}</strong>,
    },
    {
      cle: 'modele',
      entete: 'Modèle',
      valeur: (e) => e.modele ?? '',
      rendu: (e) => e.modele ?? '—',
    },
    {
      cle: 'emplacement',
      entete: 'Emplacement',
      valeur: (e) => e.emplacement ?? '',
      rendu: (e) => e.emplacement ?? '—',
    },
    {
      cle: 'detenteur',
      entete: 'Détenteur',
      valeur: (e) => e.detenteur ?? e.matricule ?? '',
      rendu: (e) =>
        // Sans compte rapproché, on montre le matricule brut : il reste un rattachement à faire.
        e.detenteur ?? (e.matricule ? <span className={local.brut}>{e.matricule}</span> : '—'),
    },
    {
      cle: 'valeur_acquisition',
      entete: "Valeur d'acquisition",
      valeur: (e) => e.valeur_acquisition ?? 0,
      rendu: (e) => <span className="tabular">{formaterMontant(e.valeur_acquisition)}</span>,
    },
    {
      cle: 'valeur_nette',
      entete: 'Valeur nette',
      valeur: (e) => e.valeur_nette ?? 0,
      rendu: (e) => <span className="tabular">{formaterMontant(e.valeur_nette)}</span>,
    },
    {
      cle: 'amorti_pct',
      entete: 'Amorti',
      largeur: '130px',
      valeur: (e) => e.amorti_pct ?? 0,
      rendu: (e) => <Amortissement pct={e.amorti_pct} />,
    },
    {
      cle: 'date_acquisition',
      entete: 'Acquis le',
      valeur: (e) => e.date_acquisition ?? '',
      rendu: (e) => formaterDate(e.date_acquisition),
    },
  ];

  const vue = VUES.find((v) => v.actif === (f.actif ?? null))?.cle ?? 'tous';
  const filtreActif = Boolean(f.q || f.emplacement_id || f.departement_id);

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Inventaire</h1>
          <p className={styles.sous}>Parc matériel de la DSI et valeur des immobilisations.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/inventaire" />
          {estAdmin && (
            <Button onClick={() => setModale(true)}>
              <Plus size={16} />
              Nouvel équipement
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
            <b>{stats.en_service}</b>
            <span>En service</span>
          </span>
          <span className={local.compteur}>
            <b>{stats.sortis}</b>
            <span>Sortis du parc</span>
          </span>
          {/* Sans détenteur : ce sont les rattachements qu'il reste à faire. */}
          {stats.sans_detenteur > 0 && (
            <span className={local.compteurAlerte}>
              <b>{stats.sans_detenteur}</b>
              <span>Sans détenteur</span>
            </span>
          )}
          <span className={local.compteurValeur}>
            <b>{formaterMontant(stats.valeur_acquisition)}</b>
            <span>Valeur du parc (FCFA)</span>
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
            placeholder="Rechercher (code immo, n° série, modèle, détenteur)…"
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
            options={emplacements.map((e) => ({ valeur: e.id, libelle: e.libelle }))}
            valeur={f.emplacement_id ?? null}
            onChange={(v) => {
              setPage(1);
              setF({ ...f, emplacement_id: v });
            }}
            placeholder="Tous les emplacements"
            permettreVide
            libelleVide="Tous les emplacements"
          />
        </div>
        <div className={filtres.filtre}>
          <SelecteurListe
            options={departements.map((d) => ({ valeur: d.id, libelle: d.libelle }))}
            valeur={f.departement_id ?? null}
            onChange={(v) => {
              setPage(1);
              setF({ ...f, departement_id: v });
            }}
            placeholder="Tous les départements"
            permettreVide
            libelleVide="Tous les départements"
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
        cleLigne={(e) => e.id}
        chargement={chargement}
        vide="Aucun équipement pour le moment."
        onLigne={(e) => setFicheId(e.id)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <FicheEquipement
        id={ficheId}
        emplacements={emplacements}
        departements={departements}
        onFermer={() => setFicheId(null)}
        onChange={() => {
          void charger();
          chargerStats();
        }}
        onReferentiels={chargerReferentiels}
      />

      <ModaleEquipement
        ouverte={modale}
        emplacements={emplacements}
        departements={departements}
        gerable={estAdmin}
        onReferentiels={chargerReferentiels}
        onFermer={() => setModale(false)}
        onCree={(cree) => {
          setModale(false);
          notifier(`${cree.designation} ajouté au parc.`, 'succes');
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
