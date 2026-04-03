# Atlas Cognitive Substrate — Build Design Specification

**Date:** 2026-03-15
**Status:** Approved for implementation planning
**Stack:** Claude Code CLI · Docker · PostgreSQL + pgvector · FastAPI · Node.js/TypeScript/React
**Spec reference:** `atlas-spec/00-atlas-overview.md` + `sidecars/01–08` + `09-contracts.md` + `10-governance.md`
**Canonical reference:** `mcaas_clean/` (Python/FastAPI/PostgreSQL/pgvector/Ollama/Redis)
**Authority:** When this document conflicts with `atlas-spec/09-contracts.md`, contracts.md governs.

---

## 1. What We Are Building

Atlas is a cognitive memory substrate for LLM agents. It provides ambient, associative, persistent memory as infrastructure — not as a tool the agent consciously uses. The agent experiences memory as context that surfaces automatically, without deliberate retrieval effort.

This build is a **from-scratch implementation** against the v5.1 atlas-spec, using the mcaas_clean reference as a canonical behavioral guide (not as code to copy). Key differences from the reference:

- Redis removed — PostgreSQL `job_queue` table with `SKIP LOCKED` replaces it for reflective sidecars
- Eidos uses a dedicated `eidos_queue` table populated by DB trigger (not job_queue)
- LLM provider abstraction layer supports Claude, OpenAI-compatible (Codex), and local Ollama
- Observability UI is new — React + TypeScript memory inspector (not in reference)
- Embedding dimension is configurable via env var (not hardcoded to 768)
- Embed backend is independently configurable from the LLM completion backend
- Full Claude Code CLI integration: hooks, skills, CLAUDE.md, AGENTS.md

---

## 2. Architecture Decision

**Chosen approach: Monorepo, Single FastAPI Process + APScheduler Workers**

All 8 sidecars run as background tasks within one FastAPI process. The real-time layer (Engram, Eidos, Anamnesis) operates synchronously or via DB trigger. The reflective layer (Kairos, Oneiros, Praxis, Psyche, Augur) runs on APScheduler intervals. The React observability app is a separate Node.js service in the same repo.

Rationale: fewest moving parts, maximum agentic buildability (each sidecar is an isolated module), direct analog to mcaas_clean's supervisord pattern. Horizontal sidecar scaling is a straightforward migration path to a worker-container split if needed later.

---

## 3. Repository Structure

```
atlas/
├── backend/
│   ├── api/                    # FastAPI route handlers
│   ├── sidecars/               # One module per sidecar
│   │   ├── base.py             # SidecarBase abstract class
│   │   ├── engram/
│   │   ├── eidos/
│   │   ├── anamnesis/
│   │   ├── kairos/
│   │   ├── oneiros/
│   │   ├── praxis/
│   │   ├── psyche/
│   │   └── augur/
│   ├── llm/                    # Provider abstraction layer
│   │   ├── provider.py         # BaseProvider protocol + factory
│   │   ├── claude.py
│   │   ├── openai_compat.py
│   │   └── ollama.py
│   ├── db/                     # Pool, Alembic migrations, query helpers
│   ├── workers/                # APScheduler setup + sidecar registration
│   ├── config.py               # Pydantic Settings, env-driven
│   └── main.py                 # FastAPI app + lifespan scheduler boot
│
├── observability/              # React + TypeScript UI
│   ├── src/
│   │   ├── api/                # Generated typed client + TanStack Query hooks
│   │   │   └── openapi-stub.yaml  # Hand-authored OpenAPI stub for parallel dev
│   │   ├── components/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.ts
│
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── Dockerfile.observability
│   └── init/
│       └── schema.sql          # Full canonical schema (authoritative)
│
├── adapters/
│   └── claude_code/
│       ├── hooks/              # 6 bash hook scripts
│       ├── skills/             # 6 slash command skills
│       └── CLAUDE.md           # Agent system instructions
│
├── AGENTS.md                   # Agentic build conventions
├── Makefile
├── .env.example
└── docs/
    └── superpowers/specs/
```

---

## 4. Container Topology

