/** Génère un mot de passe court, aléatoire et unique (cryptographiquement sûr). */
export function genererMotDePasse(): string {
  const jeu = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789@#$%&*';
  const tirage = new Uint32Array(12);
  crypto.getRandomValues(tirage);
  let mdp = '';
  for (const n of tirage) mdp += jeu.charAt(n % jeu.length);
  return mdp;
}
