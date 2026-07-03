import { useCallback, useEffect, useState } from 'react';
import { StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { BoutonsExport } from '@/common/BoutonsExport';
import { FicheTransition } from '@/common/FicheTransition';
import { useFicheUrl } from '@/common/useFicheUrl';
import { FiltreTickets } from '@/common/FiltreTickets';
import { DispatchBar } from '@/common/DispatchBar';
import { SablierSla } from '@/common/SablierSla';
import { IndicateurDiscussion } from '@/common/IndicateurDiscussion';
import { BadgeStatut } from '@/common/statuts';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { assignerLot, type FiltresListe } from '@/features/incidents/incidentsApi';
import { demandesApi, type Demande } from './demandesApi';

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
  const [chargement, setChargement] = useState(true);
  const [ficheId, setFicheId] = useState<string | null>(null);
  useFicheUrl(setFicheId);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });
  const [selection, setSelection] = useState<Set<string>>(new Set());

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

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Demandes de service</h1>
          <p className={styles.sous}>Comptes, habilitations, logiciels, VPN, matériel, assistance.</p>
        </div>
        <BoutonsExport base="/demandes" />
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
        moduleCategorie="demande"
        onFermer={() => setFicheId(null)}
        onChange={() => void charger(page)}
      />
    </div>
  );
}
