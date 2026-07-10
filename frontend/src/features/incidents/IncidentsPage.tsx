import { useCallback, useEffect, useState } from 'react';
import { StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { FiltreTickets } from '@/common/FiltreTickets';
import { SablierSla } from '@/common/SablierSla';
import { CelluleReference } from '@/common/CelluleReference';
import { NiveauSupport } from '@/common/NiveauSupport';
import { BadgeStatut } from '@/common/statuts';
import { incidentsApi, type Incident, type FiltresListe } from './incidentsApi';
import styles from './IncidentsPage.module.css';
import { useRafraichissement } from '@/common/useRafraichissement';

const PRIORITE_COULEUR: Record<number, string> = {
  1: 'var(--status-danger)',
  2: 'var(--cat-3)',
  3: 'var(--cat-7)',
  4: 'var(--cat-1)',
  5: 'var(--text-muted)',
};

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

const COLONNES: Colonne<Incident>[] = [
  {
    cle: 'reference',
    entete: 'Référence',
    valeur: (i) => i.reference,
    largeur: '190px',
    rendu: (i) => (
      <CelluleReference reference={i.reference} nombre={i.nb_commentaires} nonVus={i.nb_non_vus} />
    ),
  },
  {
    cle: 'titre',
    entete: 'Titre',
    tronque: true,
    rendu: (i) => <strong title={i.titre}>{i.titre}</strong>,
    valeur: (i) => i.titre,
  },
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
    // Où se trouve le ticket, sans ouvrir la fiche : déduit du gestionnaire à chaque import.
    cle: 'niveau',
    entete: 'Niveau',
    largeur: '90px',
    rendu: (i) => (
      <NiveauSupport niveau={i.niveau_support} transfereDbs={i.transfere_dbs} compact />
    ),
  },
  {
    cle: 'sla',
    entete: 'SLA',
    rendu: (i) => (
      <SablierSla echeance={i.sla_resolution_le} debut={i.cree_le} statut={i.statut_sla} />
    ),
  },
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
  {
    cle: 'cree_le',
    entete: 'Créé le',
    valeur: (i) => i.cree_le,
    rendu: (i) => formaterDate(i.cree_le),
  },
];

export function IncidentsPage(): JSX.Element {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const charger = useCallback(
    // `silencieux` : rafraîchissement de fond — pas de squelette, la table ne doit pas clignoter.
    async (p: number, silencieux = false): Promise<void> => {
      if (!silencieux) setChargement(true);
      try {
        const data = await incidentsApi.lister(p, filtres);
        setIncidents(data.elements);
        setTotal(data.total);
      } finally {
        if (!silencieux) setChargement(false);
      }
    },
    [filtres],
  );

  useEffect(() => {
    void charger(page);
  }, [charger, page]);

  // L'icône de discussion apparaît sans recharger la page : la liste se relit seule,
  // en pause quand l'onglet est masqué.
  useRafraichissement(() => void charger(page, true));

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Incidents</h1>
          <p className={styles.sous}>Gestion des incidents du système d'information.</p>
        </div>
        <BoutonsExport base="/incidents" />
      </header>

      <FiltreTickets
        module="incident"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

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
            setPage(p);
          },
        }}
      />

      <FicheTransition
        base="/incidents"
        id={ficheId}
        avecDocuments
        gestionnaireFige
        avecNiveauSupport
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
        onVu={(aid) =>
          setIncidents((liste) => liste.map((i) => (i.id === aid ? { ...i, nb_non_vus: 0 } : i)))
        }
      />
    </div>
  );
}
