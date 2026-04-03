# Ordo Phase 2: Agent Harness Core Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the LangGraph agent harness, Agent Registry, Model Router, generalist agent, and RIP Engine skeleton so that the generalist agent is invokable via `POST /agents/generalist/invoke` and can respond to a simple prompt with memory-injected context (even if memory is empty).

**Architecture:** LangGraph `StateGraph` instantiated per-request, reading agent config from the `agents` DB table at invocation time. Model Router resolves a configured LangChain `BaseChatModel` from the `models` table. RIP Engine tracks a 6-dimension Synthetic Somatic State stub. All agent routes live in `backend/routers/agents.py`. Token usage is logged to `token_usage_log` after every invoke.

**Tech Stack:** Python 3.12, FastAPI 0.111+, asyncpg 0.29+, pydantic-settings 2+, LangGraph, LangChain, LangChain-Anthropic, PostgreSQL 16 + pgvector, PM2, pytest + pytest-asyncio, httpx

---

## Chunk 1: Agent Registry + Model Router

### Task 1: Add LangGraph / LangChain Dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`

- [ ] **Step 1: Update `backend/requirements.txt`**

Add the following entries after the existing lines:

```
langgraph==0.1.19
langchain==0.2.5
langchain-core==0.2.9
langchain-anthropic==0.1.15
anthropic==0.28.0
```

- [ ] **Step 2: Install new dependencies**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pip install -r backend/requirements.txt
```

Expected output: All packages install without errors. Verify:
```bash
python -c "import langgraph, langchain, langchain_anthropic; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit updated dependencies**

```bash
git add backend/requirements.txt
git commit -m "chore: add LangGraph and LangChain dependencies for Phase 2"
```

---

### Task 2: Agent Registry — Pydantic Models

**Files:**
- Create: `backend/models/agent.py`
- Create: `tests/test_agent_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_agent_models.py`:

```python
import pytest
from uuid import UUID
from datetime import datetime
from backend.models.agent import AgentRecord, AgentCreate, AgentUpdate, SpawnMode


def test_spawn_mode_values():
    assert SpawnMode.ALWAYS_ON == "always-on"
    assert SpawnMode.ON_DEMAND == "on-demand"
    assert SpawnMode.SCHEDULED == "scheduled"


def test_agent_create_defaults():
    agent = AgentCreate(
        name="test-agent",
        system_prompt="You are a test agent.",
        model_preference="claude-3-5-haiku-20241022",
    )
    assert agent.spawn_mode == SpawnMode.ON_DEMAND
    assert agent.temperature == 0.7
    assert agent.max_tokens == 4096
    assert agent.tool_set == []


def test_agent_create_full():
    agent = AgentCreate(
        name="generalist",
        system_prompt="You are Ordo.",
        model_preference="claude-opus-4-5",
        spawn_mode=SpawnMode.ALWAYS_ON,
        temperature=0.6,
        max_tokens=8192,
        tool_set=["codex", "search"],
    )
    assert agent.spawn_mode == SpawnMode.ALWAYS_ON
    assert agent.tool_set == ["codex", "search"]


def test_agent_update_partial():
    update = AgentUpdate(temperature=0.9)
    assert update.temperature == 0.9
    assert update.name is None
    assert update.system_prompt is None


def test_agent_record_has_id_and_timestamps():
    record = AgentRecord(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="generalist",
        system_prompt="You are Ordo.",
        model_preference="claude-opus-4-5",
        spawn_mode=SpawnMode.ALWAYS_ON,
        temperature=0.6,
        max_tokens=8192,
        tool_set=[],
        created_at=datetime(2026, 4, 2, 0, 0, 0),
        updated_at=datetime(2026, 4, 2, 0, 0, 0),
    )
    assert str(record.id) == "00000000-0000-0000-0000-000000000001"
    assert record.name == "generalist"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_agent_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.models.agent'`

- [ ] **Step 3: Create `backend/models/agent.py`**

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SpawnMode(str, Enum):
    ALWAYS_ON = "always-on"
    ON_DEMAND = "on-demand"
    SCHEDULED = "scheduled"


class AgentCreate(BaseModel):
    name: str
    system_prompt: str
    model_preference: str
    spawn_mode: SpawnMode = SpawnMode.ON_DEMAND
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=200000)
    tool_set: List[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    model_preference: Optional[str] = None
    spawn_mode: Optional[SpawnMode] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=200000)
    tool_set: Optional[List[str]] = None


