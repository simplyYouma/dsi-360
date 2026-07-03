import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { cx } from '@/common/cx';
import styles from './Toast.module.css';

export type TonToast = 'succes' | 'erreur' | 'info';

interface ItemToast {
  id: number;
  ton: TonToast;
  message: string;
}

interface ApiToast {
  /** Affiche un toast éphémère (auto-fermeture). */
  notifier: (message: string, ton?: TonToast) => void;
}

const ContexteToast = createContext<ApiToast | null>(null);
const DUREE_MS = 4500;
const ICONE: Record<TonToast, typeof Info> = {
  succes: CheckCircle2,
  erreur: AlertCircle,
  info: Info,
};

/** Fournisseur de toasts maison (zéro composant natif). À monter une fois, près de la racine. */
export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const [items, setItems] = useState<ItemToast[]>([]);
  const compteur = useRef(0);

  const retirer = useCallback((id: number): void => {
    setItems((liste) => liste.filter((t) => t.id !== id));
  }, []);

  const notifier = useCallback((message: string, ton: TonToast = 'info'): void => {
    compteur.current += 1;
    const id = compteur.current;
    setItems((liste) => [...liste, { id, ton, message }]);
  }, []);

  return (
    <ContexteToast.Provider value={{ notifier }}>
      {children}
      {createPortal(
        <div className={styles.zone} role="region" aria-label="Notifications">
          {items.map((t) => (
            <Toast key={t.id} item={t} onFermer={() => retirer(t.id)} />
          ))}
        </div>,
        document.body,
      )}
    </ContexteToast.Provider>
  );
}

function Toast({ item, onFermer }: { item: ItemToast; onFermer: () => void }): JSX.Element {
  const Icone = ICONE[item.ton];
  useEffect(() => {
    const minuteur = setTimeout(onFermer, DUREE_MS);
    return () => clearTimeout(minuteur);
  }, [onFermer]);
  return (
    <div className={cx(styles.toast, styles[item.ton])} role="status">
      <span className={styles.icone}>
        <Icone size={18} />
      </span>
      <span className={styles.message}>{item.message}</span>
      <button type="button" className={styles.fermer} onClick={onFermer} aria-label="Fermer">
        <X size={15} />
      </button>
    </div>
  );
}

/** Accès à l'API de toasts. À utiliser sous un ToastProvider. */
export function useToast(): ApiToast {
  const ctx = useContext(ContexteToast);
  if (ctx === null) throw new Error('useToast doit être utilisé dans un ToastProvider.');
  return ctx;
}
