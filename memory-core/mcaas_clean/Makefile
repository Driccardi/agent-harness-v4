# Memory-Core as a Service — Makefile
# Run `make help` for a full command reference.

.PHONY: help build up down logs shell health export import test lint clean upgrade

# ── Setup ─────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Memory-Core as a Service (MCaaS)"
	@echo "  ════════════════════════════════"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup          First-time setup (copy .env, build, start)"
	@echo "    make build          Build the container image"
	@echo "    make up             Start the container (docker-compose)"
	@echo "    make down           Stop the container"
	@echo ""
	@echo "  Operations:"
	@echo "    make logs           Tail container logs"
	@echo "    make logs-api       Tail API logs only"
	@echo "    make logs-engram    Tail Engram worker logs"
	@echo "    make shell          Open a shell in the container"
	@echo "    make health         Check container health"
	@echo "    make status         Show all internal service statuses"
	@echo ""
	@echo "  Memory:"
	@echo "    make export         Export memory state to backup.json"
	@echo "    make import         Import from backup.json"
	@echo "    make export-stats   Show export statistics without downloading"
	@echo ""
	@echo "  Development:"
	@echo "    make test           Run test suite"
	@echo "    make test-e2e       Run end-to-end integration tests"
	@echo "    make lint           Lint all Python files"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make upgrade        Upgrade container image (preserves volumes)"
	@echo "    make reflective     Manually trigger nightly reflective run"
	@echo "    make clean          Remove containers and build artifacts"
	@echo ""

setup:
	@[ -f .env ] || (cp .env.example .env && echo "Created .env — please edit it before continuing" && exit 1)
	@touch soul.md
	@mkdir -p config
	$(MAKE) build
	$(MAKE) up
	@echo ""
	@echo "  ✓ Memory-Core is running at http://localhost:4200"
	@echo "  Run 'make health' to verify all services are up."
	@echo ""

build:
	docker build -t memory-core:latest .
	@echo "✓ Image built: memory-core:latest"

up:
	docker-compose up -d
	@echo "✓ Container started. API at http://localhost:4200"

down:
	docker-compose down

# ── Logs ──────────────────────────────────────────────────────────────────────

logs:
	docker logs memory-core -f

logs-api:
	docker exec memory-core supervisorctl tail -f api

logs-engram:
	docker exec memory-core supervisorctl tail -f engram-worker

logs-reflective:
	docker exec memory-core supervisorctl tail -f reflective-scheduler

# ── Operations ────────────────────────────────────────────────────────────────

shell:
	docker exec -it memory-core bash

health:
	@curl -sf http://localhost:$${MC_HOST_PORT:-4200}/health | python3 -m json.tool

status:
	docker exec memory-core supervisorctl status

# ── Memory management ─────────────────────────────────────────────────────────

export:
	@[ -f .env ] && export $$(cat .env | grep -v '^#' | xargs) || true; \
	curl -sf \
	  -H "X-MC-Key: $$MC_ADMIN_KEY" \
	  -H "X-MC-Human-ID: $$MC_HUMAN_ID" \
	  "http://localhost:$${MC_HOST_PORT:-4200}/v1/export/$$MC_HUMAN_ID" \
	  > backup_$$(date +%Y%m%d_%H%M%S).json && \
	echo "✓ Exported to backup_$$(date +%Y%m%d_%H%M%S).json"

import:
	@[ -f backup.json ] || (echo "ERROR: backup.json not found" && exit 1)
	@[ -f .env ] && export $$(cat .env | grep -v '^#' | xargs) || true; \
	curl -sf -X POST \
	  -H "X-MC-Key: $$MC_ADMIN_KEY" \
	  -H "X-MC-Human-ID: $$MC_HUMAN_ID" \
	  -H "Content-Type: application/json" \
	  -d "{\"archive\": $$(cat backup.json), \"mode\": \"merge\"}" \
	  "http://localhost:$${MC_HOST_PORT:-4200}/v1/import" | python3 -m json.tool

export-stats:
	@[ -f .env ] && export $$(cat .env | grep -v '^#' | xargs) || true; \
	curl -sf \
	  -H "X-MC-Key: $$MC_ADMIN_KEY" \
	  -H "X-MC-Human-ID: $$MC_HUMAN_ID" \
	  "http://localhost:$${MC_HOST_PORT:-4200}/v1/export/$$MC_HUMAN_ID" \
	  | python3 -c "import sys,json; d=json.load(sys.stdin); \
	    s=d.get('export_stats',{}); \
	    print(f'Chunks: {s.get(\"total_chunks\",0)}, Topics: {s.get(\"total_topics\",0)}')"

# ── Reflective layer ──────────────────────────────────────────────────────────

reflective:
	@[ -f .env ] && export $$(cat .env | grep -v '^#' | xargs) || true; \
	./cron/reflective_nightly.sh

# ── Development ───────────────────────────────────────────────────────────────

test:
	cd memory-core && python -m pytest tests/ -v --tb=short

test-e2e:
	python -m pytest tests/e2e/ -v --tb=short

lint:
	python -m flake8 memory-core/ adapters/ client/ --max-line-length=100 --ignore=E501,W503

# ── Upgrade (preserves volumes) ───────────────────────────────────────────────

upgrade:
	docker pull memory-core:latest || $(MAKE) build
	docker-compose up -d
	@echo "✓ Upgraded — volumes preserved"

# ── Lift-shift: full container snapshot ───────────────────────────────────────

snapshot:
	@DATE=$$(date +%Y%m%d_%H%M%S); \
	docker commit memory-core memory-core-snapshot:$$DATE; \
	docker save memory-core-snapshot:$$DATE | gzip > mc_snapshot_$$DATE.tar.gz; \
	echo "✓ Snapshot saved: mc_snapshot_$$DATE.tar.gz"

restore:
	@[ -f $${SNAPSHOT_FILE} ] || (echo "Set SNAPSHOT_FILE=mc_snapshot_YYYYMMDD.tar.gz" && exit 1)
	docker load < $$SNAPSHOT_FILE
	@echo "✓ Snapshot loaded. Run: docker run -d -p 4200:4200 memory-core-snapshot:<tag>"

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	docker-compose down
	docker rmi memory-core:latest 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "✓ Clean (volumes preserved)"

clean-all: clean
	docker-compose down -v
	@echo "⚠ Volumes deleted — all memory state lost"
