# 00 — Index de la documentation DSI 360

Guide de lecture. La **source de vérité unique** est [`/CLAUDE.md`](../CLAUDE.md) : commencer par là.

## Ordre de lecture conseillé
1. [`/CLAUDE.md`](../CLAUDE.md) — vision, périmètre (9 modules), principes, stack proposée, roadmap.
2. [`adr/0001-choix-de-la-stack.md`](adr/0001-choix-de-la-stack.md) — **décision de stack à valider par la DSI** (comparaison cahier vs proposition).
3. [`01-ARCHITECTURE.md`](01-ARCHITECTURE.md) — couches, flux de données, déploiement. ✅
4. [`02-DOMAIN-MODEL.md`](02-DOMAIN-MODEL.md) — modèle de domaine (Activité, SLA, cycles de vie, profils). ✅
5. [`05-DESIGN-SYSTEM.md`](05-DESIGN-SYSTEM.md) — tokens, composants maison, charte (cf. images d'inspi). ✅
6. [`03-API-CONTRACTS.md`](03-API-CONTRACTS.md) — conventions REST, endpoints, format d'erreur, versioning. ✅
7. [`04-SECURITY.md`](04-SECURITY.md) — auth locale, RBAC (profils métier paramétrables), cloisonnement, audit. ✅
8. [`06-DEPLOIEMENT.md`](06-DEPLOIEMENT.md) — mise en ligne serveur (Windows, IP:port, TLS, tâches, sauvegarde), standard AFG. ✅
9. [`07-ROADMAP.md`](07-ROADMAP.md) — socle transverse + phases 1/2/3, jalons. ✅

> Doc de conception **complète**. Prochaine étape : vérifier l'exécution du squelette, puis lot P1-0.

## Décisions d'architecture (ADR)
Chaque décision structurante est tracée dans [`adr/`](adr/). Une décision changée n'est pas
effacée : on ajoute un nouvel ADR qui supersède l'ancien.

## Sources de conception
Matériel de départ (cahier des charges, doc portail, procédures ITIL SI-12.01→05, rapport
d'incident, images d'inspiration UI) : [`_sources-conception/`](_sources-conception/).
