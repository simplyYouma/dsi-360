import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, ChevronRight, Inbox, Volume2, VolumeX } from 'lucide-react';
import { api } from '@/lib/api';
import { couleurStatut } from '@/common/statuts';
import { lienActivite } from '@/common/routesModule';
import { useRafraichissement } from '@/common/useRafraichissement';
import { armerSonNotif, jouerSonNotif } from '@/common/sonNotif';
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
// Réglage local du carillon (par navigateur) : il n'engage que ce poste.
const CLE_SON = 'dsi360-son-notif';

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
  // Le réglage survit au rechargement, et le son est actif par défaut : une notification qu'on
  // n'entend pas ne sert à rien, c'est à l'agent de demander le silence s'il le souhaite.
  const [son, setSon] = useState(() => localStorage.getItem(CLE_SON) !== 'non');
  const sonRef = useRef(son);
  sonRef.current = son;

  const charger = useCallback(async (): Promise<void> => {
    const data = await api.get<{ elements: Notif[]; non_lus: number }>('/notifications');
    setElements(data.elements);
    setNonLus(data.non_lus);
    if (
      sonRef.current &&
      precedentNonLus.current !== null &&
      data.non_lus > precedentNonLus.current
    ) {
      jouerSonNotif();
    }
    precedentNonLus.current = data.non_lus;
  }, []);

  useEffect(() => {
    void charger();
  }, [charger]);

  // Le navigateur n'autorise le son qu'après une interaction : on arme le déblocage au premier
  // clic. Sans cela, le carillon reste inaudible pour toute la session, sans le moindre message.
  useEffect(() => armerSonNotif(), []);

  // La pastille se met à jour seule : sans cela, elle reste muette jusqu'au prochain rechargement.
  useRafraichissement(() => void charger());

  const toutLu = async (): Promise<void> => {
    await api.post('/notifications/tout-lu');
    await charger();
  };

  const ouvrirSujet = (n: Notif): void => {
    const lien = n.activite_id ? lienActivite(n.module ?? '', n.activite_id) : null;
    if (lien === null) return;
    // Entrer dans une notif la marque lue (côté serveur + affichage immédiat).
    if (!n.lu) {
      void api.post(`/notifications/${n.id}/lu`);
      setElements((prev) => prev.map((x) => (x.id === n.id ? { ...x, lu: true } : x)));
      setNonLus((c) => Math.max(0, c - 1));
      if (precedentNonLus.current !== null) {
        precedentNonLus.current = Math.max(0, precedentNonLus.current - 1);
      }
    }
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
                {/* Réglage ET preuve : activer le son le joue aussitôt, donc on l'entend. */}
                <button
                  className={styles.lien}
                  onClick={() => {
                    const suivant = !son;
                    setSon(suivant);
                    localStorage.setItem(CLE_SON, suivant ? 'oui' : 'non');
                    if (suivant) jouerSonNotif();
                  }}
                  aria-pressed={son}
                  title={
                    son ? 'Son activé — cliquer pour couper' : 'Son coupé — cliquer pour activer'
                  }
                >
                  {son ? <Volume2 size={15} /> : <VolumeX size={15} />}
                  {son ? 'Son' : 'Muet'}
                </button>
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
