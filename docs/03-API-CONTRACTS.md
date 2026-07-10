# 03 — Contrats d'API

> API REST sous `/api/v1`. Conventions communes (cohérentes avec DORIS) ; chaque module ajoute ses
> routes au fil des lots (cf. docs/07-ROADMAP.md).

## 1. Conventions générales

- **Base** : `/api/v1`. Versionnée dans l'URL ; on n'introduit pas de rupture sans bump de version.
- **Format** : JSON (UTF-8). Champs en `snake_case`, dates **ISO 8601 UTC**.
- **Verbes** : `GET` (lecture), `POST` (création), `PUT`/`PATCH` (modification), `DELETE` (rare —
  privilégier un changement de statut, jamais de suppression d'audit).
- **Idempotence** : `PUT` idempotent ; `POST` de création renvoie `201` + l'objet créé.
- **Auth** : `Authorization: Bearer <JWT>` sur tout endpoint sauf santé et login. RBAC + cloisonnement
  vérifiés côté serveur (cf. docs/04-SECURITY.md).

## 2. Pagination, tri, filtres

- Lecture de liste : `?page=1&taille=15` → réponse enveloppée :
  ```json
  { "elements": [ ... ], "total": 128, "page": 1, "taille": 15 }
  ```
- Tri : `?tri=cree_le&ordre=desc`. Filtres par champ : `?module=incident&statut=Ouvert&priorite=1`.
- Recherche plein texte : `?q=...`.

## 3. Format d'erreur (unifié)

Toujours le même corps, avec un **identifiant de corrélation** pour le support/les logs :

```json
{
  "erreur": {
    "code": "VALIDATION",
    "message": "La priorité doit être comprise entre 1 et 5.",
    "details": [{ "champ": "priorite", "probleme": "hors_bornes" }],
    "correlation_id": "c1a2b3d4"
  }
}
```

| HTTP | `code` | Quand |
|---|---|---|
| 400 | `VALIDATION` | entrée invalide |
| 401 | `NON_AUTHENTIFIE` | jeton absent/expiré |
| 403 | `NON_AUTORISE` | profil/périmètre insuffisant |
| 404 | `INTROUVABLE` | ressource inexistante ou hors périmètre |
| 409 | `CONFLIT` | transition d'état interdite, doublon |
| 422 | `REGLE_METIER` | règle de domaine violée (ex. clôture sans validation) |
| 500 | `ERREUR_INTERNE` | inattendu (journalisé) |

## 4. Endpoints transverses (socle)

- `GET /healthz`, `GET /readyz` — santé (hors auth).
- `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout` — selon `auth_mode`
  (LOCAL : mot de passe défini par l'agent via lien d'activation, cf. ADR-0004).
- `GET /api/v1/moi` — profil, droits effectifs, périmètre.
- `GET /api/v1/referentiels/{type}` — profils, catégories, matrices SLA/priorité… (paramétrables).

## 5. Activités (modèle générique, décliné par module)

> Le socle commun (cf. docs/02) donne des routes homogènes ; `module` ∈ incident, demande, probleme,
> changement, projet, audit, risque.

- `GET /api/v1/activites?module=incident&statut=Ouvert&page=1` — liste paginée, cloisonnée par périmètre.
- `POST /api/v1/activites` — création (référence générée, priorité dérivée impact×urgence, échéances SLA).
- `GET /api/v1/activites/{id}` — détail (responsabilités, historique, pièces jointes).
- `PATCH /api/v1/activites/{id}` — modification partielle (journalisée).
- `POST /api/v1/activites/{id}/transition` — changement de statut **validé par la machine à états**
  (ex. `Résolu`→`Clôturé`, `Soumis`→`CAB`). Action sensible → garde RBAC.
- `POST /api/v1/activites/{id}/assignation`, `.../commentaires`, `.../pieces-jointes`.
- Sur **incidents** et **demandes**, les routes d'écriture n'existent pas : leur état vient du
  rapport quotidien ([ADR-0005](adr/0005-incidents-et-demandes-en-lecture-seule.md)).

## 6. Tableau de bord & exports

- `GET /api/v1/tableau-de-bord` — KPI agrégés (incidents ouverts/critiques, respect SLA, retards…),
  filtrables par période/direction selon le périmètre.
- `GET /api/v1/exports/{rapport}?format=pdf|excel|csv` — génération synchrone.
