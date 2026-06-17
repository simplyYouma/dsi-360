/** Client API minimal : base /api/v1, jeton Bearer, rafraîchissement automatique sur 401. */

const BASE = '/api/v1';
const CLE_ACCES = 'dsi360.acces';
const CLE_REFRESH = 'dsi360.refresh';

let acces: string | null = localStorage.getItem(CLE_ACCES);
let refresh: string | null = localStorage.getItem(CLE_REFRESH);

export function definirJetons(a: string, r: string): void {
  acces = a;
  refresh = r;
  localStorage.setItem(CLE_ACCES, a);
  localStorage.setItem(CLE_REFRESH, r);
}

export function effacerJetons(): void {
  acces = null;
  refresh = null;
  localStorage.removeItem(CLE_ACCES);
  localStorage.removeItem(CLE_REFRESH);
}

export function aUnJeton(): boolean {
  return acces !== null;
}

export class ErreurApi extends Error {
  constructor(
    public statut: number,
    message: string,
  ) {
    super(message);
  }
}

async function tenterRafraichir(): Promise<boolean> {
  if (refresh === null) return false;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return false;
  const data = (await res.json()) as { acces: string; refresh: string };
  definirJetons(data.acces, data.refresh);
  return true;
}

async function requete<T>(chemin: string, options: RequestInit = {}, reessayer = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (acces !== null) headers.set('Authorization', `Bearer ${acces}`);
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');

  const res = await fetch(`${BASE}${chemin}`, { ...options, headers });

  if (res.status === 401 && reessayer && (await tenterRafraichir())) {
    return requete<T>(chemin, options, false);
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const corps = (await res.json()) as { detail?: string };
      if (corps.detail !== undefined) message = corps.detail;
    } catch {
      /* corps non JSON */
    }
    throw new ErreurApi(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(chemin: string): Promise<T> => requete<T>(chemin),
  post: <T>(chemin: string, corps?: unknown): Promise<T> =>
    requete<T>(
      chemin,
      corps === undefined ? { method: 'POST' } : { method: 'POST', body: JSON.stringify(corps) },
    ),
};