```
┌─────────────────────────────────────────────────────┐
│  docker-compose                                     │
│                                                     │
│  ┌─────────────┐    ┌──────────────────────────┐   │
│  │  postgres   │◄───│       backend :4200       │   │
│  │  pgvector   │    │  FastAPI + APScheduler    │   │
│  │  pg16       │    │  8 sidecar workers        │   │
│  └─────────────┘    │  LLM provider abstraction │   │
│                     └──────────┬───────────────┘   │
│  ┌─────────────┐               │                   │
│  │   ollama    │◄──────────────┘                   │
│  │  :11434     │                                   │
│  └─────────────┘                                   │
│                     ┌──────────────────────────┐   │
│                     │  observability :5173      │   │
│                     │  React + Vite (TS)        │   │
│                     └──────────────────────────┘   │
└─────────────────────────────────────────────────────┘

External: Claude Code CLI hooks → POST /v1/ingest, GET /v1/inject
          Browser → http://localhost:5173
```

---

## 5. LLM Provider Abstraction

```python
class BaseProvider(Protocol):
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str: ...

    async def embed(self, text: str) -> list[float]: ...

def get_provider(cfg: Config) -> BaseProvider:
    match cfg.llm_backend:
        case "claude":  return ClaudeProvider(cfg)
        case "openai":  return OpenAICompatProvider(cfg)
        case "ollama":  return OllamaProvider(cfg)

def get_embed_provider(cfg: Config) -> BaseProvider:
    match cfg.embed_backend:
        case "ollama":  return OllamaProvider(cfg)
        case "openai":  return OpenAICompatProvider(cfg)
```

LLM completion and embedding are independently configured via `ATLAS_LLM_BACKEND` and `ATLAS_EMBED_BACKEND`. This allows, for example, Claude for sidecar reasoning and Ollama for embeddings (the default), or fully local Ollama for both.

| Backend | LLM calls | Key env vars |
|---|---|---|
| `claude` | Anthropic SDK | `ANTHROPIC_API_KEY`, `ATLAS_LLM_MODEL` |
| `openai` | OpenAI SDK (base_url override) | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_LLM_MODEL` |
| `ollama` | Ollama `/api/chat` | `OLLAMA_BASE_URL`, `OLLAMA_LLM_MODEL` |

| Embed Backend | Embed calls | Key env vars |
|---|---|---|
| `ollama` (default) | Ollama `/api/embeddings` | `ATLAS_EMBED_MODEL`, `ATLAS_EMBEDDING_DIM` |
| `openai` | OpenAI embeddings endpoint | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `ATLAS_EMBED_MODEL`, `ATLAS_EMBEDDING_DIM` |

---

## 6. Sidecar Architecture

### 6.1 Base Class

```python
class SidecarBase(ABC):
    def __init__(self, db: AsyncPool, llm: BaseProvider, embed: BaseProvider, cfg: Config): ...

    @abstractmethod
    async def run_once(self) -> None:
        """
        Idempotent. Called by APScheduler on each tick (interval_seconds > 0),
        or by the job queue watcher (interval_seconds == 0).
        """
        ...

    @property
    @abstractmethod
    def interval_seconds(self) -> int:
        """
        Scheduling interval. 0 means event-triggered only — the sidecar is NOT
        registered with APScheduler's IntervalTrigger. Instead, workers/ registers
        a job queue watcher that calls run_once() when a matching job appears.
        """
        ...
