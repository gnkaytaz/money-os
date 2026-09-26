SHELL := /bin/bash

.PHONY: init up down restart logs ps health seed db-shell api-logs clean

init:
	@test -f .env || cp .env.example .env
	@echo "Created .env (if absent). Edit secrets if needed."

up: init
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=100

api-logs:
	docker compose logs -f --tail=100 api

ps:
	docker compose ps

health:
	./scripts/health.sh

seed:
	./scripts/seed-demo.sh

db-shell:
	docker compose exec postgres psql -U $${POSTGRES_USER:-moneyos} -d $${POSTGRES_DB:-moneyos}

clean:
	docker compose down -v --remove-orphans
