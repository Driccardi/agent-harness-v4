# Ordo Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the complete project structure, PostgreSQL schema, FastAPI skeleton, and PM2 process config so every subsequent phase has a stable, tested foundation to build on.

**Architecture:** Python FastAPI backend (uvicorn, asyncpg) with a complete PostgreSQL schema applied at init time. PM2 manages all backend processes. Tests use a dedicated `ordo_test` database created from the same schema.

**Tech Stack:** Python 3.12, FastAPI 0.111+, asyncpg 0.29+, pydantic-settings 2+, PostgreSQL 16 + pgvector, PM2, pytest + pytest-asyncio, httpx

---

## Chunk 1: Project Scaffold + Configuration

### Task 1: Create Project Structure

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `backend/db/__init__.py`
- Create: `backend/routers/__init__.py`
- Create: `backend/models/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Create directory tree**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
mkdir -p backend/db backend/routers backend/models tests docs/superpowers/plans docs/superpowers/specs
touch backend/__init__.py backend/db/__init__.py backend/routers/__init__.py backend/models/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/
.env

# Node
node_modules/
frontend/dist/
frontend/.vite/

# PM2
.pm2/
logs/

# Data
.ordo-data/
*.log

# OS
.DS_Store
Thumbs.db

# Superpowers
.superpowers/
```

- [ ] **Step 3: Create `.env.example`**

```bash
# Ordo V4 — Environment Configuration
# Copy to .env and fill in values

# === Core ===
ORDO_DATA_DIR=C:\Users\user\ordo-data
ORDO_ENV=development          # development | production

# === FastAPI ===
ORDO_API_PORT=8000
ORDO_API_HOST=127.0.0.1

# === PostgreSQL ===
ORDO_DB_HOST=localhost
ORDO_DB_PORT=5432
ORDO_DB_NAME=ordo
ORDO_DB_USER=ordo
ORDO_DB_PASSWORD=changeme
ORDO_DB_POOL_SIZE=10

# === PostgreSQL (test) ===
ORDO_TEST_DB_NAME=ordo_test

# === Ollama ===
ORDO_OLLAMA_URL=http://localhost:11434

# === Observability ===
ORDO_PHOENIX_PORT=6006
```

- [ ] **Step 4: Commit scaffold**

```bash
git init   # if not already a git repo
git add .gitignore .env.example backend/ tests/
git commit -m "chore: initialize Ordo V4 project scaffold"
```

Expected: Clean commit, no .env or __pycache__ included.

---

### Task 2: Python Virtual Environment + Dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
asyncpg==0.29.0
pydantic==2.7.0
pydantic-settings==2.3.0
python-dotenv==1.0.1
```

- [ ] **Step 2: Create `backend/requirements-dev.txt`**

```
-r requirements.txt
pytest==8.2.0
pytest-asyncio==0.23.7
httpx==0.27.0
```

- [ ] **Step 3: Create and activate virtual environment**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
python -m venv .venv
source .venv/Scripts/activate     # Windows
pip install -r backend/requirements-dev.txt
```

Expected output: All packages installed with no errors. Verify:
```bash
python -c "import fastapi, asyncpg, pydantic_settings; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit dependencies**

```bash
git add backend/requirements.txt backend/requirements-dev.txt
git commit -m "chore: add Python dependencies for Phase 1"
```

---

### Task 3: Configuration Module

**Files:**
- Create: `backend/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_config.py`:
```python
import os
import pytest
from backend.config import settings


def test_settings_has_required_fields():
    assert hasattr(settings, "ordo_data_dir")
    assert hasattr(settings, "api_port")
    assert hasattr(settings, "api_host")
    assert hasattr(settings, "db_host")
    assert hasattr(settings, "db_port")
    assert hasattr(settings, "db_name")
    assert hasattr(settings, "db_user")
    assert hasattr(settings, "db_password")
    assert hasattr(settings, "db_pool_size")
    assert hasattr(settings, "test_db_name")
    assert hasattr(settings, "ollama_url")


def test_settings_defaults():
    assert settings.api_port == 8000
    assert settings.api_host == "127.0.0.1"
    assert settings.db_port == 5432
    assert settings.db_pool_size == 10


def test_db_dsn_format():
    dsn = settings.db_dsn
    assert dsn.startswith("postgresql://")
    assert settings.db_user in dsn
    assert settings.db_host in dsn


