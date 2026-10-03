PYTHON ?= $(CURDIR)/.venv/bin/python
DC = docker compose
.PHONY: dev demo-passwords setup up down migrate superuser test test-postgres check build schema demo smoke production-check lint-python seed-export seed-validate seed-plan seed-apply key
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r apps/backend/requirements.lock
	npm ci
key:
	$(PYTHON) -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
dev:
	bash scripts/dev.sh
demo-passwords:
	$(DC) exec api python manage.py demo_data --reset-passwords
up:
	$(DC) up --build -d
down:
	$(DC) down
migrate:
	$(DC) exec api python manage.py migrate
superuser:
	$(DC) exec api python manage.py createsuperuser
check:
	$(PYTHON) apps/backend/manage.py check
	$(PYTHON) apps/backend/manage.py makemigrations --check --dry-run
	$(DC) --env-file .env.example config --quiet
	npm run type-check
build:
	npm run build
schema:
	$(PYTHON) apps/backend/manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn
	npm run api:generate
test:
	cd apps/backend && $(PYTHON) manage.py test --settings=config.settings.test
test-postgres:
	$(DC) exec -e TEST_DATABASE_URL=postgresql://platform:platform@postgres:5432/platform api python manage.py test --settings=config.settings.test
demo:
	$(DC) exec api python manage.py demo_data
smoke:
	$(DC) exec api python manage.py smoke_services
production-check:
	$(PYTHON) scripts/check_production.py
lint-python:
	.venv/bin/ruff check apps/backend scripts
seed-export:
	$(DC) exec api python manage.py seed_export /app/production-seeds/catalog.json
seed-validate:
	$(DC) exec api python manage.py seed_validate /app/production-seeds/catalog.json
seed-plan:
	$(DC) exec api python manage.py seed_import /app/production-seeds/catalog.json --dry-run
seed-apply:
	$(DC) exec api python manage.py seed_import /app/production-seeds/catalog.json --apply