```

### 6.2 Sidecar Register

| # | Sidecar | Role | Trigger Model | LLM |
|---|---|---|---|---|
| 1 | **Engram** | Embed + store every inbound event; windowed chunking with tail buffer and 4 emission modes | Sync — inline with `/v1/ingest`; writes `eidos_queue` row after each chunk insert | No |
| 2 | **Eidos** | Enrich chunks: signal class, somatic tags, somatic snapshots | DB trigger on `chunks` insert → `eidos_queue` → Eidos polls `eidos_queue` with `SKIP LOCKED` | Optional |
| 3 | **Anamnesis** | Associative recall — 8-gate conjunctive filter, injection formatting; reads Psyche bypass channel | Sync — inline with `/v1/inject` | No |
| 4 | **Kairos** | Topic clustering, progressive summary stack, open loop detection | Async — APScheduler every 5 min | Yes |
| 5 | **Oneiros** | Consolidation — promotes episodic clusters to `consolidated_beliefs`, archives chunks atomically | Async — APScheduler every 30 min | Yes |
| 6 | **Praxis** | Skill improvement — detects invocation patterns, writes `procedural_notes` and `praxis_recommendations` | Async — session end event via `job_queue` (`interval_seconds = 0`) | Yes |
| 7 | **Psyche** | Affective tracking — writes `sss_snapshots`, updates `soul.md`, pushes gate-bypass self-narrative to Anamnesis | Async — APScheduler every 60 s | Yes |
| 8 | **Augur** | Behavioral prediction — extracts `behavioral_sequences`, maintains prefetch cache | Async — APScheduler every 10 min | Yes |

### 6.3 Engram Detail (Windowed Chunking)

Engram is not a simple "embed and store" operation. Per `atlas-spec/sidecars/01-engram.md`:

- **Tail buffer**: incoming events are held in a short ring buffer. Events are not immediately committed — Engram waits for a natural boundary (turn transition, tool episode completion) before emitting.
- **Four emission modes**: `STANDALONE` (single self-contained chunk), `TOOL_EPISODE` (tool-in + tool-out paired), `DISCOVERY_BURST` (rapid sequential tool calls collapsed), `SUPPRESSED` (noise events discarded).
- **Deduplication**: `content_hash = SHA-256(content)` checked against `UNIQUE INDEX(session_id, content_hash)` before insert. Duplicate content in the same session is silently dropped.
- **WAL fallback**: if the DB is unreachable, events are written to a local WAL file and replayed on reconnect.
- **Framework normalization**: hook payloads from Claude Code, OpenAI SDK, LangChain, etc. are normalized into `NormalizedChunk` before embedding. Each framework adapter is a small module in `backend/sidecars/engram/adapters/`.
- **After each chunk insert**: Engram inserts a row into `eidos_queue` in the same transaction, triggering Eidos enrichment.
- **`raw_events` write**: every inbound event is archived to `raw_events` before any chunking decision, providing a forensic record independent of chunking logic.

### 6.4 Psyche Gate-Bypass Channel

Psyche must inject self-narrative into Anamnesis unconditionally, bypassing all 8 gate checks. In the single-process FastAPI architecture, this channel is an **in-process `asyncio.Queue`**:

```python
# Shared in backend/main.py lifespan:
psyche_bypass_queue: asyncio.Queue[str] = asyncio.Queue()

# Psyche writes:
await psyche_bypass_queue.put(xml_self_narrative_block)

# Anamnesis reads at inject time:
bypass_content = None
if not psyche_bypass_queue.empty():
    bypass_content = psyche_bypass_queue.get_nowait()
