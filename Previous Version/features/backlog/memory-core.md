# Memory-Core Feature Plan

## Overview
Build a persistent, always-on Windows service that hosts our vector-first memory backend. The service should expose a FastAPI interface on a fixed local port, persist data in Postgres (pgvector-enabled) on `D:\`, and provide a minimal UI widget inside Atlas-core showing health/connection status. Phase 1 focuses on standing up infrastructure and APIs; migrations or graph reasoning layers come later.

---

## Functional Design Requirements
1. **Persistent Service**
   - Windows service (`AtlasMemory`) starts automatically (delayed-auto) and stays available even if no user session is active.
   - FastAPI server bound to `localhost:<fixed_port>` with health/status endpoints.
   - Service must recover automatically on reboot and continue listening on the same fixed port so Atlas-core never needs reconfiguration.

2. **Data Storage**
   - Postgres 16+ with pgvector extension; data directory lives at `D:\atlas-memory\postgres`.
   - Initial schema covers entities, events/facts, and embedding metadata. Graph edges are deferred but schema must be extensible.
   - Separate dev/prod clusters (or databases) share schemas but keep data siloed.

3. **API Surface (Phase 1)**
   - `POST /memory/ingest` – accept text payloads + metadata, embed via OpenAI (or optional local model) and store.
   - `POST /memory/query` – accept query text; return hybrid vector results with metadata.
   - `GET /health` – report DB connectivity, embedding status, queue depth.
   - All endpoints local-only (loopback). Authentication optional for now.

4. **Embeddings**
   - Default: OpenAI embeddings (model configurable via root `.env` at `voice-comm/.env`).
   - Optional: attempt local embedding model if resources allow (32 GB RAM + dual GPUs). Should be modular so we can plug in later—download into `D:\atlas-memory\models` and select via config.
   - Switching providers should be hot-reloadable to avoid restarts.

5. **DB Admin Skill**
   - New Atlas skill capable of: checking service status, running maintenance operations (VACUUM, index checks), tailing logs, and surfacing metrics.

6. **Monitoring UI**
   - Minimal widget/panel in Atlas-core showing:
     - Connection status (green/yellow/red).
     - Last health check timestamp.
     - Queue/backlog gauge (if background workers exist).

7. **Configuration**
   - `.env` additions for DB credentials, host, port, embedding API keys, service port, optional local-model toggles (e.g., `MEMORY_DB_NAME`, `MEMORY_DB_USER`, `MEMORY_SERVICE_PORT`, `MEMORY_EMBED_PROVIDER`).
   - Config file (`config/memory_service.yaml`) to house advanced knobs (batch sizes, cache limits, worker counts, GPU selection).

8. **Testing**
   - Dev + Prod environments only. Provide unit tests for schema + API; integration test that spins up temporary Postgres (or uses test DB).

---

## Technical Design & Constraints
### Stack
- **Backend:** Postgres 16+, pgvector extension, optional AGE for future graph needs.
- **Service Runtime:** Python 3.11 (FastAPI + uvicorn) packaged via PyInstaller into a Windows service executable, or use `winsvc` wrapper.
- **Embedding Layer:** OpenAI `text-embedding-3-small` by default; optional local model (LLM-based) using `sentence_transformers` with GPU acceleration.
- **Data Directory:** `D:\atlas-memory` houses Postgres data, logs, snapshots.
- **Logging:** Structured logs to `D:\atlas-memory\logs` + Windows Event Log.

### Constraints
- Local-only access for now; no remote exposure.
- Must tolerate service restarts without data loss (rely on Postgres durability).
- Machine resources: 32 GB RAM, 2 GPUs (assume at least RTX-class). Use GPU cautiously to avoid interfering with other Atlas workloads.
- Backups/migrations are out-of-scope for Phase 1; plan must not block future addition.
- Graph relationships deferred; design schema such that future tables/edges can be added without migration churn.

---

## Architecture
```
┌────────────────────────────┐
│ Atlas-Core (client)        │
│  - DB Admin Skill          │
│  - Memory UI widget        │
└──────────────┬─────────────┘
               │ HTTP (localhost)
┌──────────────▼─────────────┐
│ Atlas Memory Service       │
│  - Windows Service host    │
│  - FastAPI (uvicorn)       │
│  - Ingestion workers       │
│  - Embedding adapter (OpenAI/local) │
└──────────────┬─────────────┘
               │ psycopg2