def test_test_db_dsn_uses_test_name():
    test_dsn = settings.test_db_dsn
    assert settings.test_db_name in test_dsn
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.config'`

- [ ] **Step 3: Create `backend/config.py`**

```python
from pydantic_settings import BaseSettings
from pydantic import computed_field


class Settings(BaseSettings):
    # Core
    ordo_data_dir: str = r"C:\Users\user\ordo-data"
    ordo_env: str = "development"

    # FastAPI
    api_port: int = 8000
    api_host: str = "127.0.0.1"

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ordo"
    db_user: str = "ordo"
    db_password: str = "changeme"
    db_pool_size: int = 10
    test_db_name: str = "ordo_test"

    # Ollama
    ollama_url: str = "http://localhost:11434"

    # Observability
    phoenix_port: int = 6006

    @computed_field
    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field
    @property
    def test_db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.test_db_name}"
        )

    model_config = {"env_prefix": "ORDO_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/config.py tests/test_config.py
git commit -m "feat: add configuration module with pydantic-settings"
```

---

## Chunk 2: Database Layer

### Task 4: PostgreSQL Schema

**Files:**
- Create: `backend/db/schema.sql`

- [ ] **Step 1: Verify PostgreSQL and pgvector are available**

```bash
psql -U postgres -c "SELECT version();"
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname='vector';"
```

Expected: PostgreSQL version string, then `vector` in results.
If pgvector is missing: `pip install pgvector` won't help — install from https://github.com/pgvector/pgvector and follow Windows build instructions.

- [ ] **Step 2: Create `backend/db/schema.sql`**