```

Both Psyche and Anamnesis receive a reference to this queue at construction time via the `workers/` registration module. This is the single exception to the no-direct-sidecar-calls rule (per `09-contracts.md` Section 4.1).

### 6.5 Augur Prefetch Cache

Augur maintains an **in-memory prefetch cache** (`dict[str, list[str]]` mapping `master_session_id` to prefetched `chunk_id` lists). At session start, Anamnesis reads from this cache before issuing vector queries, reducing cold-start latency. The cache is rebuilt by Augur on each `run_once()` cycle and is not persisted to the database. Cache miss is graceful: Anamnesis falls back to on-demand retrieval.

---

## 7. Database Schema

All tables match `atlas-spec/09-contracts.md` Section 3 exactly. Canonical table names are authoritative. Vector columns use `vector(${ATLAS_EMBEDDING_DIM})` — Alembic generates DDL from the env var at migration time.

### 7.1 Core Tables

| Table | Owner (write) | Description |
|---|---|---|
| `master_sessions` | API | One row per agent+human pair, survives all sessions |
| `raw_events` | Engram | Append-only forensic archive of every inbound event |
| `chunks` | Engram (insert), Eidos (classification cols), Kairos (lifecycle cols), Oneiros (archived col) | Primary vector store — HNSW index on embedding |
| `eidos_queue` | Engram (insert), Eidos (status updates) | Dedicated enrichment queue, populated by DB trigger on chunk insert |

### 7.2 Knowledge Graph Tables

| Table | Owner | Description |
|---|---|---|
| `topic_nodes` | Kairos | Cluster centroids + labels |
| `topic_edges` | Kairos | Inter-topic relationships (semantic/temporal/causal) |
| `chunk_topics` | Kairos | Many-to-many junction between chunks and topics |
| `topic_summaries` | Kairos | Progressive summary stack (depths 0–3) per topic |
| `open_loops` | Kairos | Unresolved threads — surfaced by Anamnesis at session start |

### 7.3 Relational and Somatic Tables

| Table | Owner | Description |
|---|---|---|
| `sss_snapshots` | Eidos (initial snap), Psyche (reflection snap) | Time-series SSS — one row per snapshot, dual-owner with `generated_by` discriminator |

`sss_snapshots` is a time-series table, not a single-row "current state." Both Eidos and Psyche append rows; the UI shows the trajectory. Column-level write ownership is defined in `09-contracts.md` Section 4.4.

### 7.4 Procedural Memory Tables

| Table | Owner | Description |
|---|---|---|
| `skill_invocations` | Engram | Detected skill invocation records — Praxis reads for pattern analysis |
| `procedural_notes` | Praxis | Procedural guidance extracted from invocation patterns |
| `praxis_recommendations` | Praxis | Skill improvement proposals — human-review queue |

### 7.5 Behavioral and Prediction Tables

| Table | Owner | Description |
|---|---|---|
| `behavioral_sequences` | Augur | Extracted action sequences — Augur's primary input/output |

Augur predictions are held in the **in-memory prefetch cache** (see Section 6.5), not a database table. This is intentional: predictions are ephemeral and rebuilt each cycle.

### 7.6 Audit Tables

| Table | Owner | Description |
|---|---|---|
| `injection_log` | Anamnesis | Every injection event + gate decision audit trail |
| `consolidated_beliefs` | Oneiros | Generalized beliefs replacing archived episodic chunks |

### 7.7 Async Job Queue (Reflective Sidecars Only)

The `job_queue` table is used **only** by the five reflective sidecars (Kairos, Oneiros, Praxis, Psyche, Augur). Eidos uses its own `eidos_queue`. Engram and Anamnesis are synchronous and use neither.

```sql
CREATE TABLE job_queue (
    job_id       TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    sidecar      TEXT NOT NULL CHECK (sidecar IN (
                     'kairos', 'oneiros', 'praxis', 'psyche', 'augur')),
    job_type     TEXT NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'running', 'done', 'failed')),
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at   TIMESTAMPTZ
);

CREATE INDEX idx_job_queue_pending ON job_queue(sidecar, created_at)
    WHERE status = 'pending';
```

Claim pattern (used by `interval_seconds = 0` sidecars and event-driven workers):
```sql
SELECT * FROM job_queue
WHERE status = 'pending' AND sidecar = $1
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

### 7.8 Schema Evolution

Alembic manages all migrations. `infra/init/schema.sql` is the authoritative initial schema and runs on first container boot. After Unit 1 is complete and signed off, `infra/init/schema.sql` is **frozen** — changes require explicit human approval and a new Alembic migration. See AGENTS.md for the change request protocol.

---

## 8. API Surface

**Auth:** `X-MC-Key` header required on all routes. Session key for hooks; admin key for inspector/admin routes. `X-MC-Human-ID` required on human-scoped routes.

### 8.1 Ingest & Recall (hook-facing)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/ingest` | session | Ingest event → Engram (windowed chunk) → `eidos_queue` row inserted |
| `GET` | `/v1/inject` | session | Anamnesis recall → returns structured inject response (see Section 8.6) |
| `POST` | `/v1/recall` | session | Explicit semantic search (used by `/atlas-recall` skill) |

