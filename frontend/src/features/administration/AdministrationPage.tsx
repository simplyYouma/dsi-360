import { useCallback, useEffect, useState } from 'react';
import { Plus, Pencil, KeyRound } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, type Colonne } from '@/design-system/primitives';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import { cx } from '@/common/cx';
import { ErreurApi } from '@/lib/api';
import styles from '@/features/incidents/IncidentsPage.module.css';
import a from './AdministrationPage.module.css';
import {
  adminApi,
  type Direction,
  type EntreeJournal,
  type Matrice,
  type Profil,
  type Utilisateur,
} from './adminApi';

const MODULE_LABEL: Record<string, string> = {
  'tableau-de-bord': 'Tableau de bord',
  incidents: 'Incidents',
  demandes: 'Demandes',
  projets: 'Projets',
  changements: 'Changements',
  audit: 'Audit',
  risques: 'Risques',
  cybersecurite: 'Cybersécurité',
  gouvernance: 'Gouvernance',
  administration: 'Administration',
};

function formaterDateHeure(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ---------------------------------------------------------------- Utilisateurs

function OngletUtilisateurs({ signalCreation }: { signalCreation: number }): JSX.Element {
  const [items, setItems] = useState<Utilisateur[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [profils, setProfils] = useState<Profil[]>([]);
  const [directions, setDirections] = useState<Direction[]>([]);
  const [modale, setModale] = useState<null | { id: string | null }>(null);
  const [tempMdp, setTempMdp] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [nom, setNom] = useState('');
  const [prenom, setPrenom] = useState('');
  const [profil, setProfil] = useState('');
  const [direction, setDirection] = useState<string | null>(null);
  const [motDePasse, setMotDePasse] = useState('');
  const [actif, setActif] = useState(true);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async (p: number): Promise<void> => {
    setChargement(true);
    try {
      const data = await adminApi.utilisateurs(p);
      setItems(data.elements);
      setTotal(data.total);
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    void charger(page);
  }, [charger, page]);
  useEffect(() => {
    void adminApi.profils().then(setProfils);
    void adminApi.directions().then(setDirections);
  }, []);

  const ouvrirCreation = (): void => {
    setEmail('');
    setNom('');
    setPrenom('');
    setProfil('');
    setDirection(null);
    setMotDePasse('');
    setActif(true);
    setErreur(null);
    setModale({ id: null });
  };

  // Déclenché par le bouton "Nouvel utilisateur" remonté dans la barre d'onglets.
  useEffect(() => {
    if (signalCreation > 0) ouvrirCreation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signalCreation]);
  const ouvrirEdition = (u: Utilisateur): void => {
    setEmail(u.email);
    setNom(u.nom);
    setPrenom(u.prenom);
    setProfil(u.profil);
    setDirection(u.direction);
    setActif(u.actif);
    setErreur(null);
    setModale({ id: u.id });
  };

  const enregistrer = async (): Promise<void> => {
    setErreur(null);
    setEnvoi(true);
    try {
      if (modale?.id === null) {
        await adminApi.creerUtilisateur({
          email: email.trim(),
          nom: nom.trim(),
          prenom: prenom.trim(),
          profil_code: profil,
          direction_code: direction,
          mot_de_passe: motDePasse,
        });
      } else if (modale) {
        await adminApi.modifierUtilisateur(modale.id, {
          nom: nom.trim(),
          prenom: prenom.trim(),
          profil_code: profil,
          direction_code: direction,
          actif,
        });
      }
      setModale(null);
      await charger(page);
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Enregistrement impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const reinitialiser = async (u: Utilisateur): Promise<void> => {
    const r = await adminApi.reinitialiserMdp(u.id);
    setTempMdp(r.mot_de_passe_temporaire);
    await charger(page);
  };

  const colonnes: Colonne<Utilisateur>[] = [
    {
      cle: 'avatar',
      entete: '',
      largeur: '44px',
      rendu: (u) => <AvatarPersonnage seed={u.email} taille={32} />,
    },
    { cle: 'email', entete: 'E-mail', valeur: (u) => u.email },
    { cle: 'nom', entete: 'Nom', rendu: (u) => <strong>{`${u.prenom} ${u.nom}`}</strong> },
    { cle: 'profil', entete: 'Profil', rendu: (u) => <StatusBadge couleur="var(--cat-1)">{u.profil_libelle}</StatusBadge> },
    { cle: 'direction', entete: 'Direction', rendu: (u) => u.direction ?? '—' },
    {
      cle: 'actif',
      entete: 'Statut',
      rendu: (u) => (
        <StatusBadge statut={u.actif ? 'ok' : 'danger'}>{u.actif ? 'Actif' : 'Inactif'}</StatusBadge>
      ),
    },
    {
      cle: 'actions',
      entete: '',
      rendu: (u) => (
        <span className={a.actions}>
          <button className={a.iconBtn} title="Modifier" onClick={() => ouvrirEdition(u)}>
            <Pencil size={16} />
          </button>
          <button
            className={cx(a.iconBtn, a.danger)}
            title="Réinitialiser le mot de passe"
            onClick={() => void reinitialiser(u)}
          >
            <KeyRound size={16} />
          </button>
        </span>
      ),
    },
  ];

  return (
    <>
      <Table
        colonnes={colonnes}
        lignes={items}
        cleLigne={(u) => u.id}
        chargement={chargement}
        vide="Aucun utilisateur."
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <Modale
        ouverte={modale !== null}
        onFermer={() => setModale(null)}
        titre={modale?.id === null ? 'Nouvel utilisateur' : 'Modifier l’utilisateur'}
        pied={
          <>
            <Button variante="secondaire" onClick={() => setModale(null)}>
              Annuler
            </Button>
            <Button onClick={() => void enregistrer()} disabled={envoi}>
              {envoi ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </>
        }
      >
        {modale?.id === null && (
          <label className={styles.champ}>
            <span>E-mail</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="prenom.nom@afgbank.ml" />
          </label>
        )}
        <div className={styles.niveaux}>
          <label className={styles.champ}>
            <span>Prénom</span>
            <input value={prenom} onChange={(e) => setPrenom(e.target.value)} />
          </label>
          <label className={styles.champ}>
            <span>Nom</span>
            <input value={nom} onChange={(e) => setNom(e.target.value)} />
          </label>
        </div>
        <div className={styles.champ}>
          <span>Profil</span>
          <div className={styles.chips}>
            {profils.map((p) => (
              <button
                key={p.code}
                type="button"
                className={cx(p.code === profil ? styles.chipActif : styles.chip)}
                onClick={() => setProfil(p.code)}
              >
                {p.libelle}
              </button>
            ))}
          </div>
        </div>
        <div className={styles.champ}>
          <span>Direction (cloisonnement)</span>
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
        {modale?.id === null ? (
          <label className={styles.champ}>
            <span>Mot de passe initial (8+ car., à changer à la 1re connexion)</span>
            <input
              type="text"
              value={motDePasse}
              onChange={(e) => setMotDePasse(e.target.value)}
              placeholder="Mot de passe temporaire"
            />
          </label>
        ) : (
          <label className={styles.champ}>
            <span>Compte actif</span>
            <div className={styles.chips}>
              <button
                type="button"
                className={cx(actif ? styles.chipActif : styles.chip)}
                onClick={() => setActif(true)}
              >
                Actif
              </button>
              <button
                type="button"
                className={cx(!actif ? styles.chipActif : styles.chip)}
                onClick={() => setActif(false)}
              >
                Inactif
              </button>
            </div>
          </label>
        )}
        {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
      </Modale>

      <Modale
        ouverte={tempMdp !== null}
        onFermer={() => setTempMdp(null)}
        titre="Mot de passe réinitialisé"
        pied={
          <Button onClick={() => setTempMdp(null)}>Compris</Button>
        }
      >
        <div className={a.temp}>
          <span>Communiquez ce mot de passe temporaire à l’utilisateur. Il devra le changer à la connexion.</span>
          <span className={a.tempCode}>{tempMdp}</span>
        </div>
      </Modale>
    </>
  );
}

// ---------------------------------------------------------------- Accès

function OngletAcces(): JSX.Element {
  const [matrice, setMatrice] = useState<Matrice | null>(null);
  const [enregistre, setEnregistre] = useState<string | null>(null);

  useEffect(() => {
    void adminApi.acces().then(setMatrice);
  }, []);

  const basculer = async (profil: string, module: string): Promise<void> => {
    if (matrice === null) return;
    const role = matrice.roles.find((r) => r.profil === profil);
    if (!role) return;
    const nouveaux = role.acces.includes(module)
      ? role.acces.filter((m) => m !== module)
      : [...role.acces, module];
    setMatrice({
      ...matrice,
      roles: matrice.roles.map((r) => (r.profil === profil ? { ...r, acces: nouveaux } : r)),
    });
    await adminApi.definirAcces(profil, nouveaux);
    setEnregistre(profil);
    window.setTimeout(() => setEnregistre(null), 1200);
  };

  if (matrice === null) return <p style={{ color: 'var(--text-muted)' }}>Chargement…</p>;

  return (
    <div className={a.zone}>
      <table className={a.matrice}>
        <thead>
          <tr>
            <th>Profil</th>
            {matrice.modules.map((m) => (
              <th key={m}>{MODULE_LABEL[m] ?? m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrice.roles.map((r) => (
            <tr key={r.profil}>
              <td>
                {r.libelle}
                {enregistre === r.profil && (
                  <span style={{ color: 'var(--status-ok)', fontSize: 'var(--text-xs)', marginLeft: 8 }}>
                    enregistré
                  </span>
                )}
              </td>
              {matrice.modules.map((m) => {
                const actif = r.acces.includes(m);
                return (
                  <td key={m}>
                    <button
                      className={actif ? a.toggleOn : a.toggle}
                      onClick={() => void basculer(r.profil, m)}
                      aria-label={`${r.libelle} — ${m}`}
                    >
                      <span className={a.pastilleT} />
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- Journal

function OngletJournal(): JSX.Element {
  const [items, setItems] = useState<EntreeJournal[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);

  useEffect(() => {
    setChargement(true);
    void adminApi
      .journal(page)
      .then((d) => {
        setItems(d.elements);
        setTotal(d.total);
      })
      .finally(() => setChargement(false));
  }, [page]);

  const colonnes: Colonne<EntreeJournal>[] = [
    { cle: 'horodatage', entete: 'Date', rendu: (e) => formaterDateHeure(e.horodatage), largeur: '170px' },
    { cle: 'acteur', entete: 'Acteur', rendu: (e) => e.acteur ?? '—' },
    { cle: 'module', entete: 'Module', rendu: (e) => e.module ?? '—' },
    { cle: 'action', entete: 'Action', rendu: (e) => <StatusBadge couleur="var(--cat-7)">{e.action}</StatusBadge> },
    { cle: 'cible', entete: 'Cible', rendu: (e) => e.cible ?? '—' },
  ];

  return (
    <Table
      colonnes={colonnes}
      lignes={items}
      cleLigne={(e) => `${e.horodatage}-${e.action}-${e.cible ?? ''}`}
      chargement={chargement}
      vide="Journal vide."
      pagination={{ page, total, taille: 15, onPage: setPage }}
    />
  );
}

// ---------------------------------------------------------------- Page

export function AdministrationPage(): JSX.Element {
  const [onglet, setOnglet] = useState<'utilisateurs' | 'acces' | 'journal'>('utilisateurs');
  const [signalCreation, setSignalCreation] = useState(0);

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Administration</h1>
          <p className={styles.sous}>Utilisateurs, accès par profil et journal d’audit.</p>
        </div>
      </header>

      <div className={a.barreOnglets}>
        <div className={a.tabs}>
          <button
            className={onglet === 'utilisateurs' ? a.tabActif : a.tab}
            onClick={() => setOnglet('utilisateurs')}
          >
            Utilisateurs
          </button>
          <button className={onglet === 'acces' ? a.tabActif : a.tab} onClick={() => setOnglet('acces')}>
            Accès
          </button>
          <button
            className={onglet === 'journal' ? a.tabActif : a.tab}
            onClick={() => setOnglet('journal')}
          >
            Journal d’audit
          </button>
        </div>
        {onglet === 'utilisateurs' && (
          <div className={a.barreAction}>
            <Button onClick={() => setSignalCreation((n) => n + 1)}>
              <Plus size={16} />
              Nouvel utilisateur
            </Button>
          </div>
        )}
      </div>

      {onglet === 'utilisateurs' && <OngletUtilisateurs signalCreation={signalCreation} />}
      {onglet === 'acces' && <OngletAcces />}
      {onglet === 'journal' && <OngletJournal />}
    </div>
  );
}
