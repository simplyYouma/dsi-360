import { useCallback, useEffect, useState } from 'react';
import { Plus, Inbox } from 'lucide-react';
import { Button, Card, Modale, StatusBadge } from '@/design-system/primitives';
import { ErreurApi } from '@/lib/api';
import { cx } from '@/common/cx';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { demandesApi, type Categorie, type Demande } from './demandesApi';

const SLA: Record<Demande['statut_sla'], { libelle: string; statut: 'ok' | 'warn' | 'danger' }> = {
  a_lheure: { libelle: "À l'heure", statut: 'ok' },
  approche: { libelle: 'Approche', statut: 'warn' },
  depasse: { libelle: 'Dépassé', statut: 'danger' },
};

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

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

export function DemandesPage(): JSX.Element {
  const [demandes, setDemandes] = useState<Demande[]>([]);
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [chargement, setChargement] = useState(true);
  const [modale, setModale] = useState(false);

  const [titre, setTitre] = useState('');
  const [description, setDescription] = useState('');
  const [categorie, setCategorie] = useState<string | null>(null);
  const [impact, setImpact] = useState(3);
  const [urgence, setUrgence] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async (): Promise<void> => {
    setChargement(true);
    try {
      const page = await demandesApi.lister(1);
      setDemandes(page.elements);
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    void charger();
    void demandesApi.categories().then(setCategories);
  }, [charger]);

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
      });
      setModale(false);
      setTitre('');
      setDescription('');
      setCategorie(null);
      setImpact(3);
      setUrgence(3);
      await charger();
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
        <Button onClick={() => setModale(true)}>
          <Plus size={16} />
          Nouvelle demande
        </Button>
      </header>

      <Card sansPadding>
        {chargement ? (
          <p className={styles.vide}>Chargement…</p>
        ) : demandes.length === 0 ? (
          <div className={styles.vide}>
            <Inbox size={32} />
            <p>Aucune demande pour le moment.</p>
          </div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Référence</th>
                <th>Objet</th>
                <th>Catégorie</th>
                <th>Statut</th>
                <th>SLA</th>
                <th>Demandeur / Resp.</th>
                <th>Créée le</th>
              </tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <tr key={d.id}>
                  <td className="tabular">{d.reference}</td>
                  <td className={styles.cellTitre}>{d.titre}</td>
                  <td>
                    {d.categorie ? (
                      <StatusBadge couleur="var(--cat-1)">{d.categorie}</StatusBadge>
                    ) : (
                      <span className={styles.muted}>—</span>
                    )}
                  </td>
                  <td>
                    <StatusBadge>{d.statut}</StatusBadge>
                  </td>
                  <td>
                    <StatusBadge statut={SLA[d.statut_sla].statut}>
                      {SLA[d.statut_sla].libelle}
                    </StatusBadge>
                  </td>
                  <td className={styles.muted}>
                    {d.responsable ? `${d.responsable.prenom} ${d.responsable.nom}` : '—'}
                  </td>
                  <td className="tabular">{formaterDate(d.cree_le)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

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
