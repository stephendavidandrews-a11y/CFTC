.PHONY: test test-tracker test-ai test-intake lint format check

TRACKER_VENV = services/tracker/.venv/bin
AI_VENV = services/ai/.venv/bin
INTAKE_VENV = services/intake/.venv/bin

test-tracker:
	cd services/tracker && $(CURDIR)/$(TRACKER_VENV)/python -m pytest tests/ -v

test-ai:
	cd services/ai && $(CURDIR)/$(AI_VENV)/python -m pytest tests/ -v

test-intake:
	cd services/intake && $(CURDIR)/$(INTAKE_VENV)/python -m pytest tests/ -v

test: test-tracker test-ai test-intake

lint:
	$(TRACKER_VENV)/ruff check services/tracker/
	$(AI_VENV)/ruff check services/ai/
	$(INTAKE_VENV)/ruff check services/intake/

format:
	$(TRACKER_VENV)/ruff format services/tracker/
	$(AI_VENV)/ruff format services/ai/
	$(INTAKE_VENV)/ruff format services/intake/

check: lint test

## Service management ─────────────────────────────────────────────
start:  ## Start all services (canonical method)
	./scripts/start_services.sh all

stop:  ## Stop all services
	./scripts/start_services.sh stop

restart: stop start  ## Restart all services