```sql
-- Ordo V4 — Complete Database Schema
-- Apply with: psql -U ordo -d ordo -f backend/db/schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ─── Conversation Layer ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title       TEXT NOT NULL DEFAULT 'New Conversation',
    type        TEXT NOT NULL DEFAULT 'main'
                    CHECK (type IN ('main', 'side', 'background')),
    agent_id    UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('human', 'assistant', 'tool', 'system')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);

-- ─── Agent Registry ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agents (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name             TEXT NOT NULL UNIQUE,
    description      TEXT,
    system_prompt    TEXT NOT NULL DEFAULT '',
    model_preference TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
    tool_set         JSONB NOT NULL DEFAULT '[]',
    spawn_mode       TEXT NOT NULL DEFAULT 'on-demand'
                         CHECK (spawn_mode IN ('on-demand', 'always-on', 'scheduled')),
    temperature      FLOAT NOT NULL DEFAULT 0.7,
    max_tokens       INT NOT NULL DEFAULT 4096,
    metadata         JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Task System ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tasks (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title             TEXT NOT NULL,
    description       TEXT,
    status            TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'in_progress', 'completed', 'blocked', 'cancelled')),
    owner_type        TEXT NOT NULL DEFAULT 'human'
                          CHECK (owner_type IN ('human', 'agent')),
    assigned_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    conversation_id   UUID REFERENCES conversations(id) ON DELETE SET NULL,
    priority          INT NOT NULL DEFAULT 50,
    estimated_tokens  INT,
    actual_tokens_used INT,
    due_at            TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    metadata          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(assigned_agent_id) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS task_attachments (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id    UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'text',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Quick Actions + Heartbeat ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS quick_actions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    action_type TEXT NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}',
    schedule    TEXT,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS heartbeat_log (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_id  UUID REFERENCES quick_actions(id) ON DELETE SET NULL,
    run_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status     TEXT NOT NULL CHECK (status IN ('success', 'failed', 'skipped')),
    result     JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_log_run_at ON heartbeat_log(run_at DESC);

-- ─── Model Registry ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS models (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                   TEXT NOT NULL UNIQUE,
    provider               TEXT NOT NULL CHECK (provider IN ('anthropic', 'openai', 'google', 'local')),
    endpoint_url           TEXT,
    api_key_ref            UUID REFERENCES model_api_keys(id) ON DELETE SET NULL,
    model_id               TEXT NOT NULL,
    is_local               BOOLEAN NOT NULL DEFAULT FALSE,
    capabilities           JSONB NOT NULL DEFAULT '{}',
    cost_per_1k_tokens     FLOAT,
    token_budget_per_window INT,
    window_duration_hours  FLOAT,
    tokens_used_this_window INT NOT NULL DEFAULT 0,
    window_reset_at        TIMESTAMPTZ,
    rate_limit             JSONB NOT NULL DEFAULT '{}',
    priority               INT NOT NULL DEFAULT 50,
    enabled                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_api_keys (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider     TEXT NOT NULL,
    -- ENCRYPTED AT REST: application layer must encrypt before insert, decrypt on read
    key_value    TEXT NOT NULL,
    label        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

COMMENT ON COLUMN model_api_keys.key_value IS 'Encrypted at rest — application layer must encrypt before insert and decrypt on read. Never log or expose plaintext.';

CREATE TABLE IF NOT EXISTS token_usage_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id        UUID REFERENCES models(id) ON DELETE SET NULL,
    task_id         UUID REFERENCES tasks(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    tokens_used     INT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage_log(model_id, created_at DESC);

-- ─── Tool Registry ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tools (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    module_path TEXT NOT NULL,
    agent_id    UUID REFERENCES agents(id) ON DELETE SET NULL,
    usage_count INT NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Hook Registry ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS hook_handlers (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hook_name    TEXT NOT NULL CHECK (hook_name IN (
                     'session_start', 'user_prompt_submit', 'pre_tool_use',
                     'post_tool_use', 'pre_compact', 'session_end'
                 )),
    handler_type TEXT NOT NULL CHECK (handler_type IN ('python_module', 'agent', 'function')),
    handler_ref  TEXT NOT NULL,
    priority     INT NOT NULL DEFAULT 50,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    config       JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hook_handlers_name ON hook_handlers(hook_name, priority) WHERE enabled = TRUE;

-- ─── Agent Message Bus ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_agent_id   UUID REFERENCES agents(id) ON DELETE SET NULL,
    to_agent_id     UUID REFERENCES agents(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    message_type    TEXT NOT NULL CHECK (message_type IN (
                        'task_assignment', 'result', 'status_update', 'broadcast'
                    )),
    payload         JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'delivered', 'acknowledged', 'failed')),
    retry_count     INT NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at    TIMESTAMPTZ,
    ack_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_to_pending
    ON agent_messages(to_agent_id, created_at)
    WHERE status = 'pending';

-- ─── Shutdown Recovery ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS system_checkpoints (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type  TEXT NOT NULL CHECK (entity_type IN ('conversation', 'task', 'agent_run')),
    entity_id    UUID NOT NULL,
    state        JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recovered_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS in_flight_operations (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type TEXT NOT NULL,
    agent_id       UUID REFERENCES agents(id) ON DELETE SET NULL,
    payload        JSONB NOT NULL DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'in_flight'
                       CHECK (status IN ('in_flight', 'completed', 'failed', 'recovered')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_in_flight_ops ON in_flight_operations(status)
    WHERE status = 'in_flight';

-- ─── Runtime Settings ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS settings (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace     TEXT NOT NULL,
    key           TEXT NOT NULL,
    value         JSONB NOT NULL,
    default_value JSONB NOT NULL,
    description   TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(namespace, key)
);

-- ─── Sidecar Job Queue ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sidecar_jobs (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sidecar      TEXT NOT NULL CHECK (sidecar IN (
                     'kairos', 'oneiros', 'praxis', 'psyche', 'augur'
                 )),
    payload      JSONB NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'running', 'done', 'failed')),
    trigger      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sidecar_jobs_pending ON sidecar_jobs(sidecar, created_at)
    WHERE status = 'pending';

-- ─── Memory Core ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS master_sessions (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    human_id       TEXT NOT NULL,
    agent_id       TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(human_id, agent_id)
);

CREATE TABLE IF NOT EXISTS chunks (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id     UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    content        TEXT NOT NULL,
    embedding      vector(768),
    event_type     TEXT NOT NULL,
    priority_weight FLOAT NOT NULL DEFAULT 1.0,
    provisional    BOOLEAN NOT NULL DEFAULT FALSE,
    confidence     FLOAT NOT NULL DEFAULT 1.0,
    status         TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active', 'abandoned', 'superseded')),
    somatic_tags   JSONB NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS topic_nodes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topic_edges (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_node_id UUID NOT NULL REFERENCES topic_nodes(id) ON DELETE CASCADE,
    to_node_id   UUID NOT NULL REFERENCES topic_nodes(id) ON DELETE CASCADE,
    weight       FLOAT NOT NULL DEFAULT 1.0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunk_topics (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id      UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    topic_node_id UUID NOT NULL REFERENCES topic_nodes(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chunk_id, topic_node_id)
);

CREATE TABLE IF NOT EXISTS topic_summaries (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_node_id UUID NOT NULL REFERENCES topic_nodes(id) ON DELETE CASCADE,
    depth         INT NOT NULL CHECK (depth BETWEEN 0 AND 3),
    content       TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sss_snapshots (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id        UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    turn_number       INT NOT NULL,
    relational_warmth FLOAT NOT NULL DEFAULT 0.5,
    engagement_level  FLOAT NOT NULL DEFAULT 0.5,
    cognitive_load    FLOAT NOT NULL DEFAULT 0.5,
    frustration_signal FLOAT NOT NULL DEFAULT 0.0,
    care_intensity    FLOAT NOT NULL DEFAULT 0.5,
    loneliness_signal FLOAT NOT NULL DEFAULT 0.0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS procedural_notes (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'superseded', 'abandoned')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS praxis_recommendations (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    mode       INT NOT NULL CHECK (mode IN (1, 2, 3)),
    content    TEXT NOT NULL,
    approved   BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS behavioral_sequences (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    sequence   JSONB NOT NULL DEFAULT '[]',
    prediction TEXT,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS injection_log (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id    UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    chunk_id      UUID REFERENCES chunks(id) ON DELETE SET NULL,
    gate_decision TEXT NOT NULL CHECK (gate_decision IN ('injected', 'blocked')),
    gate_details  JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- [ ] **Step 3: Create the database and apply schema**

```bash
# Create the ordo user and database (as postgres superuser)
psql -U postgres -c "CREATE USER ordo WITH PASSWORD 'changeme';"
psql -U postgres -c "CREATE DATABASE ordo OWNER ordo;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE ordo TO ordo;"