### 8.2 Session Lifecycle

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/session/start` | session | Create/resume master session; returns orient injection + Augur session brief if available |
| `POST` | `/v1/session/end` | session | Enqueues Praxis job; triggers Psyche reflection cycle |

### 8.3 Memory Inspector (UI-facing)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/v1/chunks` | admin | Paginated chunk list — filters: type, session, date range, somatic_register, provisional, archived |
| `GET` | `/v1/chunks/{id}` | admin | Single chunk detail + related chunks (top-5 by cosine similarity) |
| `PATCH` | `/v1/chunks/{id}` | admin | Patch: archive, validate, adjust confidence |
| `DELETE` | `/v1/chunks/{id}` | admin | Hard delete (operator correction) |
| `GET` | `/v1/topics` | admin | Topic nodes + edges for graph rendering |
| `GET` | `/v1/topics/{id}/chunks` | admin | Chunks belonging to a topic |
| `GET` | `/v1/beliefs` | admin | Consolidated beliefs — sortable by confidence, freshness_sensitivity |
| `GET` | `/v1/sessions` | admin | Master session list + stats (total turns, last active, somatic trend) |
| `GET` | `/v1/somatic` | admin | SSS snapshot history per master_session |
| `GET` | `/v1/open-loops` | admin | Open loop list with status |
| `GET` | `/v1/procedural-notes` | admin | Procedural notes by skill |
| `GET` | `/v1/praxis-recommendations` | admin | Human-review queue — unreviewed recommendations |
| `PATCH` | `/v1/praxis-recommendations/{id}` | admin | Approve or reject a Praxis recommendation |
| `GET` | `/v1/injection-log` | admin | Injection audit trail with gate decision details |

### 8.4 System

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/v1/soul` | session | Read soul.md |
| `PUT` | `/v1/soul` | admin | Write soul.md |
| `GET` | `/v1/export/{human_id}` | admin | Full memory export (JSON archive) |
| `POST` | `/v1/import` | admin | Import memory archive |
| `GET` | `/v1/health` | none | Health + sidecar scheduler status |
| `GET` | `/health` | none | Liveness probe |

### 8.5 WebSocket

| Path | Description |
|---|---|
| `WS /v1/ws/events` | Real-time ingest event stream to observability UI |

### 8.6 Inject Response Schema

`GET /v1/inject` returns:

```json
{
  "inject": true,
  "injection_type": "standard",
  "content": "<xml block — see formats below>",
  "gate_checks_passed": 8,
  "gate_checks_total": 8,
  "confusion_score": 0.12,
  "chunk_ids": ["uuid1", "uuid2"]
}
```

When `inject: false`, `content` is null and `gate_checks_passed` indicates which check failed.

**Injection XML formats** (from `09-contracts.md` Section 6):

```xml
<!-- Standard memory recall -->
<memory relevance="0.87" source="prior_session" age="4_days"
        topic="jwt_auth" somatic_register="collaborative">
  Content framed as recalled context.
</memory>

<!-- Psyche self-narrative (gate bypass, always injected) -->
<self-narrative type="temporal" generated_by="psyche" turn_basis="47-95">
  Second-person cognitive posture update.
</self-narrative>

<!-- Augur session brief (session_start only) -->
<augur_session_brief confidence="0.71" based_on_sessions="23"
                     generated_at="session_start">
  <likely_focus>Predicted primary topic</likely_focus>
  <anticipated_arc><phase>exploration</phase></anticipated_arc>
  <behavioral_notes>Behavioral pattern observations.</behavioral_notes>
</augur_session_brief>

<!-- Praxis procedural note -->
<procedural_note skill="deploy_staging" confidence="0.72"
                 based_on="last_4_invocations">
  Procedural guidance derived from observed invocation patterns.
</procedural_note>

<!-- Memory steering (confusion signal rising) -->
<memory_steering signal="0.58" trend="rising">
  Gentle advisory to step back and restate the goal.
</memory_steering>

<!-- Compaction survival (gate bypass) -->
<memory type="compaction_survival" priority="elevated" chunks_recovered="3">
  Critical information likely lost during context compaction.
