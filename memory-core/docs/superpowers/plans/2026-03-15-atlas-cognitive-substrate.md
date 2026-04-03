# Atlas Cognitive Substrate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Atlas Cognitive Substrate from scratch — a full cognitive memory system for LLM agents using FastAPI, PostgreSQL/pgvector, Ollama, and a React/TypeScript observability UI.

**Architecture:** Single FastAPI process hosting all 8 sidecars via APScheduler. Real-time layer (Engram, Eidos, Anamnesis) runs synchronously or via DB trigger. Reflective layer (Kairos, Oneiros, Praxis, Psyche, Augur) runs on configurable intervals. React UI is a separate Vite service.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, Alembic, APScheduler, anthropic/openai SDKs, Ollama, PostgreSQL 16 + pgvector, pytest + pytest-asyncio, React 18, TypeScript, Vite, TanStack Query/Router, Tailwind, shadcn/ui, D3.js, Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-15-atlas-cognitive-substrate-design.md`

---

## Parallel Execution Waves

Chunk numbers map to spec Unit numbers as follows: Chunk 1 = Units 1-3 (schema+DB+LLM), Chunk 2 = Units 4-6 (real-time sidecars), Chunk 3 = Units 7-8 (reflective sidecars), Chunk 4 = Units 9-10 (API+workers), Chunk 5 = Unit 13 (infra), Chunk 6 = Unit 11 (adapters), Chunk 7 = Unit 12 (UI).

```
Wave 0 (no deps):        Task 1 (scaffold), Task 2 (schema), Task 5 (LLM provider),
                         Tasks 14 (adapters), Task 15 (UI bootstrap) — fully parallel
Wave 1 (after schema):   Task 3 (Alembic), Task 4 (DB layer + conftest)
Wave 2 (after DB+LLM):   Tasks 6-8 (Engram/Eidos/Anamnesis) parallel with Tasks 9-10 (reflective sidecars)
Wave 3 (after wave 2):   Task 11 (API routes + main.py)
Wave 4 (after wave 3):   Task 12 (workers + scheduler wiring)
Wave 5 (after all):      Task 13 (Docker/Makefile/infra), Task 16 (UI pages), Task 17 (E2E)
```

`make test-unit-N` targets map as: unit-1=schema, unit-2=db, unit-3=llm, unit-4=engram, unit-5=eidos, unit-6=anamnesis, unit-7=kairos-oneiros, unit-8=praxis-psyche-augur, unit-9=api, unit-10=workers, unit-11=adapters, unit-12=ui, unit-13=infra.

---

## File Structure Map

```
atlas/
├── backend/
│   ├── config.py                        # Pydantic Settings
│   ├── main.py                          # FastAPI app + lifespan
│   ├── db/
│   │   ├── __init__.py
│   │   ├── pool.py                      # asyncpg pool management
│   │   ├── migrations/                  # Alembic
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   └── queries/
│   │       ├── chunks.py       # insert_chunk, get_chunk, list_chunks, patch_chunk, delete_chunk, vector_search
│   │       ├── sessions.py     # upsert_master_session, get_master_session, list_sessions
│   │       ├── jobs.py         # enqueue_job, claim_job (SKIP LOCKED), complete_job, fail_job
│   │       ├── eidos_queue.py  # claim_eidos_item, complete_eidos_item, fail_eidos_item
│   │       ├── topics.py       # upsert_topic_node, upsert_topic_edge, assign_chunk_topic, upsert_summary
│   │       ├── beliefs.py      # insert_belief, list_beliefs, get_beliefs_by_topic
│   │       ├── somatic.py      # insert_sss_snapshot, list_sss_snapshots
│   │       └── audit.py        # insert_injection_event, list_injection_log, insert_raw_event
│   │       ├── eidos_queue.py
│   │       ├── topics.py
│   │       ├── beliefs.py
│   │       ├── somatic.py
│   │       └── audit.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── provider.py                  # BaseProvider protocol + factory
│   │   ├── claude.py
│   │   ├── openai_compat.py
│   │   └── ollama.py
│   ├── sidecars/
│   │   ├── base.py                      # SidecarBase ABC
│   │   ├── engram/
│   │   │   ├── __init__.py
│   │   │   ├── sidecar.py
│   │   │   ├── chunker.py               # windowed chunking + tail buffer
│   │   │   ├── emitter.py               # 4 emission modes
│   │   │   ├── wal.py                   # WAL fallback
│   │   │   └── adapters/
│   │   │       ├── base.py
│   │   │       └── claude_code.py
│   │   ├── eidos/
│   │   │   ├── __init__.py
│   │   │   └── sidecar.py
│   │   ├── anamnesis/
│   │   │   ├── __init__.py
│   │   │   ├── sidecar.py
│   │   │   └── gate.py                  # 8-check conjunctive gate
│   │   ├── kairos/
│   │   │   ├── __init__.py
│   │   │   └── sidecar.py
│   │   ├── oneiros/
│   │   │   ├── __init__.py
│   │   │   └── sidecar.py
│   │   ├── praxis/
│   │   │   ├── __init__.py
│   │   │   └── sidecar.py
│   │   ├── psyche/
│   │   │   ├── __init__.py
│   │   │   └── sidecar.py
│   │   └── augur/
│   │       ├── __init__.py
│   │       └── sidecar.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── routes/
│   │   │   ├── ingest.py
│   │   │   ├── inject.py
│   │   │   ├── recall.py
│   │   │   ├── session.py
│   │   │   ├── chunks.py
│   │   │   ├── topics.py
│   │   │   ├── beliefs.py
│   │   │   ├── somatic.py
│   │   │   ├── praxis.py
│   │   │   ├── augur.py
│   │   │   ├── soul.py
│   │   │   ├── export.py
│   │   │   └── health.py
│   │   └── ws.py                        # WebSocket event feed
│   └── workers/
│       ├── __init__.py
│       └── scheduler.py                 # APScheduler + bypass queue injection
├── observability/
│   ├── src/
│   │   ├── api/
│   │   │   ├── openapi-stub.yaml
│   │   │   ├── client.ts
│   │   │   └── hooks/
│   │   │       ├── useChunks.ts
│   │   │       ├── useTopics.ts
│   │   │       ├── useBeliefs.ts
│   │   │       ├── useSessions.ts
│   │   │       └── useHealth.ts
│   │   ├── components/
│   │   │   ├── ChunkBrowser.tsx
│   │   │   ├── ChunkDetail.tsx
│   │   │   ├── TopicGraph.tsx
│   │   │   ├── BeliefList.tsx
│   │   │   ├── SomaticView.tsx
│   │   │   └── LiveFeed.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── SessionList.tsx
│   │   │   ├── SessionDetail.tsx
│   │   │   ├── Memory.tsx
│   │   │   ├── Topics.tsx
│   │   │   ├── Beliefs.tsx
│   │   │   ├── SomaticView.tsx
│   │   │   ├── OpenLoopList.tsx
│   │   │   ├── Praxis.tsx
│   │   │   ├── InjectionLog.tsx
│   │   │   └── Admin.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── Dockerfile.observability
│   └── init/
│       └── schema.sql
├── adapters/
│   └── claude_code/
│       ├── hooks/
│       │   ├── UserPromptSubmit.sh
│       │   ├── ModelResponse.sh
│       │   ├── PreToolUse.sh
│       │   ├── PostToolUse.sh
│       │   ├── SessionStart.sh
│       │   └── Stop.sh
│       ├── skills/
│       │   ├── atlas-recall.md
│       │   ├── atlas-soul.md
│       │   ├── atlas-snapshot.md
│       │   ├── atlas-export.md
│       │   ├── atlas-health.md
│       │   └── atlas-forget.md
│       └── CLAUDE.md
├── tests/
│   ├── conftest.py            # test_db_url fixture, app factory, shared async fixtures
│   ├── test_db.py
│   ├── test_llm_provider.py
│   ├── test_engram.py
│   ├── test_eidos.py
│   ├── test_anamnesis.py
│   ├── test_kairos.py
│   ├── test_oneiros.py
│   ├── test_praxis.py
│   ├── test_psyche.py
│   ├── test_augur.py
│   ├── test_api.py
│   └── test_hooks.sh
├── AGENTS.md
├── Makefile
├── pyproject.toml
└── .env.example
```

---

## Chunk 1: Foundation — Schema + DB Layer + LLM Provider

*Wave 0/1. Units 1–3. No external dependencies.*

### Task 1: Project scaffold + pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `.env.example`
- Create: `AGENTS.md`

- [ ] Create `pyproject.toml`:

```toml
[project]
name = "atlas"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pgvector>=0.3",
    "apscheduler>=3.10",
    "anthropic>=0.40",
    "openai>=1.50",
    "httpx>=0.27",
    "pydantic-settings>=2.5",
    "python-multipart>=0.0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] Create `backend/config.py`:

