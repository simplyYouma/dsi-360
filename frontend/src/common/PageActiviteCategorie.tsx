import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { FiltreTickets } from '@/common/FiltreTickets';
import { BadgePriorite, BadgeStatut } from '@/common/statuts';
import { api, ErreurApi } from '@/lib/api';
import { cx } from '@/common/cx';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { chaineFiltres, type FiltresListe, type Incident } from '@/features/incidents/incidentsApi';
import type { Categorie } from '@/features/demandes/demandesApi';

interface Props {
  titre: string;
  sous: string;
  base: string;
  module: string;
  labelObjet: string;
  labelCategorie: string;
  labelNouveau: string;
  couleurCategorie: string;
}

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

/** Page générique d'un module d'activité à catégorie (cybersécurité, gouvernance…). */
export function PageActiviteCategorie({
  titre,
  sous,
  base,
  module,
  labelObjet,
  labelCategorie,
  labelNouveau,
  couleurCategorie,
}: Props): JSX.Element {
  const [items, setItems] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const [objet, setObjet] = useState('');
  const [description, setDescription] = useState('');
  const [categorie, setCategorie] = useState<string | null>(null);
  const [impact, setImpact] = useState(3);
  const [urgence, setUrgence] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const colonnes: Colonne<Incident>[] = [
    { cle: 'reference', entete: 'Référence', valeur: (a) => a.reference, largeur: '150px' },
    { cle: 'titre', entete: labelObjet, rendu: (a) => <strong>{a.titre}</strong>, valeur: (a) => a.titre },
    {
      cle: 'categorie',
      entete: labelCategorie,
      rendu: (a) => (a.categorie ? <StatusBadge couleur={couleurCategorie}>{a.categorie}</StatusBadge> : '—'),
    },
    { cle: 'priorite', entete: 'Priorité', valeur: (a) => a.priorite, rendu: (a) => <BadgePriorite priorite={a.priorite} /> },
    { cle: 'statut', entete: 'Statut', rendu: (a) => <BadgeStatut statut={a.statut} /> },
    {
      cle: 'responsable',
      entete: 'Responsable',
      rendu: (a) => (a.responsable ? `${a.responsable.prenom} ${a.responsable.nom}` : '—'),
    },
    { cle: 'cree_le', entete: 'Créé le', valeur: (a) => a.cree_le, rendu: (a) => formaterDate(a.cree_le) },
  ];

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await api.get<{ elements: Incident[]; total: number }>(
          `${base}?${chaineFiltres(p, filtres)}`,
        );
        setItems(data.elements);
        setTotal(data.total);
      } finally {
        setChargement(false);
      }
    },
    [base, filtres],
  );

  useEffect(() => {
    void charger(page);
  }, [charger, page]);

  useEffect(() => {
    void api.get<Categorie[]>(`/referentiels/categories?module=${module}`).then(setCategories);
  }, [module]);

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      await api.post(base, {
        titre: objet.trim(),
        description: description.trim(),
        impact,
        urgence,
        categorie_id: categorie,
      });
      setModale(false);
      setObjet('');
      setDescription('');
      setCategorie(null);
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
          <h1 className={styles.titre}>{titre}</h1>
          <p className={styles.sous}>{sous}</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base={base} />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            {labelNouveau}
          </Button>
        </div>
      </header>

      <FiltreTickets
        module={module}
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

      <Table
        colonnes={colonnes}
        lignes={items}
        cleLigne={(a) => a.id}
        chargement={chargement}
        vide="Aucun élément pour le moment."
        onLigne={(a) => setFicheId(a.id)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <FicheTransition base={base} id={ficheId} assignable onFermer={() => setFicheId(null)} onChange={() => void charger(page)} />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre={labelNouveau}
        pied={
          <>
            <Button variante="secondaire" onClick={() => setModale(false)}>
              Annuler
            </Button>
            <Button onClick={() => void creer()} disabled={envoi || objet.trim().length < 3}>
              {envoi ? 'Création…' : 'Créer'}
            </Button>
          </>
        }
      >
        <label className={styles.champ}>
          <span>{labelObjet}</span>
          <input value={objet} onChange={(e) => setObjet(e.target.value)} placeholder="Intitulé" />
        </label>
        <div className={styles.champ}>
          <span>{labelCategorie}</span>
          <div className={styles.chips}>
            {categories.map((c) => (
              <button
                key={c.id}
                type="button"
                className={cx(c.id === categorie ? styles.chipActif : styles.chip)}
                onClick={() => setCategorie(c.id)}
              >
                {c.libelle}
              </button>
            ))}
          </div>
        </div>
        <label className={styles.champ}>
          <span>Description</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="Détails…" />
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