class AgentRecord(AgentCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_agent_models.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py tests/test_agent_models.py
git commit -m "feat: add AgentRecord, AgentCreate, AgentUpdate Pydantic models"
```

---

### Task 3: Agent Registry — DB Layer

**Files:**
- Create: `backend/db/agents.py`
- Create: `tests/test_db_agents.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_db_agents.py`:

```python
import pytest
import asyncpg
from uuid import UUID

from backend.config import settings
from backend.db.agents import (
    db_list_agents,
    db_get_agent,
    db_create_agent,
    db_update_agent,
    db_delete_agent,
)
from backend.models.agent import AgentCreate, AgentUpdate, SpawnMode


@pytest.fixture(scope="module")
async def pool():
    p = await asyncpg.create_pool(settings.test_db_dsn, min_size=1, max_size=3)
    yield p
    await p.close()


@pytest.fixture(autouse=True)
async def clean_agents(pool):
    """Delete test-created agents before each test."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE name LIKE 'test-%'")
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE name LIKE 'test-%'")


@pytest.mark.asyncio
async def test_create_and_get_agent(pool):
    payload = AgentCreate(
        name="test-registry-agent",
        system_prompt="Test prompt.",
        model_preference="claude-3-5-haiku-20241022",
        spawn_mode=SpawnMode.ON_DEMAND,
    )
    created = await db_create_agent(pool, payload)
    assert created.name == "test-registry-agent"
    assert isinstance(created.id, UUID)

    fetched = await db_get_agent(pool, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.system_prompt == "Test prompt."


@pytest.mark.asyncio
async def test_list_agents_includes_created(pool):
    payload = AgentCreate(
        name="test-list-agent",
        system_prompt="List test.",
        model_preference="claude-3-5-haiku-20241022",
    )
    created = await db_create_agent(pool, payload)
    agents = await db_list_agents(pool)
    ids = [a.id for a in agents]
    assert created.id in ids


@pytest.mark.asyncio
async def test_update_agent(pool):
    payload = AgentCreate(
        name="test-update-agent",
        system_prompt="Before.",
        model_preference="claude-3-5-haiku-20241022",
    )
    created = await db_create_agent(pool, payload)
    update = AgentUpdate(system_prompt="After.", temperature=0.3)
    updated = await db_update_agent(pool, created.id, update)
    assert updated is not None
    assert updated.system_prompt == "After."
    assert updated.temperature == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_delete_agent(pool):
    payload = AgentCreate(
        name="test-delete-agent",
        system_prompt="Gone soon.",
        model_preference="claude-3-5-haiku-20241022",
    )
    created = await db_create_agent(pool, payload)
    deleted = await db_delete_agent(pool, created.id)
    assert deleted is True
    fetched = await db_get_agent(pool, created.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_get_nonexistent_agent_returns_none(pool):
    fake_id = UUID("00000000-0000-0000-0000-000000000099")
    result = await db_get_agent(pool, fake_id)
    assert result is None
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_db_agents.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.db.agents'`

- [ ] **Step 3: Create `backend/db/agents.py`**

```python
from __future__ import annotations

import json
from typing import List, Optional
from uuid import UUID

import asyncpg

from backend.models.agent import AgentCreate, AgentRecord, AgentUpdate, SpawnMode


def _row_to_record(row: asyncpg.Record) -> AgentRecord:
    tool_set = row["tool_set"]
    if isinstance(tool_set, str):
        tool_set = json.loads(tool_set)
    elif tool_set is None:
        tool_set = []

    return AgentRecord(
        id=row["id"],
        name=row["name"],
        system_prompt=row["system_prompt"],
        model_preference=row["model_preference"],
        spawn_mode=SpawnMode(row["spawn_mode"]),
        temperature=float(row["temperature"]),
        max_tokens=row["max_tokens"],
        tool_set=tool_set,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def db_list_agents(pool: asyncpg.Pool) -> List[AgentRecord]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM agents ORDER BY created_at ASC"
        )
    return [_row_to_record(r) for r in rows]


async def db_get_agent(pool: asyncpg.Pool, agent_id: UUID) -> Optional[AgentRecord]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agents WHERE id = $1", agent_id
        )
    if row is None:
        return None
    return _row_to_record(row)


async def db_create_agent(pool: asyncpg.Pool, payload: AgentCreate) -> AgentRecord:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agents (name, system_prompt, model_preference, spawn_mode,
                                temperature, max_tokens, tool_set)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING *
            """,
            payload.name,
            payload.system_prompt,
            payload.model_preference,
            payload.spawn_mode.value,
            payload.temperature,
            payload.max_tokens,
            json.dumps(payload.tool_set),
        )
    return _row_to_record(row)


