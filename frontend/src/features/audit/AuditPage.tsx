import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurGestionnaire } from '@/common/SelecteurGestionnaire';
import { ApercuEcheance } from '@/common/ApercuEcheance';
import { FiltreTickets } from '@/common/FiltreTickets';
import { BadgePriorite, BadgeStatut } from '@/common/statuts';
import { ErreurApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import type { FiltresListe } from '@/features/incidents/incidentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { auditApi, type Categorie, type Recommandation } from './auditApi';

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const COLONNES: Colonne<Recommandation>[] = [
  { cle: 'reference', entete: 'Référence', valeur: (r) => r.reference, largeur: '150px' },
  { cle: 'titre', entete: 'Recommandation', tronque: true, rendu: (r) => <strong title={r.titre}>{r.titre}</strong>, valeur: (r) => r.titre },
  {
    cle: 'categorie',
    entete: 'Source',
    rendu: (r) => (r.categorie ? <StatusBadge couleur="var(--cat-5)">{r.categorie}</StatusBadge> : '—'),
  },
  { cle: 'priorite', entete: 'Priorité', valeur: (r) => r.priorite, rendu: (r) => <BadgePriorite priorite={r.priorite} /> },
  { cle: 'statut', entete: 'Statut', rendu: (r) => <BadgeStatut statut={r.statut} /> },
  {
    cle: 'responsable',
    entete: 'Responsable',
    rendu: (r) => (r.responsable ? `${r.responsable.prenom} ${r.responsable.nom}` : '—'),
  },
  { cle: 'cree_le', entete: 'Ouverte le', valeur: (r) => r.cree_le, rendu: (r) => formaterDate(r.cree_le) },
];

export function AuditPage(): JSX.Element {
  const [items, setItems] = useState<Recommandation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const [titre, setTitre] = useState('');
  const [description, setDescription] = useState('');
  const [categorie, setCategorie] = useState<string | null>(null);
  const [gestionnaire, setGestionnaire] = useState<string | null>(null);
  const [impact, setImpact] = useState(3);
  const [urgence, setUrgence] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await auditApi.lister(p, filtres);
        setItems(data.elements);
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

  const { moi } = useAuth();
  const gerable = moi?.acces.includes('administration') ?? false;

  const chargerCategories = useCallback((): void => {
    void auditApi.categories().then(setCategories);
  }, []);
  useEffect(() => {
    chargerCategories();
  }, [chargerCategories]);

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      await auditApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        impact,
        urgence,
        categorie_id: categorie,
        responsable_id: gestionnaire,
      });
      setModale(false);
      setTitre('');
      setDescription('');
      setCategorie(null);
      setGestionnaire(null);
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
          <h1 className={styles.titre}>Audit & Recommandations</h1>
          <p className={styles.sous}>Suivi des recommandations d'audit jusqu'à leur clôture.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/audit" />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            Nouvelle recommandation
          </Button>
        </div>
      </header>

      <FiltreTickets
        module="audit"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

      <Table
        colonnes={COLONNES}
        lignes={items}
        cleLigne={(r) => r.id}
        chargement={chargement}
        vide="Aucune recommandation pour le moment."
        onLigne={(r) => setFicheId(r.id)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <FicheTransition
        base="/audit"
        id={ficheId}
        assignable
        labelCategorie="Source"
        moduleCategorie="audit"
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
      />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Nouvelle recommandation"
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
          <span>Recommandation</span>
          <input value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="Intitulé de la recommandation" />
        </label>
        {categories.length > 0 && (
          <div className={styles.champ}>
            <span>Source</span>
            <SelecteurCategorie
              categories={categories}
              valeur={categorie}
              onChange={setCategorie}
              module="audit"
              gerable={gerable}
              onModifie={chargerCategories}
            />
          </div>
        )}
        <SelecteurGestionnaire valeur={gestionnaire} onChange={setGestionnaire} />
        <label className={styles.champ}>
          <span>Plan d'action</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Actions prévues, responsable, échéance…"
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
        <ApercuEcheance impact={impact} urgence={urgence} />
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
