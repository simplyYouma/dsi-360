// Démarre l'API (FastAPI/uvicorn) ET le frontend (Vite) en une seule commande : `npm run dev`.
// Superviseur résilient : si l'un des deux tombe, il est redémarré automatiquement SANS toucher
// l'autre. Ctrl+C arrête proprement les deux. Aucune dépendance externe.
import { spawn, spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { existsSync, readFileSync } from 'node:fs';

const ici = dirname(fileURLToPath(import.meta.url));
const racine = join(ici, '..');
const win = process.platform === 'win32';

const python = win
  ? join(racine, 'backend', '.venv', 'Scripts', 'python.exe')
  : join(racine, 'backend', '.venv', 'bin', 'python');
const envFile = join(racine, 'infra', 'local', '.env');

if (!existsSync(python)) {
  console.error(`\n[dev] venv introuvable : ${python}\n      Crée-le d'abord (cf. infra/local/README.md).\n`);
  process.exit(1);
}
if (!existsSync(envFile)) {
  console.error(`\n[dev] Config absente : ${envFile}\n      Copie infra/local/.env.example en .env.\n`);
  process.exit(1);
}

// Migrations AVANT l'API : après un `git pull` qui ajoute une table, uvicorn recharge le code
// mais pas le schéma — l'API plante en boucle, l'anti-boucle abandonne, et « la page ne marche
// plus » jusqu'au redémarrage. Appliquer ici rend le redémarrage suffisant, sans étape à part.
const env = { ...process.env };
for (const ligne of readFileSync(envFile, 'utf8').split(/\r?\n/)) {
  if (ligne.trim().startsWith('#')) continue;
  const m = ligne.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
  if (m) env[m[1]] = m[2];
}
console.log('[dev] Migrations de la base…');
const migration = spawnSync(`"${python}"`, ['-m', 'dsi360.infrastructure.db.migrate'], {
  stdio: 'inherit', shell: true, cwd: join(racine, 'backend'), env,
});
if (migration.status !== 0) {
  console.error('\n[dev] Migrations en échec — corrige puis relance `npm run dev`.\n');
  process.exit(1);
}

let enArret = false;
const enfants = new Set();

/** Lance un service et le redémarre s'il s'arrête (arrêt volontaire excepté).
 *
 * On ne renonce JAMAIS définitivement : une erreur de syntaxe le temps d'une sauvegarde faisait
 * tomber le service quatre fois de suite, la supervision s'arrêtait pour de bon, et l'écran
 * restait mort jusqu'à ce qu'on relance tout à la main. On espace les tentatives (jusqu'à 15 s)
 * au lieu d'abandonner : dès que le code est corrigé, le service revient seul.
 */
function superviser(svc) {
  // shell:true requis sous Windows (Node ≥ 20) pour lancer .exe/.cmd de façon fiable.
  const p = spawn(`"${svc.cmd}"`, svc.args, { stdio: 'inherit', shell: true, cwd: svc.cwd });
  enfants.add(p);
  p.on('exit', (code) => {
    enfants.delete(p);
    if (enArret) return;
    // Échecs en rafale (< 4 s) : on ralentit progressivement, sans jamais lâcher.
    const maintenant = Date.now();
    svc.echecs = maintenant - (svc.dernier ?? 0) < 4000 ? (svc.echecs ?? 0) + 1 : 0;
    svc.dernier = maintenant;
    const attente = Math.min(1200 * 2 ** Math.max(0, svc.echecs - 1), 15000);
    const suffixe = svc.echecs >= 3 ? ` (échec ${svc.echecs} — corrige l'erreur ci-dessus)` : '';
    console.error(
      `\n[dev] ${svc.nom} s'est arrêté (code ${code ?? 0}). Nouvelle tentative dans ${Math.round(attente / 1000)} s${suffixe}\n`,
    );
    setTimeout(() => !enArret && superviser(svc), attente);
  });
}

function arreter() {
  if (enArret) return;
  enArret = true;
  for (const p of enfants) p.kill();
}
process.on('SIGINT', arreter);
process.on('SIGTERM', arreter);

superviser({
  nom: 'API',
  cmd: python,
  args: ['-m', 'uvicorn', 'dsi360.interface.app:app', '--host', '127.0.0.1', '--port', '8011',
    '--reload', '--reload-dir', join(racine, 'backend', 'src'), '--env-file', envFile],
  cwd: join(racine, 'backend'),
});
superviser({ nom: 'Vite', cmd: win ? 'npm.cmd' : 'npm', args: ['run', 'web'], cwd: ici });