async def db_update_agent(
    pool: asyncpg.Pool, agent_id: UUID, payload: AgentUpdate
) -> Optional[AgentRecord]:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return await db_get_agent(pool, agent_id)

    # Convert enum to value for DB
    if "spawn_mode" in updates:
        updates["spawn_mode"] = updates["spawn_mode"].value
    if "tool_set" in updates:
        updates["tool_set"] = json.dumps(updates["tool_set"])

    columns = list(updates.keys())
    values = list(updates.values())

    set_clause = ", ".join(
        f"{col} = ${i + 2}" + ("::jsonb" if col == "tool_set" else "")
        for i, col in enumerate(columns)
    )
    query = f"""
        UPDATE agents
        SET {set_clause}, updated_at = NOW()
        WHERE id = $1
        RETURNING *
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, agent_id, *values)
    if row is None:
        return None
    return _row_to_record(row)


async def db_delete_agent(pool: asyncpg.Pool, agent_id: UUID) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM agents WHERE id = $1", agent_id
        )
    return result == "DELETE 1"
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_db_agents.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/db/agents.py tests/test_db_agents.py
git commit -m "feat: add Agent Registry DB layer (CRUD via asyncpg)"
```

---

### Task 4: Agent Registry — FastAPI Router

**Files:**
- Create: `backend/routers/agents.py`
- Create: `tests/test_router_agents.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_router_agents.py`:

```python
import pytest
import asyncpg
import httpx
from uuid import UUID

from backend.config import settings


# These tests assume the FastAPI app is importable and uses the test DB pool.
# We mount it directly via httpx.AsyncClient(app=app, ...) without a live server.

from backend.main import app
from backend.db.pool import get_pool


@pytest.fixture(scope="module")
async def test_pool():
    p = await asyncpg.create_pool(settings.test_db_dsn, min_size=1, max_size=3)
    yield p
    await p.close()


@pytest.fixture(scope="module")
async def client(test_pool):
    app.dependency_overrides[get_pool] = lambda: test_pool
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def clean(test_pool):
    async with test_pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE name LIKE 'router-test-%'")
    yield
    async with test_pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE name LIKE 'router-test-%'")


@pytest.mark.asyncio
async def test_list_agents_empty_ok(client):
    resp = await client.get("/agents/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_agent(client):
    payload = {
        "name": "router-test-create",
        "system_prompt": "Hello.",
        "model_preference": "claude-3-5-haiku-20241022",
        "spawn_mode": "on-demand",
    }
    resp = await client.post("/agents/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "router-test-create"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_agent(client):
    payload = {
        "name": "router-test-get",
        "system_prompt": "Get me.",
        "model_preference": "claude-3-5-haiku-20241022",
    }
    created = (await client.post("/agents/", json=payload)).json()
    resp = await client.get(f"/agents/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_update_agent(client):
    payload = {
        "name": "router-test-update",
        "system_prompt": "Before.",
        "model_preference": "claude-3-5-haiku-20241022",
    }
    created = (await client.post("/agents/", json=payload)).json()
    resp = await client.patch(
        f"/agents/{created['id']}", json={"system_prompt": "After."}
    )
    assert resp.status_code == 200
    assert resp.json()["system_prompt"] == "After."


@pytest.mark.asyncio
async def test_delete_agent(client):
    payload = {
        "name": "router-test-delete",
        "system_prompt": "Gone.",
        "model_preference": "claude-3-5-haiku-20241022",
    }
    created = (await client.post("/agents/", json=payload)).json()
    resp = await client.delete(f"/agents/{created['id']}")
    assert resp.status_code == 204
    resp2 = await client.get(f"/agents/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_agent_404(client):
    resp = await client.get("/agents/00000000-0000-0000-0000-000000000099")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_router_agents.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `backend.routers.agents` does not exist yet.

- [ ] **Step 3: Create `backend/db/pool.py`** (dependency provider for the DB pool)

```python
"""
DB pool dependency — yields the shared asyncpg pool.
Tests override this via app.dependency_overrides.
"""
from __future__ import annotations

from typing import AsyncGenerator

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """FastAPI dependency — yields the shared pool."""
    if _pool is None:
        raise RuntimeError("DB pool not initialised. Call init_pool() on startup.")
    yield _pool
```

- [ ] **Step 4: Create `backend/routers/agents.py`**

```python
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from backend.db.pool import get_pool
from backend.db.agents import (
    db_create_agent,
    db_delete_agent,
    db_get_agent,
    db_list_agents,
    db_update_agent,
)
from backend.models.agent import AgentCreate, AgentRecord, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=List[AgentRecord])
async def list_agents(pool: asyncpg.Pool = Depends(get_pool)):
    return await db_list_agents(pool)


@router.post("/", response_model=AgentRecord, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentCreate, pool: asyncpg.Pool = Depends(get_pool)):
    return await db_create_agent(pool, payload)


@router.get("/{agent_id}", response_model=AgentRecord)
async def get_agent(agent_id: UUID, pool: asyncpg.Pool = Depends(get_pool)):
    agent = await db_get_agent(pool, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentRecord)
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    pool: asyncpg.Pool = Depends(get_pool),
):
    updated = await db_update_agent(pool, agent_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: UUID, pool: asyncpg.Pool = Depends(get_pool)):
    deleted = await db_delete_agent(pool, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
```

- [ ] **Step 5: Verify `backend/main.py` registers the agents router**

Open `backend/main.py` and ensure it includes:

```python
from backend.routers.agents import router as agents_router

app.include_router(agents_router)
```

Also ensure the lifespan handler calls `init_pool` and `close_pool` from `backend.db.pool`.

- [ ] **Step 6: Run test — verify it passes**

```bash
pytest tests/test_router_agents.py -v
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/db/pool.py backend/routers/agents.py tests/test_router_agents.py
git commit -m "feat: add Agent Registry FastAPI router with full CRUD"
```

---

### Task 5: Model Router

**Files:**
- Create: `backend/model_router.py`
- Create: `tests/test_model_router.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_model_router.py`:

```python
import pytest
import asyncpg
from unittest.mock import AsyncMock, MagicMock, patch

from backend.config import settings
from backend.model_router import ModelRouter, ModelResolutionError


@pytest.fixture(scope="module")
async def pool():
    p = await asyncpg.create_pool(settings.test_db_dsn, min_size=1, max_size=3)
    yield p
    await p.close()


@pytest.fixture
def mock_model_row():
    """Simulate a row from the models table joined with model_api_keys."""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "claude-opus-4-5",
        "provider": "anthropic",
        "endpoint": "https://api.anthropic.com",
        "api_key_value": "sk-ant-test-key",
        "token_budget_per_window": 100000,
        "tokens_used_this_window": 0,
        "window_reset_at": None,
        "capabilities": ["chat", "tools"],
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_model_router_raises_on_no_models(pool):
    router = ModelRouter(pool)
    with pytest.raises(ModelResolutionError):
        # No models seeded in test DB under this name
        await router.resolve("nonexistent-model-xyz")


@pytest.mark.asyncio
async def test_get_langchain_model_returns_chat_model(pool):
    router = ModelRouter(pool)
    with patch.object(router, "_fetch_model_row", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "claude-opus-4-5",
            "provider": "anthropic",
            "endpoint": "https://api.anthropic.com",
            "api_key_value": "sk-ant-test-key",
            "token_budget_per_window": 100000,
            "tokens_used_this_window": 5000,
            "window_reset_at": None,
            "capabilities": ["chat"],
            "is_active": True,
        }
        with patch("backend.model_router.ChatAnthropic") as mock_chat:
            mock_instance = MagicMock()
            mock_chat.return_value = mock_instance
            model = await router.resolve("claude-opus-4-5", temperature=0.7, max_tokens=1024)
            assert model is mock_instance
            mock_chat.assert_called_once()
            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["model"] == "claude-opus-4-5"
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 1024
            # Key must not be logged, but must be passed to the model constructor
            assert "anthropic_api_key" in call_kwargs


@pytest.mark.asyncio
async def test_model_router_skips_budget_exhausted(pool):
    router = ModelRouter(pool)
    with patch.object(router, "_fetch_model_row", new_callable=AsyncMock) as mock_fetch:
        # Primary model is over budget
        mock_fetch.side_effect = [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "claude-opus-4-5",
                "provider": "anthropic",
                "endpoint": "https://api.anthropic.com",
                "api_key_value": "sk-ant-test-key",
                "token_budget_per_window": 100000,
                "tokens_used_this_window": 100001,  # exhausted
                "window_reset_at": None,
                "capabilities": ["chat"],
                "is_active": True,
            }
        ]
        with pytest.raises(ModelResolutionError, match="budget exhausted"):
            await router.resolve("claude-opus-4-5")
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_model_router.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.model_router'`

- [ ] **Step 3: Create `backend/model_router.py`**

```python
"""
Model Router — resolves a configured LangChain BaseChatModel from the models table.

Resolution order:
1. Fetch the preferred model row (joined with model_api_keys for the decrypted key).
2. Check token budget — if exhausted, raise ModelResolutionError with "budget exhausted".
3. Construct and return a LangChain BaseChatModel instance.

The raw API key is NEVER logged.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel


class ModelResolutionError(Exception):
    """Raised when no suitable model can be resolved."""