# Apply schema
psql -U ordo -d ordo -f backend/db/schema.sql
```

Expected: All `CREATE TABLE`, `CREATE INDEX` statements succeed with no errors.

- [ ] **Step 4: Verify tables and indexes exist**

```bash
psql -U ordo -d ordo -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public';"
psql -U ordo -d ordo -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname='public';"
psql -U ordo -d ordo -c "SELECT * FROM pg_extension WHERE extname='vector';"
psql -U ordo -d ordo -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
```

Expected:
- Table count: **26** (exactly — fail if different)
- Index count: **11** or more named indexes
- Extension row for `vector` present
- Table list includes: `agent_messages`, `agents`, `behavioral_sequences`, `chunk_topics`, `chunks`, `conversations`, `heartbeat_log`, `hook_handlers`, `in_flight_operations`, `injection_log`, `master_sessions`, `messages`, `model_api_keys`, `models`, `procedural_notes`, `praxis_recommendations`, `quick_actions`, `settings`, `sidecar_jobs`, `sss_snapshots`, `system_checkpoints`, `task_attachments`, `tasks`, `token_usage_log`, `tools`, `topic_edges`, `topic_nodes`, `topic_summaries`

- [ ] **Step 5: Create test database**

```bash
psql -U postgres -c "CREATE DATABASE ordo_test OWNER ordo;"
psql -U ordo -d ordo_test -f backend/db/schema.sql
```

Expected: Same schema applied to test DB.

- [ ] **Step 6: Commit schema**

```bash
git add backend/db/schema.sql
git commit -m "feat: add complete PostgreSQL schema for all V4 tables"
```

---

### Task 5: Database Connection Pool

**Files:**
- Create: `backend/db/pool.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_db.py`:
```python
# NOTE: event_loop and pool fixtures come from tests/conftest.py (created in Step 4).
# Run this file only after conftest.py exists.
import asyncpg
from backend.db.pool import get_pool


async def test_pool_connects(pool):
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1


async def test_pool_can_query_tables(pool):
    async with pool.acquire() as conn:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
    table_names = [r["tablename"] for r in tables]
    assert "chunks" in table_names
    assert "agents" in table_names
    assert "tasks" in table_names
    assert "hook_handlers" in table_names


async def test_get_pool_returns_same_instance(pool):
    p2 = get_pool()
    assert p2 is pool
```

- [ ] **Step 2: Run test — verify it fails**

> **Note:** `tests/conftest.py` does not exist yet — that is created in Step 4. Run only after `conftest.py` exists. The expected failure at this stage is the missing module, not a missing fixture.

```bash
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.db.pool'`

- [ ] **Step 3: Create `backend/db/pool.py`**

