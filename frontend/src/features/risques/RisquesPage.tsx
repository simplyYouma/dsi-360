import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { CelluleReference } from '@/common/CelluleReference';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurGestionnaire } from '@/common/SelecteurGestionnaire';
import { FiltreTickets } from '@/common/FiltreTickets';
import { BadgeCriticite, BadgeStatut } from '@/common/statuts';
import { ErreurApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import type { FiltresListe, CategorieRef } from '@/features/incidents/incidentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { risquesApi, type Risque } from './risquesApi';

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const COLONNES: Colonne<Risque>[] = [
  {
    cle: 'reference',
    entete: 'Référence',
    valeur: (r) => r.reference,
    largeur: '190px',
    rendu: (r) => (
      <CelluleReference reference={r.reference} nombre={r.nb_commentaires} nonVus={r.nb_non_vus} />
    ),
  },
  { cle: 'titre', entete: 'Risque', tronque: true, rendu: (r) => <strong title={r.titre}>{r.titre}</strong>, valeur: (r) => r.titre },
  { cle: 'probabilite', entete: 'Probabilité', aligne: 'centre', valeur: (r) => r.probabilite, rendu: (r) => r.probabilite },
  { cle: 'impact', entete: 'Impact', aligne: 'centre', valeur: (r) => r.impact, rendu: (r) => r.impact },
  { cle: 'criticite', entete: 'Criticité', valeur: (r) => r.criticite, rendu: (r) => <BadgeCriticite niveau={r.criticite} /> },
  { cle: 'statut', entete: 'Statut', rendu: (r) => <BadgeStatut statut={r.statut} /> },
  {
    cle: 'responsable',
    entete: 'Responsable',
    rendu: (r) => (r.responsable ? `${r.responsable.prenom} ${r.responsable.nom}` : '—'),
  },
  { cle: 'cree_le', entete: 'Identifié le', valeur: (r) => r.cree_le, rendu: (r) => formaterDate(r.cree_le) },
];

export function RisquesPage(): JSX.Element {
  const [items, setItems] = useState<Risque[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const [titre, setTitre] = useState('');
  const [description, setDescription] = useState('');
  const [categories, setCategories] = useState<CategorieRef[]>([]);
  const [categorie, setCategorie] = useState<string | null>(null);
  const [gestionnaire, setGestionnaire] = useState<string | null>(null);
  const [probabilite, setProbabilite] = useState(3);
  const [impact, setImpact] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const criticite = Math.ceil((probabilite + impact) / 2);

  const { moi } = useAuth();
  const gerable = moi?.acces.includes('administration') ?? false;

  const chargerCategories = useCallback((): void => {
    void risquesApi.categories().then(setCategories);
  }, []);
  useEffect(() => {
    chargerCategories();
  }, [chargerCategories]);

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await risquesApi.lister(p, filtres);
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

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      await risquesApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        probabilite,
        impact,
        categorie_id: categorie,
        responsable_id: gestionnaire,
      });
      setModale(false);
      setTitre('');
      setDescription('');
      setCategorie(null);
      setGestionnaire(null);
      setProbabilite(3);
      setImpact(3);
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
          <h1 className={styles.titre}>Risques IT</h1>
          <p className={styles.sous}>Identification et traitement des risques (criticité = probabilité × impact).</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/risques" />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            Nouveau risque
          </Button>
        </div>
      </header>

      <FiltreTickets
        module="risque"
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
        vide="Aucun risque pour le moment."
        onLigne={(r) => setFicheId(r.id)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <FicheTransition
        base="/risques"
        id={ficheId}
        assignable
        avecRevue
        moduleCategorie="risque"
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
        onVu={(aid) =>
          setItems((liste) => liste.map((r) => (r.id === aid ? { ...r, nb_non_vus: 0 } : r)))
        }
      />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Nouveau risque IT"
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
          <span>Intitulé du risque</span>
          <input value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="Ex. Indisponibilité du datacenter" />
        </label>
        <label className={styles.champ}>
          <span>Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Scénario, causes, conséquences…"
          />
        </label>
        {categories.length > 0 && (
          <div className={styles.champ}>
            <span>Catégorie</span>
            <SelecteurCategorie
              categories={categories}
              valeur={categorie}
              onChange={setCategorie}
              module="risque"
              gerable={gerable}
              onModifie={chargerCategories}
            />
          </div>
        )}
        <SelecteurGestionnaire valeur={gestionnaire} onChange={setGestionnaire} />
        <div className={styles.niveaux}>
          <div className={styles.champ}>
            <span>Probabilité</span>
            <CurseurNiveau valeur={probabilite} onChange={setProbabilite} />
          </div>
          <div className={styles.champ}>
            <span>Impact</span>
            <CurseurNiveau valeur={impact} onChange={setImpact} />
          </div>
        </div>
        <div className={styles.champ}>
          <span>Criticité estimée</span>
          <BadgeCriticite niveau={criticite} />
        </div>
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