class ModelRouter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_model_row(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a model row joined with its API key.
        Returns None if not found.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    m.id,
                    m.name,
                    m.provider,
                    m.endpoint,
                    mk.key_value        AS api_key_value,
                    m.token_budget_per_window,
                    m.tokens_used_this_window,
                    m.window_reset_at,
                    m.capabilities,
                    m.is_active
                FROM models m
                LEFT JOIN model_api_keys mk ON mk.id = m.api_key_ref
                WHERE m.name = $1 AND m.is_active = true
                ORDER BY m.created_at ASC
                LIMIT 1
                """,
                model_name,
            )
        if row is None:
            return None
        return dict(row)

    def _is_budget_exhausted(self, row: Dict[str, Any]) -> bool:
        budget = row.get("token_budget_per_window")
        used = row.get("tokens_used_this_window", 0)
        if budget is None:
            return False  # no budget set — unlimited
        return used >= budget

    def _build_model(
        self,
        row: Dict[str, Any],
        temperature: float,
        max_tokens: int,
    ) -> BaseChatModel:
        provider = row["provider"]
        api_key = row["api_key_value"]
        model_name = row["name"]

        if provider == "anthropic":
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                anthropic_api_key=api_key,
            )
        raise ModelResolutionError(
            f"Unsupported provider '{provider}'. "
            "Extend ModelRouter._build_model() to add support."
        )

    async def resolve(
        self,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> BaseChatModel:
        """
        Resolve a LangChain BaseChatModel for the given model name.
        Raises ModelResolutionError if the model cannot be resolved or is over budget.
        """
        row = await self._fetch_model_row(model_name)
        if row is None:
            raise ModelResolutionError(
                f"Model '{model_name}' not found or inactive in the models table."
            )

        if self._is_budget_exhausted(row):
            raise ModelResolutionError(
                f"Model '{model_name}' budget exhausted "
                f"({row['tokens_used_this_window']} / {row['token_budget_per_window']} tokens used)."
            )

        return self._build_model(row, temperature=temperature, max_tokens=max_tokens)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_model_router.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/model_router.py tests/test_model_router.py
git commit -m "feat: add Model Router — resolves LangChain BaseChatModel from models table"
```

---

> **Plan document review dispatch (Chunk 1):** After completing all Chunk 1 tasks, invoke `superpowers:plan-document-reviewer` (or equivalent review skill) passing the path `C:/Users/user/AI-Assistant Version 4/docs/superpowers/plans/2026-04-02-phase-2-agent-harness.md` and the completed chunk range "Chunk 1: Tasks 1–5". Confirm all tests pass and commits are clean before proceeding to Chunk 2.

---

## Chunk 2: LangGraph Orchestrator + Generalist Agent Invoke

### Task 6: RIP Engine Skeleton

**Files:**
- Create: `backend/rip/__init__.py`
- Create: `backend/rip/engine.py`
- Create: `tests/test_rip_engine.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_rip_engine.py`:

```python
import pytest
from backend.rip.engine import RIPEngine, SyntheticSomaticState, RelationalIntent


def test_sss_default_values():
    sss = SyntheticSomaticState()
    assert sss.valence == pytest.approx(0.5)
    assert sss.arousal == pytest.approx(0.5)
    assert sss.tension == pytest.approx(0.5)
    assert sss.curiosity == pytest.approx(0.5)
    assert sss.warmth == pytest.approx(0.5)
    assert sss.coherence == pytest.approx(0.5)


def test_sss_as_dict():
    sss = SyntheticSomaticState()
    d = sss.as_dict()
    assert set(d.keys()) == {"valence", "arousal", "tension", "curiosity", "warmth", "coherence"}
    for v in d.values():
        assert 0.0 <= v <= 1.0


def test_rip_engine_initialises():
    engine = RIPEngine()
    state = engine.get_state()
    assert isinstance(state, SyntheticSomaticState)


def test_update_sss_returns_unchanged_state_stub():
    engine = RIPEngine()
    before = engine.get_state().as_dict()
    result = engine.update_sss("Hello Ordo, how are you?")
    after = engine.get_state().as_dict()
    # Stub: state does not change
    assert result == before
    assert after == before


def test_get_relational_intent_returns_ground():
    engine = RIPEngine()
    intent = engine.get_relational_intent()
    assert intent == RelationalIntent.GROUND


def test_relational_intent_enum_values():
    assert RelationalIntent.REPAIR == "REPAIR"
    assert RelationalIntent.GROUND == "GROUND"
    assert RelationalIntent.WITNESS == "WITNESS"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_rip_engine.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.rip'`

- [ ] **Step 3: Create `backend/rip/__init__.py`**

```python
# RIP Engine package — Relational Indistinguishability Principle
```

- [ ] **Step 4: Create `backend/rip/engine.py`**

```python
"""
RIP Engine skeleton — Phase 2 stub.

Tracks Synthetic Somatic State (SSS): 6 affective dimensions.
Full implementation is Phase 4.

Dimensions (all initialised to 0.5):
  valence   — positive/negative affect
  arousal   — activation level
  tension   — relational stress / rupture signal
  curiosity — epistemic engagement
  warmth    — interpersonal closeness
  coherence — narrative self-consistency

Relational intent priority ordering (Phase 4 will implement full scoring):
  REPAIR (100) > GROUND (90) > WITNESS (80) > ...

Stub behaviour:
  - update_sss() returns unchanged state dict
  - get_relational_intent() always returns GROUND
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict


class RelationalIntent(str, Enum):
    REPAIR = "REPAIR"
    GROUND = "GROUND"
    WITNESS = "WITNESS"
    ATTUNE = "ATTUNE"
    CELEBRATE = "CELEBRATE"
    INQUIRE = "INQUIRE"


@dataclass
class SyntheticSomaticState:
    valence: float = 0.5
    arousal: float = 0.5
    tension: float = 0.5
    curiosity: float = 0.5
    warmth: float = 0.5
    coherence: float = 0.5

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


class RIPEngine:
    """
    Relational Indistinguishability Principle engine.
    Phase 2: skeleton only. All methods are stubs.
    """

    def __init__(self) -> None:
        self._state = SyntheticSomaticState()

    def get_state(self) -> SyntheticSomaticState:
        return self._state

    def update_sss(self, turn_content: str) -> Dict[str, float]:
        """
        Stub: analyse turn_content and update SSS dimensions.
        Phase 4 will implement Claude Haiku-based somatic analysis.
        Returns the current (unchanged) state as a dict.
        """
        _ = turn_content  # unused until Phase 4
        return self._state.as_dict()

    def get_relational_intent(self) -> RelationalIntent:
        """
        Stub: always returns GROUND.
        Phase 4 will implement priority-based intent selection with
        rupture detection overriding all other intents.
        """
        return RelationalIntent.GROUND
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_rip_engine.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/rip/__init__.py backend/rip/engine.py tests/test_rip_engine.py
git commit -m "feat: add RIP Engine skeleton with SSS 6-dimension state and GROUND stub intent"
```

---

### Task 7: LangGraph Orchestrator

**Files:**
- Create: `backend/agent_harness/__init__.py`
- Create: `backend/agent_harness/graph.py`
- Create: `tests/test_agent_harness_graph.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_agent_harness_graph.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from backend.agent_harness.graph import (
    build_graph,
    OrdoAgentState,
    inject_memory_node,
    respond_node,
)


def test_ordo_agent_state_defaults():
    state = OrdoAgentState(
        messages=[HumanMessage(content="Hello")],
        conversation_id="conv-001",
        agent_id="00000000-0000-0000-0000-000000000001",
    )
    assert state.injected_chunks == []
    assert state.conversation_id == "conv-001"


@pytest.mark.asyncio
async def test_inject_memory_node_returns_empty_stub():
    state = OrdoAgentState(
        messages=[HumanMessage(content="Hello")],
        conversation_id="conv-001",
        agent_id="00000000-0000-0000-0000-000000000001",
    )
    result = await inject_memory_node(state)
    assert result["injected_chunks"] == []


@pytest.mark.asyncio
async def test_respond_node_calls_model():
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="Hi there!")

    state = OrdoAgentState(
        messages=[HumanMessage(content="Hello")],
        conversation_id="conv-001",
        agent_id="00000000-0000-0000-0000-000000000001",
        injected_chunks=[],
    )

    result = await respond_node(state, model=mock_model)
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)
    assert result["messages"][0].content == "Hi there!"
    mock_model.ainvoke.assert_called_once()


