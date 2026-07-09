# CLAUDE.md — Source de vérité unique (SSOT)

> **DSI 360** — Plateforme de gouvernance, pilotage et gestion des activités de la Direction
> des Systèmes d'Information — **AFG Bank Mali**.
> Ce fichier est la **source de vérité unique** pour toute personne (humaine ou agent IA) qui
> contribue au projet. Toute décision structurante vit ici ou dans un ADR référencé ici. Si le code
> et ce document divergent, **ce document fait foi** : on corrige le code ou on met à jour le
> document via une décision tracée. **Jamais de divergence silencieuse.**

---

## 1. En une phrase

Une plateforme web interne, sécurisée et évolutive qui **centralise la gestion des activités de la
DSI** (incidents, demandes, projets, changements, audit, risques, cybersécurité, gouvernance),
applique des **SLA paramétrables**, **trace toutes les actions**, et restitue à la Direction
Générale des **indicateurs et reportings** fiables — en remplacement du suivi manuel sous Excel.

Ce qu'elle **n'est pas** : un outil de supervision technique temps réel (monitoring réseau/serveurs),
ni un ITSM générique du marché. C'est l'**outil de pilotage et de gouvernance** propre à la DSI d'AFG.

## 2. Statut du projet

- **Phase de conception** (architecture avant code). Aucune ligne de code applicatif tant que les
  fondations documentaires ne sont pas posées.
- **Stack : décidée** — on retient la **meilleure stack moderne** (cf.
  [ADR-0001](docs/adr/0001-choix-de-la-stack.md)) ; la stack du cahier (Laravel/MySQL/Blade/AdminLTE)
  n'est **pas** suivie. À présenter à la DSI pour information.

## 3. Périmètre fonctionnel (cahier des charges)

Neuf modules, livrés par phases (cf. §7) :

1. **Tableau de bord exécutif** — vue globale, KPI temps réel, alertes, activités en retard, SLA, vue DG.
2. **Incidents** — création, classification, priorisation, affectation, escalade, historique, pièces jointes, clôture.
3. **Demandes** (création de compte, habilitations, logiciels, assistance, VPN, matériel…) — workflow de validation, suivi SLA.
4. **Projets** — planning, budget, jalons, risques, COPIL, documents, % d'avancement.
5. **Changements (ITIL)** — RFC, workflow **CAB / ECAB**, analyses d'impact et de risque, plans de déploiement et de retour arrière, post-implémentation. Types : standard / normal / urgent.
6. **Audit & Recommandations** — sources (Audit Groupe, Interne, BCEAO, Contrôle Permanent, Risques, CAC), plan d'action, échéance, justificatifs, validation de clôture.
7. **Risques IT** — identification, probabilité × impact = criticité, plan de traitement, revue périodique.
8. **Cybersécurité** — habilitations sensibles, comptes admin, revue des accès, vulnérabilités, correctifs, MFA, contrôles IAM.
9. **Gouvernance DSI** — COPIL, comités, décisions DG, plan d'actions, suivi des engagements.

**Transversal à toute activité** : Demandeur · Responsable principal · Contributeur(s) · Valideur(s)
· Date d'échéance · Priorité · **SLA**.

## 4. Exigences transversales (cahier des charges)

- **SLA paramétrables** par type d'activité / priorité / criticité / catégorie (prise en charge +
  résolution). Exemple : Critique 15 min / 4 h ; Haute 30 min / 8 h ; Moyenne 2 h / 2 j ; Faible 1 j / 5 j.
