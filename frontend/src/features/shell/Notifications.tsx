import { useCallback, useEffect, useState } from 'react';
import { Bell, CheckCheck, Inbox } from 'lucide-react';
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

const TON: Record<string, string> = {
  SLA_DEPASSE: 'var(--status-danger)',
  SLA_APPROCHE: 'var(--status-warn)',
};

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
  const [elements, setElements] = useState<Notif[]>([]);
  const [nonLus, setNonLus] = useState(0);

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

  return (
    <div className={styles.conteneur}>
      <button
        className={styles.cloche}
        onClick={() => {
          setOuvert((o) => !o);
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
              <span className={styles.titre}>Notifications</span>
              {nonLus > 0 && (
                <button className={styles.toutLu} onClick={() => void toutLu()}>
                  <CheckCheck size={15} />
                  Tout lire
                </button>
              )}
            </div>
            {elements.length === 0 ? (
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
