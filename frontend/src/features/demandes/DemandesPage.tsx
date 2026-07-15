import { useCallback, useEffect, useState } from 'react';
import { StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { BandeauStats } from '@/common/BandeauStats';
import { CelluleActeur } from '@/common/CelluleActeur';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { FiltreTickets } from '@/common/FiltreTickets';
import { SablierSla } from '@/common/SablierSla';
import { CelluleReference } from '@/common/CelluleReference';
import { NiveauSupport } from '@/common/NiveauSupport';
import { BadgeStatut } from '@/common/statuts';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { type FiltresListe } from '@/features/incidents/incidentsApi';
import { demandesApi, type Demande } from './demandesApi';
import { useRafraichissement } from '@/common/useRafraichissement';

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

const COLONNES: Colonne<Demande>[] = [
  {
    cle: 'reference',
    entete: 'Référence',
    valeur: (d) => d.reference,
    largeur: '190px',
    rendu: (d) => (
      <CelluleReference reference={d.reference} nombre={d.nb_commentaires} nonVus={d.nb_non_vus} />
    ),
  },
  {
    cle: 'titre',
    entete: 'Objet',
    tronque: true,
    rendu: (d) => <strong title={d.titre}>{d.titre}</strong>,
    valeur: (d) => d.titre,
  },
  {
    cle: 'categorie',
    entete: 'Catégorie',
    valeur: (d) => d.categorie ?? '',
    rendu: (d) =>
      d.categorie ? <StatusBadge couleur="var(--cat-1)">{d.categorie}</StatusBadge> : '—',
  },
  {
    cle: 'statut',
    entete: 'Statut',
    valeur: (d) => d.statut,
    rendu: (d) => <BadgeStatut statut={d.statut} />,
  },
  {
    // Où se trouve le ticket, sans ouvrir la fiche : déduit du gestionnaire à chaque import.
    cle: 'niveau',
    entete: 'Niveau',
    largeur: '90px',
    valeur: (d) => d.niveau_support ?? 99,
    rendu: (d) => (
      <NiveauSupport niveau={d.niveau_support} transfereDbs={d.transfere_dbs} compact />
    ),
  },
  {
    cle: 'sla',
    entete: 'SLA',
    valeur: (d) => d.sla_resolution_le ?? '',
    rendu: (d) => (
      <SablierSla
        echeance={d.sla_resolution_le}
        debut={d.cree_le}
        statut={d.statut_sla}
        arrete={d.sla_arrete}
      />
    ),
  },
  {
    cle: 'gestionnaire',
    entete: 'Gestionnaire',
    valeur: (d) => d.gestionnaire ?? '',
    rendu: (d) => <CelluleActeur nom={d.gestionnaire} contributeur={d.contributeur} />,
  },
  {
    cle: 'cree_le',
    entete: 'Créée le',
    valeur: (d) => d.cree_le,
    rendu: (d) => formaterDate(d.cree_le),
  },
];

export function DemandesPage(): JSX.Element {
  const [demandes, setDemandes] = useState<Demande[]>([]);
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
        const data = await demandesApi.lister(p, filtres);
        setDemandes(data.elements);
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
          <h1 className={styles.titre}>Demandes de service</h1>
          <p className={styles.sous}>
            Comptes, habilitations, logiciels, VPN, matériel, assistance.
          </p>
        </div>
        <BoutonsExport base="/demandes" />
      </header>

      <BandeauStats base="/demandes" signal={total} />

      <FiltreTickets
        module="demande"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

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
            setPage(p);
          },
        }}
      />

      <FicheTransition
        base="/demandes"
        id={ficheId}
        gestionnaireFige
        avecNiveauSupport
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
        onVu={(aid) =>
          setDemandes((liste) => liste.map((d) => (d.id === aid ? { ...d, nb_non_vus: 0 } : d)))
        }
      />
    </div>
  );
}
