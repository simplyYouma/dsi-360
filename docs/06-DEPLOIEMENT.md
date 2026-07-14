# 06 — Déploiement serveur (DSI 360)

> Procédure **concrète et éprouvée** pour mettre DSI 360 en ligne sur le serveur interne AFG Bank
> Mali (Windows, accès par **IP:port**, exécution native sans Docker). Elle applique le **standard
> serveur AFG** (tiré des déploiements VIREMA/DORIS) aux valeurs réelles de ce projet.
>
> But : que le déploiement **marche du premier coup**, ne casse **aucun autre projet** du serveur,
> et qu'un opérateur — humain ou assistant IA — puisse dérouler la séquence sans tâtonner. La
> dernière section (« Algorithme pour l'assistant ») est faite pour ça.

Références : [ADR-0002 exécution native](adr/0002-execution-native-sans-docker.md) ·
[04-SECURITY.md](04-SECURITY.md) · [01-ARCHITECTURE.md](01-ARCHITECTURE.md).

---

## 0. Fiche du projet (valeurs réelles)

| Champ | Valeur DSI 360 |
|---|---|
| **Dossier serveur** | `C:\MY_APPS\dsi-360` (le *nom des tâches* reste `DSI360`, sans tiret) |
| **Runtime backend** | Python **3.12+**, venv `backend\.venv`, FastAPI/uvicorn |
| **Base de données** | **PostgreSQL 16+ native** (rôle applicatif `dsi360`, base `dsi360`) |
| **Frontend** | React + Vite → `frontend\dist`, **servi par l'API** (même origine) |
| **Port** | **8453** (HTTPS) — cf. registre des ports §1 ; à ouvrir au pare-feu par un admin |
| **Certificat** | `C:\MY_APPS\dsi-360\cert\cert.pem` / `key.pem` — **jamais** versionné |
| **Préfixe des variables** | `DSI360_` (ex. `DSI360_JWT_SECRET_KEY`, `DSI360_DATABASE_URL`) |
| **Tâches planifiées** | `DSI360` (app), `DSI360-Sauvegarde` (pg_dump) — **préfixées, jamais génériques** |
| **Lanceurs bureau** | **`installer-tache.bat`** — démarrage auto avec Windows (une fois) · **`maj-prod.bat`** — mise à jour un-clic. Les deux s'élèvent en admin tout seuls. |
| **PWA** | Oui — installable (manifest + service worker). Le SW ne met **jamais** `/api` en cache et sert la navigation en réseau-d'abord ; après un `git pull` + rebuild, il se met à jour tout seul au prochain chargement en ligne. |
| **Reverse-proxy** | **Facultatif** : l'API termine elle-même le TLS (voir §1) |

---

## 1. Architecture cible & isolation multi-projets

Le serveur fait tourner **plusieurs projets en parallèle** (DORIS, VIREMA, DSI 360, futurs).
La règle d'or : **chaque projet ne touche que lui-même.**

- **Un seul processus, un seul port.** L'API FastAPI sert à la fois `/api/v1/**` **et** la SPA
  compilée (`frontend\dist`). Le front appelle l'API en **chemin relatif** (`/api/...`) → **même
  origine** → zéro CORS, un seul certificat, un seul port à ouvrir. C'est pourquoi DSI 360 **n'a
  pas besoin de reverse-proxy** ni de configuration CORS.
- **TLS terminé par l'app.** `uvicorn --ssl-certfile … --ssl-keyfile …` : accès direct
  `https://<IP>:8453`, sans nom d'hôte. (Un reverse-proxy IIS/Nginx reste possible — voir annexe —
  mais non requis.)
- **Un seul processus uvicorn — jamais `--workers N`.** L'ordonnanceur SLA/escalade/notifications
  tourne **en processus** (asyncio, cf. [`app.py`](../backend/src/dsi360/interface/app.py)
  `_ordonnanceur`, ADR-0002). Deux workers = deux ordonnanceurs = **notifications et e-mails en
  double**. La charge interne ne le justifie pas ; on reste mono-process.
