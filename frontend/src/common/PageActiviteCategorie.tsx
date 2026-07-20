import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { CelluleActeur } from '@/common/CelluleActeur';
import { CelluleReference } from '@/common/CelluleReference';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurGestionnaire } from '@/common/SelecteurGestionnaire';
import { ApercuEcheance } from '@/common/ApercuEcheance';
import { FiltreTickets } from '@/common/FiltreTickets';
import { BadgePriorite, BadgeStatut } from '@/common/statuts';
import { api, ErreurApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { SablierSla } from '@/common/SablierSla';
import { chaineFiltres, type FiltresListe, type Incident } from '@/features/incidents/incidentsApi';
import type { Categorie } from '@/features/demandes/demandesApi';
import { useRafraichissement } from '@/common/useRafraichissement';
import { BandeauStats } from '@/common/BandeauStats';
import { SaisieLiens, persisterLiens, type LienSaisi } from '@/common/SaisieLiens';

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
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
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
  const [gestionnaire, setGestionnaire] = useState<string | null>(null);
  const [impact, setImpact] = useState(3);
  const [urgence, setUrgence] = useState(3);
  const [liens, setLiens] = useState<LienSaisi[]>([]);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const { moi } = useAuth();
  const gerable = moi?.acces.includes('administration') ?? false;

  const colonnes: Colonne<Incident>[] = [
    {
      cle: 'reference',
      entete: 'Référence',
      valeur: (a) => a.reference,
      largeur: '190px',
      rendu: (a) => (
        <CelluleReference
          reference={a.reference}
          nombre={a.nb_commentaires}
          nonVus={a.nb_non_vus}
        />
      ),
    },
    {
      cle: 'titre',
      entete: labelObjet,
      tronque: true,
      rendu: (a) => <strong title={a.titre}>{a.titre}</strong>,
      valeur: (a) => a.titre,
    },
    {
      cle: 'categorie',
      entete: labelCategorie,
      valeur: (a) => a.categorie ?? '',
      rendu: (a) =>
        a.categorie ? <StatusBadge couleur={couleurCategorie}>{a.categorie}</StatusBadge> : '—',
    },
    {
      cle: 'priorite',
      entete: 'Priorité',
      valeur: (a) => a.priorite,
      rendu: (a) => <BadgePriorite priorite={a.priorite} />,
    },
    {
      cle: 'statut',
      entete: 'Statut',
      valeur: (a) => a.statut,
      rendu: (a) => <BadgeStatut statut={a.statut} module={module} />,
    },
    {
      cle: 'responsable',
      entete: 'Responsable',
      valeur: (a) => (a.responsable ? `${a.responsable.prenom} ${a.responsable.nom}` : ''),
      rendu: (a) => (
        <CelluleActeur
          nom={a.responsable ? `${a.responsable.prenom} ${a.responsable.nom}` : null}
          contributeur={a.contributeur}
          vide="—"
        />
      ),
    },
    {
      cle: 'sla',
      entete: 'Échéance SLA',
      valeur: (a) => a.sla_resolution_le ?? '',
      rendu: (a) => (
        <SablierSla
          echeance={a.sla_resolution_le}
          debut={a.cree_le}
          statut={a.statut_sla ?? 'a_lheure'}
          arrete={a.sla_arrete}
        />
      ),
    },
    {
      cle: 'cree_le',
      entete: 'Créé le',
      valeur: (a) => a.cree_le,
      rendu: (a) => formaterDate(a.cree_le),
    },
  ];

  const charger = useCallback(
    // `silencieux` : rafraîchissement de fond — pas de squelette, la table ne doit pas clignoter.
    async (p: number, silencieux = false): Promise<void> => {
      if (!silencieux) setChargement(true);
      try {
        const data = await api.get<{ elements: Incident[]; total: number }>(
          `${base}?${chaineFiltres(p, filtres)}`,
        );
        setItems(data.elements);
        setTotal(data.total);
      } finally {
        if (!silencieux) setChargement(false);
      }
    },
    [base, filtres],
  );

  useEffect(() => {
    void charger(page);
  }, [charger, page]);

  // L'icône de discussion apparaît sans recharger la page : la liste se relit seule,
  // en pause quand l'onglet est masqué.
  useRafraichissement(() => void charger(page, true));

  const chargerCategories = useCallback((): void => {
    void api.get<Categorie[]>(`/referentiels/categories?module=${module}`).then(setCategories);
  }, [module]);
  useEffect(() => {
    chargerCategories();
  }, [chargerCategories]);

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      const cree = await api.post<{ id: string }>(base, {
        titre: objet.trim(),
        description: description.trim(),
        impact,
        urgence,
        categorie_id: categorie,
        responsable_id: gestionnaire,
      });
      await persisterLiens((l) => api.post(`${base}/${cree.id}/liens`, l), liens);
      setModale(false);
      setObjet('');
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

      <BandeauStats base={base} signal={total} />

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

      <FicheTransition
        base={base}
        id={ficheId}
        assignable
        avecDocuments
        avecRevue
        avecLiens
        labelCategorie={labelCategorie}
        moduleCategorie={module}
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
        onVu={(aid) =>
          setItems((liste) => liste.map((a) => (a.id === aid ? { ...a, nb_non_vus: 0 } : a)))
        }
      />

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
        {(categories.length > 0 || gerable) && (
          <div className={styles.champ}>
            <span>{labelCategorie}</span>
            <SelecteurCategorie
              categories={categories}
              valeur={categorie}
              onChange={setCategorie}
              module={module}
              gerable={gerable}
              onModifie={chargerCategories}
            />
          </div>
        )}
        <SelecteurGestionnaire valeur={gestionnaire} onChange={setGestionnaire} />
        <label className={styles.champ}>
          <span>Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Détails…"
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
        <ApercuEcheance impact={impact} urgence={urgence} module={module} />
        <div className={styles.champ}>
          <span>Liens utiles</span>
          <SaisieLiens valeur={liens} onChange={setLiens} />
        </div>
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
