import { useCallback, useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, Search } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { cx } from '@/common/cx';
import { ErreurApi } from '@/lib/api';
import styles from '@/features/incidents/IncidentsPage.module.css';
import local from './DemandeursPage.module.css';
import { adminApi, type Direction } from '@/features/administration/adminApi';
import { demandeursApi, type Demandeur } from './demandeursApi';

export function DemandeursPage(): JSX.Element {
  const [items, setItems] = useState<Demandeur[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [chargement, setChargement] = useState(true);
  const [directions, setDirections] = useState<Direction[]>([]);
  const [modale, setModale] = useState<null | { id: string | null }>(null);

  const [nom, setNom] = useState('');
  const [direction, setDirection] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [actif, setActif] = useState(true);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async (p: number, terme: string): Promise<void> => {
    setChargement(true);
    try {
      const data = await demandeursApi.lister(p, terme);
      setItems(data.elements);
      setTotal(data.total);
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    void charger(page, q);
  }, [charger, page, q]);
  useEffect(() => {
    void adminApi.directions().then(setDirections);
  }, []);

  const ouvrirCreation = (): void => {
    setNom('');
    setDirection(null);
    setEmail('');
    setActif(true);
    setErreur(null);
    setModale({ id: null });
  };
  const ouvrirEdition = (d: Demandeur): void => {
    setNom(d.nom_complet);
    setDirection(directions.find((x) => x.libelle === d.direction)?.code ?? null);
    setEmail(d.email ?? '');
    setActif(d.actif);
    setErreur(null);
    setModale({ id: d.id });
  };

  const enregistrer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      const corps = {
        nom_complet: nom.trim(),
        direction_code: direction,
        email: email.trim() === '' ? null : email.trim(),
        actif,
      };
      if (modale?.id === null) await demandeursApi.creer(corps);
      else if (modale) await demandeursApi.modifier(modale.id, corps);
      setModale(null);
      await charger(page, q);
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Enregistrement impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const supprimer = async (d: Demandeur): Promise<void> => {
    try {
      await demandeursApi.supprimer(d.id);
      await charger(page, q);
    } catch (err) {
      // 409 = rattaché à des tickets : on remonte le message (proposer la désactivation).
      window.alert(err instanceof ErreurApi ? err.message : 'Suppression impossible.');
    }
  };

  const colonnes: Colonne<Demandeur>[] = [
    { cle: 'nom', entete: 'Nom complet', rendu: (d) => <strong>{d.nom_complet}</strong>, valeur: (d) => d.nom_complet },
    { cle: 'direction', entete: 'Direction', rendu: (d) => d.direction ?? '—' },
    { cle: 'email', entete: 'E-mail', rendu: (d) => d.email ?? '—' },
    {
      cle: 'actif',
      entete: 'Statut',
      rendu: (d) => (
        <StatusBadge statut={d.actif ? 'ok' : 'danger'}>{d.actif ? 'Actif' : 'Inactif'}</StatusBadge>
      ),
    },
    {
      cle: 'actions',
      entete: '',
      rendu: (d) => (
        <span className={local.actions}>
          <button className={local.iconBtn} title="Modifier" onClick={() => ouvrirEdition(d)}>
            <Pencil size={16} />
          </button>
          <button
            className={cx(local.iconBtn, local.danger)}
            title="Supprimer"
            onClick={() => void supprimer(d)}
          >
            <Trash2 size={16} />
          </button>
        </span>
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Demandeurs</h1>
          <p className={styles.sous}>
            Agents de la banque qui remontent incidents et demandes. Reconnus automatiquement à
            l’import ; complétez ici leur direction.
          </p>
        </div>
        <Button onClick={ouvrirCreation}>
          <Plus size={16} />
          Nouveau demandeur
        </Button>
      </header>

      <label className={local.recherche}>
        <Search size={16} />
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder="Rechercher un demandeur…"
        />
      </label>

      <Table
        colonnes={colonnes}
        lignes={items}
        cleLigne={(d) => d.id}
        chargement={chargement}
        vide="Aucun demandeur."
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <Modale
        ouverte={modale !== null}
        onFermer={() => setModale(null)}
        titre={modale?.id === null ? 'Nouveau demandeur' : 'Modifier le demandeur'}
        pied={
          <>
            <Button variante="secondaire" onClick={() => setModale(null)}>
              Annuler
            </Button>
            <Button onClick={() => void enregistrer()} disabled={envoi || nom.trim().length < 2}>
              {envoi ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </>
        }
      >
        <label className={styles.champ}>
          <span>Nom complet</span>
          <input value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Prénom NOM" />
        </label>
        <div className={styles.champ}>
          <span>Direction</span>
          <div className={styles.chips}>
            <button
              type="button"
              className={cx(direction === null ? styles.chipActif : styles.chip)}
              onClick={() => setDirection(null)}
            >
              Aucune
            </button>
            {directions.map((d) => (
              <button
                key={d.code}
                type="button"
                className={cx(d.code === direction ? styles.chipActif : styles.chip)}
                onClick={() => setDirection(d.code)}
              >
                {d.libelle}
              </button>
            ))}
          </div>
        </div>
        <label className={styles.champ}>
          <span>E-mail (optionnel)</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="prenom.nom@afgbank.ml" />
        </label>
        {modale?.id !== null && (
          <div className={styles.champ}>
            <span>Statut</span>
            <div className={styles.chips}>
              <button type="button" className={cx(actif ? styles.chipActif : styles.chip)} onClick={() => setActif(true)}>
                Actif
              </button>
              <button type="button" className={cx(!actif ? styles.chipActif : styles.chip)} onClick={() => setActif(false)}>
                Inactif
              </button>
            </div>
          </div>
        )}
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>
    </div>
  );
}