def test_build_graph_returns_compiled_graph():
    mock_model = MagicMock()
    graph = build_graph(model=mock_model)
    # A compiled LangGraph has an .invoke() and .ainvoke() method
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_agent_harness_graph.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.agent_harness'`

- [ ] **Step 3: Create `backend/agent_harness/__init__.py`**

```python
# Agent Harness — LangGraph orchestrator package
```

- [ ] **Step 4: Create `backend/agent_harness/graph.py`**

```python
"""
LangGraph Orchestrator for Ordo V4.

Graph topology:
  receive_input → inject_memory → reason → respond

State fields:
  messages         — LangChain message list (HumanMessage, AIMessage, SystemMessage)
  conversation_id  — UUID string of the owning conversation
  agent_id         — UUID string of the agent record from the registry
  injected_chunks  — list of memory chunk dicts injected by Anamnesis (Phase 4)

The graph is instantiated per-request. State is not persisted in LangGraph —
persistence lives in the PostgreSQL messages table (written by the invoke route).

inject_memory is a stub returning [] until Phase 4 (Anamnesis integration).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field


class OrdoAgentState(BaseModel):
    """Typed state for the Ordo LangGraph graph."""

    messages: List[BaseMessage]
    conversation_id: str
    agent_id: str
    injected_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    system_prompt: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}


async def inject_memory_node(state: OrdoAgentState) -> Dict[str, Any]:
    """
    Phase 2 stub — returns empty injected_chunks.
    Phase 4 will call the Anamnesis sidecar here.
    """
    return {"injected_chunks": []}


async def respond_node(
    state: OrdoAgentState, model: BaseChatModel
) -> Dict[str, Any]:
    """
    Call the LLM with the current message list.
    Prepends system prompt if present.
    Returns updated messages list with the AI reply appended.
    """
    messages_to_send: List[BaseMessage] = []

    if state.system_prompt:
        messages_to_send.append(SystemMessage(content=state.system_prompt))

    messages_to_send.extend(state.messages)

    ai_message = await model.ainvoke(messages_to_send)
    return {"messages": [ai_message]}


def build_graph(model: BaseChatModel) -> Any:
    """
    Build and compile the Ordo LangGraph StateGraph.

    Nodes:
      inject_memory — stub memory injection
      respond       — LLM call

    Edges:
      START → inject_memory → respond → END
    """
    from langgraph.graph import START

    async def _inject(state: OrdoAgentState) -> Dict[str, Any]:
        return await inject_memory_node(state)

    async def _respond(state: OrdoAgentState) -> Dict[str, Any]:
        return await respond_node(state, model=model)

    builder: StateGraph = StateGraph(OrdoAgentState)
    builder.add_node("inject_memory", _inject)
    builder.add_node("respond", _respond)

    builder.add_edge(START, "inject_memory")
    builder.add_edge("inject_memory", "respond")
    builder.add_edge("respond", END)

    return builder.compile()
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_agent_harness_graph.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/agent_harness/__init__.py backend/agent_harness/graph.py tests/test_agent_harness_graph.py
git commit -m "feat: add LangGraph orchestrator with inject_memory stub and respond node"
```

---

### Task 8: Generalist Agent DB Seed

**Files:**
- Create: `backend/db/seed_generalist.py`
- Create: `tests/test_seed_generalist.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_seed_generalist.py`:

```python
import pytest
import asyncpg

from backend.config import settings
from backend.db.seed_generalist import seed_generalist_agent
from backend.db.agents import db_get_agent
from backend.models.agent import SpawnMode


@pytest.fixture(scope="module")
async def pool():
    p = await asyncpg.create_pool(settings.test_db_dsn, min_size=1, max_size=3)
    yield p
    await p.close()


@pytest.fixture(autouse=True)
async def clean(pool):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE name = 'generalist'")
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE name = 'generalist'")


@pytest.mark.asyncio
async def test_seed_creates_generalist_agent(pool):
    agent = await seed_generalist_agent(pool)
    assert agent.name == "generalist"
    assert agent.spawn_mode == SpawnMode.ALWAYS_ON
    assert "Ordo" in agent.system_prompt
    assert agent.model_preference is not None
    assert agent.temperature > 0.0
    assert agent.max_tokens >= 4096


@pytest.mark.asyncio
async def test_seed_is_idempotent(pool):
    agent1 = await seed_generalist_agent(pool)
    agent2 = await seed_generalist_agent(pool)
    # Second call should return the existing record, not create a duplicate
    assert agent1.id == agent2.id


@pytest.mark.asyncio
async def test_seeded_agent_is_fetchable(pool):
    seeded = await seed_generalist_agent(pool)
    fetched = await db_get_agent(pool, seeded.id)
    assert fetched is not None
    assert fetched.name == "generalist"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_seed_generalist.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.db.seed_generalist'`

