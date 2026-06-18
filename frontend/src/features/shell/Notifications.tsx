import { useCallback, useEffect, useState } from 'react';
import { Bell, CheckCheck, Inbox, Settings, ArrowLeft } from 'lucide-react';
import { api } from '@/lib/api';
import { couleurStatut } from '@/common/statuts';
import styles from './Notifications.module.css';

interface Notif {
  id: number;
  type: string;
  titre: string;
  message: string;
  lu: boolean;
  cree_le: string;
}
interface Preferences {
  interne: boolean;
  email: boolean;
  teams: boolean;
  whatsapp: boolean;
}

const TON: Record<string, string> = {
  SLA_DEPASSE: 'var(--status-danger)',
  SLA_APPROCHE: 'var(--status-warn)',
};

const CANAUX: { cle: keyof Preferences; libelle: string; phase2?: boolean }[] = [
  { cle: 'interne', libelle: 'Notifications internes' },
  { cle: 'email', libelle: 'E-mail' },
  { cle: 'teams', libelle: 'Microsoft Teams', phase2: true },
  { cle: 'whatsapp', libelle: 'WhatsApp', phase2: true },
];

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function Notifications(): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [vuePref, setVuePref] = useState(false);
  const [elements, setElements] = useState<Notif[]>([]);
  const [nonLus, setNonLus] = useState(0);
  const [pref, setPref] = useState<Preferences | null>(null);

  const charger = useCallback(async (): Promise<void> => {
    const data = await api.get<{ elements: Notif[]; non_lus: number }>('/notifications');
    setElements(data.elements);
    setNonLus(data.non_lus);
  }, []);

  useEffect(() => {
    void charger();
  }, [charger]);

  const toutLu = async (): Promise<void> => {
    await api.post('/notifications/tout-lu');
    await charger();
  };

  const ouvrirPref = async (): Promise<void> => {
    setVuePref(true);
    setPref(await api.get<Preferences>('/notifications/preferences'));
  };

  const basculer = async (cle: keyof Preferences): Promise<void> => {
    if (pref === null) return;
    const maj = { ...pref, [cle]: !pref[cle] };
    setPref(maj);
    await api.put('/notifications/preferences', maj);
  };

  return (
    <div className={styles.conteneur}>
      <button
        className={styles.cloche}
        onClick={() => {
          setOuvert((o) => !o);
          setVuePref(false);
          void charger();
        }}
        aria-label="Notifications"
      >
        <Bell size={20} />
        {nonLus > 0 && <span className={styles.pastille}>{nonLus > 9 ? '9+' : nonLus}</span>}
      </button>

      {ouvert && (
        <>
          <div className={styles.voile} onClick={() => setOuvert(false)} />
          <div className={styles.panneau}>
            <div className={styles.tete}>
              {vuePref ? (
                <button className={styles.lien} onClick={() => setVuePref(false)}>
                  <ArrowLeft size={15} />
                  Notifications
                </button>
              ) : (
                <span className={styles.titre}>Notifications</span>
              )}
              <div className={styles.actionsTete}>
                {!vuePref && nonLus > 0 && (
                  <button className={styles.lien} onClick={() => void toutLu()}>
                    <CheckCheck size={15} />
                    Tout lire
                  </button>
                )}
                {!vuePref && (
                  <button className={styles.icone} onClick={() => void ouvrirPref()} aria-label="Préférences">
                    <Settings size={16} />
                  </button>
                )}
              </div>
            </div>

            {vuePref ? (
              <ul className={styles.canaux}>
                {CANAUX.map((c) => {
                  const actif = pref?.[c.cle] ?? false;
                  return (
                    <li key={c.cle} className={styles.canal}>
                      <span className={styles.canalNom}>
                        {c.libelle}
                        {c.phase2 && <span className={styles.tag}>Phase 2</span>}
                      </span>
                      <button
                        className={actif ? styles.toggleOn : styles.toggle}
                        disabled={c.phase2 || pref === null}
                        onClick={() => void basculer(c.cle)}
                        aria-label={c.libelle}
                      >
                        <span className={styles.pastilleT} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : elements.length === 0 ? (
              <div className={styles.vide}>
                <Inbox size={26} />
                <span>Aucune notification.</span>
              </div>
            ) : (
              <ul className={styles.liste}>
                {elements.map((n) => (
                  <li key={n.id} className={n.lu ? styles.item : styles.itemNonLu}>
                    <span
                      className={styles.barre}
                      style={{ background: TON[n.type] ?? couleurStatut(n.type) }}
                    />
                    <div className={styles.corps}>
                      <span className={styles.itemTitre}>{n.titre}</span>
                      <span className={styles.itemMsg}>{n.message}</span>
                      <span className={styles.itemDate}>{formaterDate(n.cree_le)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
