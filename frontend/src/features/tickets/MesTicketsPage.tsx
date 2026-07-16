import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Inbox,
  List,
  LayoutGrid,
  BarChart3,
  ListChecks,
  Search,
  X,
  Circle,
  Clock,
  AlertTriangle,
  Eye,
} from 'lucide-react';
import { Table, StatusBadge, useToast, type Colonne } from '@/design-system/primitives';
import { COULEUR_STATUT_TACHE, type StatutTache } from '@/common/tacheTypes';
import { BadgeStatut, BadgePriorite, couleurStatut } from '@/common/statuts';
import { SablierSla } from '@/common/SablierSla';
import { CelluleReference } from '@/common/CelluleReference';
import { Kanban, type ColonneKanban } from '@/common/Kanban';
import { FicheTransition } from '@/common/FicheTransition';
import { useNavigate } from 'react-router-dom';
import {
  CAPACITES_MODULE,
  LIBELLE_MODULE,
  MODULES_PAGE_DEDIEE,
  ROUTE_MODULE,
} from '@/common/routesModule';
import { cx } from '@/common/cx';
import { api, ErreurApi } from '@/lib/api';
import { TableauBordAgent } from './TableauBordAgent';
import { BoutonExportPdf } from '@/common/BoutonExportPdf';
import { FiltrePeriode } from '@/common/FiltrePeriode';
import { PERIODE_TOUT, type Periode } from '@/common/periode';
import { BandeauAgent } from './BandeauAgent';
import { useAuth } from '@/lib/auth';
import { SelecteurListe } from '@/common/SelecteurListe';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import local from './MesTickets.module.css';
import { useRafraichissement } from '@/common/useRafraichissement';
import {
  mesTicketsApi,
  type MonTicket,
  type MesStats,
  type SegmentTicket,
  type MaTache,
  type StatsTaches,
  type FiltreTache,
} from './mesTicketsApi';

const SEGMENTS: { cle: SegmentTicket; libelle: string }[] = [
  { cle: 'actifs', libelle: 'Actifs' },
  { cle: 'a_valider', libelle: 'À valider' },
  { cle: 'resolus', libelle: 'Résolus' },
  { cle: 'termines', libelle: 'Terminés' },
  { cle: 'tout', libelle: 'Tout' },
];

const MODULE_COULEUR: Record<string, string> = {
  incident: 'var(--cat-1)',
  demande: 'var(--cat-2)',
  changement: 'var(--cat-4)',
  audit: 'var(--cat-5)',
  cybersecurite: 'var(--cat-4)',
  gouvernance: 'var(--cat-6)',
};

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

const COLONNES: Colonne<MonTicket>[] = [
  {
    cle: 'module',
    entete: 'Type',
    largeur: '130px',
    valeur: (t) => LIBELLE_MODULE[t.module] ?? t.module,
    rendu: (t) => (
      <StatusBadge couleur={MODULE_COULEUR[t.module] ?? 'var(--text-muted)'}>
        {LIBELLE_MODULE[t.module] ?? t.module}
      </StatusBadge>
    ),
  },
  {
    cle: 'reference',
    entete: 'Référence',
    valeur: (t) => t.reference,
    largeur: '180px',
    rendu: (t) => (
      <CelluleReference reference={t.reference} nombre={t.nb_commentaires} nonVus={t.nb_non_vus} />
    ),
  },
  {
    cle: 'titre',
    entete: 'Objet',
    tronque: true,
    rendu: (t) => <strong title={t.titre}>{t.titre}</strong>,
    valeur: (t) => t.titre,
  },
  {
    cle: 'priorite',
    entete: 'Priorité',
    valeur: (t) => t.priorite ?? 9,
    rendu: (t) => (t.priorite ? <BadgePriorite priorite={t.priorite} /> : '—'),
  },
  {
    cle: 'sla',
    entete: 'SLA',
    valeur: (t) => t.sla_resolution_le ?? '',
    rendu: (t) => (
      <SablierSla
        echeance={t.sla_resolution_le}
        debut={t.cree_le}
        statut={t.statut_sla}
        arrete={t.sla_arrete}
      />
    ),
  },
  {
    cle: 'statut',
    entete: 'Statut',
    valeur: (t) => t.statut,
    rendu: (t) => <BadgeStatut statut={t.statut} />,
  },
  {
    cle: 'cree_le',
    entete: 'Reçu le',
    valeur: (t) => t.cree_le,
    rendu: (t) => formaterDate(t.cree_le),
  },
];

