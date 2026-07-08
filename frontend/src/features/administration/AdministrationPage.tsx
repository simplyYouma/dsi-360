import { useCallback, useEffect, useState } from 'react';
import { Plus, Pencil, KeyRound, Dices, Trash2, Ban, ShieldCheck, Check } from 'lucide-react';
import { Button, Modale, StatusBadge, Table, useToast, type Colonne } from '@/design-system/primitives';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import { SelecteurListe } from '@/common/SelecteurListe';
import { SelecteurDate } from '@/common/SelecteurDate';
import { BadgePriorite } from '@/common/statuts';
import { categoriesApi } from '@/common/categoriesApi';
import { cx } from '@/common/cx';
import { api, ErreurApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { genererMotDePasse } from '@/common/motDePasse';
import styles from '@/features/incidents/IncidentsPage.module.css';
import a from './AdministrationPage.module.css';
import {
  adminApi,
  type Direction,
  type EntreeJournal,
  type Matrice,
  type Profil,
  type SlaRegle,
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
  const { notifier } = useToast();
  const { moi } = useAuth();

  const [email, setEmail] = useState('');
  const [nom, setNom] = useState('');
  const [prenom, setPrenom] = useState('');
  const [profil, setProfil] = useState('');
  const [direction, setDirection] = useState<string | null>(null);
  const [niveau, setNiveau] = useState<string | null>(null);
  const [motDePasse, setMotDePasse] = useState('');
  const [actif, setActif] = useState(true);
  const [temporaire, setTemporaire] = useState(false);
  const [expiration, setExpiration] = useState<string | null>(null);
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
    setNiveau(null);
    setMotDePasse(genererMotDePasse()); // un mot de passe provisoire unique par utilisateur
    setActif(true);
    setTemporaire(false);
    setExpiration(null);
    setErreur(null);
    setModale({ id: null });
  };

  // Déclenché par le bouton "Nouvel utilisateur" remonté dans la barre d'onglets.
  useEffect(() => {
    if (signalCreation > 0) ouvrirCreation();
     
  }, [signalCreation]);
  const ouvrirEdition = (u: Utilisateur): void => {
    setEmail(u.email);
    setNom(u.nom);
    setPrenom(u.prenom);
    setProfil(u.profil);
    setDirection(u.direction);
    setNiveau(u.niveau_support !== null ? String(u.niveau_support) : null);
    setActif(u.actif);
    setTemporaire(u.expire_le !== null);
    setExpiration(u.expire_le ? u.expire_le.slice(0, 10) : null);
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
          niveau_support: niveau !== null ? Number(niveau) : null,
          mot_de_passe: motDePasse,
          expire_le: temporaire ? expiration : null,
        });
      } else if (modale) {
        await adminApi.modifierUtilisateur(modale.id, {
          nom: nom.trim(),
          prenom: prenom.trim(),
          profil_code: profil,
          direction_code: direction,
          niveau_support: niveau !== null ? Number(niveau) : null,
          actif,
          expire_le: temporaire ? expiration : null,
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

  // Blocage / déblocage immédiat (appliqué côté serveur à chaque requête, sans contournement).
  const basculerActif = async (u: Utilisateur): Promise<void> => {
    try {
      await adminApi.modifierUtilisateur(u.id, {
        nom: u.nom,
        prenom: u.prenom,
        profil_code: u.profil,
        direction_code: u.direction,
        niveau_support: u.niveau_support,
        actif: !u.actif,
        expire_le: u.expire_le,
      });
      await charger(page);
      notifier(u.actif ? 'Accès bloqué' : 'Accès rétabli', 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Action impossible.', 'erreur');
    }
  };

  const statutUtilisateur = (u: Utilisateur): JSX.Element => {
    if (!u.actif) return <StatusBadge statut="danger">Bloqué</StatusBadge>;
    if (u.expire_le !== null && new Date(u.expire_le) <= new Date())
      return <StatusBadge statut="danger">Expiré</StatusBadge>;
    if (u.expire_le !== null)
      return (
        <StatusBadge statut="warn">
          Jusqu’au{' '}
          {new Date(u.expire_le).toLocaleDateString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
          })}
        </StatusBadge>
      );
    return <StatusBadge statut="ok">Actif</StatusBadge>;
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
      cle: 'niveau',
      entete: 'Niveau',
      rendu: (u) =>
        u.niveau_support !== null ? (
          <StatusBadge couleur="var(--cat-4)">N{u.niveau_support}</StatusBadge>
        ) : (
          <span style={{ color: 'var(--text-muted)' }}>—</span>
        ),
    },
    {
      cle: 'actif',
      entete: 'Statut',
      rendu: (u) => statutUtilisateur(u),
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
            className={a.iconBtn}
            title="Réinitialiser le mot de passe"
            onClick={() => void reinitialiser(u)}
          >
            <KeyRound size={16} />
          </button>
          {u.id !== moi?.id &&
            (u.actif ? (
              <button
                className={cx(a.iconBtn, a.danger)}
                title="Bloquer l’accès"
                onClick={() => void basculerActif(u)}
              >
                <Ban size={16} />
              </button>
            ) : (
              <button
                className={a.iconBtn}
                title="Rétablir l’accès"
                onClick={() => void basculerActif(u)}
              >
                <ShieldCheck size={16} />
              </button>
            ))}
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
        <div className={styles.niveaux}>
          <div className={styles.champ}>
            <span>Profil</span>
            <SelecteurListe
              options={profils.map((p) => ({ valeur: p.code, libelle: p.libelle }))}
              valeur={profil === '' ? null : profil}
              onChange={(v) => setProfil(v ?? '')}
              placeholder="Choisir un profil"
            />
          </div>
          <div className={styles.champ}>
            <span>Direction (cloisonnement)</span>
            <SelecteurListe
              options={directions.map((d) => ({ valeur: d.code, libelle: d.libelle }))}
              valeur={direction}
              onChange={setDirection}
              permettreVide
              libelleVide="Aucune (transverse)"
              placeholder="Choisir une direction"
            />
          </div>
        </div>
        <div className={styles.champ}>
          <span>Niveau de support (escalade)</span>
          <SelecteurListe
            options={[
              { valeur: '1', libelle: 'N1 — Service Desk' },
              { valeur: '2', libelle: 'N2 — Expert' },
              { valeur: '3', libelle: 'N3 — Référent' },
            ]}
            valeur={niveau}
            onChange={setNiveau}
            permettreVide
            libelleVide="Aucun (pas un gestionnaire de support)"
            placeholder="Choisir un niveau"
          />
        </div>
        <div className={styles.champ}>
          <button
            type="button"
            className={a.caseLigne}
            onClick={() => {
              const v = !temporaire;
              setTemporaire(v);
              if (!v) setExpiration(null);
            }}
          >
            <span className={cx(a.case, temporaire && a.caseOn)}>
              {temporaire && <Check size={13} />}
            </span>
            Compte temporaire (l’accès expire à une date)
          </button>
          {temporaire && (
            <div style={{ marginTop: 'var(--space-2)' }}>
              <SelecteurDate
                valeur={expiration}
                onChange={setExpiration}
                placeholder="Choisir la date d’expiration"
              />
            </div>
          )}
        </div>
        {modale?.id === null ? (
          <label className={styles.champ}>
            <span>Mot de passe initial (8+ car., à changer à la 1re connexion)</span>
            <div className={a.champMdp}>
              <input
                type="text"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
                placeholder="Mot de passe temporaire"
              />
              <button
                type="button"
                className={a.genererMdp}
                title="Générer un mot de passe aléatoire"
                onClick={() => setMotDePasse(genererMotDePasse())}
              >
                <Dices size={16} />
              </button>
            </div>
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
    <div className={cx(a.zone, a.zoneRemplir)}>
      <table className={cx(a.matrice, a.matriceRemplir)}>
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

// ---------------------------------------------------------------- SLA

/** Convertit des minutes en durée lisible (15 min, 4 h, 2 j) pour lever l'ambiguïté des décimales. */
function formaterDureeSla(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) {
    const h = minutes / 60;
    return `${Number.isInteger(h) ? h : h.toFixed(2)} h`;
  }
  const j = minutes / (60 * 24);
  return `${Number.isInteger(j) ? j : j.toFixed(1)} j`;
}

const LIBELLES_MODULE_SLA: Record<string, string> = {
  incident: 'Incidents',
  demande: 'Demandes',
  changement: 'Changements',
  cybersecurite: 'Cybersécurité',
};

function OngletSla(): JSX.Element {
  const [modules, setModules] = useState<string[]>([]);
  const [moduleSel, setModuleSel] = useState<string>('');
  const [regles, setRegles] = useState<SlaRegle[]>([]);
  const [enregistre, setEnregistre] = useState(false);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    void adminApi.modulesSla().then((m) => {
      setModules(m);
      setModuleSel((sel) => sel || m[0] || '');
    });
  }, []);

  useEffect(() => {
    if (moduleSel !== '') void adminApi.sla(moduleSel).then(setRegles);
  }, [moduleSel]);

  const majHeures = (priorite: number, champ: keyof SlaRegle, heures: string): void => {
    const minutes = Math.max(1, Math.round(Number(heures) * 60));
    setRegles((rs) => rs.map((r) => (r.priorite === priorite ? { ...r, [champ]: minutes } : r)));
  };

  const enregistrer = async (): Promise<void> => {
    setEnvoi(true);
    try {
      await adminApi.definirSla(moduleSel, regles);
      setEnregistre(true);
      window.setTimeout(() => setEnregistre(false), 1500);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={a.zone} style={{ padding: 'var(--space-4)' }}>
      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginBottom: 'var(--space-4)' }}>
        {modules.map((m) => (
          <button
            key={m}
            type="button"
            className={m === moduleSel ? a.tabActif : a.tab}
            onClick={() => setModuleSel(m)}
          >
            {LIBELLES_MODULE_SLA[m] ?? m}
          </button>
        ))}
      </div>
      <p className={styles.sous} style={{ marginBottom: 'var(--space-4)' }}>
        Cibles propres à <strong>{LIBELLES_MODULE_SLA[moduleSel] ?? moduleSel}</strong>, par priorité,{' '}
        <strong>en heures</strong> : <strong>prise en charge</strong> (démarrage) et{' '}
        <strong>résolution</strong> (clôture). Un incident P1 peut différer d'une demande P1.
      </p>
      <table className={cx(a.matrice, a.matriceSla)}>
        <thead>
          <tr>
            <th>Priorité</th>
            <th>Prise en charge (h)</th>
            <th>Résolution (h)</th>
          </tr>
        </thead>
        <tbody>
          {regles.map((r) => (
            <tr key={r.priorite}>
              <td>
                <BadgePriorite priorite={r.priorite} />
              </td>
              <td>
                <div className={a.slaCellule}>
                  <input
                    className={a.slaInput}
                    type="number"
                    min="0.25"
                    step="0.25"
                    value={r.prise_en_charge_minutes / 60}
                    onChange={(e) =>
                      majHeures(r.priorite, 'prise_en_charge_minutes', e.target.value)
                    }
                  />
                  <span className={a.slaEquiv}>= {formaterDureeSla(r.prise_en_charge_minutes)}</span>
                </div>
              </td>
              <td>
                <div className={a.slaCellule}>
                  <input
                    className={a.slaInput}
                    type="number"
                    min="0.25"
                    step="0.25"
                    value={r.resolution_minutes / 60}
                    onChange={(e) => majHeures(r.priorite, 'resolution_minutes', e.target.value)}
                  />
                  <span className={a.slaEquiv}>= {formaterDureeSla(r.resolution_minutes)}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
        <Button onClick={() => void enregistrer()} disabled={envoi}>
          {envoi ? 'Enregistrement…' : 'Enregistrer les règles'}
        </Button>
        {enregistre && (
          <span style={{ color: 'var(--status-ok)', fontSize: 'var(--text-sm)' }}>Enregistré</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Catégories

interface CategorieAdmin {
  id: string;
  code: string;
  libelle: string;
}

// Changement exclu : ses types (Standard/Normal/Urgent) sont un vocabulaire ITIL fixe.
const MODULES_CATEGORIE: { code: string; libelle: string }[] = [
  { code: 'incident', libelle: 'Incidents' },
  { code: 'demande', libelle: 'Demandes' },
  { code: 'audit', libelle: 'Audit & recommandations' },
  { code: 'risque', libelle: 'Risques' },
  { code: 'cybersecurite', libelle: 'Cybersécurité' },
  { code: 'gouvernance', libelle: 'Gouvernance' },
];

function OngletCategories(): JSX.Element {
  const { notifier } = useToast();
  const [module, setModule] = useState('incident');
  const [categories, setCategories] = useState<CategorieAdmin[]>([]);
  const [nouveau, setNouveau] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const charger = useCallback((): void => {
    void api
      .get<CategorieAdmin[]>(`/referentiels/categories?module=${module}`)
      .then(setCategories);
  }, [module]);
  useEffect(() => {
    charger();
  }, [charger]);

  const ajouter = async (): Promise<void> => {
    const libelle = nouveau.trim();
    if (libelle === '') return;
    setEnvoi(true);
    try {
      await categoriesApi.creer(module, libelle);
      setNouveau('');
      charger();
      notifier('Catégorie ajoutée', 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Ajout impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  const supprimer = async (id: string): Promise<void> => {
    setEnvoi(true);
    try {
      await categoriesApi.supprimer(id);
      charger();
      notifier('Catégorie supprimée', 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Suppression impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={a.zone} style={{ padding: 'var(--space-4)' }}>
      <p className={styles.sous} style={{ marginBottom: 'var(--space-4)' }}>
        Catégories par module (paramétrage). Ajout/suppression aussi disponible en ligne dans les
        formulaires. Une catégorie déjà utilisée par des activités ne peut pas être supprimée.
      </p>
      <div style={{ maxWidth: 280, marginBottom: 'var(--space-4)' }}>
        <SelecteurListe
          options={MODULES_CATEGORIE.map((m) => ({ valeur: m.code, libelle: m.libelle }))}
          valeur={module}
          onChange={(v) => setModule(v ?? 'incident')}
        />
      </div>
      <table className={a.matrice}>
        <thead>
          <tr>
            <th>Libellé</th>
            <th>Code</th>
            <th style={{ width: 60, textAlign: 'right' }} />
          </tr>
        </thead>
        <tbody>
          {categories.map((c) => (
            <tr key={c.id}>
              <td>{c.libelle}</td>
              <td style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                {c.code}
              </td>
              <td style={{ textAlign: 'right' }}>
                <button
                  type="button"
                  className={a.supprCat}
                  disabled={envoi}
                  title="Supprimer"
                  aria-label={`Supprimer ${c.libelle}`}
                  onClick={() => void supprimer(c.id)}
                >
                  <Trash2 size={15} />
                </button>
              </td>
            </tr>
          ))}
          {categories.length === 0 && (
            <tr>
              <td colSpan={3} style={{ color: 'var(--text-muted)' }}>
                Aucune catégorie pour ce module.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-4)', maxWidth: 420 }}>
        <input
          className={a.slaInput}
          style={{ flex: 1, textAlign: 'left' }}
          value={nouveau}
          placeholder="Nouvelle catégorie"
          onChange={(e) => setNouveau(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void ajouter();
            }
          }}
        />
        <Button onClick={() => void ajouter()} disabled={envoi || nouveau.trim() === ''}>
          <Plus size={16} />
          Ajouter
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Page

export function AdministrationPage(): JSX.Element {
  const [onglet, setOnglet] = useState<
    'utilisateurs' | 'acces' | 'journal' | 'sla' | 'categories'
  >('utilisateurs');
  const [signalCreation, setSignalCreation] = useState(0);

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>Administration</h1>
          <p className={styles.sous}>Utilisateurs, accès, catégories, SLA et journal d’audit.</p>
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
            className={onglet === 'categories' ? a.tabActif : a.tab}
            onClick={() => setOnglet('categories')}
          >
            Catégories
          </button>
          <button className={onglet === 'sla' ? a.tabActif : a.tab} onClick={() => setOnglet('sla')}>
            SLA
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
      {onglet === 'sla' && <OngletSla />}
      {onglet === 'categories' && <OngletCategories />}
    </div>
  );
}