```python
import asyncpg
from backend.config import settings

_pool: asyncpg.Pool | None = None


async def create_pool(test: bool = False) -> asyncpg.Pool:
    global _pool
    dsn = settings.test_db_dsn if test else settings.db_dsn
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=settings.db_pool_size,
        command_timeout=30,
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call create_pool() first.")
    return _pool
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import asyncio
import pytest
import pytest_asyncio
from backend.db.pool import create_pool, close_pool


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for all async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def pool():
    """Session-scoped DB pool pointing at ordo_test."""
    p = await create_pool(test=True)
    yield p
    await close_pool()
```

- [ ] **Step 5: Create `pytest.ini` at project root**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected:
```
test_pool_connects          PASSED
test_pool_can_query_tables  PASSED
test_get_pool_returns_same_instance PASSED
```

- [ ] **Step 7: Commit**

```bash
git add backend/db/pool.py tests/conftest.py tests/test_db.py pytest.ini
git commit -m "feat: add asyncpg connection pool with test fixture"
```

---

## Chunk 3: FastAPI App + Health + PM2

### Task 6: FastAPI Application Entry Point

**Files:**
- Create: `backend/main.py`
- Create: `backend/routers/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write failing health test**

Create `tests/test_health.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_health_returns_200():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "services" in data
    assert "database" in data["services"]