- **Runtime isolé** : venv propre à DSI 360, dossier propre, base propre. Rien de partagé.
- **Scripts qui ne visent que DSI 360.** `start-prod.sh` refuse de démarrer si le port est déjà
  pris (au lieu d'écraser un voisin). **Jamais** de `Get-Process python | Stop-Process` global :
  cibler la tâche `DSI360` ou le port 8453.

### Registre des ports (à tenir à jour, tous projets)

| Projet | Ports |
|---|---|
| DORIS | 8443 / 8080 / 8000 |
| VIREMA | 5180 |
| **DSI 360** | **8453** |

> Avant d'ouvrir 8453 au pare-feu, vérifier qu'il n'entre pas en collision avec un projet existant.
> `8453` est déjà la valeur par défaut de `DSI360_URL_APP` dans la configuration.

---

## 2. Prérequis (une fois par serveur)

1. **PostgreSQL 16+** installé (service Windows), client `psql`/`pg_dump` disponibles
   (`C:\Program Files\PostgreSQL\17\bin`).
2. **Python 3.12+** et **Node 20+** installés.
3. **Git** installé (avec Git Bash pour la génération du certificat).
4. **Port 8453 ouvert au pare-feu** (demander à l'admin — une seule fois).
5. Dossier `C:\MY_APPS\dsi-360` créé.

---

## 3. Premier déploiement (sur le serveur)

### 3.1 Récupérer le code
```powershell
cd C:\MY_APPS
git clone <URL_DU_DEPOT> dsi-360
cd C:\MY_APPS\dsi-360
```

### 3.2 Base de données (native)
```powershell
# Rôle applicatif + base (en superuser postgres). Le script porte le mot de passe applicatif :
# il est gitignore — le renseigner sur le serveur.
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f infra\local\provisionner-db.sql
```

### 3.3 Backend : venv, secrets, migrations
```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -U pip
backend\.venv\Scripts\python.exe -m pip install -e ".\backend"

Copy-Item infra\local\.env.example infra\local\.env
```
Éditer `infra\local\.env` — **valeurs de production** (jamais celles du dev) :

| Clé | Valeur serveur |
|---|---|
| `DSI360_ENVIRONNEMENT` | `prod` (ou `recette`) — **active HSTS**, désactive les outils de dev |
| `DSI360_DATABASE_URL` | `postgresql+asyncpg://dsi360:<MDP_FORT>@127.0.0.1:5432/dsi360` |
| `DSI360_JWT_SECRET_KEY` | **secret fort, propre au serveur** — `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DSI360_SEED_ADMIN_EMAIL` / `_PASSWORD` | compte admin initial (mot de passe changé à la 1re connexion) |
| `DSI360_URL_APP` | `https://<IP>:8453` (liens dans les e-mails) |
| `DSI360_NOTIF_EMAIL_ACTIVE` | `false` tant que le relais SMTP n'est pas fourni (voir §6) |

> **Pas de deadlock SMTP** : le compte admin est seedé avec un **mot de passe direct** (pas de lien
> d'activation) — il se connecte même sans relais e-mail. Les envois automatiques dégradent
> proprement si SMTP est injoignable (log, pas de blocage).

Migrer + seed :
```powershell
infra\local\migrer.ps1
```
> Les migrations se rejouent **aussi au démarrage** de l'API (`migrer_au_demarrage`, idempotent) :
> après un `git pull`, un simple redémarrage de la tâche met la base à jour.

### 3.4 Frontend : build de production
```powershell
infra\local\front-build.ps1     # génère frontend\dist
```

### 3.5 Certificat HTTPS « Chrome-proof » (SAN=IP + EKU serverAuth)

Chrome ignore le `CN` et exige un **SAN** avec l'IP **et** l'usage `serverAuth`. Dans **Git Bash**,
au dossier de l'app (chemins **relatifs** — sinon openssl Windows ne comprend pas `/c/...`) :
```bash
cd /c/MY_APPS/dsi-360
mkdir -p cert
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout cert/key.pem -out cert/cert.pem \
  -subj "/CN=<IP>" \
  -addext "subjectAltName=IP:<IP>" \
  -addext "keyUsage=digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth"
```
Vérifier :
```powershell
certutil -dump "C:\MY_APPS\dsi-360\cert\cert.pem"
# Doit montrer :  Subject Alternative Name -> IP Address=<IP>
#                 Enhanced Key Usage       -> Server Authentication
```
> **Idéal** : un vrai certificat émis par la **PKI interne AFG** pour l'IP (racine déjà de confiance
> sur les postes du domaine → cadenas propre partout, sans import poste par poste).

### 3.6 Rendre le certificat de confiance (par poste, ou par GPO)
**PowerShell administrateur** :
```powershell
Import-Certificate -FilePath "C:\MY_APPS\dsi-360\cert\cert.pem" -CertStoreLocation Cert:\LocalMachine\Root
Import-Certificate -FilePath "C:\MY_APPS\dsi-360\cert\cert.pem" -CertStoreLocation Cert:\CurrentUser\Root
```
> Grande échelle : distribuer le `.crt` par **GPO** (Autorités de certification racines de confiance).

### 3.7 Lancement automatique au démarrage de Windows (tâche planifiée `DSI360`)

Le lanceur de production est **`infra/local/start-prod.sh`** (Git Bash — prérequis serveur §2). Il
applique les points non négociables : `--no-server-header` (bannière masquée), `--ssl-*` (TLS), bind
`0.0.0.0`, **pas** de `--reload`, **pas** de `--workers`. Il termine par `exec` : python **remplace**
le shell, donc la tâche surveille l'API elle-même, sans processus intermédiaire.

**En un clic** — double-cliquer **`infra\local\installer-tache.bat`** (élévation admin automatique).
Il installe la tâche, ouvre le port au pare-feu, démarre l'app et contrôle sa santé. Idempotent :
réexécutable, il remplace la tâche existante. Options : `-Port`, `-SansPareFeu`, `-SansDemarrer`.

Il refuse d'installer la tâche si le déploiement est incomplet (venv, `.env`, `frontend\dist`,
certificat) : une tâche posée sur un déploiement bancal échoue à **chaque** démarrage, sans que
personne ne le voie.

Ce que fait `installer-tache.ps1`, et pourquoi :

| Réglage | Raison |
|---|---|
| Déclencheur **au démarrage**, compte **SYSTEM**, `RunLevel Highest` | l'app tourne sans session ouverte, dès le boot |
| Délai **1 min** sur le déclencheur + **3 relances** (1 min) | au boot, PostgreSQL n'écoute pas encore ; l'API migre au démarrage et s'arrêterait si la base était injoignable |
| **`ExecutionTimeLimit = 0`** | **indispensable** : la valeur Windows par défaut est **3 jours** — sans ce réglage, le planificateur **tue l'application au bout de 72 h** |
| `MultipleInstances = IgnoreNew` | jamais deux uvicorn sur le port 8453 (cf. §1) |
| Règle de pare-feu entrante sur le port | sans elle, l'app ne répond qu'en local |

> **Vérifier ce que lance réellement la tâche** (piège fréquent) — **en session élevée** : sur ce
> serveur, une session non élevée ne *voit pas* les tâches SYSTEM et croit à tort qu'elles sont absentes.
> ```powershell
> (Get-ScheduledTask -TaskName "DSI360").Actions | Format-List Execute, Arguments
> ```
> **Démarrer / redémarrer** :
> ```powershell
> Stop-ScheduledTask  -TaskName "DSI360"
> Start-ScheduledTask -TaskName "DSI360"
> ```

### 3.8 Sauvegarde planifiée (tâche `DSI360-Sauvegarde`)
```powershell
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument @'
-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\MY_APPS\dsi-360\infra\local\sauvegarde-db.ps1" -Destination "C:\MY_APPS\logs\DSI360\backups" -RetentionJours 30
'@
$t = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -TaskName "DSI360-Sauvegarde" -Action $a -Trigger $t -RunLevel Highest -User "SYSTEM"
```
> Restauration testée : `infra\local\restaurer-db.ps1 -Fichier <chemin\vers\.dump>`.
> **Vérifier la restauration au moins une fois** — une sauvegarde jamais restaurée n'est pas une
> sauvegarde. La cible doit être **hors git** et, idéalement, sur un volume sauvegardé/chiffré.

### 3.9 Vérifier le déploiement
```powershell
Get-NetTCPConnection -State Listen -LocalPort 8453 -ErrorAction SilentlyContinue   # le port écoute ?
curl.exe -I -k https://<IP>:8453/                                                  # en-têtes + TLS
curl.exe -k https://<IP>:8453/readyz                                               # base joignable ?
```
Attendu :
- `HTTP/1.1 200 OK` sur `https://` → **TLS fonctionne** ;
- `strict-transport-security: max-age=31536000` → **HSTS** (car `DSI360_ENVIRONNEMENT≠dev`) ;
- `content-security-policy`, `x-frame-options: DENY`, `x-content-type-options: nosniff`,
  `referrer-policy: no-referrer`, `permissions-policy` ;
- **PAS** de ligne `server: uvicorn` (bannière masquée) ;
- `/readyz` → `{"statut":"pret","db":"ok"}`.

Puis **dérouler le test d'intrusion** avant d'ouvrir aux utilisateurs :
```powershell
infra\local\pentest.ps1 -Url https://<IP>:8453/api/v1 -SansVerifTls
```
Attendu : `21 contrôles franchis, 0 faille(s)` (détail : [04-SECURITY.md](04-SECURITY.md) §6).

---

## 4. Mettre à jour une version déjà déployée

### En un clic (recommandé)

Double-cliquer **`infra\local\maj-prod.bat`** (ou son raccourci sur le bureau du serveur). Il
demande l'élévation administrateur puis déroule, tout seul et dans l'ordre :

1. **contrôle du dépôt** (refuse s'il y a des modifications locales — le code ne se modifie que par git) ;
2. **`git pull --ff-only`** (jamais de fusion surprise) ;
3. **dépendances backend** (`pip install -e .\backend`) ;
4. **migrations** (idempotentes, verrouillées) ;
5. **build du frontend** (`npm ci && npm run build`) ;
6. **redémarrage de la tâche `DSI360`** (sans quoi l'ancien code et l'ancien certificat restent en mémoire) ;
7. **contrôle de santé** (`/healthz` doit répondre 200).

Le moteur est `infra\local\maj-prod.ps1` — le `.bat` n'est que l'enveloppe qui l'élève et l'exécute.
En cas d'anomalie, le script s'arrête net sur l'étape fautive et l'affiche.

> Démarrage/arrêt manuels du service : ils passent par la **tâche planifiée `DSI360`**
> (`Start-ScheduledTask`/`Stop-ScheduledTask`, ou le Planificateur de tâches Windows). Le boot du
> serveur la lance seule ; `maj-prod.bat` la redémarre après chaque mise à jour.

### À la main (équivalent, si besoin)
```powershell
cd C:\MY_APPS\dsi-360
git pull --ff-only
backend\.venv\Scripts\python.exe -m pip install -e ".\backend"   # si dépendances changées
infra\local\front-build.ps1                                       # rebuild du front
Stop-ScheduledTask  -TaskName "DSI360"
Start-ScheduledTask -TaskName "DSI360"
```
> **Toujours redémarrer la tâche après un `git pull`** : un serveur non relancé sert l'ancien code
> et l'**ancien certificat en mémoire**. Les migrations en attente s'appliquent au redémarrage.

---

## 5. Pièges rencontrés & correctifs (mémoire de guerre AFG)

| # | Symptôme | Cause | Correctif |
|---|---|---|---|
| 1 | `openssl … No such file` (génération du cert) | `MSYS_NO_PATHCONV=1` casse la conversion de `/c/...` | Se placer dans le dossier, **chemins relatifs** (`cert/key.pem`). |
| 2 | « Votre connexion n'est pas privée » alors que le cert est importé | Cert sans **SAN=IP** ou sans **EKU serverAuth** | Régénérer avec `subjectAltName=IP:<IP>` + `extendedKeyUsage=serverAuth` ; vérifier via `certutil -dump`. |
| 3 | Nouveau cert importé, toujours pas de cadenas | Ancien cert chargé **en mémoire** | **Redémarrer la tâche** `DSI360` après tout changement de certificat. |
| 4 | La tâche démarre « autrement » que prévu (HTTP au lieu d'HTTPS) | L'action pointe le mauvais script / sans `--cert` | `(Get-ScheduledTask …).Actions | Format-List` **en session élevée** puis corriger (§3.7). **Déjà vu sur ce serveur** : un uvicorn lancé à la main en HTTP squattait 8453, exposé au réseau — vérifier la ligne de commande du process : `Get-CimInstance Win32_Process -Filter "ProcessId=<PID>"`. |
| 5 | En-tête `server: uvicorn` visible | Bannière non masquée | `start-prod.sh` passe déjà `--no-server-header` — vérifier qu'il est bien le script lancé. |
| 6 | Variables d'env « oubliées » | `$env:VAR=…` est temporaire | Tout vit dans `infra\local\.env`, lu par la tâche via `start-prod.sh`. |
| 7 | **Notifications / e-mails en double** | Plusieurs workers uvicorn → plusieurs ordonnanceurs | **Un seul process** : jamais `--workers`. (Déjà garanti par `start-prod.sh`.) |
| 8 | Deux backends se battent pour 8453 | Ancien process encore vivant | `start-prod.sh` refuse de démarrer ; libérer le port (ci-dessous) puis relancer. |
| 9 | 503 aux requêtes après un plantage Postgres | Base momentanément absente | **Normal et voulu** : l'app rend un 503 propre et se rétablit seule dès que la base revient (`pool_pre_ping`). Aucune action. |

**Libérer le port 8453** :
```powershell
Get-NetTCPConnection -State Listen -LocalPort 8453 -ErrorAction SilentlyContinue |
  Select-Object -Expand OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## 6. E-mail (SMTP) — activation ultérieure

Les envois automatiques (affectation, mention, approche/dépassement SLA, escalade…) sont **coupés
par défaut** (`DSI360_NOTIF_EMAIL_ACTIVE=false`) : les notifications **internes** (cloche + son)
fonctionnent sans SMTP. Pour activer les e-mails, quand la banque fournit un relais :

1. Vérifier que le relais est **réellement joignable** : `Test-NetConnection <relais> -Port 587`.
   (Ne jamais laisser un hôte « exemple » type `smtp.afgbank.local` non résolu.)
2. Renseigner dans `.env` : `SMTP_HOTE`, `SMTP_PORT`, `SMTP_UTILISATEUR`, `SMTP_MOT_DE_PASSE`,
   `SMTP_EXPEDITEUR`, puis `DSI360_NOTIF_EMAIL_ACTIVE=true`.
3. Redémarrer la tâche `DSI360`.

> Le client SMTP **dégrade proprement** (disjoncteur) : un relais injoignable ne bloque aucun flux
> métier — l'action réussit, l'e-mail est simplement journalisé comme non envoyé.

---

## 7. Sécurité minimale exigée (checklist de mise en ligne)

- [ ] **HTTPS** actif (TLS terminé par l'app, `--ssl-*`), certificat SAN=IP + serverAuth de confiance.
- [ ] `DSI360_ENVIRONNEMENT` = `recette`/`prod` → **HSTS** émis.
- [ ] En-têtes présents : **CSP**, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`,
      `Permissions-Policy`. **Bannière serveur masquée.**
- [ ] `DSI360_JWT_SECRET_KEY` **fort, aléatoire, propre au serveur**, jamais commité.
- [ ] **Un seul process** uvicorn (ordonnanceur unique).
- [ ] `.env`, `cert/`, `*.pem`, `*.key`, `provisionner-db.sql`, `/data/` **hors git** (déjà
      `.gitignore`).
- [ ] **Sauvegarde** planifiée (`DSI360-Sauvegarde`) **et restauration testée**.
- [ ] **Pare-feu** : seul le port 8453 ouvert, une fois, par un admin.
- [ ] **Test d'intrusion** au vert (`pentest.ps1` → 21/21).

---

## 8. Algorithme pour l'assistant (séquence déterministe)

Remplacer `<IP>` et `<URL_DU_DEPOT>` par les valeurs réelles.

1. **Contexte** : Windows, accès par **IP:8453** (pas de nom d'hôte), dossier `C:\MY_APPS\dsi-360`,
   port 8453 ouvert au pare-feu.
2. **Code** : `git clone`/`git pull` dans `C:\MY_APPS\dsi-360`.
3. **Base** : `provisionner-db.sql` (1re fois), puis `infra\local\migrer.ps1`.
4. **Backend** : venv + `pip install -e .\backend` ; `.env.example` → `.env`, y injecter un **secret
   fort**, `DSI360_ENVIRONNEMENT=prod`, la DSN, `DSI360_URL_APP=https://<IP>:8453`.
5. **Frontend** : `infra\local\front-build.ps1`.
6. **Certificat** : générer SAN=IP + EKU serverAuth dans `cert\` (Git Bash, chemins **relatifs**),
   **vérifier `certutil -dump`**, puis importer dans `LocalMachine\Root` + `CurrentUser\Root`.
7. **Tâche `DSI360`** : `installer-tache.bat` → `start-prod.sh` (HTTPS + bannière masquée + un seul process), au
   démarrage ; **vérifier l'action réellement enregistrée** ; `Start-ScheduledTask`.
8. **Tâche `DSI360-Sauvegarde`** : `sauvegarde-db.ps1` quotidien ; **tester une restauration**.
9. **Vérifier** : port en écoute + `curl -I -k https://<IP>:8453/` (200, HSTS, CSP, DENY, **pas** de
   `server:`) + `/readyz` `db:ok`.
10. **Test d'intrusion** : `pentest.ps1 -Url https://<IP>:8453/api/v1 -SansVerifTls` → **21/21,
    0 faille**. (`-SansVerifTls` : le certificat est auto-signé — sans l'option, le client refuse
    la connexion et le test ne démarre même pas.)
11. **Anomalie** : dérouler le tableau des **pièges (§5)** — surtout #2 (SAN/EKU), #3 (relancer
    après changement de cert), #4 (script réellement lancé), #7 (jamais plusieurs workers).
12. **Règles permanentes** : ne **jamais** commiter `.env`/`cert/`/`/data/` ; **redémarrer la tâche
    après chaque `git pull`** ; garder **dev et serveur séparés** (code par git, secrets/données par
    environnement) ; **un seul process** uvicorn.

---

## Annexe — Option reverse-proxy (si un jour requis)

Si l'app doit être publiée par **nom d'hôte** ou sur le **443 standard**, placer IIS/Nginx devant et
démarrer l'API **en HTTP** (`start-prod.sh` sans `--cert`). Le proxy termine le TLS et
transmet ; garder **un seul process** applicatif. Ce montage n'est pas nécessaire pour l'accès
interne par IP:port, qui est le standard AFG.