const COLONNES_TACHE: Colonne<MaTache>[] = [
  {
    cle: 'statut',
    entete: 'Statut',
    largeur: '120px',
    valeur: (t) => t.statut,
    rendu: (t) => (
      <StatusBadge couleur={COULEUR_STATUT_TACHE[t.statut as StatutTache] ?? 'var(--text-muted)'}>
        {t.statut}
      </StatusBadge>
    ),
  },
  {
    cle: 'titre',
    entete: 'Tâche',
    tronque: true,
    rendu: (t) => <strong title={t.titre}>{t.titre}</strong>,
    valeur: (t) => t.titre,
  },
  {
    cle: 'activite',
    entete: 'Rattachée à',
    rendu: (t) => (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        <StatusBadge couleur={MODULE_COULEUR[t.module] ?? 'var(--text-muted)'}>
          {LIBELLE_MODULE[t.module] ?? t.module}
        </StatusBadge>
        <span title={t.activite_titre}>{t.reference}</span>
      </span>
    ),
    valeur: (t) => t.reference,
  },
  {
    cle: 'role',
    entete: 'Mon rôle',
    largeur: '150px',
    valeur: (t) => libelleRole(t.role_activite, t.module),
    rendu: (t) => <span className="tabular">{libelleRole(t.role_activite, t.module)}</span>,
  },
  {
    cle: 'echeance',
    entete: 'Échéance',
    valeur: (t) => t.echeance ?? '',
    rendu: (t) =>
      t.echeance ? (
        <SablierSla echeance={t.echeance} debut={t.cree_le} />
      ) : (
        <span style={{ color: 'var(--text-muted)' }}>—</span>
      ),
  },
];

/** Mon rôle dans l'activité parente, dit dans le vocabulaire du module. */
function libelleRole(role: string, module: string): string {
  if (role === 'RESPONSABLE') return module === 'projet' ? 'Chef de projet' : 'Gestionnaire';
  if (role === 'CONTRIBUTEUR') return 'Contributeur';
  return 'Assigné';
}