</memory>
```

The hook script reads the `content` field and writes it to stdout as the `system-reminder` output.

---

## 9. Observability UI

**Stack:** Vite + React 18 + TypeScript, TanStack Query, TanStack Router, Tailwind CSS, shadcn/ui, D3.js (TopicGraph only).

### 9.1 Pages

| Route | Page | Description |
|---|---|---|
| `/` | Dashboard | Health card, live WS event feed, sidecar scheduler status |
| `/sessions` | SessionList | Master sessions + stats |
| `/sessions/:id` | SessionDetail | Chronological chunk timeline per session |
| `/memory` | ChunkBrowser | Filterable paginated chunks + live WS feed |
| `/memory/:id` | ChunkDetail | Full detail, patch controls, related chunks |
| `/topics` | TopicGraph | D3 force-directed topic graph — click node to drill into chunks |
| `/beliefs` | BeliefList | Consolidated belief cards — sortable by confidence |
| `/somatic` | SomaticView | SSS snapshot history per session |
| `/loops` | OpenLoopList | Open loop tracking with status |
| `/praxis` | PraxisPanel | Procedural notes + human-review recommendation queue |
| `/injection-log` | InjectionLog | Gate decision audit trail |
| `/admin` | AdminPanel | Soul editor, export/import, health |

### 9.2 API Client

**Development phase (Unit 11 parallel build):** Unit 11 builds against `src/api/openapi-stub.yaml` — a hand-authored OpenAPI stub maintained in the repo. This stub encodes the API contract from Section 8 and allows the UI to be built before Unit 8 (FastAPI routes) is complete.

**After Unit 8 completes:** The stub is replaced by the generated schema from `GET /openapi.json`. The `openapi-typescript` codegen step runs in CI.

All components import from TanStack Query hooks in `src/api/hooks/`. No raw fetch calls in component files.

**Auth:** Admin key stored in `localStorage`, sent as `X-MC-Key` on every request. Prompted on first load if not present.

---

## 10. Claude Code CLI Integration

### 10.1 Hooks (`adapters/claude_code/hooks/`)

| Hook file | Event | Atlas call | Notes |
|---|---|---|---|
| `UserPromptSubmit.sh` | User sends message | `POST /v1/ingest` (HUMAN event) | |
| `ModelResponse.sh` | Model replies | `POST /v1/ingest` (MODEL event), then `GET /v1/inject` | Two independent calls — inject does not depend on ingest completing |
| `PreToolUse.sh` | Before tool executes | `POST /v1/ingest` (TOOL_IN event) | |
| `PostToolUse.sh` | After tool completes | `POST /v1/ingest` (TOOL_OUT event), then `GET /v1/inject` | |
| `SessionStart.sh` | Session opens | `POST /v1/session/start` | Returns orient injection + Augur brief |
| `Stop.sh` | Session closes | `POST /v1/session/end` | Triggers Praxis job + Psyche reflection |

Each hook is a minimal bash script. It reads `CLAUDE_HOOK_*` env vars, POSTs JSON to `http://localhost:4200`, and writes the `content` field from the inject response to stdout (which Claude Code injects as `system-reminder`). Ingest and inject calls are independent — a failure in ingest does not block inject, and vice versa.

### 10.2 Skills (`adapters/claude_code/skills/`)

| Skill file | Slash command | Description |
|---|---|---|
| `atlas-recall.md` | `/atlas-recall <query>` | Semantic search via `POST /v1/recall`, prints top-N chunks inline |
| `atlas-soul.md` | `/atlas-soul` | Reads `soul.md` via `GET /v1/soul` and prints it |
| `atlas-snapshot.md` | `/atlas-snapshot` | Enqueues immediate Oneiros consolidation job |
| `atlas-export.md` | `/atlas-export` | Triggers `GET /v1/export/{human_id}`, downloads JSON archive |
| `atlas-health.md` | `/atlas-health` | Prints `GET /v1/health` output — sidecar status, DB, Ollama |
| `atlas-forget.md` | `/atlas-forget <chunk_id>` | Archives a chunk via `PATCH /v1/chunks/{id}` — operator correction |

### 10.3 CLAUDE.md

Installed at `.claude/CLAUDE.md` in the user's project. Covers:

