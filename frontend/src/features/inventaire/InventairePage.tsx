import { useCallback, useEffect, useState } from 'react';
import { Plus, Search, X } from 'lucide-react';
import { Button, Modale, Table, useToast, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { SelecteurListe } from '@/common/SelecteurListe';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import { useFicheUrl } from '@/common/useFicheUrl';
import { useAuth } from '@/lib/auth';
import { ErreurApi } from '@/lib/api';
import styles from '@/features/incidents/IncidentsPage.module.css';
import filtres from '@/common/FiltreTickets.module.css';
import { FicheEquipement } from './FicheEquipement';
import { ModaleEquipement } from './ModaleEquipement';
import local from './Inventaire.module.css';
import {
  CONSTATS,
  inventaireApi,
  LIBELLE_ETAT,
  type Equipement,
  type EtatConstat,
  type FiltresInventaire,
  type ReferentielItem,
  type StatsInventaire,
} from './inventaireApi';
import { api } from '@/lib/api';

function jourLong(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

/** Ce que dit le dernier contrôle : l'état, sa date, son auteur et son motif. */
function infobulleConstat(e: Equipement): string | undefined {
  if (e.etat_constate === null) return 'Jamais contrôlé sur le terrain';
  const morceaux = [
    `${LIBELLE_ETAT[e.etat_constate] ?? e.etat_constate} — ${jourLong(e.constate_le)}`,
  ];
  if (e.constate_par !== null) morceaux.push(`par ${e.constate_par}`);
  if (e.constat_motif !== null) morceaux.push(`« ${e.constat_motif} »`);
  return morceaux.join(' · ');
}

/** Montant en francs CFA, séparé par milliers. Sans décimales : elles n'apportent rien ici. */
export function formaterMontant(valeur: number | null): string {
  if (valeur === null) return '—';
  return Math.round(valeur).toLocaleString('fr-FR');
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
  const [agents, setAgents] = useState<Agent[]>([]);
  const [f, setF] = useState<FiltresInventaire>({ actif: true });
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const { moi } = useAuth();
  const { notifier } = useToast();
  const estAdmin = moi?.profil === 'ADMIN';

  // --- Contrôle de terrain : le constat se pose directement sur la ligne du matériel. ---
  // Ce qu'on a vu se justifie : on demande le motif avant d'écrire. Retirer un constat posé
  // par erreur ne se justifie pas — c'est un effacement, pas une observation.
  const [motif, setMotif] = useState<{ equipement: Equipement; etat: EtatConstat } | null>(null);
  const [texteMotif, setTexteMotif] = useState('');
  const [envoiConstat, setEnvoiConstat] = useState(false);

  const erreurConstat = (e: unknown, repli: string): void =>
    notifier(e instanceof ErreurApi ? e.message : repli, 'erreur');

  const demanderConstat = async (equipement: Equipement, etat: EtatConstat): Promise<void> => {
    // Recliquer le constat déjà posé l'efface : le matériel redevient « à contrôler ».
    if (equipement.etat_constate === etat) {
      try {
        await inventaireApi.retirerConstat(equipement.id);
        await charger();
        chargerStats();
      } catch (err) {
        erreurConstat(err, 'Constat impossible.');
      }
      return;
    }
    setTexteMotif('');
    setMotif({ equipement, etat });
  };

  const enregistrerConstat = async (): Promise<void> => {
    if (motif === null) return;
    setEnvoiConstat(true);
    try {
      await inventaireApi.constater(motif.equipement.id, motif.etat, texteMotif);
      setMotif(null);
      await charger();
      chargerStats();
    } catch (err) {
      erreurConstat(err, 'Constat impossible.');
    } finally {
      setEnvoiConstat(false);
    }
  };

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
  useEffect(() => {
    void chargerAgents().then(setAgents);
  }, []);

  const colonnes: Colonne<Equipement>[] = [
    {
      cle: 'code_immo',
      entete: 'Code immo',
      largeur: '130px',
      valeur: (e) => e.code_immo ?? '',
      // Le même style « gravé sur le matériel » que la fiche : monospace sur pastille.
      rendu: (e) =>
        e.code_immo !== null ? (
          <span className={local.technique}>{e.code_immo}</span>
        ) : (
          <span className={local.vide}>—</span>
        ),
    },
    {
      cle: 'designation',
      entete: 'Désignation',
      tronque: true,
      valeur: (e) => e.designation,
      rendu: (e) => <strong title={e.designation}>{e.designation}</strong>,
    },
    // Le modèle, la valeur d'acquisition et la date d'achat restent dans la fiche : la liste
    // garde l'essentiel — identifier, localiser, savoir ce que ça vaut encore.
    {
      cle: 'emplacement',
      entete: 'Emplacement',
      valeur: (e) => e.emplacement ?? '',
      rendu: (e) =>
        e.emplacement !== null ? (
          <span className={local.lieu} title={e.emplacement}>
            {e.emplacement}
          </span>
        ) : (
          <span className={local.vide}>—</span>
        ),
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
      cle: 'valeur_nette',
      entete: 'Valeur nette',
      valeur: (e) => e.valeur_nette ?? 0,
      // La colonne dit ce que le chiffre veut dire : verte tant que le bien pèse au bilan,
      // ambre sous le quart restant, « Amorti » quand il ne vaut plus rien.
      rendu: (e) => {
        if (e.valeur_nette === null) return <span className={local.vide}>—</span>;
        const part =
          e.valeur_acquisition !== null && e.valeur_acquisition > 0
            ? e.valeur_nette / e.valeur_acquisition
            : null;
        const classe =
          e.valeur_nette === 0
            ? local.vncNulle
            : part !== null && part < 0.25
              ? local.vncFaible
              : local.vncSaine;
        return <span className={`tabular ${classe}`}>{formaterMontant(e.valeur_nette)}</span>;
      },
    },
    {
      cle: 'amorti_pct',
      entete: 'Amorti',
      largeur: '130px',
      valeur: (e) => e.amorti_pct ?? 0,
      rendu: (e) => <Amortissement pct={e.amorti_pct} />,
    },
  ];

  // Le contrôle de terrain, sur la ligne du matériel : trois boutons, celui qui est posé
  // porte sa couleur. L'infobulle rappelle qui a constaté, quand, et sur quoi il se fondait.
  colonnes.push({
    cle: 'constat',
    entete: 'Constat',
    largeur: '235px',
    valeur: (e) => e.etat_constate ?? '',
    rendu: (e) => (
      <span className={local.constats} title={infobulleConstat(e)}>
        {CONSTATS.map(({ etat, libelle, couleur }) => {
          const pose = e.etat_constate === etat;
          return (
            <button
              key={etat}
              type="button"
              className={pose ? local.constatOn : local.constat}
              // La couleur sémantique est portée en variable : posée elle remplit le bouton,
              // sinon elle s'annonce au survol.
              style={
                {
                  '--constat': couleur,
                  ...(pose ? { background: couleur, borderColor: couleur } : {}),
                } as React.CSSProperties
              }
              onClick={(ev) => {
                // Sans quoi le clic ouvrirait la fiche de la ligne.
                ev.stopPropagation();
                void demanderConstat(e, etat);
              }}
            >
              {libelle}
            </button>
          );
        })}
      </span>
    ),
  });

  const vue = VUES.find((v) => v.actif === (f.actif ?? null))?.cle ?? 'tous';
  const filtreActif = Boolean(
    f.q || f.emplacement_id || f.departement_id || f.detenteur_id || f.etat_constate ||
      f.a_controler,
  );

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

      {/* L'état constaté du parc, et surtout ce qu'il reste à contrôler : cliquer sur un
          compteur filtre la liste, c'est de là que part le travail de terrain. */}
      {stats !== null && (
        <div className={local.compteurs}>
          {(
            [
              { cle: 'BON', libelle: 'Bons', valeur: stats.bons, couleur: 'var(--status-ok)' },
              {
                cle: 'REBUT',
                libelle: 'Rebuts',
                valeur: stats.rebuts,
                couleur: 'var(--status-warn)',
              },
              {
                cle: 'CASSE',
                libelle: 'Cassés',
                valeur: stats.casses,
                couleur: 'var(--status-danger)',
              },
            ] as const
          ).map((c) => (
            <button
              key={c.cle}
              type="button"
              className={f.etat_constate === c.cle ? local.compteurActif : local.compteurClic}
              onClick={() => {
                setPage(1);
                setF({
                  ...f,
                  actif: true,
                  a_controler: false,
                  etat_constate: f.etat_constate === c.cle ? null : c.cle,
                });
              }}
            >
              <b style={{ color: c.couleur }}>{c.valeur}</b>
              <span>{c.libelle}</span>
            </button>
          ))}
          <button
            type="button"
            className={
              f.a_controler === true
                ? local.compteurActif
                : stats.a_controler > 0
                  ? local.compteurAlerteClic
                  : local.compteurClic
            }
            onClick={() => {
              setPage(1);
              setF({
                ...f,
                actif: true,
                etat_constate: null,
                a_controler: f.a_controler !== true,
              });
            }}
            title="Jamais contrôlés, ou pas depuis plus d'un an"
          >
            <b style={{ color: stats.a_controler > 0 ? 'var(--status-warn)' : 'var(--text-muted)' }}>
              {stats.a_controler}
            </b>
            <span>À contrôler</span>
          </button>
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
        {/* « Quel matériel détient X ? » — la question qu'on pose le plus souvent au parc.
            « Non attribué » en tête : ce sont les rattachements qui restent à faire. */}
        <div className={filtres.filtre}>
          <SelecteurListe
            options={[
              { valeur: 'AUCUN', libelle: 'Non attribué', special: true },
              ...agents.map((a) => ({ valeur: a.id, libelle: a.nom })),
            ]}
            valeur={f.detenteur_id ?? null}
            onChange={(v) => {
              setPage(1);
              setF({ ...f, detenteur_id: v });
            }}
            placeholder="Tous les détenteurs"
            permettreVide
            libelleVide="Tous les détenteurs"
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
        onConstat={(equipement, etat) => void demanderConstat(equipement, etat)}
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

      {/* Le motif du constat : ce qu'on a vu, en une phrase. Il se relira dans un an. */}
      <Modale
        ouverte={motif !== null}
        onFermer={() => setMotif(null)}
        titre={
          motif !== null
            ? `Constat « ${CONSTATS.find((c) => c.etat === motif.etat)?.libelle ?? ''} »`
            : 'Constat'
        }
        pied={
          <>
            <Button variante="secondaire" onClick={() => setMotif(null)}>
              Annuler
            </Button>
            <Button
              onClick={() => void enregistrerConstat()}
              disabled={envoiConstat || texteMotif.trim().length < 3}
            >
              {envoiConstat ? 'Enregistrement…' : 'Enregistrer le constat'}
            </Button>
          </>
        }
      >
        {motif !== null && (
          <>
            <p className={local.noteModale}>
              {motif.equipement.designation}
              {motif.equipement.code_immo !== null ? ` · ${motif.equipement.code_immo}` : ''}
            </p>
            <label className={styles.champ}>
              <span>Qu'avez-vous constaté ?</span>
              <input
                autoFocus
                value={texteMotif}
                onChange={(ev) => setTexteMotif(ev.target.value)}
                onKeyDown={(ev) => {
                  if (ev.key === 'Enter' && texteMotif.trim().length >= 3) {
                    void enregistrerConstat();
                  }
                }}
                placeholder="Ex. écran fêlé, retrouvé en réserve, ne démarre plus…"
                maxLength={200}
              />
            </label>
          </>
        )}
      </Modale>

    </div>
  );
}
