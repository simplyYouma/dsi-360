import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx } from '@/common/cx';
import styles from './Button.module.css';

type Variante = 'primaire' | 'secondaire' | 'fantome' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  pleineLargeur?: boolean;
  children: ReactNode;
}

export function Button({
  variante = 'primaire',
  pleineLargeur = false,
  className,
  children,
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      className={cx(styles.btn, styles[variante], pleineLargeur && styles.pleineLargeur, className)}
      {...rest}
    >
      {children}
    </button>
  );
}
