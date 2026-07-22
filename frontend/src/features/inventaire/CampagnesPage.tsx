import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ClipboardCheck, Plus, Search } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, useToast, type Colonne } from '@/design-system/primitives';
import { useAuth } from '@/lib/auth';
import { ErreurApi } from '@/lib/api';
import styles from '@/features/incidents/IncidentsPage.module.css';
import filtres from '@/common/FiltreTickets.module.css';
import local from './Inventaire.module.css';
import {
  campagnesApi,
  type CampagneInventaire,
  type EtatConstat,
  type LigneRecensement,
} from './inventaireApi';

const CONSTATS: { etat: EtatConstat; libelle: string; couleur: string }[] = [
  { etat: 'BON', libelle: 'Bon', couleur: 'var(--status-ok)' },
  { etat: 'REBUT', libelle: 'Rebut', couleur: 'var(--status-warn)' },
  { etat: 'CASSE', libelle: 'Cassé', couleur: 'var(--status-danger)' },
];

const LIBELLE_ETAT: Record<string, string> = {
  BON: 'Bon',
  REBUT: 'Rebut',
  CASSE: 'Cassé',
  NON_RETROUVE: 'Non retrouvé',
};

function jour(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

/** Avancement d'une campagne : recensés sur parc actif (ouverte) ou total constaté (clôturée). */
function Avancement({ c, parc }: { c: CampagneInventaire; parc: number }): JSX.Element {
  const denominateur = c.statut === 'OUVERTE' ? Math.max(parc, c.constates) : c.constates;
  const pct = denominateur === 0 ? 0 : Math.round((c.constates * 100) / denominateur);
  return (
    <div className={local.avancee}>
      <span className={local.avanceePiste}>
        <span className={local.avanceePlein} style={{ width: `${pct}%` }} />
      </span>
      <span className={local.avanceeTexte}>
        {c.statut === 'OUVERTE' ? `${c.constates} / ${denominateur} recensés` : `${c.constates} recensés`}
      </span>
    </div>
  );
}

/** Campagnes d'inventaire : recenser le parc, constater bon/rebut/cassé, clôturer.
 *  Les cartes se lisent côte à côte — c'est la comparaison d'une année sur l'autre. */
export function CampagnesPage(): JSX.Element {
  const [campagnes, setCampagnes] = useState<CampagneInventaire[]>([]);
  const [parc, setParc] = useState(0);
  const [active, setActive] = useState<string | null>(null);
  const [lignes, setLignes] = useState<LigneRecensement[]>([]);
  const [chargement, setChargement] = useState(true);
  const [q, setQ] = useState('');
  const [ouvertureVisible, setOuvertureVisible] = useState(false);
  const [libelle, setLibelle] = useState('');
  const [clotureVisible, setClotureVisible] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const navigate = useNavigate();
  const { moi } = useAuth();
  const { notifier } = useToast();
  const estAdmin = moi?.profil === 'ADMIN';

  const charger = useCallback(async (): Promise<void> => {
    const r = await campagnesApi.lister();
    setCampagnes(r.campagnes);
    setParc(r.parc_actif);
    // À l'arrivée, on se place sur la campagne en cours ; sinon la plus récente.
    setActive((a) => a ?? (r.campagnes.find((c) => c.statut === 'OUVERTE') ?? r.campagnes[0])?.id ?? null);
  }, []);
  useEffect(() => {
    void charger().finally(() => setChargement(false));
  }, [charger]);

  const chargerRecensement = useCallback(async (): Promise<void> => {
    if (active === null) return;
    setLignes(await campagnesApi.recensement(active));
  }, [active]);
  useEffect(() => {
    setLignes([]);
    void chargerRecensement();
  }, [chargerRecensement]);

  const campagne = campagnes.find((c) => c.id === active) ?? null;
  const ouverte = campagne?.statut === 'OUVERTE';

  const visibles = useMemo(() => {
    const terme = q.trim().toLowerCase();
    if (terme === '') return lignes;
    return lignes.filter((l) =>
      [l.designation, l.code_immo, l.numero_serie, l.emplacement, l.detenteur]
        .filter((v): v is string => v !== null)
        .some((v) => v.toLowerCase().includes(terme)),
    );
  }, [lignes, q]);

  const erreur = (e: unknown, repli: string): void =>
    notifier(e instanceof ErreurApi ? e.message : repli, 'erreur');

  const ouvrir = async (): Promise<void> => {
    setEnvoi(true);
    try {
      const creee = await campagnesApi.ouvrir(libelle);
      setOuvertureVisible(false);
      setLibelle('');
      setActive(creee.id);
      await charger();
      notifier(`Campagne « ${creee.libelle} » ouverte : le recensement peut commencer.`, 'succes');
    } catch (e) {
      erreur(e, 'Ouverture impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const constater = async (ligne: LigneRecensement, etat: EtatConstat): Promise<void> => {
    if (campagne === null) return;
    try {
      // Recliquer le même constat l'annule : l'équipement redevient « à recenser ».
      if (ligne.etat === etat) await campagnesApi.retirerConstat(campagne.id, ligne.id);
      else await campagnesApi.constater(campagne.id, ligne.id, etat);
      await Promise.all([chargerRecensement(), charger()]);
    } catch (e) {
      erreur(e, 'Constat impossible.');
    }
  };

  const cloturer = async (): Promise<void> => {
    if (campagne === null) return;
    setEnvoi(true);
    try {
      const r = await campagnesApi.cloturer(campagne.id);
      setClotureVisible(false);
      await Promise.all([charger(), chargerRecensement()]);
      notifier(
        r.non_retrouves === 0
          ? 'Campagne clôturée : tout le parc a été retrouvé.'
          : `Campagne clôturée : ${r.non_retrouves} équipement(s) non retrouvé(s).`,
        r.non_retrouves === 0 ? 'succes' : 'erreur',
      );
    } catch (e) {
      erreur(e, 'Clôture impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const colonnes: Colonne<LigneRecensement>[] = [
    {
      cle: 'code_immo',
      entete: 'Code immo',
      largeur: '120px',
      valeur: (l) => l.code_immo ?? '',
      rendu: (l) => <span className="tabular">{l.code_immo ?? '—'}</span>,
    },
    {
      cle: 'designation',
      entete: 'Désignation',
      tronque: true,
      valeur: (l) => l.designation,
      rendu: (l) => <strong title={l.designation}>{l.designation}</strong>,
    },
    {
      cle: 'emplacement',
      entete: 'Emplacement',
      valeur: (l) => l.emplacement ?? '',
      rendu: (l) => l.emplacement ?? '—',
    },
    {
      cle: 'detenteur',
      entete: 'Détenteur',
      valeur: (l) => l.detenteur ?? '',
      rendu: (l) => l.detenteur ?? '—',
    },
    {
      cle: 'etat',
      entete: 'Constat',
      largeur: '260px',
      valeur: (l) => l.etat ?? '',
      rendu: (l) =>
        ouverte ? (
          <span className={local.constats}>
            {CONSTATS.map(({ etat, libelle: lib, couleur }) => (
              <button
                key={etat}
                type="button"
                className={l.etat === etat ? local.constatOn : local.constat}
                style={l.etat === etat ? { background: couleur, borderColor: couleur } : undefined}
                onClick={(e) => {
                  e.stopPropagation();
                  void constater(l, etat);
                }}
                title={l.constate_par !== null ? `Constaté par ${l.constate_par}` : undefined}
              >
                {lib}
              </button>
            ))}
          </span>
        ) : l.etat !== null ? (
          <StatusBadge
            statut={l.etat === 'BON' ? 'ok' : 'danger'}
          >
            {LIBELLE_ETAT[l.etat] ?? l.etat}
          </StatusBadge>
        ) : (
          <span className={local.vide}>—</span>
        ),
    },
  ];

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Campagnes d'inventaire</h1>
          <p className={styles.sous}>
            Recenser le parc, constater l'état, relever les non retrouvés à la clôture.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <Button variante="secondaire" onClick={() => navigate('/inventaire')}>
            <ArrowLeft size={16} />
            Inventaire
          </Button>
          {estAdmin && !campagnes.some((c) => c.statut === 'OUVERTE') && (
            <Button onClick={() => setOuvertureVisible(true)}>
              <Plus size={16} />
              Ouvrir une campagne
            </Button>
          )}
        </div>
      </header>

      {!chargement && campagnes.length === 0 && (
        <p className={local.vide}>
          Aucune campagne pour le moment. L'administrateur en ouvre une, puis chaque agent du
          module recense les équipements qu'il retrouve.
        </p>
      )}

      <div className={local.cartesCampagnes}>
        {campagnes.map((c) => (
          <button
            key={c.id}
            type="button"
            className={c.id === active ? local.carteCampagneOn : local.carteCampagne}
            onClick={() => setActive(c.id)}
          >
            <span className={local.carteTete}>
              <span className={local.carteLibelle}>{c.libelle}</span>
              {c.statut === 'OUVERTE' ? (
                <StatusBadge statut="ok">En cours</StatusBadge>
              ) : (
                <StatusBadge couleur="var(--text-muted)">Clôturée</StatusBadge>
              )}
            </span>
            <span className={local.carteQuand}>
              {c.statut === 'OUVERTE'
                ? `Ouverte le ${jour(c.ouverte_le)}`
                : `Clôturée le ${jour(c.cloturee_le)}`}
              {c.ouverte_par !== null ? ` · ${c.ouverte_par}` : ''}
            </span>
            <Avancement c={c} parc={parc} />
            {/* La comparaison annuelle tient dans ces quatre chiffres, carte contre carte. */}
            <span className={local.carteComptes}>
              <span style={{ color: 'var(--status-ok)' }}>
                <b>{c.bons}</b> bons
              </span>
              <span style={{ color: 'var(--status-warn)' }}>
                <b>{c.rebuts}</b> rebuts
              </span>
              <span style={{ color: 'var(--status-danger)' }}>
                <b>{c.casses}</b> cassés
              </span>
              <span style={{ color: c.non_retrouves > 0 ? 'var(--status-danger)' : 'var(--text-muted)' }}>
                <b>{c.non_retrouves}</b> non retrouvés
              </span>
            </span>
          </button>
        ))}
      </div>

      {campagne !== null && (
        <>
          <div className={filtres.barre}>
            <label className={filtres.recherche}>
              <Search size={16} />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Rechercher dans le recensement…"
              />
            </label>
            {ouverte && estAdmin && (
              <Button variante="secondaire" onClick={() => setClotureVisible(true)}>
                <ClipboardCheck size={16} />
                Clôturer la campagne
              </Button>
            )}
          </div>

          <Table
            colonnes={colonnes}
            lignes={visibles}
            cleLigne={(l) => l.id}
            chargement={chargement}
            vide="Aucun équipement dans ce recensement."
          />
        </>
      )}

      <Modale
        ouverte={ouvertureVisible}
        onFermer={() => setOuvertureVisible(false)}
        titre="Ouvrir une campagne d'inventaire"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setOuvertureVisible(false)}>
              Annuler
            </Button>
            <Button onClick={() => void ouvrir()} disabled={envoi || libelle.trim().length < 2}>
              {envoi ? 'Ouverture…' : 'Ouvrir'}
            </Button>
          </>
        }
      >
        <label className={styles.champ}>
          <span>Libellé</span>
          <input
            autoFocus
            value={libelle}
            onChange={(e) => setLibelle(e.target.value)}
            placeholder="Ex. Inventaire physique 2026"
          />
        </label>
        <p className={local.noteModale}>
          Une seule campagne peut être ouverte à la fois. Chaque agent du module pourra poser ses
          constats ; la clôture relèvera les non retrouvés.
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
            <Button onClick={() => void cloturer()} disabled={envoi}>
              {envoi ? 'Clôture…' : 'Clôturer'}
            </Button>
          </>
        }
      >
        <p className={local.noteModale}>
          {campagne !== null &&
            `${campagne.constates} équipement(s) recensé(s) sur ${Math.max(parc, campagne.constates)}. ` +
              `Les ${Math.max(0, parc - campagne.constates)} restants seront marqués « non retrouvés ». `}
          La clôture est définitive : les constats seront figés.
        </p>
      </Modale>
    </div>
  );
}
