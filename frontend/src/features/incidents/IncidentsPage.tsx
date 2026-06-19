import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { FiltreTickets } from '@/common/FiltreTickets';
import { DispatchBar } from '@/common/DispatchBar';
import { SablierSla } from '@/common/SablierSla';
import { IndicateurDiscussion } from '@/common/IndicateurDiscussion';
import { BadgeStatut } from '@/common/statuts';
import { ErreurApi } from '@/lib/api';
import { incidentsApi, assignerLot, type Incident, type FiltresListe } from './incidentsApi';
import styles from './IncidentsPage.module.css';

const PRIORITE_COULEUR: Record<number, string> = {
  1: 'var(--status-danger)',
  2: 'var(--cat-3)',
  3: 'var(--cat-7)',
  4: 'var(--cat-1)',
  5: 'var(--text-muted)',
};

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const COLONNES: Colonne<Incident>[] = [
  { cle: 'reference', entete: 'Référence', valeur: (i) => i.reference, largeur: '150px' },
  { cle: 'titre', entete: 'Titre', tronque: true, rendu: (i) => <strong title={i.titre}>{i.titre}</strong>, valeur: (i) => i.titre },
  {
    cle: 'priorite',
    entete: 'Priorité',
    valeur: (i) => i.priorite,
    rendu: (i) => (
      <StatusBadge couleur={PRIORITE_COULEUR[i.priorite] ?? 'var(--text-muted)'}>
        P{i.priorite}
      </StatusBadge>
    ),
  },
  { cle: 'statut', entete: 'Statut', rendu: (i) => <BadgeStatut statut={i.statut} /> },
  {
    cle: 'sla',
    entete: 'SLA',
    rendu: (i) => <SablierSla echeance={i.sla_resolution_le} debut={i.cree_le} statut={i.statut_sla} />,
  },
  { cle: 'demandeur', entete: 'Demandeur', rendu: (i) => i.demandeur ?? '—' },
  {
    cle: 'gestionnaire',
    entete: 'Gestionnaire',
    rendu: (i) =>
      i.gestionnaire ? (
        i.gestionnaire
      ) : (
        <span style={{ color: 'var(--text-muted)' }}>Non assigné</span>
      ),
  },
  { cle: 'cree_le', entete: 'Créé le', valeur: (i) => i.cree_le, rendu: (i) => formaterDate(i.cree_le) },
  {
    cle: 'discussion',
    entete: '',
    aligne: 'centre',
    largeur: '46px',
    rendu: (i) => <IndicateurDiscussion nombre={i.nb_commentaires} />,
  },
];

export function IncidentsPage(): JSX.Element {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });
  const [selection, setSelection] = useState<Set<string>>(new Set());

  const [titre, setTitre] = useState('');
  const [demandeur, setDemandeur] = useState('');
  const [description, setDescription] = useState('');
  const [impact, setImpact] = useState(3);
  const [urgence, setUrgence] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await incidentsApi.lister(p, filtres);
        setIncidents(data.elements);
        setTotal(data.total);
      } finally {
        setChargement(false);
      }
    },
    [filtres],
  );

  useEffect(() => {
    void charger(page);
  }, [charger, page]);

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      await incidentsApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        impact,
        urgence,
        demandeur: demandeur.trim() === '' ? null : demandeur.trim(),
      });
      setModale(false);
      setTitre('');
      setDemandeur('');
      setDescription('');
      setImpact(3);
      setUrgence(3);
      if (page === 1) await charger(1);
      else setPage(1);
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Création impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Incidents</h1>
          <p className={styles.sous}>Gestion des incidents du système d'information.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/incidents" />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            Nouvel incident
          </Button>
        </div>
      </header>

      <FiltreTickets
        module="incident"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setSelection(new Set());
          setFiltres(f);
        }}
      />

      {selection.size > 0 && (
        <DispatchBar
          count={selection.size}
          onEffacer={() => setSelection(new Set())}
          onAssigner={async (resp) => {
            await assignerLot('/incidents', [...selection], resp);
            setSelection(new Set());
            await charger(page);
          }}
        />
      )}

      <Table
        colonnes={COLONNES}
        lignes={incidents}
        cleLigne={(i) => i.id}
        chargement={chargement}
        vide="Aucun incident pour le moment."
        onLigne={(i) => setFicheId(i.id)}
        classeLigne={(i) => (i.statut_sla === 'depasse' ? 'ligne-sla-depasse' : undefined)}
        pagination={{
          page,
          total,
          taille: 15,
          onPage: (p) => {
            setSelection(new Set());
            setPage(p);
          },
        }}
        selection={{
          selectionnes: selection,
          onBasculer: (id) =>
            setSelection((s) => {
              const n = new Set(s);
              if (n.has(id)) n.delete(id);
              else n.add(id);
              return n;
            }),
          onTout: (ids, tout) =>
            setSelection((s) => {
              const n = new Set(s);
              ids.forEach((i) => (tout ? n.add(i) : n.delete(i)));
              return n;
            }),
        }}
      />

      <FicheTransition
        base="/incidents"
        id={ficheId}
        assignable
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
      />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Nouvel incident"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setModale(false)}>
              Annuler
            </Button>
            <Button onClick={() => void creer()} disabled={envoi || titre.trim().length < 3}>
              {envoi ? 'Création…' : 'Créer'}
            </Button>
          </>
        }
      >
        <label className={styles.champ}>
          <span>Titre</span>
          <input
            value={titre}
            onChange={(e) => setTitre(e.target.value)}
            placeholder="Décrivez l'incident en une phrase"
          />
        </label>
        <label className={styles.champ}>
          <span>Demandeur</span>
          <input
            value={demandeur}
            onChange={(e) => setDemandeur(e.target.value)}
            placeholder="Agent qui remonte l'incident (Prénom NOM)"
          />
        </label>
        <label className={styles.champ}>
          <span>Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Contexte, impact observé, étapes…"
          />
        </label>
        <div className={styles.niveaux}>
          <div className={styles.champ}>
            <span>Impact</span>
            <CurseurNiveau valeur={impact} onChange={setImpact} />
          </div>
          <div className={styles.champ}>
            <span>Urgence</span>
            <CurseurNiveau valeur={urgence} onChange={setUrgence} />
          </div>
        </div>
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