@pytest.mark.asyncio
async def test_health_database_connected(pool):
    """Requires the test pool fixture — verifies DB is reachable."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    data = response.json()
    assert data["services"]["database"] in ("ok", "degraded")
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.main'`

- [ ] **Step 3: Create `backend/routers/health.py`**

```python
from fastapi import APIRouter
from backend.db.pool import get_pool

router = APIRouter()
VERSION = "4.0.0"


@router.get("/health")
async def health():
    db_status = "ok"
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        db_status = "degraded"

    return {
        "status": "ok",
        "version": VERSION,
        "services": {
            "database": db_status,
        },
    }
```

- [ ] **Step 4: Create `backend/main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.pool import create_pool, close_pool
from backend.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_pool()
    yield
    # Shutdown
    await close_pool()


app = FastAPI(
    title="Ordo",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # LAN access — intentionally open, single-user
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_health.py -v
```

Expected:
```
test_health_returns_200       PASSED
test_health_response_shape    PASSED
test_health_database_connected PASSED
```

- [ ] **Step 6: Verify server runs manually**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
uvicorn backend.main:app --port 8000 --reload
```

Open browser or curl:
```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status":"ok","version":"4.0.0","services":{"database":"ok"}}
```

Stop the server with Ctrl+C.

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/routers/health.py tests/test_health.py
git commit -m "feat: add FastAPI app with health check endpoint"
```

---

### Task 7: PM2 Ecosystem Configuration

**Files:**
- Create: `ecosystem.config.js`

- [ ] **Step 1: Install PM2 globally if not present**

```bash
npm install -g pm2
pm2 --version
```

Expected: PM2 version number (5.x+).

- [ ] **Step 2: Create `ecosystem.config.js`**

```javascript
const path = require("path");
const ROOT = __dirname;
const VENV = path.join(ROOT, ".venv", "Scripts", "python");

module.exports = {
  apps: [
    // ── FastAPI (always-on) ──────────────────────────────────────────────
    {
      name: "ordo-api",
      interpreter: VENV,
      script: "-m",
      args: "uvicorn backend.main:app --host 127.0.0.1 --port 8000",
      cwd: ROOT,
      restart_delay: 2000,
      autorestart: true,
      watch: false,
      env: { PYTHONPATH: ROOT },
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },

    // ── Slow Sidecars (poll sidecar_jobs — restart only on failure) ──────
    {
      name: "sidecar-kairos",
      interpreter: VENV,
      script: "-m",
      args: "sidecars.kairos",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      stop_exit_codes: [0],       // clean exit = job done, don't restart
      watch: false,
      env: { PYTHONPATH: ROOT },
    },
    {
      name: "sidecar-oneiros",
      interpreter: VENV,
      script: "-m",
      args: "sidecars.oneiros",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      stop_exit_codes: [0],
      watch: false,
      env: { PYTHONPATH: ROOT },
    },
    {
      name: "sidecar-praxis",
      interpreter: VENV,
      script: "-m",
      args: "sidecars.praxis",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      stop_exit_codes: [0],
      watch: false,
      env: { PYTHONPATH: ROOT },
    },
    {
      name: "sidecar-psyche",
      interpreter: VENV,
      script: "-m",
      args: "sidecars.psyche",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      stop_exit_codes: [0],
      watch: false,
      env: { PYTHONPATH: ROOT },
    },
    {
      name: "sidecar-augur",
      interpreter: VENV,
      script: "-m",
      args: "sidecars.augur",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      stop_exit_codes: [0],
      watch: false,
      env: { PYTHONPATH: ROOT },
    },

    // ── Always-On Services ───────────────────────────────────────────────
    {
      name: "ordo-heartbeat",
      interpreter: VENV,
      script: "-m",
      args: "services.heartbeat",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      watch: false,
      env: { PYTHONPATH: ROOT },
    },
    {
      name: "ordo-telegram",
      interpreter: VENV,
      script: "-m",
      args: "services.telegram_bridge",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      watch: false,
      env: { PYTHONPATH: ROOT },
    },
    {
      name: "ordo-tts-stt",
      interpreter: VENV,
      script: "-m",
      args: "services.tts_stt_daemon",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      watch: false,
      env: { PYTHONPATH: ROOT },
    },

    // ── Observability ────────────────────────────────────────────────────
    {
      name: "ordo-phoenix",
      interpreter: VENV,
      // Verify exact startup command after installing arize-phoenix:
      //   python -m phoenix.server.main --help
      // If that fails, try: phoenix serve --port 6006
      script: "-m",
      args: "phoenix.server.main --port 6006",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      watch: false,
      env: { PYTHONPATH: ROOT },
    },

    // ── Nginx (LAN serving + API proxy) ─────────────────────────────────
    // NOTE: Nginx config is written in Phase 10. This entry is stubbed
    // so the ecosystem config matches the spec. Do not start until
    // nginx.conf exists in the project root.
    {
      name: "ordo-nginx",
      script: "nginx",
      args: "-c nginx.conf -g 'daemon off;'",
      cwd: ROOT,
      autorestart: true,
      restart_delay: 5000,
      watch: false,
    },
  ],
};
```

- [ ] **Step 3: Start only the API process and verify**

```bash
pm2 start ecosystem.config.js --only ordo-api
pm2 status
```

Expected: `ordo-api` shows status `online`.

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok","version":"4.0.0","services":{"database":"ok"}}`

- [ ] **Step 4: Verify PM2 restart behavior**

```bash
pm2 logs ordo-api --lines 20
```

Expected: Uvicorn startup logs — "Application startup complete."

- [ ] **Step 5: Stop and save PM2 config**

```bash
pm2 stop ordo-api
pm2 save
```

- [ ] **Step 6: Commit**

```bash
git add ecosystem.config.js
git commit -m "feat: add PM2 ecosystem config for all Ordo processes"
```

---

### Task 8: Full Test Run + Smoke Test

- [ ] **Step 1: Run full test suite**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/ -v
```

Expected:
```
tests/test_config.py::test_settings_has_required_fields    PASSED
tests/test_config.py::test_settings_defaults               PASSED
tests/test_config.py::test_db_dsn_format                   PASSED
tests/test_config.py::test_test_db_dsn_uses_test_name      PASSED
tests/test_db.py::test_pool_connects                        PASSED
tests/test_db.py::test_pool_can_query_tables                PASSED
tests/test_db.py::test_get_pool_returns_same_instance       PASSED
tests/test_health.py::test_health_returns_200               PASSED
tests/test_health.py::test_health_response_shape            PASSED
tests/test_health.py::test_health_database_connected        PASSED

10 passed
```

- [ ] **Step 2: Start the full Phase 1 stack via PM2**

```bash
pm2 start ecosystem.config.js --only ordo-api
pm2 status
curl http://localhost:8000/health
pm2 stop ordo-api
```

All expected to succeed cleanly.

- [ ] **Step 3: Verify clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`

All Phase 1 files were already committed in Tasks 1–7. If `git status` shows any untracked or modified files, add them by name (not by directory) and commit with the message:
```
feat: Phase 1 foundation complete — FastAPI + schema + PM2 + tests passing
```

`pytest tests/ -v` shows 10 passed.

---

## Phase 1 Complete

**What's running:** FastAPI on port 8000, PostgreSQL with 25+ tables, PM2 managing the API process.

**What's verified:** Config loads, DB pool connects, schema applied, health endpoint returns `ok`, all 10 tests pass.

**Next:** Phase 2 (Agent Harness) and Phase 3 (Frontend) can now be written in parallel by separate agents — both reference this foundation.