```python
from pydantic_settings import BaseSettings
from typing import Literal

class Config(BaseSettings):
    # Auth
    atlas_session_key: str = "changeme-session"
    atlas_admin_key: str = "changeme-admin"

    # LLM completion
    atlas_llm_backend: Literal["claude", "openai", "ollama"] = "claude"
    atlas_llm_model: str = "claude-haiku-4-5-20251001"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_llm_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://ollama:11434"
    ollama_llm_model: str = "llama3"

    # Embeddings
    atlas_embed_backend: Literal["ollama", "openai"] = "ollama"
    atlas_embed_model: str = "nomic-embed-text"
    atlas_embedding_dim: int = 768
    openai_embed_model: str = "text-embedding-3-small"

    # Database
    atlas_db_url: str = "postgresql+asyncpg://atlas:dev@postgres:5432/atlas"
    atlas_db_password: str = "dev"

    # Sidecar intervals (seconds; 0 = event-triggered)
    atlas_eidos_interval: int = 30
    atlas_kairos_interval: int = 300
    atlas_oneiros_interval: int = 1800
    atlas_praxis_interval: int = 0
    atlas_psyche_interval: int = 60
    atlas_augur_interval: int = 600

    class Config:
        env_file = ".env"

_cfg: Config | None = None

def get_config() -> Config:
    global _cfg
    if _cfg is None:
        _cfg = Config()
    return _cfg
```

- [ ] Create `.env.example` with all vars from spec Section 11 (blank values, comments)
- [ ] Create `AGENTS.md` with frozen-interface rules and change request protocol from spec Section 10.4

- [ ] Create `tests/conftest.py`:

```python
import asyncio
import os
import pytest
import asyncpg

TEST_DB_URL = os.environ.get(
    "ATLAS_TEST_DB_URL",
    "postgresql://postgres:dev@localhost:5433/atlas_test"
)

@pytest.fixture(scope="session")
def test_db_url():
    return TEST_DB_URL

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_pool(test_db_url):
    pool = await asyncpg.create_pool(test_db_url, min_size=1, max_size=3)
    yield pool
    await pool.close()
```

- [ ] Create `tests/test_hooks.sh` — bash integration test that fires each hook script against a running Atlas instance and asserts HTTP 200 responses:

```bash
#!/usr/bin/env bash
set -euo pipefail
ATLAS_URL="${ATLAS_URL:-http://localhost:4200}"
KEY="${ATLAS_SESSION_KEY:-changeme-session}"

echo "Testing SessionStart hook..."
RESULT=$(CLAUDE_HOOK_HUMAN_ID=test-hooks CLAUDE_HOOK_SESSION_ID=hook-test \
  CLAUDE_HOOK_AGENT_ID=test ATLAS_SESSION_KEY="$KEY" \
  bash adapters/claude_code/hooks/SessionStart.sh)
echo "SessionStart: OK"

echo "All hook tests passed."
```

- [ ] Commit: `git add . && git commit -m "chore: project scaffold, config, conftest.py, test_hooks.sh, AGENTS.md"`

---

### Task 2: PostgreSQL schema

**Files:**
- Create: `infra/init/schema.sql`

- [ ] Write `infra/init/schema.sql` — full canonical schema from `atlas-spec/09-contracts.md` Section 3, all 17 tables.

> **Embedding dimension note:** `schema.sql` hardcodes `vector(768)` as the initial default. The configurable-dimension requirement (acceptance criterion 10) is satisfied by Task 3 (Alembic): `backend/db/migrations/env.py` reads `ATLAS_EMBEDDING_DIM` and the migration that changes the dimension (e.g., 768→1024) must DROP and recreate the HNSW index with the new dimension. `schema.sql` is for first-boot only; all dim changes go through Alembic.

