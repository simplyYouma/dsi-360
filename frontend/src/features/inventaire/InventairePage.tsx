import { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck, Plus, Search, X } from 'lucide-react';
import {
  Button,
  Modale,
  StatusBadge,
  Table,
  useToast,
  type Colonne,
} from '@/design-system/primitives';
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
  campagnesApi,
  CONSTATS,
  COULEUR_ETAT,
  inventaireApi,
  type CampagneInventaire,
  type Equipement,
  type EtatConstat,
  type FiltresInventaire,
  type ReferentielItem,
  type StatsInventaire,
} from './inventaireApi';
import { api } from '@/lib/api';

const LIBELLE_ETAT: Record<string, string> = {
  BON: 'Bon',
  REBUT: 'Rebut',
  CASSE: 'Cassé',
  NON_RETROUVE: 'Non retrouvé',
};

function jourLong(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
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

  // --- Campagne d'inventaire : le recensement se fait ici, dans la liste du parc. ---
  const [campagnes, setCampagnes] = useState<CampagneInventaire[]>([]);
  const [parcActif, setParcActif] = useState(0);
  const [campagneId, setCampagneId] = useState<string | null>(null);
  const [constats, setConstats] = useState<Record<string, string>>({});
  const [ouvertureVisible, setOuvertureVisible] = useState(false);
  const [libelleCampagne, setLibelleCampagne] = useState('');
  const [clotureVisible, setClotureVisible] = useState(false);
  const [envoiCampagne, setEnvoiCampagne] = useState(false);

  const chargerCampagnes = useCallback(async (): Promise<void> => {
    const r = await campagnesApi.lister();
    setCampagnes(r.campagnes);
    setParcActif(r.parc_actif);
    // La campagne en cours s'affiche d'elle-même ; les closes restent au sélecteur.
    setCampagneId((id) => id ?? r.campagnes.find((c) => c.statut === 'OUVERTE')?.id ?? null);
  }, []);
  useEffect(() => {
    void chargerCampagnes().catch(() => undefined);
  }, [chargerCampagnes]);

  const campagne = campagnes.find((c) => c.id === campagneId) ?? null;
  const enRecensement = campagne?.statut === 'OUVERTE';

  // Les constats de la campagne affichée, par équipement — la colonne de la liste s'en nourrit.
  useEffect(() => {
    if (campagneId === null) {
      setConstats({});
      return;
    }
    void campagnesApi
      .recensement(campagneId)
      .then((lignes) =>
        setConstats(
          Object.fromEntries(
            lignes.filter((l) => l.etat !== null).map((l) => [l.id, l.etat as string]),
          ),
        ),
      )
      .catch(() => setConstats({}));
  }, [campagneId, campagnes]);

  const erreurCampagne = (e: unknown, repli: string): void =>
    notifier(e instanceof ErreurApi ? e.message : repli, 'erreur');

  const constater = async (equipementId: string, etat: EtatConstat): Promise<void> => {
    if (campagne === null || !enRecensement) return;
    try {
      // Recliquer le même constat l'annule : l'équipement redevient « à recenser ».
      if (constats[equipementId] === etat)
        await campagnesApi.retirerConstat(campagne.id, equipementId);
      else await campagnesApi.constater(campagne.id, equipementId, etat);
      await chargerCampagnes();
    } catch (err) {
      erreurCampagne(err, 'Constat impossible.');
    }
  };

  const ouvrirCampagne = async (): Promise<void> => {
    setEnvoiCampagne(true);
    try {
      const creee = await campagnesApi.ouvrir(libelleCampagne);
      setOuvertureVisible(false);
      setLibelleCampagne('');
      setCampagneId(creee.id);
      await chargerCampagnes();
      notifier(`Campagne « ${creee.libelle} » ouverte : le recensement peut commencer.`, 'succes');
    } catch (e) {
      erreurCampagne(e, 'Ouverture impossible.');
    } finally {
      setEnvoiCampagne(false);
    }
  };

  const cloturerCampagne = async (): Promise<void> => {
    if (campagne === null) return;
    setEnvoiCampagne(true);
    try {
      const r = await campagnesApi.cloturer(campagne.id);
      setClotureVisible(false);
      await chargerCampagnes();
      notifier(
        r.non_retrouves === 0
          ? 'Campagne clôturée : tout le parc a été retrouvé.'
          : `Campagne clôturée : ${r.non_retrouves} équipement(s) non retrouvé(s).`,
        r.non_retrouves === 0 ? 'succes' : 'erreur',
      );
    } catch (e) {
      erreurCampagne(e, 'Clôture impossible.');
    } finally {
      setEnvoiCampagne(false);
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

  // La colonne de constat n'existe que lorsqu'une campagne est affichée : pendant le
  // recensement on clique, sur une campagne close on relit.
  if (campagne !== null) {
    colonnes.push({
      cle: 'constat',
      entete: `Constat ${new Date(campagne.ouverte_le).getFullYear()}`,
      largeur: '235px',
      valeur: (e) => constats[e.id] ?? '',
      rendu: (e) => {
        const pose = constats[e.id];
        if (enRecensement) {
          return (
            <span className={local.constats}>
              {CONSTATS.map(({ etat, libelle, couleur }) => (
                <button
                  key={etat}
                  type="button"
                  className={pose === etat ? local.constatOn : local.constat}
                  // La couleur sémantique est portée en variable : posé elle remplit le
                  // bouton, sinon elle s'annonce au survol.
                  style={
                    {
                      '--constat': couleur,
                      ...(pose === etat ? { background: couleur, borderColor: couleur } : {}),
                    } as React.CSSProperties
                  }
                  onClick={(ev) => {
                    // Sans quoi le clic ouvrirait la fiche de la ligne.
                    ev.stopPropagation();
                    void constater(e.id, etat);
                  }}
                >
                  {libelle}
                </button>
              ))}
            </span>
          );
        }
        if (pose === undefined) return <span className={local.vide}>—</span>;
        // Campagne close : le verdict remplit la cellule, dans sa couleur.
        return (
          <span
            className={local.constatFinal}
            style={{ '--constat': COULEUR_ETAT[pose] ?? 'var(--text-muted)' } as React.CSSProperties}
          >
            {LIBELLE_ETAT[pose] ?? pose}
          </span>
        );
      },
    });
  }

  const vue = VUES.find((v) => v.actif === (f.actif ?? null))?.cle ?? 'tous';
  const filtreActif = Boolean(f.q || f.emplacement_id || f.departement_id || f.detenteur_id);

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Inventaire</h1>
          <p className={styles.sous}>Parc matériel de la DSI et valeur des immobilisations.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          {estAdmin && !campagnes.some((c) => c.statut === 'OUVERTE') && (
            <Button variante="secondaire" onClick={() => setOuvertureVisible(true)}>
              <ClipboardCheck size={16} />
              Ouvrir une campagne
            </Button>
          )}
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

      {/* La campagne d'inventaire vit dans la même liste que le parc : on choisit laquelle
          regarder, et la colonne « Constat » suit. Pas de page à part pour cliquer trois fois. */}
      {campagnes.length > 0 && (
        <div className={local.bandeauCampagne}>
          <div className={local.campagneTete}>
            <span className={local.campagneSelecteur}>
              <SelecteurListe
                options={campagnes.map((c) => ({ valeur: c.id, libelle: c.libelle }))}
                valeur={campagneId}
                onChange={setCampagneId}
                placeholder="Voir une campagne"
                permettreVide
                libelleVide="Aucune campagne affichée"
              />
            </span>
            {campagne !== null && (
              <>
                {campagne.statut === 'OUVERTE' ? (
                  <StatusBadge statut="ok">En cours</StatusBadge>
                ) : (
                  <StatusBadge couleur="var(--text-muted)">Clôturée</StatusBadge>
                )}
                <span className={local.carteQuand}>
                  {campagne.statut === 'OUVERTE'
                    ? `Ouverte le ${jourLong(campagne.ouverte_le)}`
                    : `Clôturée le ${jourLong(campagne.cloturee_le)}`}
                  {campagne.ouverte_par !== null ? ` · ${campagne.ouverte_par}` : ''}
                </span>
                {enRecensement && estAdmin && (
                  <Button
                    variante="secondaire"
                    className={local.btnCloture}
                    onClick={() => setClotureVisible(true)}
                  >
                    <ClipboardCheck size={15} />
                    Clôturer
                  </Button>
                )}
              </>
            )}
          </div>
          {campagne !== null && (
            <div className={local.compteurs}>
              {(() => {
                const denominateur =
                  campagne.statut === 'OUVERTE'
                    ? Math.max(parcActif, campagne.constates)
                    : campagne.constates;
                const pct =
                  denominateur === 0 ? 0 : Math.round((campagne.constates * 100) / denominateur);
                return (
                  <span className={local.compteurAvancee}>
                    <b>
                      {campagne.constates}
                      <em> / {denominateur}</em>
                    </b>
                    <span className={local.avanceePiste}>
                      <span className={local.avanceePlein} style={{ width: `${pct}%` }} />
                    </span>
                    <span>Recensés · {pct} %</span>
                  </span>
                );
              })()}
              <span className={local.compteur}>
                <b style={{ color: 'var(--status-ok)' }}>{campagne.bons}</b>
                <span>Bons</span>
              </span>
              <span className={local.compteur}>
                <b style={{ color: 'var(--status-warn)' }}>{campagne.rebuts}</b>
                <span>Rebuts</span>
              </span>
              <span className={local.compteur}>
                <b style={{ color: 'var(--status-danger)' }}>{campagne.casses}</b>
                <span>Cassés</span>
              </span>
              <span className={campagne.non_retrouves > 0 ? local.compteurAlerte : local.compteur}>
                <b
                  style={{
                    color:
                      campagne.non_retrouves > 0 ? 'var(--status-danger)' : 'var(--text-muted)',
                  }}
                >
                  {campagne.non_retrouves}
                </b>
                <span>Non retrouvés</span>
              </span>
            </div>
          )}
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
        {/* « Quel matériel détient X ? » — la question qu'on pose le plus souvent au parc. */}
        <div className={filtres.filtre}>
          <SelecteurListe
            options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
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
        recensement={
          enRecensement && campagne !== null && ficheId !== null
            ? {
                libelle: campagne.libelle,
                etat: constats[ficheId] ?? null,
                onConstat: (etat) => void constater(ficheId, etat),
              }
            : null
        }
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

      <Modale
        ouverte={ouvertureVisible}
        onFermer={() => setOuvertureVisible(false)}
        titre="Ouvrir une campagne d'inventaire"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setOuvertureVisible(false)}>
              Annuler
            </Button>
            <Button
              onClick={() => void ouvrirCampagne()}
              disabled={envoiCampagne || libelleCampagne.trim().length < 2}
            >
              {envoiCampagne ? 'Ouverture…' : 'Ouvrir'}
            </Button>
          </>
        }
      >
        <label className={styles.champ}>
          <span>Libellé</span>
          <input
            autoFocus
            value={libelleCampagne}
            onChange={(e) => setLibelleCampagne(e.target.value)}
            placeholder="Ex. Inventaire physique 2026"
          />
        </label>
        <p className={local.noteModale}>
          Une seule campagne peut être ouverte à la fois. La colonne « Constat » apparaît dans la
          liste : chaque agent du module y pose ce qu'il voit ; la clôture relèvera les non
          retrouvés.
        </p>
      </Modale>

      <Modale
        ouverte={clotureVisible}
        onFermer={() => setClotureVisible(false)}
        titre="Clôturer la campagne"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setClotureVisible(false)}>
              Annuler
            </Button>
            <Button onClick={() => void cloturerCampagne()} disabled={envoiCampagne}>
              {envoiCampagne ? 'Clôture…' : 'Clôturer'}
            </Button>
          </>
        }
      >
        <p className={local.noteModale}>
          {campagne !== null &&
            `${campagne.constates} équipement(s) recensé(s) sur ${Math.max(parcActif, campagne.constates)}. ` +
              `Les ${Math.max(0, parcActif - campagne.constates)} restants seront marqués « non retrouvés ». `}
          La clôture est définitive : les constats seront figés.
        </p>
      </Modale>
    </div>
  );
}
