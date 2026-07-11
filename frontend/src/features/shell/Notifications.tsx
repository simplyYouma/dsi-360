import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, Inbox, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { couleurStatut } from '@/common/statuts';
import { lienActivite } from '@/common/routesModule';
import { useRafraichissement } from '@/common/useRafraichissement';
import { jouerSonNotif } from '@/common/sonNotif';
import { cx } from '@/common/cx';
import styles from './Notifications.module.css';

interface Notif {
  id: number;
  type: string;
  titre: string;
  message: string;
  lu: boolean;
  cree_le: string;
  module: string | null;
  activite_id: string | null;
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
  const navigate = useNavigate();
  const [ouvert, setOuvert] = useState(false);
  const [elements, setElements] = useState<Notif[]>([]);
  const [nonLus, setNonLus] = useState(0);
  // Compteur précédent : un carillon ne sonne qu'à l'arrivée d'un nouveau non-lu, jamais au
  // premier chargement ni quand on marque comme lu.
  const precedentNonLus = useRef<number | null>(null);

  const charger = useCallback(async (): Promise<void> => {
    const data = await api.get<{ elements: Notif[]; non_lus: number }>('/notifications');
    setElements(data.elements);
    setNonLus(data.non_lus);
    if (precedentNonLus.current !== null && data.non_lus > precedentNonLus.current) {
      jouerSonNotif();
    }
    precedentNonLus.current = data.non_lus;
  }, []);

  useEffect(() => {
    void charger();
  }, [charger]);

  // La pastille se met à jour seule : sans cela, elle reste muette jusqu'au prochain rechargement.
  useRafraichissement(() => void charger());

  const toutLu = async (): Promise<void> => {
    await api.post('/notifications/tout-lu');
    await charger();
  };

  const ouvrirSujet = (n: Notif): void => {
    const lien = n.activite_id ? lienActivite(n.module ?? '', n.activite_id) : null;
    if (lien === null) return;
    setOuvert(false);
    navigate(lien);
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
              <div className={styles.actionsTete}>
                {nonLus > 0 && (
                  <button className={styles.lien} onClick={() => void toutLu()}>
                    <CheckCheck size={15} />
                    Tout lire
                  </button>
                )}
              </div>
            </div>

            {elements.length === 0 ? (
              <div className={styles.vide}>
                <Inbox size={26} />
                <span>Aucune notification.</span>
              </div>
            ) : (
              <ul className={styles.liste}>
                {elements.map((n) => {
                  const cliquable = n.activite_id !== null && n.module !== null;
                  const classe = cx(
                    n.lu ? styles.item : styles.itemNonLu,
                    cliquable && styles.cliquable,
                  );
                  const contenu = (
                    <>
                      <span
                        className={styles.barre}
                        style={{ background: TON[n.type] ?? couleurStatut(n.type) }}
                      />
                      <div className={styles.corps}>
                        <span className={styles.itemTitre}>{n.titre}</span>
                        <span className={styles.itemMsg}>{n.message}</span>
                        <span className={styles.itemDate}>{formaterDate(n.cree_le)}</span>
                      </div>
                      {cliquable && <ChevronRight size={16} className={styles.fleche} />}
                    </>
                  );
                  return (
                    <li key={n.id}>
                      {cliquable ? (
                        <button type="button" className={classe} onClick={() => ouvrirSujet(n)}>
                          {contenu}
                        </button>
                      ) : (
                        <div className={classe}>{contenu}</div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
