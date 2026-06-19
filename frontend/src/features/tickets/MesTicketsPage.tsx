import { useCallback, useEffect, useState } from 'react';
import { Inbox } from 'lucide-react';
import { Table, StatusBadge, type Colonne } from '@/design-system/primitives';
import { BadgeStatut, BadgePriorite } from '@/common/statuts';
import { SablierSla } from '@/common/SablierSla';
import { FicheTransition } from '@/common/FicheTransition';
import { LIBELLE_MODULE, ROUTE_MODULE } from '@/common/routesModule';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import local from './MesTickets.module.css';
import { mesTicketsApi, type MonTicket } from './mesTicketsApi';

const MODULE_COULEUR: Record<string, string> = {
  incident: 'var(--cat-1)',
  demande: 'var(--cat-2)',
  changement: 'var(--cat-4)',
  audit: 'var(--cat-5)',
  cybersecurite: 'var(--cat-4)',
  gouvernance: 'var(--cat-6)',
};

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const COLONNES: Colonne<MonTicket>[] = [
  {
    cle: 'module',
    entete: 'Type',
    largeur: '130px',
    rendu: (t) => (
      <StatusBadge couleur={MODULE_COULEUR[t.module] ?? 'var(--text-muted)'}>
        {LIBELLE_MODULE[t.module] ?? t.module}
      </StatusBadge>
    ),
  },
  { cle: 'reference', entete: 'Référence', valeur: (t) => t.reference, largeur: '140px' },
  { cle: 'titre', entete: 'Objet', tronque: true, rendu: (t) => <strong title={t.titre}>{t.titre}</strong>, valeur: (t) => t.titre },
  {
    cle: 'priorite',
    entete: 'Priorité',
    valeur: (t) => t.priorite ?? 9,
    rendu: (t) => (t.priorite ? <BadgePriorite priorite={t.priorite} /> : '—'),
  },
  {
    cle: 'sla',
    entete: 'SLA',
    rendu: (t) => <SablierSla echeance={t.sla_resolution_le} priorite={t.priorite} statut={t.statut_sla} />,
  },
  { cle: 'demandeur', entete: 'Demandeur', rendu: (t) => t.demandeur ?? '—' },
  { cle: 'statut', entete: 'Statut', rendu: (t) => <BadgeStatut statut={t.statut} /> },
  { cle: 'cree_le', entete: 'Reçu le', valeur: (t) => t.cree_le, rendu: (t) => formaterDate(t.cree_le) },
];

export function MesTicketsPage(): JSX.Element {
  const [items, setItems] = useState<MonTicket[]>([]);
  const [chargement, setChargement] = useState(true);
  const [fiche, setFiche] = useState<{ base: string; id: string } | null>(null);

  const charger = useCallback((): void => {
    setChargement(true);
    void mesTicketsApi
      .lister()
      .then(setItems)
      .finally(() => setChargement(false));
  }, []);

  useEffect(() => {
    charger();
  }, [charger]);

  const enRetard = items.filter((t) => t.statut_sla === 'depasse').length;
  const approche = items.filter((t) => t.statut_sla === 'approche').length;
  const p1 = items.filter((t) => t.priorite === 1).length;
  const kpis = [
    { libelle: 'À traiter', valeur: items.length, couleur: 'var(--text)' },
    { libelle: 'SLA dépassé', valeur: enRetard, couleur: 'var(--status-danger)' },
    { libelle: 'Échéance proche', valeur: approche, couleur: 'var(--status-warn)' },
    { libelle: 'Critiques (P1)', valeur: p1, couleur: 'var(--cat-1)' },
  ];

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Mes tickets</h1>
          <p className={incidents.sous}>
            Votre file de travail — du plus prioritaire au plus urgent. Les SLA dépassés sont
            surlignés.
          </p>
        </div>
      </header>

      {!chargement && (
        <section className={local.kpis}>
          {kpis.map((k) => (
            <div key={k.libelle} className={local.kpi}>
              <span className={local.kpiValeur} style={{ color: k.couleur }}>
                {k.valeur}
              </span>
              <span className={local.kpiLibelle}>{k.libelle}</span>
            </div>
          ))}
        </section>
      )}

      {!chargement && items.length === 0 ? (
        <div className={incidents.vide}>
          <Inbox size={28} />
          <span>Aucun ticket ne vous est assigné pour le moment.</span>
        </div>
      ) : (
        <Table
          colonnes={COLONNES}
          lignes={items}
          cleLigne={(t) => `${t.module}-${t.id}`}
          chargement={chargement}
          vide="Aucun ticket assigné."
          onLigne={(t) => {
            const base = ROUTE_MODULE[t.module];
            if (base !== undefined) setFiche({ base, id: t.id });
          }}
          classeLigne={(t) => (t.statut_sla === 'depasse' ? 'ligne-sla-depasse' : undefined)}
        />
      )}

      <FicheTransition
        base={fiche?.base ?? ''}
        id={fiche?.id ?? null}
        assignable
        onFermer={() => setFiche(null)}
        onChange={charger}
      />
    </div>
  );
}
