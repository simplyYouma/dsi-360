import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { BandeauStats } from '@/common/BandeauStats';
import { CelluleActeur } from '@/common/CelluleActeur';
import { CelluleReference } from '@/common/CelluleReference';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurGestionnaire } from '@/common/SelecteurGestionnaire';
import { ApercuEcheance } from '@/common/ApercuEcheance';
import { SaisieLiens, persisterLiens, type LienSaisi } from '@/common/SaisieLiens';
import { FiltreTickets } from '@/common/FiltreTickets';
import { BadgePriorite, BadgeStatut } from '@/common/statuts';
import { api, ErreurApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import type { FiltresListe } from '@/features/incidents/incidentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { SablierSla } from '@/common/SablierSla';
import { auditApi, type Categorie, type Recommandation } from './auditApi';

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

const COLONNES: Colonne<Recommandation>[] = [
  {
    cle: 'reference',
    entete: 'Référence',
    valeur: (r) => r.reference,
    largeur: '190px',
    rendu: (r) => (
      <CelluleReference reference={r.reference} nombre={r.nb_commentaires} nonVus={r.nb_non_vus} />
    ),
  },
  {
    cle: 'titre',
    entete: 'Recommandation',
    tronque: true,
    rendu: (r) => <strong title={r.titre}>{r.titre}</strong>,
    valeur: (r) => r.titre,
  },
  {
    cle: 'categorie',
    entete: 'Source',
    rendu: (r) =>
      r.categorie ? <StatusBadge couleur="var(--cat-5)">{r.categorie}</StatusBadge> : '—',
  },
  {
    cle: 'priorite',
    entete: 'Priorité',
    valeur: (r) => r.priorite,
    rendu: (r) => <BadgePriorite priorite={r.priorite} />,
  },
  { cle: 'statut', entete: 'Statut', rendu: (r) => <BadgeStatut statut={r.statut} /> },
  {
    cle: 'responsable',
    entete: 'Responsable',
    rendu: (r) => (
      <CelluleActeur
        nom={r.responsable ? `${r.responsable.prenom} ${r.responsable.nom}` : null}
        contributeur={r.contributeur}
        vide="—"
      />
    ),
  },
  {
    cle: 'sla',
    entete: 'Échéance SLA',
    valeur: (r) => r.sla_resolution_le ?? '',
    rendu: (r) => (
      <SablierSla
        echeance={r.sla_resolution_le}
        debut={r.cree_le}
        statut={r.statut_sla ?? 'a_lheure'}
        arrete={r.sla_arrete}
      />
    ),
  },
  {
    cle: 'cree_le',
    entete: 'Ouverte le',
    valeur: (r) => r.cree_le,
    rendu: (r) => formaterDate(r.cree_le),
  },
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
  const [liens, setLiens] = useState<LienSaisi[]>([]);
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
      const cree = await auditApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        impact,
        urgence,
        categorie_id: categorie,
        responsable_id: gestionnaire,
      });
      await persisterLiens((l) => api.post(`/audit/${cree.id}/liens`, l), liens);
      setModale(false);
      setTitre('');
      setDescription('');
      setCategorie(null);
      setGestionnaire(null);
      setImpact(3);
      setUrgence(3);
      setLiens([]);
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

      <BandeauStats base="/audit" signal={total} />

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
        avecDocuments
        labelCategorie="Source"
        moduleCategorie="audit"
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
        onVu={(aid) =>
          setItems((liste) => liste.map((r) => (r.id === aid ? { ...r, nb_non_vus: 0 } : r)))
        }
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
          <input
            value={titre}
            onChange={(e) => setTitre(e.target.value)}
            placeholder="Intitulé de la recommandation"
          />
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
        <ApercuEcheance impact={impact} urgence={urgence} module="audit" />
        <div className={styles.champ}>
          <span>Liens utiles</span>
          <SaisieLiens valeur={liens} onChange={setLiens} />
        </div>
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