export function MesTicketsPage(): JSX.Element {
  const [items, setItems] = useState<MonTicket[]>([]);
  const [stats, setStats] = useState<MesStats | null>(null);
  const [chargement, setChargement] = useState(true);
  const [fiche, setFiche] = useState<{ base: string; id: string; module: string } | null>(null);
  const [vue, setVue] = useState<'liste' | 'kanban'>('liste');
  const [onglet, setOnglet] = useState<'tickets' | 'taches' | 'analyse'>('tickets');
  const [periodeAnalyse, setPeriodeAnalyse] = useState<Periode>(PERIODE_TOUT);
  const [taches, setTaches] = useState<MaTache[]>([]);
  const [segment, setSegment] = useState<SegmentTicket>('actifs');
  const [aValider, setAValider] = useState(0);
  const [recherche, setRecherche] = useState('');
  const [statsTaches, setStatsTaches] = useState<StatsTaches | null>(null);
  const [filtreTache, setFiltreTache] = useState<FiltreTache>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageTaches, setPageTaches] = useState(1);
  const [totalTaches, setTotalTaches] = useState(0);
  const analyseRef = useRef<HTMLDivElement>(null);
  const { notifier } = useToast();
  const navigate = useNavigate();
  const { moi } = useAuth();

  // Un administrateur n'a presque jamais de tickets. Il peut consulter la file d'un gestionnaire
  // (tickets, tâches, analyses) comme si c'était lui, en lecture. Réservé à l'admin (garde serveur).
  const estAdmin = moi?.profil === 'ADMIN';
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentCible, setAgentCible] = useState<string | null>(null);

  useEffect(() => {
    if (estAdmin) void chargerAgents().then(setAgents);
  }, [estAdmin]);

  const choisirAgent = (id: string | null): void => {
    setAgentCible(id);
    setPage(1);
    setPageTaches(1);
  };

  const charger = useCallback(
    // `silencieux` : rafraîchissement de fond — pas de squelette, la liste ne doit pas clignoter.
    (silencieux = false): void => {
      if (!silencieux) setChargement(true);
      void mesTicketsApi
        .lister(segment, page, recherche, agentCible)
        .then((p) => {
          setItems(p.elements);
          setTotal(p.total);
          setAValider(p.a_valider);
        })
        .finally(() => {
          if (!silencieux) setChargement(false);
        });
    },
    [segment, page, recherche, agentCible],
  );

  const baseDe = useCallback(
    (id: string): { base: string; ticket: MonTicket } | null => {
      const t = items.find((x) => x.id === id);
      const base = t ? ROUTE_MODULE[t.module] : undefined;
      return t && base !== undefined ? { base, ticket: t } : null;
    },
    [items],
  );

  const ouvrir = useCallback(
    (id: string): void => {
      const ref = baseDe(id);
      if (!ref) return;
      // Projets et changements ont une page dédiée (tâches, jalons, RFC) : on y renvoie plutôt que
      // d'ouvrir la fiche modale partielle.
      if (MODULES_PAGE_DEDIEE.has(ref.ticket.module)) {
        navigate(`${ref.base}/${ref.ticket.id}`);
        return;
      }
      setFiche({ base: ref.base, id: ref.ticket.id, module: ref.ticket.module });
    },
    [baseDe, navigate],
  );

  // Glisser-déposer : transitions autorisées de la carte, puis exécution de la transition.
  const ciblesValides = useCallback(
    async (id: string): Promise<string[]> => {
      const ref = baseDe(id);
      if (!ref) return [];
      const d = await api.get<{ transitions_possibles: string[] }>(`${ref.base}/${ref.ticket.id}`);
      return d.transitions_possibles;
    },
    [baseDe],
  );
  const deplacer = useCallback(
    (id: string, statut: string): void => {
      const ref = baseDe(id);
      if (!ref) return;
      void api
        .post(`${ref.base}/${ref.ticket.id}/transition`, { vers: statut })
        .then(() => {
          notifier(`${ref.ticket.reference} · ${statut}`, 'succes');
          charger();
        })
        .catch((e) =>
          notifier(e instanceof ErreurApi ? e.message : 'Transition impossible.', 'erreur'),
        );
    },
    [baseDe, charger, notifier],
  );

  useEffect(() => {
    charger();
  }, [charger]);

  // L'icône de discussion apparaît sans recharger la page : la liste se relit seule,
  // en pause quand l'onglet est masqué.
  useRafraichissement(() => charger(true));

  useEffect(() => {
    if (onglet !== 'taches') return;
    void mesTicketsApi.taches(false, pageTaches, recherche, filtreTache, agentCible).then((p) => {
      setTaches(p.elements);
      setTotalTaches(p.total);
      setStatsTaches(p.stats);
    });
  }, [onglet, pageTaches, recherche, filtreTache, agentCible]);

  // Les indicateurs de l'onglet Analyse suivent la période choisie.
  useEffect(() => {
    void mesTicketsApi.stats(periodeAnalyse, agentCible).then(setStats);
  }, [periodeAnalyse, agentCible]);

  // Kanban : une colonne par statut présent (ordre d'apparition : déjà trié priorité/SLA).
  const statutsPresents = [...new Set(items.map((t) => t.statut))];
  const colonnesKanban: ColonneKanban[] = statutsPresents.map((statut) => ({
    cle: statut,
    titre: statut,
    couleur: couleurStatut(statut),
    cartes: items
      .filter((t) => t.statut === statut)
      .map((t) => ({
        id: t.id,
        reference: t.reference,
        titre: t.titre,
        priorite: t.priorite,
        echeance: t.sla_resolution_le,
        debut: t.cree_le,
        statutSla: t.statut_sla,
        meta: t.demandeur,
        nbCommentaires: t.nb_commentaires,
        nbNonVus: t.nb_non_vus,
        etiquette: {
          texte: LIBELLE_MODULE[t.module] ?? t.module,
          couleur: MODULE_COULEUR[t.module] ?? 'var(--text-muted)',
        },
      })),
  }));

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Mes tickets</h1>
          <p className={incidents.sous}>
            {onglet === 'tickets'
              ? 'Votre file de travail — du plus prioritaire au plus urgent. Les SLA dépassés sont surlignés.'
              : onglet === 'taches'
                ? 'Les tâches qui vous sont assignées dans les projets et les changements.'
                : 'Analyse complète de votre activité : SLA, charge et rythme de résolution.'}
          </p>
        </div>
        <div className={local.ongletsBarre}>
          <div className={local.onglets} role="tablist" aria-label="Vues de la page">
            <button
              role="tab"
              aria-selected={onglet === 'tickets'}
              className={cx(local.onglet, onglet === 'tickets' && local.ongletOn)}
              onClick={() => setOnglet('tickets')}
            >
              <Inbox size={15} />
              Tickets
            </button>
            <button
              role="tab"
              aria-selected={onglet === 'taches'}
              className={cx(local.onglet, onglet === 'taches' && local.ongletOn)}
              onClick={() => setOnglet('taches')}
            >
              <ListChecks size={15} />
              {agentCible === null ? 'Mes tâches' : agentCible === 'tous' ? 'Tâches' : 'Ses tâches'}
            </button>
            <button
              role="tab"
              aria-selected={onglet === 'analyse'}
              className={cx(local.onglet, onglet === 'analyse' && local.ongletOn)}
              onClick={() => setOnglet('analyse')}
            >
              <BarChart3 size={15} />
              Analyse
            </button>
          </div>
          {estAdmin && (
            <div className={local.consulterSelecteur}>
              <SelecteurListe
                options={[
                  { valeur: 'tous', libelle: 'Tous les agents (vue globale)', special: true },
                  ...agents.map((ag) => ({ valeur: ag.id, libelle: ag.nom })),
                ]}
                valeur={agentCible}
                onChange={choisirAgent}
                placeholder="Ma file"
                permettreVide
                libelleVide="Ma file"
              />
            </div>
          )}
        </div>
      </header>

      {agentCible !== null && (
        <span className={local.consulterBandeau}>
          <Eye size={14} /> Vue en lecture —{' '}
          <strong>
            {agentCible === 'tous'
              ? 'tous les agents'
              : (agents.find((x) => x.id === agentCible)?.nom ?? 'cet agent')}
          </strong>
        </span>
      )}

      {onglet !== 'analyse' && (
        <div className={local.recherche}>
          <Search size={16} className={local.rechercheIcone} />
          <input
            className={local.rechercheInput}
            value={recherche}
            onChange={(e) => {
              setRecherche(e.target.value);
              setPage(1);
              setPageTaches(1);
            }}
            placeholder={onglet === 'taches' ? 'Rechercher une tâche…' : 'Rechercher un ticket…'}
          />
          {recherche !== '' && (
            <button
              type="button"
              className={local.rechercheReset}
              onClick={() => {
                setRecherche('');
                setPage(1);
                setPageTaches(1);
              }}
              aria-label="Effacer la recherche"
            >
              <X size={15} />
            </button>
          )}
        </div>
      )}

      {onglet === 'analyse' ? (
        stats !== null && (
          <>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 'var(--space-3)',
                flexWrap: 'wrap',
              }}
            >
              <FiltrePeriode valeur={periodeAnalyse} onChange={setPeriodeAnalyse} />
              <BoutonExportPdf
                cible={analyseRef}
                titre="Mon activité — Mes tickets"
                nomFichier="dsi360-mon-activite.pdf"
              />
            </div>
            <div
              ref={analyseRef}
              style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}
            >
              <TableauBordAgent stats={stats} />
            </div>
          </>
        )
      ) : onglet === 'taches' ? (
        <>
          {statsTaches !== null && (
            <div className={local.tachesFiltres} role="tablist" aria-label="Filtrer mes tâches">
              {(
                [
                  {
                    cle: null,
                    lib: 'Toutes',
                    val: statsTaches.a_faire + statsTaches.en_cours,
                    icone: <ListChecks size={15} />,
                    couleur: 'var(--text)',
                  },
                  {
                    cle: 'a_faire',
                    lib: 'À faire',
                    val: statsTaches.a_faire,
                    icone: <Circle size={15} />,
                    couleur: 'var(--text)',
                  },
                  {
                    cle: 'en_cours',
                    lib: 'En cours',
                    val: statsTaches.en_cours,
                    icone: <Clock size={15} />,
                    couleur: 'var(--cat-1)',
                  },
                  {
                    cle: 'en_retard',
                    lib: 'En retard',
                    val: statsTaches.en_retard,
                    icone: <AlertTriangle size={15} />,
                    couleur:
                      statsTaches.en_retard > 0 ? 'var(--status-danger)' : 'var(--text-muted)',
                  },
                ] as const
              ).map((s) => (
                <button
                  key={s.lib}
                  type="button"
                  role="tab"
                  aria-selected={filtreTache === s.cle}
                  className={cx(local.statPastille, filtreTache === s.cle && local.statPastilleOn)}
                  onClick={() => {
                    setFiltreTache(s.cle);
                    setPageTaches(1);
                  }}
                >
                  <span className={local.statIcone} style={{ color: s.couleur }}>
                    {s.icone}
                  </span>
                  <span className={local.statValeur} style={{ color: s.couleur }}>
                    {s.val}
                  </span>
                  <span className={local.statLibelle}>{s.lib}</span>
                </button>
              ))}
            </div>
          )}
          <Table
            colonnes={COLONNES_TACHE}
            lignes={taches}
            cleLigne={(t) => t.id}
            vide="Aucune tâche ne vous est assignée pour le moment."
            onLigne={(t) => navigate(`${ROUTE_MODULE[t.module] ?? ''}/${t.activite_id}`)}
            pagination={{ page: pageTaches, total: totalTaches, taille: 15, onPage: setPageTaches }}
          />
        </>
      ) : (
        <>
          {stats !== null && <BandeauAgent stats={stats} />}

          <div className={local.barreFile}>
            <div className={local.onglets} role="tablist" aria-label="Filtrer la file">
              {SEGMENTS.map((s) => (
                <button
                  key={s.cle}
                  role="tab"
                  aria-selected={segment === s.cle}
                  className={cx(local.onglet, segment === s.cle && local.ongletOn)}
                  onClick={() => {
                    setSegment(s.cle);
                    setPage(1);
                  }}
                >
                  {s.libelle}
                  {s.cle === 'a_valider' && aValider > 0 && (
                    <span className={local.badgeSegment}>{aValider}</span>
                  )}
                </button>
              ))}
            </div>
            <div className={incidents.vues}>
              <button
                className={cx(incidents.vue, vue === 'liste' && incidents.vueOn)}
                onClick={() => setVue('liste')}
                title="Vue liste"
              >
                <List size={16} />
              </button>
              <button
                className={cx(incidents.vue, vue === 'kanban' && incidents.vueOn)}
                onClick={() => setVue('kanban')}
                title="Vue Kanban"
              >
                <LayoutGrid size={16} />
              </button>
            </div>
          </div>

          {!chargement && items.length === 0 ? (
            <div className={incidents.vide}>
              <Inbox size={28} />
              <span>
                {segment === 'actifs'
                  ? 'Aucun ticket actif ne vous est assigné pour le moment.'
                  : 'Aucun ticket dans ce filtre.'}
              </span>
            </div>
          ) : vue === 'kanban' ? (
            <>
              <Kanban
                colonnes={colonnesKanban}
                onOuvrir={ouvrir}
                onDeplacer={deplacer}
                ciblesValides={ciblesValides}
                cleStockage="mes-tickets"
              />
            </>
          ) : (
            <Table
              colonnes={COLONNES}
              lignes={items}
              cleLigne={(t) => `${t.module}-${t.id}`}
              chargement={chargement}
              vide="Aucun ticket assigné."
              onLigne={(t) => ouvrir(t.id)}
              classeLigne={(t) => (t.statut_sla === 'depasse' ? 'ligne-sla-depasse' : undefined)}
              pagination={{ page, total, taille: 15, onPage: setPage }}
            />
          )}
        </>
      )}

      <FicheTransition
        base={fiche?.base ?? ''}
        id={fiche?.id ?? null}
        assignable
        {...(fiche ? (CAPACITES_MODULE[fiche.module] ?? {}) : {})}
        onFermer={() => setFiche(null)}
        onChange={charger}
        onVu={(aid) =>
          setItems((liste) => liste.map((t) => (t.id === aid ? { ...t, nb_non_vus: 0 } : t)))
        }
      />
    </div>
  );
}