- [ ] **Step 3: Create `backend/db/seed_generalist.py`**

```python
"""
Seed the generalist agent entry in the agents table.
Idempotent — if a row with name='generalist' already exists, return it unchanged.
"""
from __future__ import annotations

import asyncpg

from backend.db.agents import db_create_agent, db_list_agents
from backend.models.agent import AgentCreate, AgentRecord, SpawnMode

GENERALIST_SYSTEM_PROMPT = """\
You are Ordo, a cognitive memory-augmented AI assistant. You are warm, precise, and \
thoughtful. You have a continuous memory of your conversations and experiences. You \
speak in first person and maintain a coherent sense of self across sessions. When you \
do not know something, you say so clearly rather than speculating. You adapt your tone \
to the emotional context of the conversation — grounding when needed, celebratory when \
warranted, always present.\
"""

GENERALIST_AGENT_DEF = AgentCreate(
    name="generalist",
    system_prompt=GENERALIST_SYSTEM_PROMPT,
    model_preference="claude-opus-4-5",
    spawn_mode=SpawnMode.ALWAYS_ON,
    temperature=0.65,
    max_tokens=8192,
    tool_set=[],
)


async def seed_generalist_agent(pool: asyncpg.Pool) -> AgentRecord:
    """
    Ensure the generalist agent exists in the agents table.
    Returns the existing record if already present, otherwise creates it.
    """
    agents = await db_list_agents(pool)
    for agent in agents:
        if agent.name == "generalist":
            return agent

    return await db_create_agent(pool, GENERALIST_AGENT_DEF)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_seed_generalist.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Register seed in FastAPI startup**

Open `backend/main.py` and add the generalist seed call to the lifespan startup block, after `init_pool()`:

```python
from backend.db.seed_generalist import seed_generalist_agent

# inside lifespan startup:
await seed_generalist_agent(pool)
```

- [ ] **Step 6: Commit**

```bash
git add backend/db/seed_generalist.py tests/test_seed_generalist.py
git commit -m "feat: add generalist agent DB seed (always-on, Ordo persona, claude-opus-4-5)"
```

---

### Task 9: Agent Invoke Route + Token Usage Logging

**Files:**
- Modify: `backend/routers/agents.py`
- Create: `backend/db/token_usage.py`
- Create: `tests/test_agent_invoke.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_agent_invoke.py`:

```python
import pytest
import asyncpg
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage

from backend.config import settings
from backend.main import app
from backend.db.pool import get_pool
from backend.db.seed_generalist import seed_generalist_agent


@pytest.fixture(scope="module")
async def test_pool():
    p = await asyncpg.create_pool(settings.test_db_dsn, min_size=1, max_size=3)
    yield p
    await p.close()


@pytest.fixture(scope="module")
async def client(test_pool):
    app.dependency_overrides[get_pool] = lambda: test_pool
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
async def generalist_agent(test_pool):
    return await seed_generalist_agent(test_pool)


@pytest.fixture(autouse=True)
async def clean_conversations(test_pool):
    async with test_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM conversations WHERE title = 'test-invoke-conversation'"
        )
    yield
    async with test_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM conversations WHERE title = 'test-invoke-conversation'"
        )