- **Notifications** automatiques (création, affectation, commentaire, validation, rejet, approche
  d'échéance, dépassement SLA, clôture). Canaux : e-mail + interne ; *Phase 2* : Teams, WhatsApp.
- **Traçabilité / audit** : toute action journalisée (utilisateur, date/heure, module, action,
  **ancienne et nouvelle valeur**, adresse IP). Consultable par les administrateurs.
- **Reporting** : exports PDF / Excel / CSV ; rapports par responsable, par direction, SLA,
  incidents, projets, audits, risques.
- **Gestion des accès — profils métier paramétrables** ([ADR-0003](docs/adr/0003-profils-metier-et-perimetre-dsi.md)) :
  Administrateur · IT Support Applicatif et HelpDesk · Réseau télécom · Système et Réseau télécom ·
  IT Support Applicatif. Créables, renommables, supprimables depuis l'administration ; seul `ADMIN`
  est protégé. Les accès se déclarent **par module et par action**. Remplace les 7 rôles
  hiérarchiques du cahier (Chef de Service, Chef de Projet, Technicien, Métier, DG), qui ne
  décrivaient pas le travail réel de la DSI. **Aucun code ne dépend d'une liste figée de profils.**
- **Périmètre — la DSI seule** : une unique direction, `DSI`. Les niveaux de support sont **N1 et
  N2** ; escalader au-delà transfère le ticket à **DBS**, qui n'a aucun compte dans le système.
- **Non fonctionnel** : multi-utilisateurs, **haute disponibilité (> 99 %)**, **respect SLA > 90 %**,
  authentification **Active Directory / LDAP / Microsoft 365**.

## 5. Stack technique — **figée** (cf. [ADR-0001](docs/adr/0001-choix-de-la-stack.md))

Meilleure stack moderne et maîtrisée, mutualisée avec **DORIS** (cohérence Groupe, design system et
sécurité réutilisés). La stack du cahier (Laravel/MySQL/Blade/AdminLTE) n'est pas retenue.

| Couche | Choix |
|---|---|
| Backend | **Python 3.12 + FastAPI + Pydantic v2**, SQLAlchemy async (DDD léger) |
| Base de données | **PostgreSQL 16** |
| File / tâches | **Différé** (échéances & dépassements SLA, notifications) — sans Celery/Redis ; réintroduit via APScheduler in-process ou tâche planifiée (cf. [ADR-0002](docs/adr/0002-execution-native-sans-docker.md)) |
| Frontend | **React 18 + TypeScript strict + Vite** + **design system maison** (tokens, zéro composant natif) |
| Graphiques | bibliothèque maîtrisée (ex. Recharts) — pas de template |
| Authentification | **AD / LDAP / Microsoft 365 (OIDC Entra ID)** + JWT court + RBAC (7 profils) |
| Exports | Excel (openpyxl), PDF (WeasyPrint/ReportLab), CSV |
| Infra | **Exécution native, sans Docker** ([ADR-0002](docs/adr/0002-execution-native-sans-docker.md)) : PostgreSQL natif + venv/uvicorn + Vite (dev) / FastAPI-StaticFiles (prod) ; TLS par reverse-proxy (IIS/Nginx) en prod |

## 6. Principes non négociables

1. **Architecture avant code.** Aucune implémentation sans clarté d'architecture (standard *AI Vibe Coding*).
2. **Single Source Of Truth.** SLA, profils, catégories, sources d'audit, types de changement… =
   des objets **paramétrables**, jamais codés en dur. Ajouter une catégorie = du paramétrage, zéro déploiement.
3. **Sécurité par défaut.** Toute entrée est hostile ; tout accès vérifié **côté serveur** (jamais
   seulement à l'écran) ; secrets jamais commités ; cloisonnement par profil/périmètre.
4. **Zéro perte, traçabilité totale.** Journal d'audit **append-only** (ancienne/nouvelle valeur, IP),
   jamais de suppression silencieuse, historique conservé.
5. **Évolutivité sans refonte.** Nouveau module / type / source = paramétrage ou module isolé, jamais
   réécriture du cœur.
6. **Design sobre et original.** Charte neutre, **premium, jamais “template standard”** ; **zéro
   composant natif du navigateur** (listes, calendriers, toasts… maison) ; icônes Lucide ; **zéro
   emoji** dans l'UI ; aucune animation clignotante ; **la couleur réservée au sens** (statut/accent).
7. **Qualité à chaque livraison.** Lint + types + tests + e2e au vert. **Rien n'est « fini » tant que
   ce n'est pas vérifié.**

## 7. Roadmap (cahier des charges)

- **Phase 1** : Incidents · Demandes · Projets · Tableau de bord. Socle : auth + RBAC + SLA + audit.
- **Phase 2** : Changements (ITIL) · Audit & Recommandations · Risques IT.
- **Phase 3** : Cybersécurité · PRA · Budget DSI · application mobile.

Détail et jalons : à formaliser dans `docs/07-ROADMAP.md` après validation de la stack.

## 8. Indicateurs de succès

- Réduction du suivi manuel sous Excel.
- Respect des SLA **> 90 %**, disponibilité **> 99 %**.
- Traçabilité complète et vérifiable des actions.
- Réduction des délais de traitement ; reporting consolidé disponible pour la DG.

## 9. Documentation (cible)

| Doc | Objet |
|---|---|
| `docs/00-INDEX.md` | Sommaire et guide de lecture |
| `docs/01-ARCHITECTURE.md` | Vue d'ensemble, couches, flux, déploiement |
| `docs/02-DOMAIN-MODEL.md` | Modèle de domaine (activité, SLA, profils, modules) |
| `docs/03-API-CONTRACTS.md` | Conventions REST, endpoints, erreurs, versioning |
| `docs/04-SECURITY.md` | Auth AD/LDAP/M365, RBAC, cloisonnement, audit |
| `docs/05-DESIGN-SYSTEM.md` | Tokens, composants, accessibilité, charte (inspi : `docs/_sources-conception/`) |
| `docs/07-ROADMAP.md` | Phases, livrables, jalons |
| `docs/adr/` | Décisions d'architecture (ADR) |

## 10. Sources de conception

Cahier des charges, doc « AFG IT Portal / DSI 360 », procédures ITIL (SI-12.01 à 05), rapport
d'incident type et images d'inspiration UI : `docs/_sources-conception/` (matériel de départ).
