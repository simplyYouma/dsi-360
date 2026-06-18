import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { FicheTransition } from '@/common/FicheTransition';
import { ErreurApi } from '@/lib/api';
import { cx } from '@/common/cx';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { changementsApi, type Categorie, type Changement } from './changementsApi';

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

const COLONNES: Colonne<Changement>[] = [
  { cle: 'reference', entete: 'Référence', valeur: (c) => c.reference, largeur: '150px' },
  { cle: 'titre', entete: 'Objet', rendu: (c) => <strong>{c.titre}</strong>, valeur: (c) => c.titre },
  {
    cle: 'categorie',
    entete: 'Type',
    rendu: (c) => (c.categorie ? <StatusBadge couleur="var(--cat-5)">{c.categorie}</StatusBadge> : '—'),
  },
  {
    cle: 'priorite',
    entete: 'Priorité',
    valeur: (c) => c.priorite,
    rendu: (c) => (
      <StatusBadge couleur={PRIORITE_COULEUR[c.priorite] ?? 'var(--text-muted)'}>P{c.priorite}</StatusBadge>
    ),
  },
  { cle: 'statut', entete: 'Statut', rendu: (c) => <StatusBadge>{c.statut}</StatusBadge> },
  {
    cle: 'responsable',
    entete: 'Responsable',
    rendu: (c) => (c.responsable ? `${c.responsable.prenom} ${c.responsable.nom}` : '—'),
  },
  { cle: 'cree_le', entete: 'Créé le', valeur: (c) => c.cree_le, rendu: (c) => formaterDate(c.cree_le) },
];

function Niveau({ valeur, onChange }: { valeur: number; onChange: (n: number) => void }): JSX.Element {
  return (
    <div className={styles.niveau}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={n === valeur ? styles.niveauActif : styles.niveauItem}
          onClick={() => onChange(n)}
        >
          {n}
        </button>
      ))}
    </div>
  );
}

export function ChangementsPage(): JSX.Element {
  const [changements, setChangements] = useState<Changement[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);

  const [titre, setTitre] = useState('');
  const [description, setDescription] = useState('');
  const [categorie, setCategorie] = useState<string | null>(null);
  const [impact, setImpact] = useState(3);
  const [urgence, setUrgence] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async (p: number): Promise<void> => {
    setChargement(true);
    try {
      const data = await changementsApi.lister(p);
      setChangements(data.elements);
      setTotal(data.total);
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    void charger(page);
  }, [charger, page]);

  useEffect(() => {
    void changementsApi.categories().then(setCategories);
  }, []);

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      await changementsApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        impact,
        urgence,
        categorie_id: categorie,
      });
      setModale(false);
      setTitre('');
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
          <h1 className={styles.titre}>Changements</h1>
          <p className={styles.sous}>Demandes de changement (RFC) — workflow CAB / ECAB.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/changements" />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            Nouveau changement
          </Button>
        </div>
      </header>

      <Table
        colonnes={COLONNES}
        lignes={changements}
        cleLigne={(c) => c.id}
        chargement={chargement}
        vide="Aucun changement pour le moment."
        onLigne={(c) => setFicheId(c.id)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <FicheTransition
        base="/changements"
        id={ficheId}
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
      />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Nouveau changement (RFC)"
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
          <span>Objet du changement</span>
          <input value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="Ex. Mise à jour du pare-feu" />
        </label>
        <div className={styles.champ}>
          <span>Type</span>
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
          <span>Description / plan</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Analyse d'impact, plan de déploiement, retour arrière…"
          />
        </label>
        <div className={styles.niveaux}>
          <div className={styles.champ}>
            <span>Impact</span>
            <Niveau valeur={impact} onChange={setImpact} />
          </div>
          <div className={styles.champ}>
            <span>Urgence</span>
            <Niveau valeur={urgence} onChange={setUrgence} />
          </div>
        </div>
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
