/** Client API minimal : base /api/v1, jeton Bearer, rafraîchissement automatique sur 401. */

const BASE = '/api/v1';
const CLE_ACCES = 'dsi360.acces';
const CLE_REFRESH = 'dsi360.refresh';
// Jetons réels mis de côté pendant qu'on incarne un autre compte (développement seulement).
// Conservés au même endroit que les autres : on doit pouvoir revenir à soi après un F5.
const CLE_ACCES_REEL = 'dsi360.reel.acces';
const CLE_REFRESH_REEL = 'dsi360.reel.refresh';

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
  localStorage.removeItem(CLE_ACCES_REEL);
  localStorage.removeItem(CLE_REFRESH_REEL);
}

export function aUnJeton(): boolean {
  return acces !== null;
}

/** Met ses propres jetons de côté et prend ceux du compte incarné. */
export function commencerIncarnation(a: string, r: string): void {
  if (acces !== null && refresh !== null && !incarneUnCompte()) {
    localStorage.setItem(CLE_ACCES_REEL, acces);
    localStorage.setItem(CLE_REFRESH_REEL, refresh);
  }
  definirJetons(a, r);
}

/** Reprend ses jetons. Sans effet si l'on n'incarnait personne. */
export function cesserIncarnation(): void {
  const a = localStorage.getItem(CLE_ACCES_REEL);
  const r = localStorage.getItem(CLE_REFRESH_REEL);
  localStorage.removeItem(CLE_ACCES_REEL);
  localStorage.removeItem(CLE_REFRESH_REEL);
  if (a !== null && r !== null) definirJetons(a, r);
}

export function incarneUnCompte(): boolean {
  return localStorage.getItem(CLE_ACCES_REEL) !== null;
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

  let res: Response;
  try {
    res = await fetch(`${BASE}${chemin}`, { ...options, headers });
  } catch {
    // Serveur injoignable (réseau coupé, serveur tombé) : un message clair, pas un
    // « Failed to fetch » cryptique. statut 0 = pas de réponse HTTP.
    throw new ErreurApi(0, 'Service injoignable. Vérifiez votre connexion, puis réessayez.');
  }

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

/** Télécharge un fichier protégé (jeton Bearer) et déclenche l'enregistrement navigateur. */
export async function telecharger(chemin: string): Promise<void> {
  const headers = new Headers();
  if (acces !== null) headers.set('Authorization', `Bearer ${acces}`);
  let res = await fetch(`${BASE}${chemin}`, { headers });
  if (res.status === 401 && (await tenterRafraichir())) {
    if (acces !== null) headers.set('Authorization', `Bearer ${acces}`);
    res = await fetch(`${BASE}${chemin}`, { headers });
  }
  if (!res.ok) throw new ErreurApi(res.status, res.statusText);
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const correspondance = /filename=([^;]+)/.exec(disposition);
  const nom = correspondance?.[1]?.trim() ?? 'export';
  const url = URL.createObjectURL(blob);
  const lien = document.createElement('a');
  lien.href = url;
  lien.download = nom;
  lien.click();
  URL.revokeObjectURL(url);
}

/** Récupère un fichier protégé sous forme de Blob (pour un aperçu in-app). Bearer + réessai 401. */
export async function recupererBlob(chemin: string): Promise<Blob> {
  const headers = new Headers();
  if (acces !== null) headers.set('Authorization', `Bearer ${acces}`);
  let res = await fetch(`${BASE}${chemin}`, { headers });
  if (res.status === 401 && (await tenterRafraichir())) {
    if (acces !== null) headers.set('Authorization', `Bearer ${acces}`);
    res = await fetch(`${BASE}${chemin}`, { headers });
  }
  if (!res.ok) throw new ErreurApi(res.status, res.statusText);
  return res.blob();
}

/** Envoie un formulaire multipart (fichiers + champs) avec jeton Bearer et réessai sur 401. */
export async function envoyerFormulaire<T>(chemin: string, corps: FormData): Promise<T> {
  const envoyer = async (): Promise<Response> => {
    const headers = new Headers();
    if (acces !== null) headers.set('Authorization', `Bearer ${acces}`);
    return fetch(`${BASE}${chemin}`, { method: 'POST', headers, body: corps });
  };
  let res = await envoyer();
  if (res.status === 401 && (await tenterRafraichir())) res = await envoyer();
  if (!res.ok) {
    let message = res.statusText;
    try {
      const c = (await res.json()) as { detail?: string };
      if (c.detail !== undefined) message = c.detail;
    } catch {
      /* corps non JSON */
    }
    throw new ErreurApi(res.status, message);
  }
  return (await res.json()) as T;
}

/** Téléverse un fichier (multipart) avec jeton Bearer et réessai sur 401. */
export async function televerser<T>(chemin: string, fichier: File, champ = 'fichier'): Promise<T> {
  const corps = new FormData();
  corps.append(champ, fichier);
  const envoyer = async (): Promise<Response> => {
    const headers = new Headers();
    if (acces !== null) headers.set('Authorization', `Bearer ${acces}`);
    return fetch(`${BASE}${chemin}`, { method: 'POST', headers, body: corps });
  };
  let res = await envoyer();
  if (res.status === 401 && (await tenterRafraichir())) res = await envoyer();
  if (!res.ok) {
    let message = res.statusText;
    try {
      const c = (await res.json()) as { detail?: string };
      if (c.detail !== undefined) message = c.detail;
    } catch {
      /* corps non JSON */
    }
    throw new ErreurApi(res.status, message);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(chemin: string): Promise<T> => requete<T>(chemin),
  post: <T>(chemin: string, corps?: unknown): Promise<T> =>
    requete<T>(
      chemin,
      corps === undefined ? { method: 'POST' } : { method: 'POST', body: JSON.stringify(corps) },
    ),
  put: <T>(chemin: string, corps: unknown): Promise<T> =>
    requete<T>(chemin, { method: 'PUT', body: JSON.stringify(corps) }),
  patch: <T>(chemin: string, corps: unknown): Promise<T> =>
    requete<T>(chemin, { method: 'PATCH', body: JSON.stringify(corps) }),
  del: <T>(chemin: string): Promise<T> => requete<T>(chemin, { method: 'DELETE' }),
};