Key tables in order:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- master_sessions
CREATE TABLE master_sessions (
    master_session_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    human_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_master_sessions_human ON master_sessions(human_id);

-- raw_events (append-only forensic archive)
CREATE TABLE raw_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    hook_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    chunk_id TEXT,
    emission_mode TEXT CHECK (emission_mode IN (
        'standalone','tool_episode','discovery_burst','suppressed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_raw_events_session ON raw_events(session_id);

-- chunks (primary vector store)
CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    master_session_id TEXT NOT NULL REFERENCES master_sessions(master_session_id),
    turn_index INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    chunk_type TEXT NOT NULL CHECK (chunk_type IN (
        'human','model','tool_in','tool_out','reasoning','system')),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding vector(768),
    signal_class TEXT CHECK (signal_class IN (
        'episodic','semantic','emotional','environmental','procedural')),
    somatic_valence TEXT CHECK (somatic_valence IN ('positive','neutral','negative')),
    somatic_energy TEXT CHECK (somatic_energy IN ('high','moderate','low')),
    somatic_register TEXT CHECK (somatic_register IN (
        'engaging','tedious','tense','playful','frustrated',
        'collaborative','uncertain','resolved')),
    somatic_relational TEXT CHECK (somatic_relational IN (
        'aligned','misaligned','correcting','exploring')),
    confidence REAL NOT NULL DEFAULT 0.5,
    provisional BOOLEAN NOT NULL DEFAULT FALSE,
    validated BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    input_route TEXT,
    session_gap_hours REAL,
    human_local_time TEXT,
    branch_session_id TEXT,
    branch_hypothesis TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m=16, ef_construction=64);
CREATE INDEX idx_chunks_session ON chunks(session_id);
CREATE INDEX idx_chunks_master_session ON chunks(master_session_id);
CREATE INDEX idx_chunks_type ON chunks(chunk_type);
CREATE INDEX idx_chunks_not_archived ON chunks(archived) WHERE archived=FALSE;
CREATE INDEX idx_chunks_provisional ON chunks(provisional) WHERE provisional=TRUE;
CREATE UNIQUE INDEX idx_chunks_dedup ON chunks(session_id, content_hash);

-- eidos_queue (trigger-populated)
CREATE TABLE eidos_queue (
    chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id),
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','processing','completed','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
CREATE INDEX idx_eidos_queue_pending ON eidos_queue(status) WHERE status='pending';

-- DB trigger: enqueue chunk into eidos_queue after insert
CREATE OR REPLACE FUNCTION enqueue_for_eidos()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO eidos_queue(chunk_id) VALUES (NEW.chunk_id)
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER after_chunk_insert
    AFTER INSERT ON chunks
    FOR EACH ROW EXECUTE FUNCTION enqueue_for_eidos();

-- topic_nodes
CREATE TABLE topic_nodes (
    node_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    keywords JSONB NOT NULL DEFAULT '[]',
    centroid_embedding vector(768),
    chunk_count INTEGER NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ NOT NULL,
    last_active TIMESTAMPTZ NOT NULL,
    session_count INTEGER NOT NULL DEFAULT 1,
    confidence REAL NOT NULL DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_topic_nodes_centroid ON topic_nodes
    USING hnsw (centroid_embedding vector_cosine_ops)
    WITH (m=16, ef_construction=64);

-- topic_edges
CREATE TABLE topic_edges (
    source_node_id TEXT NOT NULL REFERENCES topic_nodes(node_id),
    target_node_id TEXT NOT NULL REFERENCES topic_nodes(node_id),
    edge_type TEXT NOT NULL CHECK (edge_type IN ('semantic','temporal','causal')),
    weight REAL NOT NULL DEFAULT 0.5,
    co_occurrence_count INTEGER NOT NULL DEFAULT 1,
    last_observed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_node_id, target_node_id, edge_type)
);

-- chunk_topics (many-to-many)
CREATE TABLE chunk_topics (
    chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id),
    topic_node_id TEXT NOT NULL REFERENCES topic_nodes(node_id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assignment_method TEXT NOT NULL CHECK (assignment_method IN (
        'heuristic','embedding_similarity','llm_classification','deferred_batch')),
    confidence REAL NOT NULL DEFAULT 0.5,
    PRIMARY KEY (chunk_id, topic_node_id)
);

-- topic_summaries (progressive summary stack depth 0-3)
CREATE TABLE topic_summaries (
    topic_node_id TEXT NOT NULL REFERENCES topic_nodes(node_id),
    depth INTEGER NOT NULL CHECK (depth BETWEEN 0 AND 3),
    content TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    chunk_count_at_generation INTEGER NOT NULL,
    PRIMARY KEY (topic_node_id, depth)
);

-- open_loops
CREATE TABLE open_loops (
    loop_id TEXT PRIMARY KEY,
    master_session_id TEXT NOT NULL REFERENCES master_sessions(master_session_id),
    description TEXT NOT NULL,
    topic_ids JSONB NOT NULL DEFAULT '[]',
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolution_signals JSONB NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','stale')),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_open_loops_master ON open_loops(master_session_id);
CREATE INDEX idx_open_loops_open ON open_loops(status) WHERE status='open';

-- sss_snapshots (time-series, dual-owner)
CREATE TABLE sss_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    master_session_id TEXT NOT NULL REFERENCES master_sessions(master_session_id),
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    turn_index INTEGER NOT NULL,
    relational_warmth REAL NOT NULL,
    cognitive_resonance REAL NOT NULL,
    attunement_quality REAL NOT NULL,
    motivational_engagement REAL NOT NULL,
    accumulated_relational_tone REAL NOT NULL,
    historical_relational_baseline REAL NOT NULL,
    recent_correction_impact REAL NOT NULL DEFAULT 0.0,
    recent_recognition_impact REAL NOT NULL DEFAULT 0.0,
    unresolved_tension REAL NOT NULL DEFAULT 0.0,
    anticipatory_engagement REAL NOT NULL DEFAULT 0.0,
    session_gap_effect REAL NOT NULL DEFAULT 0.0,
    session_arc_phase TEXT NOT NULL CHECK (session_arc_phase IN (
        'opening','developing','deepening','closing','rupture')),
    rupture_active BOOLEAN NOT NULL DEFAULT FALSE,
    rupture_severity REAL,
    generated_by TEXT NOT NULL CHECK (generated_by IN ('eidos','psyche')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sss_master ON sss_snapshots(master_session_id);
CREATE INDEX idx_sss_timestamp ON sss_snapshots(timestamp);

-- skill_invocations (Engram writes, Praxis reads)
CREATE TABLE skill_invocations (
    invocation_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    master_session_id TEXT NOT NULL REFERENCES master_sessions(master_session_id),
    timestamp TIMESTAMPTZ NOT NULL,
    turn_index INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    skill_path TEXT,
    skill_version_hash TEXT,
    preceding_turns INTEGER,
    preceding_tool_calls JSONB DEFAULT '[]',
    human_prompt_before TEXT,
    turns_to_complete INTEGER,
    tool_calls_during JSONB DEFAULT '[]',
    model_corrections INTEGER NOT NULL DEFAULT 0,
    human_corrections INTEGER NOT NULL DEFAULT 0,
    task_complete_message TEXT,
    task_complete_was_null BOOLEAN NOT NULL DEFAULT FALSE,
    subsequent_skill TEXT,
    steps_skipped JSONB DEFAULT '[]',
    steps_added JSONB DEFAULT '[]',
    modifications_made TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_skill_inv_skill ON skill_invocations(skill_name);
CREATE INDEX idx_skill_inv_master ON skill_invocations(master_session_id);

-- procedural_notes (Praxis output)
CREATE TABLE procedural_notes (
    note_id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    based_on_invocations INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated TIMESTAMPTZ,
    outcome_delta_metric TEXT,
    outcome_delta_before REAL,
    outcome_delta_after REAL,
    outcome_delta_sample_size INTEGER
);
CREATE INDEX idx_proc_notes_skill ON procedural_notes(skill_name);

-- praxis_recommendations (human-review queue)
CREATE TABLE praxis_recommendations (
    recommendation_id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    recommendation_type TEXT NOT NULL CHECK (recommendation_type IN (
        'refactor','new_script','step_reorder','deprecation','parameter_change')),
    content TEXT NOT NULL,
    confidence REAL NOT NULL,
    based_on_invocations INTEGER NOT NULL,
    human_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    human_approved BOOLEAN,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_praxis_recs_unreviewed ON praxis_recommendations(human_reviewed)
    WHERE human_reviewed=FALSE;

-- behavioral_sequences (Augur)
CREATE TABLE behavioral_sequences (
    sequence_id TEXT PRIMARY KEY,
    master_session_id TEXT NOT NULL REFERENCES master_sessions(master_session_id),
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    action_detail JSONB,
    topic_id TEXT REFERENCES topic_nodes(node_id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_behavioral_seq_master ON behavioral_sequences(master_session_id);

-- injection_log (Anamnesis audit)
CREATE TABLE injection_log (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hook_type TEXT NOT NULL CHECK (hook_type IN (
        'post_tool_use','user_prompt_submit','pre_compact',
        'session_start','session_end','pre_tool_use')),
    chunks_injected JSONB NOT NULL DEFAULT '[]',
    gate_checks_passed INTEGER NOT NULL,
    gate_checks_total INTEGER NOT NULL,
    confusion_score_at_injection REAL NOT NULL DEFAULT 0.0,
    injection_type TEXT NOT NULL CHECK (injection_type IN (
        'standard','branch_synthesis','compaction_survival',
        'psyche_narrative','augur_brief','praxis_note','memory_steering')),
    gate_details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_injection_log_session ON injection_log(session_id);

-- consolidated_beliefs (Oneiros output)
CREATE TABLE consolidated_beliefs (
    belief_id TEXT PRIMARY KEY,
    topic_node_id TEXT NOT NULL REFERENCES topic_nodes(node_id),
    content TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    belief_type TEXT NOT NULL CHECK (belief_type IN (
        'factual','constraint','preference','pattern','open_question')),
    basis TEXT NOT NULL,
    freshness_sensitivity TEXT NOT NULL DEFAULT 'moderate' CHECK (
        freshness_sensitivity IN ('stable','moderate','volatile')),
    replaces_chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_reviewed TIMESTAMPTZ
);
CREATE INDEX idx_beliefs_topic ON consolidated_beliefs(topic_node_id);
CREATE INDEX idx_beliefs_volatile ON consolidated_beliefs(freshness_sensitivity)
    WHERE freshness_sensitivity='volatile';

-- job_queue (reflective sidecars only)
CREATE TABLE job_queue (
    job_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    sidecar TEXT NOT NULL CHECK (sidecar IN (
        'kairos','oneiros','praxis','psyche','augur')),
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending','running','done','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ
);
CREATE INDEX idx_job_queue_pending ON job_queue(sidecar, created_at)
    WHERE status='pending';
```

- [ ] Verify schema loads against a local postgres with pgvector:
  ```bash
  docker run --rm -e POSTGRES_PASSWORD=dev -p 5433:5432 pgvector/pgvector:pg16 &
  sleep 5
  psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE atlas_test;"
  psql -h localhost -p 5433 -U postgres -d atlas_test -f infra/init/schema.sql
  ```
  Expected: all CREATE TABLE/INDEX statements succeed, no errors.

- [ ] Commit: `git add infra/init/schema.sql && git commit -m "feat: full PostgreSQL schema (17 tables, pgvector, eidos trigger)"`

---

### Task 3: Alembic migrations setup

**Files:**
- Create: `backend/db/migrations/env.py`
- Create: `backend/db/migrations/versions/0001_initial.py`

- [ ] Initialize Alembic: `cd backend && alembic init db/migrations`
- [ ] Write `backend/db/migrations/env.py` to use `ATLAS_DB_URL` from config and support `ATLAS_EMBEDDING_DIM` as a DDL variable
- [ ] Create initial migration that mirrors `schema.sql` exactly (auto-generate from schema, then review)
- [ ] Test: `alembic upgrade head` against test DB — all tables created
- [ ] Commit: `git add backend/db/migrations && git commit -m "feat: Alembic migration setup"`

---

### Task 4: DB pool + query helpers

**Files:**
- Create: `backend/db/pool.py`
- Create: `backend/db/queries/chunks.py`
- Create: `backend/db/queries/sessions.py`
- Create: `backend/db/queries/jobs.py`
- Create: `backend/db/queries/eidos_queue.py`
- Create: `tests/test_db.py`

- [ ] Write failing test first:

```python
# tests/test_db.py
import pytest
from backend.db.pool import get_pool, close_pool

@pytest.mark.asyncio
async def test_pool_connects(test_db_url):
    pool = await get_pool(test_db_url)
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1
    await close_pool()
```

- [ ] Run: `pytest tests/test_db.py -v` → FAIL (pool not implemented)

- [ ] Implement `backend/db/pool.py`:

```python
import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

async def get_pool(url: str | None = None) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        from backend.config import get_config
        cfg = get_config()
        dsn = url or cfg.atlas_db_url.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    return _pool

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
```

- [ ] Write `backend/db/queries/chunks.py` — `insert_chunk`, `get_chunk`, `list_chunks` (filterable), `patch_chunk`, `delete_chunk`, `vector_search` (cosine ANN via pgvector `<=>` operator)
- [ ] Write `backend/db/queries/sessions.py` — `upsert_master_session`, `get_master_session`, `list_sessions`
- [ ] Write `backend/db/queries/jobs.py` — `enqueue_job`, `claim_job` (SKIP LOCKED), `complete_job`, `fail_job`
- [ ] Write `backend/db/queries/eidos_queue.py` — `claim_eidos_item`, `complete_eidos_item`, `fail_eidos_item`
- [ ] Write `backend/db/queries/topics.py` — `upsert_topic_node`, `upsert_topic_edge`, `assign_chunk_topic`, `upsert_topic_summary`, `get_topic_graph` (nodes + edges for UI)
- [ ] Write `backend/db/queries/beliefs.py` — `insert_belief`, `list_beliefs`, `get_beliefs_by_topic`
- [ ] Write `backend/db/queries/somatic.py` — `insert_sss_snapshot`, `list_sss_snapshots` (time-series by master_session)
- [ ] Write `backend/db/queries/audit.py` — `insert_injection_event`, `list_injection_log`, `insert_raw_event`, `delete_raw_events_before` (retention)
- [ ] Add these to `tests/test_db.py` with at least one test per query file verifying round-trip insert + select
- [ ] Run: `pytest tests/test_db.py -v` → PASS
- [ ] Commit: `git add backend/db && git commit -m "feat: DB pool and all query helpers (8 modules)"`

---

### Task 5: LLM provider abstraction

**Files:**
- Create: `backend/llm/provider.py`
- Create: `backend/llm/claude.py`
- Create: `backend/llm/openai_compat.py`
- Create: `backend/llm/ollama.py`
- Create: `tests/test_llm_provider.py`

- [ ] Write failing tests:

```python
# tests/test_llm_provider.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.llm.provider import get_provider, get_embed_provider
from backend.config import Config

@pytest.mark.asyncio
async def test_get_provider_claude():
    cfg = Config(atlas_llm_backend="claude", anthropic_api_key="test-key")
    provider = get_provider(cfg)
    assert provider.__class__.__name__ == "ClaudeProvider"

@pytest.mark.asyncio
async def test_embed_returns_correct_dim():
    cfg = Config(atlas_embed_backend="ollama", atlas_embedding_dim=768)
    provider = get_embed_provider(cfg)
    # Mock the HTTP call
    with patch.object(provider, "_http_embed", return_value=[0.1] * 768):
        result = await provider.embed("hello world")
    assert len(result) == 768

@pytest.mark.asyncio
async def test_provider_factory_all_backends():
    for backend in ["claude", "openai", "ollama"]:
        cfg = Config(atlas_llm_backend=backend)
        provider = get_provider(cfg)
        assert provider is not None
```

- [ ] Run: `pytest tests/test_llm_provider.py -v` → FAIL

- [ ] Implement `backend/llm/provider.py`:

```python
from typing import Protocol, runtime_checkable
from dataclasses import dataclass

@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str

@runtime_checkable
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

def get_provider(cfg) -> BaseProvider:
    match cfg.atlas_llm_backend:
        case "claude":
            from backend.llm.claude import ClaudeProvider
            return ClaudeProvider(cfg)
        case "openai":
            from backend.llm.openai_compat import OpenAICompatProvider
            return OpenAICompatProvider(cfg)
        case "ollama":
            from backend.llm.ollama import OllamaProvider
            return OllamaProvider(cfg)
        case _:
            raise ValueError(f"Unknown LLM backend: {cfg.atlas_llm_backend}")

def get_embed_provider(cfg) -> BaseProvider:
    match cfg.atlas_embed_backend:
        case "ollama":
            from backend.llm.ollama import OllamaProvider
            return OllamaProvider(cfg)
        case "openai":
            from backend.llm.openai_compat import OpenAICompatProvider
            return OpenAICompatProvider(cfg)
        case _:
            raise ValueError(f"Unknown embed backend: {cfg.atlas_embed_backend}")
```

- [ ] Implement `backend/llm/claude.py` — wraps `anthropic.AsyncAnthropic`, implements `complete()` and `embed()` (embed delegates to Ollama HTTP since Claude has no embed API)
- [ ] Implement `backend/llm/openai_compat.py` — wraps `openai.AsyncOpenAI` with `base_url` override; `embed()` calls embeddings endpoint
- [ ] Implement `backend/llm/ollama.py` — pure `httpx.AsyncClient` calls to `/api/chat` and `/api/embeddings`
- [ ] Run: `pytest tests/test_llm_provider.py -v` → PASS
- [ ] Commit: `git add backend/llm && git commit -m "feat: LLM provider abstraction (Claude, OpenAI-compat, Ollama)"`

---

## Chunk 2: Real-Time Sidecars — Engram, Eidos, Anamnesis

*Wave 2. Depends on Chunk 1. Units 4–6.*

### Task 6: SidecarBase + Engram

**Files:**
- Create: `backend/sidecars/base.py`
- Create: `backend/sidecars/engram/chunker.py`
- Create: `backend/sidecars/engram/emitter.py`
- Create: `backend/sidecars/engram/wal.py`
- Create: `backend/sidecars/engram/adapters/claude_code.py`
- Create: `backend/sidecars/engram/sidecar.py`
- Create: `tests/test_engram.py`

- [ ] Write failing tests:

```python
# tests/test_engram.py
import pytest
from backend.sidecars.engram.chunker import Chunker, EmissionMode
from backend.sidecars.engram.adapters.claude_code import ClaudeCodeAdapter

def test_chunker_standalone_emission():
    chunker = Chunker(tail_buffer_size=5)
    event = {"type": "human", "content": "hello", "turn_index": 1}
    chunks = chunker.process(event)
    assert len(chunks) == 1
    assert chunks[0].emission_mode == EmissionMode.STANDALONE

def test_chunker_dedup_same_content():
    chunker = Chunker(tail_buffer_size=5)
    event = {"type": "human", "content": "hello", "turn_index": 1, "session_id": "s1"}
    chunker.process(event)
    chunks2 = chunker.process(event)  # same content, same session
    assert len(chunks2) == 0  # suppressed as duplicate

def test_chunker_tool_episode_pair():
    chunker = Chunker(tail_buffer_size=5)
    tool_in = {"type": "tool_in", "content": "read file", "turn_index": 2, "tool_name": "Read"}
    tool_out = {"type": "tool_out", "content": "file contents", "turn_index": 2, "tool_name": "Read"}
    chunker.process(tool_in)
    chunks = chunker.process(tool_out)
    assert any(c.emission_mode == EmissionMode.TOOL_EPISODE for c in chunks)

def test_claude_code_adapter_normalizes():
    adapter = ClaudeCodeAdapter()
    raw = {"hook_event_name": "UserPromptSubmit", "user_prompt": "fix the bug", "turn_id": "t1"}
    normalized = adapter.normalize(raw)
    assert normalized["type"] == "human"
    assert normalized["content"] == "fix the bug"
```

- [ ] Run: `pytest tests/test_engram.py -v` → FAIL

- [ ] Implement `backend/sidecars/base.py`:

```python
from abc import ABC, abstractmethod
import asyncpg
from backend.llm.provider import BaseProvider
from backend.config import Config

class SidecarBase(ABC):
    def __init__(self, pool: asyncpg.Pool, llm: BaseProvider, embed: BaseProvider, cfg: Config):
        self.pool = pool
        self.llm = llm
        self.embed = embed
        self.cfg = cfg

    @abstractmethod
    async def run_once(self) -> None:
        """Idempotent. Called by APScheduler or job queue watcher."""
        ...

    @property
    @abstractmethod
    def interval_seconds(self) -> int:
        """0 = event-triggered only (job queue watcher, not APScheduler)."""
        ...
```

- [ ] Implement `backend/sidecars/engram/chunker.py` — `Chunker` class with:
  - `tail_buffer: deque` holding recent events
  - `_seen_hashes: dict[str, set]` for per-session dedup
  - `process(event) -> list[NormalizedChunk]` with emission mode logic
  - `EmissionMode` enum: `STANDALONE`, `TOOL_EPISODE`, `DISCOVERY_BURST`, `SUPPRESSED`

- [ ] Implement `backend/sidecars/engram/emitter.py` — `decide_emission_mode(event, buffer) -> EmissionMode`
- [ ] Implement `backend/sidecars/engram/wal.py` — write events to `wal.jsonl` on disk; `replay(pool)` on startup
- [ ] Implement `backend/sidecars/engram/adapters/claude_code.py` — normalize Claude Code hook payloads to common event dict
- [ ] Implement `backend/sidecars/engram/sidecar.py` — `EngramSidecar(SidecarBase)`:
  - `interval_seconds = 0` (event-driven, not scheduled)
  - `ingest(raw_payload, framework="claude_code") -> str` — main entry point called by API
  - Internally: normalize → chunk → embed → write `raw_events` + `chunks` in one transaction → `eidos_queue` row inserted by DB trigger

- [ ] Run: `pytest tests/test_engram.py -v` → PASS
- [ ] Commit: `git add backend/sidecars/engram backend/sidecars/base.py && git commit -m "feat: Engram sidecar (windowed chunking, 4 emission modes, WAL, Claude Code adapter)"`

---

### Task 7: Eidos sidecar

**Files:**
- Create: `backend/sidecars/eidos/sidecar.py`
- Create: `tests/test_eidos.py`

- [ ] Write failing tests:

```python
# tests/test_eidos.py
import pytest
from unittest.mock import AsyncMock
from backend.sidecars.eidos.sidecar import EidosSidecar, classify_signal_class

def test_classify_signal_class_emotional():
    content = "I'm so frustrated with this codebase"
    assert classify_signal_class(content) == "emotional"

def test_classify_signal_class_procedural():
    content = "always run make health before deploying"
    assert classify_signal_class(content) == "procedural"

def test_classify_signal_class_environmental():
    content = '{"status": 200, "body": {"result": "ok"}}'
    assert classify_signal_class(content) == "environmental"

@pytest.mark.asyncio
async def test_eidos_interval():
    sidecar = EidosSidecar.__new__(EidosSidecar)
    sidecar.cfg = type("C", (), {"atlas_eidos_interval": 30})()
    assert sidecar.interval_seconds == 30
```

- [ ] Run: `pytest tests/test_eidos.py -v` → FAIL

- [ ] Implement `backend/sidecars/eidos/sidecar.py`:
  - `classify_signal_class(content: str) -> str` — rule-based classifier (regex patterns for procedural/emotional/environmental, falls back to LLM if ambiguous)
  - `infer_somatic_register(content: str, signal_class: str) -> dict` — maps content patterns to somatic dimensions
  - `run_once()` — claims up to 10 rows from `eidos_queue` (SKIP LOCKED), classifies each, writes classification columns back to `chunks` in a single `UPDATE`, marks `eidos_queue` row complete
  - Also writes an `sss_snapshots` row (generated_by='eidos') after each classification batch if somatic signals changed materially

- [ ] Run: `pytest tests/test_eidos.py -v` → PASS
- [ ] Commit: `git add backend/sidecars/eidos && git commit -m "feat: Eidos sidecar (signal classification, somatic tagging)"`

---

### Task 8: Anamnesis sidecar (8-gate conjunctive filter)

**Files:**
- Create: `backend/sidecars/anamnesis/gate.py`
- Create: `backend/sidecars/anamnesis/sidecar.py`
- Create: `tests/test_anamnesis.py`

- [ ] Write failing tests:

```python
# tests/test_anamnesis.py
import pytest
from backend.sidecars.anamnesis.gate import GateCheck, run_all_gates

def test_similarity_floor_fails_below_threshold():
    candidate = {"similarity": 0.60, "chunk_id": "c1", "content": "x", "created_at": "2026-01-01"}
    result = run_all_gates(
        candidate=candidate,
        context_window_tokens=[],
        session_id="s1",
        confusion_score=0.1,
        injection_history=[],
        threshold=0.72,
    )
    assert result.inject == False
    assert any(c.check_name == "similarity_floor" and not c.passed for c in result.all_failures)

def test_all_gates_pass():
    candidate = {
        "similarity": 0.90,
        "chunk_id": "c1",
        "content": "use JWT tokens for auth",
        "created_at": "2026-01-01",
        "session_id": "old-session",
    }
    result = run_all_gates(
        candidate=candidate,
        context_window_tokens=["unrelated content"],
        session_id="current-session",
        confusion_score=0.1,
        injection_history=[],
        threshold=0.72,
    )
    assert result.inject == True
    assert result.gate_checks_passed == 8
```

- [ ] Run: `pytest tests/test_anamnesis.py -v` → FAIL

- [ ] Implement `backend/sidecars/anamnesis/gate.py` — `GateCheck`, `GateDecision`, `run_all_gates()` implementing all 8 checks:
  1. Similarity floor (>= 0.72)
  2. Not-in-context (content not recoverable from context window)
  3. Temporal confidence (age penalty applied)
  4. Topic frequency (suppress already-injected-frequently topics)
  5. Net-new information (adds info not expressible from context)
  6. Branch contamination (suppress immature branch findings)
  7. Confusion headroom (confusion score allows injection)
  8. Recency flood (suppress current-session content)

- [ ] Implement `backend/sidecars/anamnesis/sidecar.py` — `AnamnesisRecall(SidecarBase)`:
  - Constructor signature: `__init__(self, pool, llm, embed, cfg, bypass_queue: asyncio.Queue[str], augur_cache: dict[str, list[str]])`
  - `bypass_queue` is created in `workers/scheduler.py` and injected at construction. Type is `asyncio.Queue[str]` where the string is a pre-formatted XML self-narrative block.
  - `augur_cache` is a `dict[master_session_id → list[chunk_id]]` maintained by `AugurSidecar` and injected at construction.
  - `interval_seconds = 0` (sync, called inline)
  - `recall(session_id, master_session_id, query_embedding, hook_type, context_tokens) -> InjectResponse` — runs vector search, applies gate, formats XML, logs to `injection_log`
  - Reads Psyche bypass channel (`bypass_queue.get_nowait()` if not empty) and prepends any pending self-narrative unconditionally before gate
  - Reads `augur_cache[master_session_id]` before issuing vector query — uses prefetched chunk IDs as priority candidates

- [ ] Run: `pytest tests/test_anamnesis.py -v` → PASS
- [ ] Commit: `git add backend/sidecars/anamnesis && git commit -m "feat: Anamnesis sidecar (8-gate conjunctive filter, injection formatting)"`

---

## Chunk 3: Reflective Sidecars — Kairos, Oneiros, Praxis, Psyche, Augur

*Wave 2 (parallel with Chunk 2). Depends on Tasks 2 (schema), 4 (DB layer), and 5 (LLM provider) — all of which are in Wave 0/1. Do NOT start until Task 4 is complete. Units 7–8.*

### Task 9: Kairos + Oneiros

**Files:**
- Create: `backend/sidecars/kairos/sidecar.py`
- Create: `backend/sidecars/oneiros/sidecar.py`
- Create: `tests/test_kairos.py`
- Create: `tests/test_oneiros.py`

- [ ] Write failing tests:

```python
# tests/test_kairos.py
from backend.sidecars.kairos.sidecar import KairosSidecar, assign_chunk_to_topic

def test_assign_chunk_creates_new_topic_when_no_match():
    """When no existing topic is similar enough, a new one is created."""
    existing_topics = []  # no topics yet
    chunk_embedding = [0.1] * 768
    result = assign_chunk_to_topic(chunk_embedding, existing_topics, threshold=0.75)
    assert result["action"] == "create_new"

def test_assign_chunk_merges_when_similar():
    existing = [{"node_id": "t1", "centroid": [0.9] * 768, "label": "auth"}]
    chunk_embedding = [0.85] * 768
    result = assign_chunk_to_topic(chunk_embedding, existing, threshold=0.75)
    assert result["action"] == "assign_existing"
    assert result["topic_id"] == "t1"
```

```python
# tests/test_oneiros.py
from backend.sidecars.oneiros.sidecar import OnerosSidecar, should_consolidate

def test_should_consolidate_threshold():
    """A cluster of 10+ old chunks should trigger consolidation."""
    chunks = [{"chunk_id": f"c{i}", "archived": False, "created_at": "2026-01-01"} for i in range(12)]
    assert should_consolidate(chunks, min_cluster_size=10) == True

def test_should_not_consolidate_small_cluster():
    chunks = [{"chunk_id": f"c{i}", "archived": False} for i in range(3)]
    assert should_consolidate(chunks, min_cluster_size=10) == False
```

- [ ] Run both test files → FAIL
- [ ] Implement `backend/sidecars/kairos/sidecar.py`:
  - `interval_seconds` from `cfg.atlas_kairos_interval`
  - `run_once()` — reads unassigned chunks (no `chunk_topics` row), computes cosine similarity against existing topic centroids, assigns or creates topics, updates `topic_summaries` (depths 0–2), detects open loops
  - Uses LLM to generate topic labels and depth-2 summaries

- [ ] Implement `backend/sidecars/oneiros/sidecar.py`:
  - `interval_seconds` from `cfg.atlas_oneiros_interval`
  - `run_once()` — finds topics with 10+ unarchived chunks older than threshold, calls LLM to synthesize a `ConsolidatedBelief`, then in a single transaction: `INSERT consolidated_beliefs` + `UPDATE chunks SET archived=TRUE` (atomic per spec Section 5.5)

- [ ] Run both test files → PASS
- [ ] Commit: `git add backend/sidecars/kairos backend/sidecars/oneiros && git commit -m "feat: Kairos (topic clustering) + Oneiros (consolidation) sidecars"`

---

### Task 10: Praxis + Psyche + Augur

**Files:**
- Create: `backend/sidecars/praxis/sidecar.py`
- Create: `backend/sidecars/psyche/sidecar.py`
- Create: `backend/sidecars/augur/sidecar.py`
- Create: `tests/test_praxis.py`
- Create: `tests/test_psyche.py`
- Create: `tests/test_augur.py`

- [ ] Write failing tests:

```python
# tests/test_praxis.py
from backend.sidecars.praxis.sidecar import PraxisSidecar, extract_patterns

def test_extract_patterns_detects_skip():
    invocations = [
        {"skill_name": "deploy", "steps_skipped": ["health_check"], "turns_to_complete": 5},
        {"skill_name": "deploy", "steps_skipped": ["health_check"], "turns_to_complete": 7},
        {"skill_name": "deploy", "steps_skipped": ["health_check"], "turns_to_complete": 6},
    ]
    patterns = extract_patterns(invocations)
    assert any("health_check" in p["observation"] for p in patterns)
```

```python
# tests/test_psyche.py
from backend.sidecars.psyche.sidecar import PsycheSidecar, compute_session_arc_phase

def test_arc_phase_opening_at_start():
    assert compute_session_arc_phase(turn_index=2, total_turns_estimate=40) == "opening"

def test_arc_phase_closing_at_end():
    assert compute_session_arc_phase(turn_index=38, total_turns_estimate=40) == "closing"
```

```python
# tests/test_augur.py
from backend.sidecars.augur.sidecar import AugurSidecar, extract_behavioral_sequences

def test_extract_sequences_produces_records():
    chunks = [
        {"chunk_type": "human", "content": "fix auth", "turn_index": 1},
        {"chunk_type": "tool_in", "content": "read file", "turn_index": 2},
    ]
    seqs = extract_behavioral_sequences("session-1", "master-1", chunks)
    assert len(seqs) == 2
    assert seqs[0]["action_type"] == "human_message"
```

- [ ] Run all three test files → FAIL
- [ ] Implement `backend/sidecars/praxis/sidecar.py`:
  - `interval_seconds = 0` (session-end triggered via job_queue)
  - `run_once()` — claims a `praxis` job from `job_queue`, reads `skill_invocations` for the session, calls `extract_patterns()`, upserts `procedural_notes`, creates `praxis_recommendations` for human review

- [ ] Implement `backend/sidecars/psyche/sidecar.py`:
  - `interval_seconds` from `cfg.atlas_psyche_interval`
  - `run_once()` — reads recent chunks + `sss_snapshots` for trajectory, calls LLM to generate self-narrative XML (`<self-narrative>`), writes result to `psyche_bypass_queue` (asyncio.Queue), updates `soul.md` if relational arc shifted materially

- [ ] Implement `backend/sidecars/augur/sidecar.py`:
  - `interval_seconds` from `cfg.atlas_augur_interval`
  - `run_once()` — reads recent session chunks, extracts behavioral sequences, writes to `behavioral_sequences`, updates in-memory prefetch cache (`dict[master_session_id, list[chunk_id]]`)

- [ ] Run all three test files → PASS
- [ ] Commit: `git add backend/sidecars/praxis backend/sidecars/psyche backend/sidecars/augur && git commit -m "feat: Praxis + Psyche + Augur sidecars"`

---

## Chunk 4: API Layer + Workers + Integration

*Wave 3. Depends on Chunks 1–3.*

### Task 11: Auth + API skeleton

**Files:**
- Create: `backend/api/auth.py`
- Create: `backend/api/__init__.py`
- Create: `backend/main.py`
- Create: `tests/test_api.py`

- [ ] Write failing test:

```python
# tests/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import create_app

@pytest.mark.asyncio
async def test_health_no_auth():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_ingest_requires_auth():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/ingest", json={})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_ingest_with_session_key():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/ingest",
            json={"session_id": "s1", "human_id": "h1", "agent_id": "a1",
                  "hook_type": "user_prompt_submit", "payload": {"content": "hello"}},
            headers={"X-MC-Key": "changeme-session", "X-MC-Human-ID": "h1"},
        )
    assert resp.status_code == 200
```

- [ ] Run: `pytest tests/test_api.py -v` → FAIL

- [ ] Implement `backend/api/auth.py`:

```python
from fastapi import Header, HTTPException
from backend.config import get_config

def require_session_key(x_mc_key: str = Header(...)):
    cfg = get_config()
    if x_mc_key not in (cfg.atlas_session_key, cfg.atlas_admin_key):
        raise HTTPException(401, "Invalid key")

def require_admin_key(x_mc_key: str = Header(...)):
    cfg = get_config()
    if x_mc_key != cfg.atlas_admin_key:
        raise HTTPException(401, "Admin key required")

def get_human_id(x_mc_human_id: str = Header(...)) -> str:
    return x_mc_human_id
```

- [ ] Implement `backend/main.py` with `create_app()` factory and lifespan (pool init, Augur cache init, psyche bypass queue init)
- [ ] Implement `backend/api/routes/ingest.py` — `POST /v1/ingest`: normalizes payload, instantiates `EngramSidecar` (obtained from app state set in lifespan), calls `await engram.ingest(payload, framework="claude_code")`, broadcasts to WebSocket clients. The `EngramSidecar` instance lives on `app.state.engram` — set in `main.py` lifespan alongside the pool.
- [ ] Implement `backend/api/routes/inject.py` — `GET /v1/inject`: obtains query embedding via embed provider, calls `await anamnesis.recall(...)`, returns structured inject response (Section 8.6 of spec)
- [ ] Implement `backend/api/routes/recall.py` — `POST /v1/recall`: explicit semantic search, returns top-k chunks with similarity scores
- [ ] Implement `backend/api/routes/session.py` — `POST /v1/session/start` and `/end`
- [ ] Implement `backend/api/routes/chunks.py` — `GET/GET-one/PATCH/DELETE /v1/chunks`
- [ ] Implement `backend/api/routes/topics.py` — `GET /v1/topics`, `GET /v1/topics/{id}/chunks`
- [ ] Implement `backend/api/routes/beliefs.py` — `GET /v1/beliefs`
- [ ] Implement `backend/api/routes/somatic.py` — `GET /v1/somatic`
- [ ] Implement `backend/api/routes/praxis.py` — `GET /v1/procedural-notes`, `GET /v1/praxis-recommendations`, `PATCH /v1/praxis-recommendations/{id}`
- [ ] Implement `backend/api/routes/injection_log.py` — `GET /v1/injection-log`
- [ ] Implement `backend/api/routes/open_loops.py` — `GET /v1/open-loops`
- [ ] Implement `backend/api/routes/soul.py` — `GET/PUT /v1/soul`
- [ ] Implement `backend/api/routes/export.py` — `GET /v1/export/{human_id}`, `POST /v1/import`, **`DELETE /v1/raw-events`** (admin, per governance Section 13 — deletes raw_events older than a given date via `db/queries/audit.delete_raw_events_before`)
- [ ] Implement `backend/api/routes/health.py` — `GET /health` (liveness), `GET /v1/health` (sidecar scheduler status from `app.state.scheduler`)
- [ ] Implement `backend/api/ws.py` — WebSocket manager that broadcasts ingest events
- [ ] Run: `pytest tests/test_api.py -v` → PASS
- [ ] Commit: `git add backend/api backend/main.py && git commit -m "feat: FastAPI routes (all 25 endpoints + WebSocket)"`

---

### Task 12: APScheduler workers + full wiring

**Files:**
- Create: `backend/workers/scheduler.py`
- Create: `tests/test_workers.py`

- [ ] Write failing test:

```python
# tests/test_workers.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.workers.scheduler import build_scheduler

@pytest.mark.asyncio
async def test_scheduler_registers_interval_sidecars():
    mock_pool = AsyncMock()
    mock_llm = AsyncMock()
    mock_embed = AsyncMock()
    cfg = type("C", (), {
        "atlas_eidos_interval": 30,
        "atlas_kairos_interval": 300,
        "atlas_oneiros_interval": 1800,
        "atlas_praxis_interval": 0,
        "atlas_psyche_interval": 60,
        "atlas_augur_interval": 600,
    })()

    scheduler, bypass_queue, sidecars = build_scheduler(mock_pool, mock_llm, mock_embed, cfg)
    job_ids = [job.id for job in scheduler.get_jobs()]
    # Praxis has interval=0, should NOT be in scheduler jobs
    assert "praxis" not in job_ids
    # Others should be registered
    assert any("kairos" in j for j in job_ids)
    assert any("psyche" in j for j in job_ids)
```

- [ ] Run: `pytest tests/test_workers.py -v` → FAIL

- [ ] Implement `backend/workers/scheduler.py`:

```python
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.sidecars.eidos.sidecar import EidosSidecar
from backend.sidecars.kairos.sidecar import KairosSidecar
from backend.sidecars.oneiros.sidecar import OnerosSidecar
from backend.sidecars.praxis.sidecar import PraxisSidecar
from backend.sidecars.psyche.sidecar import PsycheSidecar
from backend.sidecars.augur.sidecar import AugurSidecar

def build_scheduler(pool, llm, embed, cfg):
    bypass_queue: asyncio.Queue[str] = asyncio.Queue()

    sidecars = {
        "eidos":   EidosSidecar(pool, llm, embed, cfg),
        "kairos":  KairosSidecar(pool, llm, embed, cfg),
        "oneiros": OnerosSidecar(pool, llm, embed, cfg),
        "praxis":  PraxisSidecar(pool, llm, embed, cfg),
        "psyche":  PsycheSidecar(pool, llm, embed, cfg, bypass_queue=bypass_queue),
        "augur":   AugurSidecar(pool, llm, embed, cfg),
    }

    scheduler = AsyncIOScheduler()

    for name, sidecar in sidecars.items():
        if sidecar.interval_seconds > 0:
            scheduler.add_job(
                sidecar.run_once,
                "interval",
                seconds=sidecar.interval_seconds,
                id=name,
                max_instances=1,
                coalesce=True,
            )
        # interval_seconds == 0 → polled by job queue watcher task

    return scheduler, bypass_queue, sidecars
```

- [ ] Run: `pytest tests/test_workers.py -v` → PASS
- [ ] Wire `build_scheduler` into `backend/main.py` lifespan — start/stop scheduler, inject bypass_queue and Augur prefetch cache into Anamnesis
- [ ] Commit: `git add backend/workers && git commit -m "feat: APScheduler wiring, Psyche bypass queue, job queue watcher"`

---

## Chunk 5: Infra — Docker + Makefile

*Wave 3 (can start earlier — needs only Dockerfiles to exist).*

### Task 13: Docker Compose + Dockerfiles

**Files:**
- Create: `infra/docker-compose.yml`
- Create: `infra/Dockerfile.backend`
- Create: `infra/Dockerfile.observability`
- Create: `Makefile`

- [ ] Write `infra/Dockerfile.backend`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[dev]"
COPY backend/ ./backend/
COPY infra/init/schema.sql ./infra/init/schema.sql
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "4200"]
```

- [ ] Write `infra/Dockerfile.observability`:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY observability/package.json observability/package-lock.json ./
RUN npm ci
COPY observability/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
```

- [ ] Write `infra/docker-compose.yml` (4 services: postgres, ollama, backend, observability) — from spec Section 5
- [ ] Write `Makefile` with targets:
  - `make setup` — build images + `docker compose up -d`
  - `make health` — `curl http://localhost:4200/health`
  - `make test` — `pytest tests/ -v`
  - `make test-unit-1` — `psql ... -f infra/init/schema.sql` (schema loads clean)
  - `make test-unit-2` — `pytest tests/test_db.py -v`
  - `make test-unit-3` — `pytest tests/test_llm_provider.py -v`
  - `make test-unit-4` — `pytest tests/test_engram.py -v`
  - `make test-unit-5` — `pytest tests/test_eidos.py -v`
  - `make test-unit-6` — `pytest tests/test_anamnesis.py -v`
  - `make test-unit-7` — `pytest tests/test_kairos.py tests/test_oneiros.py -v`
  - `make test-unit-8` — `pytest tests/test_praxis.py tests/test_psyche.py tests/test_augur.py -v`
  - `make test-unit-9` — `pytest tests/test_api.py -v`
  - `make test-unit-10` — `pytest tests/test_workers.py -v`
  - `make test-unit-11` — `bash tests/test_hooks.sh`
  - `make test-unit-12` — `cd observability && npm run build`
  - `make test-unit-13` — `docker compose config --quiet` (validates compose file)
  - `make logs` — `docker compose logs -f backend`
  - `make export` — `curl -s http://localhost:4200/v1/export/default -H "X-MC-Key: $$ATLAS_ADMIN_KEY" -H "X-MC-Human-ID: default" > backup_$$(date +%Y%m%d).json`
  - `make import` — `curl -sf -X POST http://localhost:4200/v1/import ...`

- [ ] Run `make setup` against local Docker — all 4 services start, `make health` returns `{"status":"ok"}`
- [ ] Commit: `git add infra Makefile && git commit -m "feat: Docker Compose, Dockerfiles, Makefile"`

---

## Chunk 6: Claude Code Adapters

*Wave 0 — no backend dependency, only needs API contract.*

### Task 14: Hooks + CLAUDE.md + Skills

**Files:**
- Create: `adapters/claude_code/hooks/SessionStart.sh`
- Create: `adapters/claude_code/hooks/Stop.sh`
- Create: `adapters/claude_code/hooks/UserPromptSubmit.sh`
- Create: `adapters/claude_code/hooks/ModelResponse.sh`
- Create: `adapters/claude_code/hooks/PreToolUse.sh`
- Create: `adapters/claude_code/hooks/PostToolUse.sh`
- Create: `adapters/claude_code/skills/atlas-recall.md`
- Create: `adapters/claude_code/skills/atlas-soul.md`
- Create: `adapters/claude_code/skills/atlas-snapshot.md`
- Create: `adapters/claude_code/skills/atlas-export.md`
- Create: `adapters/claude_code/skills/atlas-health.md`
- Create: `adapters/claude_code/skills/atlas-forget.md`
- Create: `adapters/claude_code/CLAUDE.md`

- [ ] Write `adapters/claude_code/hooks/SessionStart.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ATLAS_URL="${ATLAS_URL:-http://localhost:4200}"
ATLAS_SESSION_KEY="${ATLAS_SESSION_KEY:-changeme-session}"
HUMAN_ID="${CLAUDE_HOOK_HUMAN_ID:-default}"
SESSION_ID="${CLAUDE_HOOK_SESSION_ID:-$(uuidgen)}"
AGENT_ID="${CLAUDE_HOOK_AGENT_ID:-claude-code}"

RESPONSE=$(curl -sf -X POST "$ATLAS_URL/v1/session/start" \
  -H "Content-Type: application/json" \
  -H "X-MC-Key: $ATLAS_SESSION_KEY" \
  -H "X-MC-Human-ID: $HUMAN_ID" \
  -d "{\"session_id\":\"$SESSION_ID\",\"agent_id\":\"$AGENT_ID\",\"human_id\":\"$HUMAN_ID\"}" \
  2>/dev/null || echo '{}')

CONTENT=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('content',''))" 2>/dev/null || true)

if [ -n "$CONTENT" ]; then
  echo "$CONTENT"
fi
```

- [ ] Write all 6 hook scripts following the same pattern — ingest calls POST, inject calls GET, print `content` field to stdout
- [ ] Key difference for `ModelResponse.sh` and `PostToolUse.sh`: make **two independent curl calls** — first POST to `/v1/ingest`, then GET `/v1/inject`. A failure in ingest must not block inject (use `|| true` on ingest)
- [ ] Write `adapters/claude_code/CLAUDE.md` — full system instructions per spec Section 10.3

- [ ] Write all 6 skill files in Claude Code skill format:

```markdown
---
name: atlas-recall
description: Search Atlas memory for relevant chunks matching a query
---

Search Atlas memory for chunks semantically similar to the given query.

1. Run: `curl -sf -X POST http://localhost:4200/v1/recall \
   -H "X-MC-Key: $ATLAS_SESSION_KEY" \
   -H "X-MC-Human-ID: $HUMAN_ID" \
   -H "Content-Type: application/json" \
   -d '{"query":"<USER_QUERY>","top_k":5,"session_id":"<SESSION_ID>"}'`
2. Print the returned chunks with their relevance scores and content
3. Note the chunk_ids for potential use with /atlas-forget
```

- [ ] Test hooks by running against a live Atlas instance:
  ```bash
  ATLAS_SESSION_KEY=changeme-session CLAUDE_HOOK_HUMAN_ID=test \
    CLAUDE_HOOK_SESSION_ID=test-session CLAUDE_HOOK_AGENT_ID=test \
    bash adapters/claude_code/hooks/SessionStart.sh
  ```
  Expected: JSON or XML inject content printed, no errors

- [ ] Commit: `git add adapters/claude_code && git commit -m "feat: Claude Code hooks, skills, CLAUDE.md"`

---

## Chunk 7: Observability UI

*Wave 0/5 — builds against OpenAPI stub, final codegen after API is complete.*

### Task 15: React app bootstrap + API client

**Files:**
- Create: `observability/package.json`
- Create: `observability/vite.config.ts`
- Create: `observability/src/main.tsx`
- Create: `observability/src/api/openapi-stub.yaml`
- Create: `observability/src/api/client.ts`
- Create: `observability/src/api/hooks/useChunks.ts`
- Create: `observability/src/api/hooks/useHealth.ts`

- [ ] Init project:
  ```bash
  cd observability
  npm create vite@latest . -- --template react-ts
  npm install @tanstack/react-query @tanstack/react-router \
    tailwindcss @shadcn/ui d3 openapi-typescript
  npx tailwindcss init
  ```

- [ ] Write `observability/src/api/openapi-stub.yaml` — hand-authored OpenAPI 3.1 spec capturing all routes from spec Section 8, response schemas for chunks, topics, beliefs, sessions, somatic, inject response

- [ ] Generate types: `npx openapi-typescript src/api/openapi-stub.yaml -o src/api/types.ts`

- [ ] Write `observability/src/api/client.ts` — typed fetch wrapper using generated types, reads `VITE_ATLAS_URL` and admin key from `localStorage`

- [ ] Write TanStack Query hooks in `src/api/hooks/`:
  - `useChunks(filters)` — `GET /v1/chunks` with pagination
  - `useChunk(id)` — `GET /v1/chunks/:id`
  - `useTopics()` — `GET /v1/topics`
  - `useBeliefs()` — `GET /v1/beliefs`
  - `useSessions()` — `GET /v1/sessions`
  - `useSomatic(masterSessionId)` — `GET /v1/somatic`
  - `useHealth()` — `GET /v1/health`
  - `useInjectionLog()` — `GET /v1/injection-log`

- [ ] Run: `npm run dev` → app starts at `http://localhost:5173`
- [ ] Commit: `git add observability && git commit -m "feat: React app bootstrap, API stub, typed client, TanStack Query hooks"`

---

### Task 16: Core UI pages

**Files:**
- Create: `observability/src/pages/Dashboard.tsx`
- Create: `observability/src/pages/Memory.tsx`
- Create: `observability/src/components/ChunkBrowser.tsx`
- Create: `observability/src/components/ChunkDetail.tsx`
- Create: `observability/src/pages/Topics.tsx`
- Create: `observability/src/components/TopicGraph.tsx`
- Create: `observability/src/components/LiveFeed.tsx`
- Create: `observability/src/api/ws.ts`

- [ ] Implement `observability/src/api/ws.ts` — WebSocket client connecting to `WS /v1/ws/events`, exposes `useEventFeed()` hook

- [ ] Implement `LiveFeed.tsx` — scrolling list of recent ingest events from WebSocket, shows chunk_type badge + content preview + timestamp

- [ ] Implement `Dashboard.tsx`:
  - Health card (sidecar status grid from `useHealth()`)
  - LiveFeed panel (right side)
  - Stats row: total chunks, sessions, beliefs

- [ ] Implement `ChunkBrowser.tsx`:
  - Filterable table (chunk_type, somatic_register, provisional, archived, date range)
  - Paginated via TanStack Query infinite scroll
  - Row actions: View, Archive, Validate, Delete

- [ ] Implement `ChunkDetail.tsx`:
  - Full content display
  - Metadata grid (confidence, somatic dimensions, signal_class, topic assignments)
  - Confidence slider (PATCH on change)
  - Archive/Validate toggle buttons
  - Related chunks panel (top-5 by cosine similarity via `/v1/recall`)

- [ ] Implement `TopicGraph.tsx`:
  - D3 force-directed graph of `topic_nodes` (size = chunk_count) and `topic_edges` (weight = line thickness)
  - Click node → filter ChunkBrowser to that topic

- [ ] Implement `SessionList.tsx` — table of master sessions, stats, click → `SessionDetail.tsx`
- [ ] Implement `SessionDetail.tsx` — chronological chunk timeline for a session, filterable by chunk_type
- [ ] Implement `Beliefs.tsx` — card list of `consolidated_beliefs`, sortable by confidence/type
- [ ] Implement `SomaticView.tsx` — time-series SSS line chart per master session (relational_warmth, cognitive_resonance over time)
- [ ] Implement `OpenLoopList.tsx` — table of `open_loops` with status badges; route `/loops`
- [ ] Implement `Praxis.tsx` — two panels: procedural notes by skill, and `praxis_recommendations` review queue with Approve/Reject buttons (PATCH `/v1/praxis-recommendations/{id}`)
- [ ] Implement `InjectionLog.tsx` — paginated table of injection events, gate_checks_passed/total, confusion_score, injection_type badge
- [ ] Implement `Admin.tsx` — soul.md textarea editor (GET/PUT `/v1/soul`), export button, import dropzone, health summary card

- [ ] Run `npm run build` — no TypeScript errors
- [ ] Commit: `git add observability/src && git commit -m "feat: all observability UI pages and components"`

---

## Final Integration Verification

### Task 17: End-to-end smoke test

- [ ] Start full stack: `make setup`
- [ ] Pull Ollama model: `docker exec atlas-ollama ollama pull nomic-embed-text`
- [ ] Verify health: `make health` → `{"status":"ok"}`
- [ ] Install Claude Code hooks: `cp -r adapters/claude_code/hooks ~/.claude/hooks/`
- [ ] Trigger a test session:
  ```bash
  ATLAS_SESSION_KEY=changeme-session CLAUDE_HOOK_HUMAN_ID=test \
    CLAUDE_HOOK_SESSION_ID=e2e-test CLAUDE_HOOK_AGENT_ID=test \
    bash adapters/claude_code/hooks/SessionStart.sh
  ```
  Expected: orient injection XML printed

- [ ] Ingest a test chunk directly:
  ```bash
  curl -sf -X POST http://localhost:4200/v1/ingest \
    -H "X-MC-Key: changeme-session" \
    -H "X-MC-Human-ID: test" \
    -H "Content-Type: application/json" \
    -d '{"session_id":"e2e-test","human_id":"test","agent_id":"test",
         "hook_type":"user_prompt_submit","payload":{"content":"always use JWT for auth"}}'
  ```

- [ ] Wait 35 seconds for Eidos to classify, then verify in UI: open `http://localhost:5173/memory` → chunk appears with signal_class populated

- [ ] Verify inject returns content:
  ```bash
  curl -sf "http://localhost:4200/v1/inject?session_id=e2e-test&human_id=test&query=authentication&hook_type=user_prompt_submit" \
    -H "X-MC-Key: changeme-session" -H "X-MC-Human-ID: test"
  ```
  Expected: `{"inject":true,"content":"<memory ...>..."}` or `{"inject":false}` with gate details

- [ ] Run full test suite: `make test` → all tests pass
- [ ] Commit: `git add . && git commit -m "chore: end-to-end smoke test verified"`

---

## Acceptance Checklist (from spec Section 14)

- [ ] `make health` returns `{"status":"ok"}` with all 8 sidecars listed
- [ ] Hook fires correctly — ingest events appear in ChunkBrowser within 5 seconds
- [ ] `/atlas-recall <query>` returns semantically relevant chunks
- [ ] Anamnesis `<memory>` block appears in inject response
- [ ] Eidos enriches chunks within 30 seconds (somatic tags visible)
- [ ] TopicGraph renders after 3+ sessions with Kairos active
- [ ] `consolidated_beliefs` appear after Oneiros run on 20+ chunks
- [ ] Export/import round-trip preserves all data
- [ ] All 3 LLM backends pass `make test-unit-3`
- [ ] Embedding dimension switches 768↔1024 via env var + Alembic migration
- [ ] Psyche gate-bypass self-narrative appears in inject independent of gate
- [ ] Praxis recommendations appear after 3+ skill invocations
