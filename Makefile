COMPOSE = docker compose -f infra/docker-compose.yml --env-file infra/env/.env

.PHONY: help init certs up down logs ps build migrate seed backend-shell db-shell front-dev

help: ## Liste les commandes
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n",$$1,$$2}'

init: certs up ## Première mise en route (certs + stack)

certs: ## Génère un certificat TLS auto-signé de dev
	mkdir -p infra/nginx/certs
	openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
	  -keyout infra/nginx/certs/dsi360.key -out infra/nginx/certs/dsi360.crt \
	  -subj "/C=ML/O=AFG Bank/CN=localhost"

up: ## Démarre la stack
	$(COMPOSE) up -d --build
down: ## Arrête la stack
	$(COMPOSE) down
logs: ## Suit les logs
	$(COMPOSE) logs -f --tail=100
ps: ## État des conteneurs
	$(COMPOSE) ps

migrate: ## Applique les migrations SQL
	$(COMPOSE) exec -T api python -m dsi360.infrastructure.db.migrate

seed: ## Charge les référentiels + le compte administrateur initial
	$(COMPOSE) exec -T api python -m dsi360.infrastructure.db.seed

backend-shell: ## Shell dans le conteneur API
	$(COMPOSE) exec api bash
db-shell: ## Console PostgreSQL
	$(COMPOSE) exec postgres psql -U dsi360 -d dsi360

front-dev: ## Serveur Vite de dev (hors Docker)
	cd frontend && npm run dev
