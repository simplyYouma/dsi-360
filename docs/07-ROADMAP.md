# 07 — Roadmap

> Principe : **fondations définitives, pas de jetable**. Chaque lot est livré **complètement**
> (back + front + tests + e2e) avant le suivant. Le socle transverse (auth, RBAC, SLA, audit,
> notifications, design system) est construit **une fois** et réutilisé par tous les modules.

## Socle transverse (préalable à tout module)

- Scaffolding monorepo + Docker + qualité (lint/format/types/tests).
- Schéma DB (core / audit), migrations versionnées.
- Auth **OIDC (Entra ID) / LDAP** + JWT + **RBAC 7 profils** + cloisonnement.
- Entité **Activité** + machines à états + **moteur SLA** (priorité P1–P5, échéances) + ordonnanceur.
- **Audit append-only**, **notifications** (e-mail + interne), **design system maison** (tokens + primitives).

## Phase 1 — Cœur opérationnel

| Lot | Contenu | État |
|---|---|---|
| **P1-0** | Socle transverse (ci-dessus) | à faire |
| **P1-1** | **Incidents** : cycle de vie, priorité/SLA, affectation, escalade, pièces jointes, clôture | à faire |
| **P1-2** | **Demandes de service** : catégories, workflow de validation, suivi SLA | à faire |
| **P1-3** | **Projets** : planning, jalons, budget, % d'avancement, COPIL, documents | à faire |
| **P1-4** | **Tableau de bord exécutif** : KPI temps réel, alertes, activités en retard, vue DG, exports PDF/Excel/CSV | à faire |

## Phase 2 — Gouvernance & maîtrise

| Lot | Contenu |
|---|---|
| **P2-1** | **Changements (ITIL)** : RFC, workflow **CAB/ECAB**, analyses d'impact/risque, plan de déploiement & retour arrière, post-implémentation |
| **P2-2** | **Audit & Recommandations** : sources (Groupe, Interne, BCEAO, Contrôle Permanent, Risques, CAC), plan d'action, validation de clôture |
| **P2-3** | **Risques IT** : probabilité × impact = criticité, plan de traitement, revue périodique |
| **P2-4** | Notifications **Teams / WhatsApp** ; reporting avancé |

## Phase 3 — Sécurité & extension

| Lot | Contenu |
|---|---|
| **P3-1** | **Cybersécurité** : habilitations sensibles, comptes admin, revue d'accès, vulnérabilités, correctifs, MFA, IAM |
| **P3-2** | **Gouvernance DSI** : COPIL, comités, décisions DG, suivi des engagements |
| **P3-3** | **PRA**, **Budget DSI**, **application mobile** |
| **P3-4** | **Recette sécurité RSSI**, durcissement, mise en production |

## Indicateurs de succès (cahier)

Réduction du suivi Excel · **respect SLA > 90 %** · **disponibilité > 99 %** · traçabilité complète ·
réduction des délais · reporting consolidé pour la DG.

## Décisions à confirmer avec la DSI (avant ou pendant P1-0)

1. Validation de la **stack** (ADR-0001) pour information.
2. Modalités **AD / Microsoft 365** (Entra ID, tenant, comptes de service).
3. **Hébergement / haute disponibilité** (serveur, sauvegarde, supervision).
4. **SLA réels** par type/priorité, **catégories** par module, **matrice d'escalade**.
5. Exigences **RSSI** (journalisation, rétention, recette sécurité).