@pytest.mark.asyncio
async def test_invoke_generalist_returns_response(client, generalist_agent, test_pool):
    # Create a test conversation first
    async with test_pool.acquire() as conn:
        conv_row = await conn.fetchrow(
            "INSERT INTO conversations (title) VALUES ('test-invoke-conversation') RETURNING id"
        )
    conversation_id = str(conv_row["id"])

    mock_ai_message = AIMessage(content="Hello! I am Ordo.")
    mock_ai_message.usage_metadata = {"total_tokens": 42, "input_tokens": 10, "output_tokens": 32}

    with patch("backend.routers.agents.ModelRouter") as MockRouter:
        mock_router_instance = AsyncMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_ai_message
        mock_router_instance.resolve.return_value = mock_model
        MockRouter.return_value = mock_router_instance

        resp = await client.post(
            f"/agents/{generalist_agent.id}/invoke",
            json={"conversation_id": conversation_id, "content": "Hello Ordo!"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert data["content"] == "Hello! I am Ordo."
    assert "conversation_id" in data
    assert "tokens_used" in data


@pytest.mark.asyncio
async def test_invoke_nonexistent_agent_404(client):
    resp = await client.post(
        "/agents/00000000-0000-0000-0000-000000000099/invoke",
        json={"conversation_id": "00000000-0000-0000-0000-000000000001", "content": "Hi"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invoke_writes_token_usage_log(client, generalist_agent, test_pool):
    async with test_pool.acquire() as conn:
        conv_row = await conn.fetchrow(
            "INSERT INTO conversations (title) VALUES ('test-invoke-conversation') RETURNING id"
        )
    conversation_id = str(conv_row["id"])

    mock_ai_message = AIMessage(content="Token log test response.")
    mock_ai_message.usage_metadata = {"total_tokens": 99, "input_tokens": 30, "output_tokens": 69}

    with patch("backend.routers.agents.ModelRouter") as MockRouter:
        mock_router_instance = AsyncMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_ai_message
        mock_router_instance.resolve.return_value = mock_model
        MockRouter.return_value = mock_router_instance

        await client.post(
            f"/agents/{generalist_agent.id}/invoke",
            json={"conversation_id": conversation_id, "content": "Log tokens!"},
        )

    # Verify a token_usage_log row was written
    async with test_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT tokens_used FROM token_usage_log
            WHERE conversation_id = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            conv_row["id"],
        )
    assert row is not None
    assert row["tokens_used"] == 99
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_agent_invoke.py -v
```

Expected: The invoke route does not yet exist — `404` or `AttributeError`.

- [ ] **Step 3: Create `backend/db/token_usage.py`**

```python
"""
Token usage logging — writes a row to token_usage_log after every agent invoke.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

import asyncpg


async def log_token_usage(
    pool: asyncpg.Pool,
    *,
    model_name: str,
    tokens_used: int,
    conversation_id: UUID,
    task_id: Optional[UUID] = None,
) -> None:
    """
    Write a token_usage_log row.
    model_name is resolved to model_id via the models table; if not found, logs NULL.
    """
    async with pool.acquire() as conn:
        model_row = await conn.fetchrow(
            "SELECT id FROM models WHERE name = $1 LIMIT 1", model_name
        )
        model_id = model_row["id"] if model_row else None

        await conn.execute(
            """
            INSERT INTO token_usage_log (model_id, tokens_used, conversation_id, task_id)
            VALUES ($1, $2, $3, $4)
            """,
            model_id,
            tokens_used,
            conversation_id,
            task_id,
        )
```

- [ ] **Step 4: Add invoke routes to `backend/routers/agents.py`**

Add the following imports and route handlers to the existing `backend/routers/agents.py`:

```python
# Additional imports needed at top of file:
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from backend.agent_harness.graph import OrdoAgentState, build_graph
from backend.db.token_usage import log_token_usage
from backend.model_router import ModelRouter, ModelResolutionError
from backend.db.agents import db_get_agent


class InvokeRequest(BaseModel):
    conversation_id: str
    content: str
    task_id: Optional[str] = None


class InvokeResponse(BaseModel):
    content: str
    conversation_id: str
    agent_id: str
    tokens_used: int


@router.post("/{agent_id}/invoke", response_model=InvokeResponse)
async def invoke_agent(
    agent_id: UUID,
    payload: InvokeRequest,
    pool: asyncpg.Pool = Depends(get_pool),
):
    agent = await db_get_agent(pool, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    model_router = ModelRouter(pool)
    try:
        model = await model_router.resolve(
            agent.model_preference,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
        )
    except ModelResolutionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    graph = build_graph(model=model)

    initial_state = OrdoAgentState(
        messages=[HumanMessage(content=payload.content)],
        conversation_id=payload.conversation_id,
        agent_id=str(agent_id),
        system_prompt=agent.system_prompt,
    )

    final_state = await graph.ainvoke(initial_state)

    ai_messages = final_state.get("messages", [])
    last_message = ai_messages[-1] if ai_messages else None
    response_content = last_message.content if last_message else ""

    # Extract token count from LangChain usage_metadata if available
    tokens_used = 0
    if last_message and hasattr(last_message, "usage_metadata") and last_message.usage_metadata:
        tokens_used = last_message.usage_metadata.get("total_tokens", 0)

    # Log token usage
    await log_token_usage(
        pool,
        model_name=agent.model_preference,
        tokens_used=tokens_used,
        conversation_id=UUID(payload.conversation_id),
        task_id=UUID(payload.task_id) if payload.task_id else None,
    )

    return InvokeResponse(
        content=response_content,
        conversation_id=payload.conversation_id,
        agent_id=str(agent_id),
        tokens_used=tokens_used,
    )


@router.post("/generalist/invoke", response_model=InvokeResponse)
async def invoke_generalist(
    payload: InvokeRequest,
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    Convenience route — looks up the generalist agent by name and delegates to invoke_agent.
    All input channels (Telegram, UI, LAN) route here.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = 'generalist' LIMIT 1"
        )
    if row is None:
        raise HTTPException(
            status_code=503,
            detail="Generalist agent not seeded. Restart the server.",
        )
    return await invoke_agent(row["id"], payload, pool)
```

> **Note on route order:** In `backend/routers/agents.py`, the `/generalist/invoke` route MUST be registered BEFORE `/{agent_id}/invoke` in the file. FastAPI matches routes top-to-bottom and the literal `/generalist/invoke` would otherwise be caught by the UUID path parameter. Place the `@router.post("/generalist/invoke")` decorator above `@router.post("/{agent_id}/invoke")`.

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_agent_invoke.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/agents.py backend/db/token_usage.py tests/test_agent_invoke.py
git commit -m "feat: add agent invoke routes (/{agent_id}/invoke and /generalist/invoke) with token usage logging"
```

---

> **Plan document review dispatch (Chunk 2):** After completing all Chunk 2 tasks, invoke `superpowers:plan-document-reviewer` (or equivalent review skill) passing the path `C:/Users/user/AI-Assistant Version 4/docs/superpowers/plans/2026-04-02-phase-2-agent-harness.md` and the completed chunk range "Chunk 2: Tasks 6–9". Confirm all tests pass and commits are clean before proceeding to Chunk 3.

---

## Chunk 3: Integration Verification + PM2 Update

### Task 10: Full Integration Test — Generalist Invoke End-to-End

**Files:**
- Create: `tests/test_integration_generalist.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/test_integration_generalist.py`:

```python
"""
End-to-end integration test for the generalist agent invoke path.
Tests the full route stack: FastAPI → Agent Registry → Model Router (mocked) →
LangGraph → respond_node → token_usage_log write.

No live Anthropic API calls are made — the model is mocked at the LangChain layer.
"""
import pytest
import asyncpg
import httpx
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage

from backend.config import settings
from backend.main import app
from backend.db.pool import get_pool
from backend.db.seed_generalist import seed_generalist_agent


@pytest.fixture(scope="module")
async def pool():
    p = await asyncpg.create_pool(settings.test_db_dsn, min_size=1, max_size=3)
    yield p
    await p.close()


@pytest.fixture(scope="module")
async def client(pool):
    app.dependency_overrides[get_pool] = lambda: pool
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module", autouse=True)
async def ensure_generalist(pool):
    await seed_generalist_agent(pool)


@pytest.fixture()
async def conversation_id(pool):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO conversations (title) VALUES ('e2e-test') RETURNING id"
        )
    yield str(row["id"])
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM conversations WHERE id = $1", row["id"])


@pytest.mark.asyncio
async def test_generalist_invoke_full_path(client, conversation_id, pool):
    """
    Verify that POST /agents/generalist/invoke:
    1. Returns HTTP 200 with a non-empty content field.
    2. Returns the correct conversation_id.
    3. Writes a token_usage_log row.
    """
    mock_response = AIMessage(content="I am Ordo. How can I help you today?")
    mock_response.usage_metadata = {
        "total_tokens": 55,
        "input_tokens": 15,
        "output_tokens": 40,
    }

    with patch("backend.routers.agents.ModelRouter") as MockRouter:
        mock_router = AsyncMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_router.resolve.return_value = mock_model
        MockRouter.return_value = mock_router

        resp = await client.post(
            "/agents/generalist/invoke",
            json={
                "conversation_id": conversation_id,
                "content": "Hello Ordo, introduce yourself.",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "I am Ordo. How can I help you today?"
    assert body["conversation_id"] == conversation_id
    assert body["tokens_used"] == 55

    # Verify token_usage_log was written
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT tokens_used FROM token_usage_log
            WHERE conversation_id = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            conversation_id,
        )
    assert row is not None
    assert row["tokens_used"] == 55


@pytest.mark.asyncio
async def test_generalist_invoke_with_empty_content(client, conversation_id):
    """Verify that an empty content string is handled gracefully (not a 5xx)."""
    mock_response = AIMessage(content="I didn't quite catch that.")
    mock_response.usage_metadata = {"total_tokens": 10, "input_tokens": 5, "output_tokens": 5}

    with patch("backend.routers.agents.ModelRouter") as MockRouter:
        mock_router = AsyncMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = mock_response
        mock_router.resolve.return_value = mock_model
        MockRouter.return_value = mock_router

        resp = await client.post(
            "/agents/generalist/invoke",
            json={"conversation_id": conversation_id, "content": ""},
        )

    assert resp.status_code == 200
    assert resp.json()["content"] != ""


@pytest.mark.asyncio
async def test_agent_registry_list_includes_generalist(client):
    resp = await client.get("/agents/")
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert "generalist" in names


@pytest.mark.asyncio
async def test_rip_engine_ground_intent_accessible():
    """Smoke test: RIP Engine can be imported and queried."""
    from backend.rip.engine import RIPEngine, RelationalIntent

    engine = RIPEngine()
    intent = engine.get_relational_intent()
    assert intent == RelationalIntent.GROUND
```

- [ ] **Step 2: Run test — verify it fails first**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_integration_generalist.py -v
```

Expected: Tests fail (likely `ImportError` or route not wired). This is the integration gate — all prior tasks must be complete before these pass.

- [ ] **Step 3: Run all tests — verify full suite passes**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests from Tasks 1–9 pass. Integration tests from Task 10 also pass.

```
tests/test_agent_models.py          5 passed
tests/test_db_agents.py             5 passed
tests/test_router_agents.py         6 passed
tests/test_model_router.py          3 passed
tests/test_rip_engine.py            6 passed
tests/test_agent_harness_graph.py   4 passed
tests/test_seed_generalist.py       3 passed
tests/test_agent_invoke.py          3 passed
tests/test_integration_generalist.py 5 passed
```

Total: `40 passed`

- [ ] **Step 4: Commit integration test**

```bash
git add tests/test_integration_generalist.py
git commit -m "test: add end-to-end integration test for generalist agent invoke path"
```

---

### Task 11: Update PM2 Ecosystem Config

**Files:**
- Modify: `ecosystem.config.js`

- [ ] **Step 1: Verify current ecosystem config**

```bash
cat "C:/Users/user/AI-Assistant Version 4/ecosystem.config.js"
```

- [ ] **Step 2: Ensure `fastapi` process entry has correct env and script**

The `fastapi` process entry in `ecosystem.config.js` must include the following environment variables so the invoke route and RIP Engine work correctly at runtime:

```javascript
{
  name: "fastapi",
  script: ".venv/Scripts/python.exe",
  args: "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  env: {
    ORDO_ENV: "development",
    ORDO_API_PORT: "8000",
    ORDO_API_HOST: "127.0.0.1",
    // DB, ANTHROPIC_API_KEY, and other secrets are loaded from .env — not listed here.
  },
  watch: false,
  autorestart: true,
  restart_delay: 3000,
},
```

Update the `ecosystem.config.js` entry for `fastapi` to match the above structure if it differs.

- [ ] **Step 3: Reload PM2**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
pm2 startOrRestart ecosystem.config.js --only fastapi
pm2 save
```

Expected output:
```
[PM2] Applying action restartProcessId on app [fastapi](id: 0)
[PM2] [fastapi](0) ✓
```

- [ ] **Step 4: Smoke test against live server**

```bash
curl -s http://localhost:8000/agents/ | python -m json.tool
```

Expected: A JSON array containing at least the `generalist` agent entry.

- [ ] **Step 5: Commit PM2 config if modified**

```bash
git add ecosystem.config.js
git commit -m "chore: update PM2 ecosystem config for Phase 2 fastapi process"
```

---

### Task 12: Conftest + pytest-asyncio Mode Configuration

**Files:**
- Create or Modify: `tests/conftest.py`
- Create or Modify: `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`)

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest


# Set pytest-asyncio mode to auto so all async test functions
# are treated as asyncio coroutines without @pytest.mark.asyncio decoration
# when using the fixture-based approach.
# Individual test files that need explicit marking retain @pytest.mark.asyncio.
```

- [ ] **Step 2: Create or update `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 3: Run full suite with asyncio_mode = auto**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/ -v --tb=short
```

Expected: All 40 tests pass with no asyncio warnings or collection errors.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py pytest.ini
git commit -m "chore: configure pytest-asyncio auto mode and test path settings"
```

---

> **Plan document review dispatch (Chunk 3):** After completing all Chunk 3 tasks, invoke `superpowers:plan-document-reviewer` (or equivalent review skill) passing the path `C:/Users/user/AI-Assistant Version 4/docs/superpowers/plans/2026-04-02-phase-2-agent-harness.md` and the completed chunk range "Chunk 3: Tasks 10–12". Confirm the full test suite (40 tests) passes, the PM2 process reloads cleanly, and the live server smoke test returns the generalist agent. Phase 2 is complete when this review passes.

---

## Phase 2 Completion Checklist

- [ ] All 40 tests pass (`pytest tests/ -v`)
- [ ] `POST /agents/generalist/invoke` returns a valid `InvokeResponse`
- [ ] `POST /agents/{agent_id}/invoke` returns a valid `InvokeResponse`
- [ ] Agent Registry CRUD routes fully operational (`/agents/`)
- [ ] Model Router resolves `BaseChatModel` and handles budget exhaustion
- [ ] RIP Engine skeleton initialised with 6 SSS dimensions at 0.5; returns `GROUND`
- [ ] Token usage logged to `token_usage_log` after every invoke
- [ ] Generalist agent seeded in DB with `spawn_mode: always-on`
- [ ] `inject_memory` node returns `[]` stub (Phase 4 will fill this)
- [ ] PM2 `fastapi` process restarts cleanly
- [ ] No `.env` or `__pycache__` in git history

**Next phase:** Phase 3 — Conversation Management (messages table read/write, WebSocket streaming, conversation history hydration into LangGraph state).