1. **What Atlas is** — one paragraph: ambient memory substrate, not a tool to consciously invoke
2. **Behavior rules** — trust injected `[ATLAS INJECT]` context; do not issue explicit recall queries; do not write to memory directly
3. **Injection interpretation** — how to read `<memory>`, `<self-narrative>`, `<augur_session_brief>`, `<procedural_note>`, `<memory_steering>` blocks
4. **Skill usage guide** — when to invoke `/atlas-recall` (explicit search not ambient), `/atlas-forget` (operator correction), `/atlas-health` (debugging)
5. **Operator correction protocol** — use `/atlas-forget <chunk_id>` for wrong memories, not manual file edits; use `/atlas-soul` to read and `PUT /v1/soul` to edit the self-model

### 10.4 AGENTS.md (root)

Root-level `AGENTS.md` defines the agentic build conventions for parallel agent builds:

**Frozen interfaces** (no changes without human approval):
- `infra/init/schema.sql` — frozen after Unit 1 completes
- `backend/llm/provider.py` (`BaseProvider` protocol) — frozen after Unit 3 completes
- `backend/sidecars/base.py` (`SidecarBase` interface) — frozen after Unit 3 completes
- API route signatures in `backend/api/` — frozen after Unit 8 completes

**Change request protocol:** An agent needing a schema or interface change creates a file at `SCHEMA_CHANGE_REQUEST.md` in the repo root describing the required change and the reason. No agent may modify frozen files unilaterally. A human reviews and approves before the change is applied.

**Directory ownership:** Each build unit owns a directory. Agents write only to their unit's directory. Cross-unit reads are fine; cross-unit writes are not.

**Acceptance tests:** Each unit passes `make test-unit-N` before being declared complete. The test file is co-located with the unit.

---

## 11. Environment Configuration

```bash
# ── Required ────────────────────────────────────────────────────────────────
ATLAS_SESSION_KEY=changeme-session
ATLAS_ADMIN_KEY=changeme-admin

# ── LLM completion backend: claude | openai | ollama ────────────────────────
ATLAS_LLM_BACKEND=claude
ATLAS_LLM_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=                          # required if LLM_BACKEND=claude

# OpenAI-compatible (LLM_BACKEND=openai or EMBED_BACKEND=openai)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_LLM_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small

# Ollama (LLM_BACKEND=ollama or EMBED_BACKEND=ollama)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_LLM_MODEL=llama3

# ── Embedding backend: ollama | openai ──────────────────────────────────────
# Independently configurable from LLM backend.
# Default: ollama (local, no external dependency for embeddings).
ATLAS_EMBED_BACKEND=ollama
ATLAS_EMBED_MODEL=nomic-embed-text
ATLAS_EMBEDDING_DIM=768                     # 768 for nomic-embed-text, 1024 for mxbai-embed-large

# ── Database ────────────────────────────────────────────────────────────────
ATLAS_DB_URL=postgresql+asyncpg://atlas:dev@postgres:5432/atlas
ATLAS_DB_PASSWORD=dev

# ── Sidecar scheduling ──────────────────────────────────────────────────────
# interval_seconds for each APScheduler sidecar.
# 0 = event-triggered only (Praxis); registered as job queue watcher, not interval.
ATLAS_EIDOS_INTERVAL=30          # polls eidos_queue
ATLAS_KAIROS_INTERVAL=300        # topic clustering batch
ATLAS_ONEIROS_INTERVAL=1800      # consolidation run
ATLAS_PRAXIS_INTERVAL=0          # session-end event only
ATLAS_PSYCHE_INTERVAL=60         # reflection cycle
ATLAS_AUGUR_INTERVAL=600         # behavioral prediction cycle
```

---

## 12. Agentic Build Units

Twelve independently buildable units. Each has a clear directory scope, interface contract, and acceptance test.

