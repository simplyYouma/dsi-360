import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { SelecteurDate } from '@/common/SelecteurDate';
import { SelecteurListe } from '@/common/SelecteurListe';
import { FiltreTickets } from '@/common/FiltreTickets';
import { useFicheUrl } from '@/common/useFicheUrl';
import { api, ErreurApi } from '@/lib/api';
import type { FiltresListe } from '@/features/incidents/incidentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { ProjetFiche } from './ProjetFiche';
import { projetsApi, type Projet } from './projetsApi';

interface Agent {
  id: string;
  nom: string;
  profil: string;
}

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function formaterBudget(v: number | null): string {
  if (v === null) return '—';
  return new Intl.NumberFormat('fr-FR', { notation: 'compact', maximumFractionDigits: 1 }).format(v);
}

function Avancement({ valeur }: { valeur: number }): JSX.Element {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', minWidth: 130 }}>
      <div style={{ flex: 1, height: 6, background: 'var(--bg-subtle)', borderRadius: 'var(--radius-pill)' }}>
        <div
          style={{
            width: `${valeur}%`,
            height: '100%',
            background: 'var(--secondary)',
            borderRadius: 'var(--radius-pill)',
          }}
        />
      </div>
      <span className="tabular" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
        {valeur}%
      </span>
    </div>
  );
}

const COLONNES: Colonne<Projet>[] = [
  { cle: 'reference', entete: 'Référence', valeur: (p) => p.reference, largeur: '150px' },
  { cle: 'titre', entete: 'Projet', rendu: (p) => <strong>{p.titre}</strong>, valeur: (p) => p.titre },
  { cle: 'statut', entete: 'Statut', rendu: (p) => <StatusBadge>{p.statut}</StatusBadge> },
  {
    cle: 'chef',
    entete: 'Chef de projet',
    rendu: (p) => (p.chef ? `${p.chef.prenom} ${p.chef.nom}` : '—'),
  },
  {
    cle: 'avancement',
    entete: 'Avancement',
    valeur: (p) => p.avancement,
    rendu: (p) => <Avancement valeur={p.avancement} />,
  },
  {
    cle: 'budget',
    entete: 'Budget (FCFA)',
    aligne: 'droite',
    valeur: (p) => p.budget ?? 0,
    rendu: (p) => <span className="tabular">{formaterBudget(p.budget)}</span>,
  },
  { cle: 'date_fin', entete: 'Échéance', rendu: (p) => p.date_fin ?? '—' },
  { cle: 'cree_le', entete: 'Créé le', valeur: (p) => p.cree_le, rendu: (p) => formaterDate(p.cree_le) },
];

export function ProjetsPage(): JSX.Element {
  const [projets, setProjets] = useState<Projet[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const [titre, setTitre] = useState('');
  const [sponsor, setSponsor] = useState('');
  const [chef, setChef] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [budget, setBudget] = useState('');
  const [dateDebut, setDateDebut] = useState('');
  const [dateFin, setDateFin] = useState('');
  const [description, setDescription] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await projetsApi.lister(p, filtres);
        setProjets(data.elements);
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
  useEffect(() => {
    void api.get<Agent[]>('/referentiels/agents').then(setAgents);
  }, []);

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      await projetsApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        sponsor: sponsor.trim(),
        budget: budget.trim() === '' ? null : Number(budget),
        date_debut: dateDebut.trim() === '' ? null : dateDebut.trim(),
        date_fin: dateFin.trim() === '' ? null : dateFin.trim(),
        responsable_id: chef,
      });
      setModale(false);
      setTitre('');
      setSponsor('');
      setChef(null);
      setBudget('');
      setDateDebut('');
      setDateFin('');
      setDescription('');
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
          <h1 className={styles.titre}>Projets</h1>
          <p className={styles.sous}>Suivi des projets de la DSI : planning, budget, avancement.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/projets" />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            Nouveau projet
          </Button>
        </div>
      </header>

      <FiltreTickets
        module="projet"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

      <Table
        colonnes={COLONNES}
        lignes={projets}
        cleLigne={(p) => p.id}
        chargement={chargement}
        vide="Aucun projet pour le moment."
        onLigne={(p) => setFicheId(p.id)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <ProjetFiche id={ficheId} onFermer={() => setFicheId(null)} onChange={() => void charger(page)} />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Nouveau projet"
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
          <span>Intitulé du projet</span>
          <input value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="Nom du projet" />
        </label>
        <label className={styles.champ}>
          <span>Sponsor</span>
          <input value={sponsor} onChange={(e) => setSponsor(e.target.value)} placeholder="Direction / responsable sponsor" />
        </label>
        <div className={styles.champ}>
          <span>Chef de projet</span>
          <SelecteurListe
            options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
            valeur={chef}
            onChange={setChef}
            placeholder="Désigner un chef de projet"
            permettreVide
            libelleVide="Non désigné"
          />
        </div>
        <div className={styles.niveaux}>
          <label className={styles.champ}>
            <span>Budget (FCFA)</span>
            <input
              value={budget}
              onChange={(e) => setBudget(e.target.value.replace(/[^0-9]/g, ''))}
              inputMode="numeric"
              placeholder="0"
            />
          </label>
          <div className={styles.champ}>
            <span>Début</span>
            <SelecteurDate valeur={dateDebut || null} onChange={(v) => setDateDebut(v ?? '')} placeholder="jj/mm/aaaa" />
          </div>
          <div className={styles.champ}>
            <span>Échéance</span>
            <SelecteurDate valeur={dateFin || null} onChange={(v) => setDateFin(v ?? '')} placeholder="jj/mm/aaaa" />
          </div>
        </div>
        <label className={styles.champ}>
          <span>Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Objectifs, périmètre…"
          />
        </label>
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
