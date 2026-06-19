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
import { cx } from '@/common/cx';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { assignerLot, type FiltresListe } from '@/features/incidents/incidentsApi';
import { demandesApi, type Categorie, type Demande } from './demandesApi';

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const COLONNES: Colonne<Demande>[] = [
  { cle: 'reference', entete: 'Référence', valeur: (d) => d.reference, largeur: '150px' },
  { cle: 'titre', entete: 'Objet', tronque: true, rendu: (d) => <strong title={d.titre}>{d.titre}</strong>, valeur: (d) => d.titre },
  {
    cle: 'categorie',
    entete: 'Catégorie',
    rendu: (d) =>
      d.categorie ? <StatusBadge couleur="var(--cat-1)">{d.categorie}</StatusBadge> : '—',
  },
  { cle: 'statut', entete: 'Statut', rendu: (d) => <BadgeStatut statut={d.statut} /> },
  {
    cle: 'sla',
    entete: 'SLA',
    rendu: (d) => <SablierSla echeance={d.sla_resolution_le} debut={d.cree_le} statut={d.statut_sla} />,
  },
  { cle: 'demandeur', entete: 'Demandeur', rendu: (d) => d.demandeur ?? '—' },
  {
    cle: 'gestionnaire',
    entete: 'Gestionnaire',
    rendu: (d) =>
      d.gestionnaire ? (
        d.gestionnaire
      ) : (
        <span style={{ color: 'var(--text-muted)' }}>Non assigné</span>
      ),
  },
  { cle: 'cree_le', entete: 'Créée le', valeur: (d) => d.cree_le, rendu: (d) => formaterDate(d.cree_le) },
  {
    cle: 'discussion',
    entete: '',
    aligne: 'centre',
    largeur: '46px',
    rendu: (d) => <IndicateurDiscussion nombre={d.nb_commentaires} />,
  },
];

export function DemandesPage(): JSX.Element {
  const [demandes, setDemandes] = useState<Demande[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });
  const [selection, setSelection] = useState<Set<string>>(new Set());

  const [titre, setTitre] = useState('');
  const [demandeur, setDemandeur] = useState('');
  const [description, setDescription] = useState('');
  const [categorie, setCategorie] = useState<string | null>(null);
  const [impact, setImpact] = useState(3);
  const [urgence, setUrgence] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await demandesApi.lister(p, filtres);
        setDemandes(data.elements);
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
    void demandesApi.categories().then(setCategories);
  }, []);

  const creer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      await demandesApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        impact,
        urgence,
        categorie_id: categorie,
        demandeur: demandeur.trim() === '' ? null : demandeur.trim(),
      });
      setModale(false);
      setTitre('');
      setDemandeur('');
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
          <h1 className={styles.titre}>Demandes de service</h1>
          <p className={styles.sous}>Comptes, habilitations, logiciels, VPN, matériel, assistance.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <BoutonsExport base="/demandes" />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            Nouvelle demande
          </Button>
        </div>
      </header>

      <FiltreTickets
        module="demande"
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
            await assignerLot('/demandes', [...selection], resp);
            setSelection(new Set());
            await charger(page);
          }}
        />
      )}

      <Table
        colonnes={COLONNES}
        lignes={demandes}
        cleLigne={(d) => d.id}
        chargement={chargement}
        vide="Aucune demande pour le moment."
        onLigne={(d) => setFicheId(d.id)}
        classeLigne={(d) => (d.statut_sla === 'depasse' ? 'ligne-sla-depasse' : undefined)}
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
        base="/demandes"
        id={ficheId}
        assignable
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
      />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Nouvelle demande"
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
          <span>Objet</span>
          <input
            value={titre}
            onChange={(e) => setTitre(e.target.value)}
            placeholder="Décrivez la demande en une phrase"
          />
        </label>
        <label className={styles.champ}>
          <span>Demandeur</span>
          <input
            value={demandeur}
            onChange={(e) => setDemandeur(e.target.value)}
            placeholder="Agent qui fait la demande (Prénom NOM)"
          />
        </label>
        <div className={styles.champ}>
          <span>Catégorie</span>
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
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Détails utiles au traitement…"
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