| Unit | Directory | Description | Depends on |
|---|---|---|---|
| 1 | `infra/init/schema.sql` + Alembic env | Full canonical PostgreSQL schema (all 16 tables) + migration tooling | — |
| 2 | `backend/db/` | Async pool (`asyncpg`), query helpers, job_queue client, eidos_queue client | 1 |
| 3 | `backend/llm/` | `BaseProvider` protocol + Claude, OpenAI-compat, Ollama backends (both LLM + embed) | — |
| 4 | `backend/sidecars/engram/` | Windowed chunking, tail buffer, 4 emission modes, WAL, framework adapters | 2, 3 |
| 5 | `backend/sidecars/eidos/` | Signal classification, somatic tagging, `sss_snapshots` writes, `eidos_queue` polling | 2, 3 |
| 6 | `backend/sidecars/anamnesis/` | 8-gate conjunctive filter, injection formatting, Psyche bypass channel, prefetch cache reads | 2 |
| 7 | `backend/sidecars/kairos/` + `oneiros/` | Topic clustering, progressive summaries, open loops, consolidation | 2, 3 |
| 8 | `backend/sidecars/praxis/` + `psyche/` + `augur/` | Procedural opt., self-narrative, Psyche bypass channel (write side), behavioral prediction | 2, 3 |
| 9 | `backend/api/` + `backend/main.py` | All FastAPI routes, WebSocket, lifespan, APScheduler registration | 2, stubs for 4–8 |
| 10 | `backend/workers/` | APScheduler setup, sidecar registration, Psyche bypass queue injection, job queue watcher | 9, 4–8 |
| 11 | `adapters/claude_code/` | Hooks, skills, CLAUDE.md, AGENTS.md | API contract only (Section 8) |
| 12 | `observability/` | React app — all pages, components, API stub, WS client | API stub in `src/api/openapi-stub.yaml`; Unit 8 for final codegen |
| 13 | `infra/` | Dockerfiles, docker-compose, Makefile, .env.example, README | All |

**Parallel execution waves:**

```
Wave 0 (immediate, no deps):  Unit 1, Unit 3, Unit 11, Unit 12 (partial)
Wave 1 (after 1 + 3):         Unit 2
Wave 2 (after 2):             Units 4, 5, 6, 7, 8 (parallel)
Wave 3 (after 2 + stubs):     Unit 9 (with sidecar stubs)
Wave 4 (after 9 + 4-8):       Unit 10 (full wiring)
Wave 5 (after all):           Unit 13 (infra), Unit 12 (final codegen)
```

---

## 13. Governance Summary

From `atlas-spec/10-governance.md` — build-relevant constraints:

- **`raw_events` retention:** Raw events are append-only and must not be deleted except by explicit operator action (`DELETE /v1/raw-events` with admin key). Retention policy default: 90 days.
- **PII handling:** Content in `chunks` and `raw_events` may contain PII. No external logging of chunk content. Logs may record chunk_ids and metadata only.
- **Auth at rest:** `ATLAS_SESSION_KEY` and `ATLAS_ADMIN_KEY` must not be logged. `.env` must be in `.gitignore`.
- **soul.md:** Written atomically (write-to-temp + rename). Not stored in the database. Human may edit directly — Psyche reads fresh on each cycle.
- **Export/import:** Full export JSON contains all user data. The export endpoint requires admin key. Imports are append-only — existing data is not overwritten.

---

## 14. Success Criteria

- `make health` returns `{"status": "ok"}` with all 8 sidecars listed as active
- Claude Code hooks fire correctly — ingest events appear in ChunkBrowser within 5 seconds
- `/atlas-recall <query>` returns semantically relevant chunks
- Anamnesis `<memory>` block appears in model context on `ModelResponse` hook
- Eidos enriches chunks within 30 seconds of ingest (somatic tags visible in ChunkBrowser)
- TopicGraph renders nodes and edges after 3+ sessions with Kairos active
- `consolidated_beliefs` appear after Oneiros runs on a session with 20+ chunks
- Export/import round-trip preserves all chunks, beliefs, topic nodes, and open loops
- All 3 LLM backends (`claude`, `openai`, `ollama`) pass `make test-unit-3`
- Embedding dimension switches cleanly between 768 and 1024 via env var (Alembic migration required)
- Psyche gate-bypass self-narrative appears in inject response independent of gate checks
- Praxis recommendations appear in UI after a skill is invoked 3+ times in a session