┌──────────────▼─────────────┐
│ Postgres + pgvector (D:\)  │
│  - Tables: entities, facts │
│  - Future: relationships   │
└────────────────────────────┘
```

### Service Components
1. **Service Host**
   - Wraps FastAPI app in Windows service (e.g., `win32serviceutil`).
   - Manages lifecycle: start DB connection pool, spawn background workers.

2. **FastAPI App**
   - Routes for ingest/query/health.
   - Uses dependency injection for DB sessions and embedding provider.

3. **Embedding Provider**
   - Interface with two implementations: OpenAI (HTTP) and LocalModel (if configured).
   - LocalModel optional: load from `D:\atlas-memory\models`.

4. **DB Layer**
   - SQLAlchemy or psycopg2 with connection pooling.
   - Schema versioning via Alembic scripts.

5. **Background Jobs**
   - Task queue (simple: `asyncio` queue or `RQ`). Handles embedding + DB writes asynchronously so API can respond quickly.

6. **Monitoring Widget**
   - Atlas-core polls `/health` periodically, displays status in UI.

---

## Architecture Decisions
| Decision | Status | Notes |
|----------|--------|-------|
| Host memory-core as Windows service exposing FastAPI on fixed port (default 5147) | **Agreed** | Satisfies “always-on” requirement with Services MMC control + restart policies. |
| Install Postgres 16 + pgvector on `D:\atlas-memory` | **Agreed** | Uses dedicated SSD provided by Dave; isolates IO from system drive. |
| Use OpenAI `text-embedding-3-small` as default provider via `.env` | **Agreed** | Most reliable to ship quickly; `.env` allows future upgrades. |
| Provide optional local embedding model leveraging GPU | **Proposed** | Requires managed download + VRAM allocation; track readiness in config flag. |
| `.env` at repo root stores DB + embedding secrets | **Agreed** | Keeps config aligned with rest of project; watchers already load this file. |
| Minimal Atlas-core UI widget for service health + queue depth | **Agreed** | Gives immediate observability per Dave’s request. |
| Authentication deferred because service stays on loopback | **Agreed** | Acceptable risk in local-only environment; revisit before remote exposure. |
| Graph edge storage via future tables/AGE extension | **Proposed** | Keep schema flexible but do not ship edges in Phase 1. |

---

## Implementation Plan

### Phase 1 – Core Infrastructure (Worker Agent A)
1. **Postgres Setup Script**
   - PowerShell automation to install Postgres silently, enable pgvector, configure to use D:\.
   - Script ensures Windows service account permissions on `D:\atlas-memory`.
2. **Schema + Alembic Baseline**
   - Define tables: `entities`, `facts`, `embeddings_queue`, `service_state`.
3. **FastAPI App Skeleton**
   - Basic routes returning static responses; integrate `.env` config loading via `pydantic-settings`.
4. **Windows Service Wrapper**
   - Implement service entry point (start/stop) launching uvicorn.
5. **Health Endpoint + UI Widget Stub**
   - `/health` returns DB + embedding probe results; Atlas UI displays simple “Connected/Down”.

### Phase 2 – Embedding + Persistence (Worker Agent B)
1. **Embedding Adapter**
   - Implement OpenAI client using `.env` keys.
   - Stub local model loader; if GPU available and model present, use it (torch + CUDA check).
2. **Ingest Flow**
   - Accept payload → enqueue → background worker computes embedding → upsert entity/fact.
3. **Query Flow**
   - Implement vector similarity search via pgvector; return structured results.
4. **DB Admin Skill**
   - New CLI/skill commands to check service status, tail logs, run maintenance queries, and surface queue stats.
5. **UI Widget Completion**
   - Display queue depth, embedding provider status, last error, and clickable link to open service logs.

### Phase 3 – Hardening & Tests (Worker Agent C)
1. **Authentication/Rate Limits (local optional)**
   - Maybe simple API key or Windows ACL check.
2. **Logging & Metrics**
   - Structured logs, Windows Event Log integration, optional Prometheus endpoint for future remote scraping.
3. **Unit/Integration Tests**
   - Expand coverage per test table below.
4. **Installer/Deployment**
   - Scripts to register service, set env vars, start/stop, update; include verification commands and rollback steps.

---

## Unit / Integration Tests
| Test ID | Description | Type |
|---------|-------------|------|
| T1 | FastAPI `/health` returns 200 and includes DB + embedding status when DB is available. | Unit (mock DB) |
| T2 | Ingest endpoint enqueues payload and returns tracking ID without blocking. | Unit |
| T3 | Background worker processes queue items, calls embedding provider, and writes to Postgres. | Integration (uses test DB) |
| T4 | Query endpoint performs vector similarity search and returns ordered results. | Integration |
| T5 | Windows service start/stop lifecycle runs FastAPI and shuts down cleanly. | Integration |
| T6 | `.env` configuration loading fails gracefully when mandatory keys missing. | Unit |
| T7 | UI widget polling detects service down state and flags red. | Unit/UI |
| T8 | DB admin skill commands (status, VACUUM) execute and surface results. | Integration |

---

## Notes / Future Work
- Graph edges & advanced relationship reasoning to be scoped after Phase 1 stability.
- Backup strategy (snapshots, `pg_dump`, offsite) deferred.
- Migration tooling from current markdown memories will follow once API/service is solid.
