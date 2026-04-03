# Ordo Phase 4: Memory Core Fast Lane Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three fast-lane sidecars (Engram, Eidos, Anamnesis) as asyncio background tasks inside FastAPI, the hook handler dispatch system, and the full RIP Engine. After this phase, every conversation turn triggers memory ingestion, somatic classification, and conditional injection — all within latency budgets — with zero data loss and a conjunctive gate biased toward silence.

**Architecture:** All fast sidecars run as `asyncio.create_task()` inside the FastAPI process — no IPC, no subprocesses. Hook events arrive via `POST /hooks/{hook_name}`, are dispatched by `hooks/dispatcher.py` (querying `hook_handlers` table), and fan out to sidecar coroutines. Embeddings are generated locally via Ollama (`nomic-embed-text`, 768-dim). Eidos calls Claude Haiku via LangChain Model Router with a hard 200ms timeout. Anamnesis enforces a five-dimension conjunctive gate and logs every decision to `injection_log`. The RIP Engine tracks a six-dimension SSS, detects rupture, and selects relational intent each turn.

**Tech Stack:** Python 3.12, FastAPI 0.111+, asyncpg 0.29+, httpx (Ollama calls), langchain-anthropic (Eidos Haiku), pydantic 2+, pytest + pytest-asyncio

---

## Chunk 1: UniversalEvent Schema + Hook Dispatcher

### Task 1: UniversalEvent Pydantic Schema

**Files:**
- Create: `backend/schemas/__init__.py`
- Create: `backend/schemas/events.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_schemas.py`:
```python
import pytest
from datetime import datetime, timezone
from uuid import UUID
from backend.schemas.events import UniversalEvent, EventType


def test_event_type_enum_members():
    expected = {
        "HUMAN_TURN", "MODEL_TURN", "MODEL_REASONING",
        "TOOL_USE", "TOOL_RESULT", "SKILL_INVOKE",
        "SKILL_RESULT", "SYSTEM_MESSAGE", "SESSION_START",
        "SESSION_END", "HUMAN_CORRECTION",
    }
    actual = {e.value for e in EventType}
    assert actual == expected


def test_universal_event_required_fields():
    event = UniversalEvent(
        event_type=EventType.HUMAN_TURN,
        content="Hello Ordo",
        conversation_id="conv-001",
        session_id="sess-001",
        agent_id="generalist",
    )
    assert event.event_type == EventType.HUMAN_TURN
    assert event.content == "Hello Ordo"
    assert isinstance(event.timestamp, datetime)
    assert event.metadata == {}


def test_universal_event_metadata_accepts_dict():
    event = UniversalEvent(
        event_type=EventType.TOOL_USE,
        content="read_file",
        conversation_id="conv-001",
        session_id="sess-001",
        agent_id="generalist",
        metadata={"tool_name": "read_file", "args": {"path": "/tmp/x"}},
    )
    assert event.metadata["tool_name"] == "read_file"


def test_universal_event_timestamp_is_utc():
    event = UniversalEvent(
        event_type=EventType.SESSION_START,
        content="",
        conversation_id="c",
        session_id="s",
        agent_id="a",
    )
    assert event.timestamp.tzinfo is not None


def test_universal_event_serializes_to_dict():
    event = UniversalEvent(
        event_type=EventType.MODEL_TURN,
        content="Here is my response.",
        conversation_id="c",
        session_id="s",
        agent_id="a",
    )
    d = event.model_dump()
    assert d["event_type"] == "MODEL_TURN"
    assert "timestamp" in d
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_schemas.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.schemas'`

- [ ] **Step 3: Create `backend/schemas/__init__.py`**

```python
# schemas package
```

- [ ] **Step 4: Create `backend/schemas/events.py`**

```python
"""
UniversalEvent — shared event schema for all hook paths and sidecar ingestion.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    HUMAN_TURN = "HUMAN_TURN"
    MODEL_TURN = "MODEL_TURN"
    MODEL_REASONING = "MODEL_REASONING"
    TOOL_USE = "TOOL_USE"
    TOOL_RESULT = "TOOL_RESULT"
    SKILL_INVOKE = "SKILL_INVOKE"
    SKILL_RESULT = "SKILL_RESULT"
    SYSTEM_MESSAGE = "SYSTEM_MESSAGE"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    HUMAN_CORRECTION = "HUMAN_CORRECTION"


class UniversalEvent(BaseModel):
    event_type: EventType
    content: str
    conversation_id: str
    session_id: str
    agent_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_schemas.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/schemas/__init__.py backend/schemas/events.py tests/test_schemas.py
git commit -m "feat: add UniversalEvent schema with EventType enum"
```

---

### Task 2: Hook Handler Dispatcher

**Files:**
- Create: `backend/hooks/__init__.py`
- Create: `backend/hooks/dispatcher.py`
- Create: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_dispatcher.py`:
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.hooks.dispatcher import HookDispatcher, HookEvent
from backend.schemas.events import UniversalEvent, EventType


@pytest.fixture
def mock_pool():
    """Return a mock asyncpg pool."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_dispatcher_queries_hook_handlers(mock_pool):
    pool, conn = mock_pool
    conn.fetch.return_value = []  # no handlers registered

    dispatcher = HookDispatcher(pool=pool)
    event = UniversalEvent(
        event_type=EventType.HUMAN_TURN,
        content="test",
        conversation_id="c",
        session_id="s",
        agent_id="a",
    )
    hook_event = HookEvent(hook_name="user_prompt_submit", universal_event=event)
    result = await dispatcher.dispatch(hook_event)

    conn.fetch.assert_called_once()
    call_args = conn.fetch.call_args[0]
    assert "hook_handlers" in call_args[0]
    assert "user_prompt_submit" in call_args
    assert result["handlers_invoked"] == 0


@pytest.mark.asyncio
async def test_dispatcher_skips_disabled_handlers(mock_pool):
    pool, conn = mock_pool
    # fetch returns empty — disabled handlers are filtered in SQL
    conn.fetch.return_value = []

    dispatcher = HookDispatcher(pool=pool)
    hook_event = HookEvent(
        hook_name="session_start",
        universal_event=UniversalEvent(
            event_type=EventType.SESSION_START,
            content="",
            conversation_id="c",
            session_id="s",
            agent_id="a",
        ),
    )
    result = await dispatcher.dispatch(hook_event)
    assert result["handlers_invoked"] == 0


@pytest.mark.asyncio
async def test_hook_event_has_required_fields():
    event = UniversalEvent(
        event_type=EventType.SESSION_END,
        content="",
        conversation_id="c",
        session_id="s",
        agent_id="a",
    )
    hook_event = HookEvent(hook_name="session_end", universal_event=event)
    assert hook_event.hook_name == "session_end"
    assert hook_event.universal_event.event_type == "SESSION_END"


def test_valid_hook_names():
    from backend.hooks.dispatcher import VALID_HOOK_NAMES
    assert "session_start" in VALID_HOOK_NAMES
    assert "user_prompt_submit" in VALID_HOOK_NAMES
    assert "pre_tool_use" in VALID_HOOK_NAMES
    assert "post_tool_use" in VALID_HOOK_NAMES
    assert "pre_compact" in VALID_HOOK_NAMES
    assert "session_end" in VALID_HOOK_NAMES
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_dispatcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.hooks'`

- [ ] **Step 3: Create `backend/hooks/__init__.py`**

```python
# hooks package
```

- [ ] **Step 4: Create `backend/hooks/dispatcher.py`**

```python
"""
Hook Handler Dispatcher.

On each hook event:
  1. Query hook_handlers WHERE hook_name = $1 AND enabled = true ORDER BY priority ASC
  2. For each handler:
     - fast handlers (python_module / function): asyncio.create_task()
     - slow handlers (session_end only): write sidecar_jobs row
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg
from pydantic import BaseModel

from backend.schemas.events import UniversalEvent

log = logging.getLogger(__name__)

VALID_HOOK_NAMES = frozenset({
    "session_start",
    "user_prompt_submit",
    "pre_tool_use",
    "post_tool_use",
    "pre_compact",
    "session_end",
})

# Hooks that fan out to slow sidecars via sidecar_jobs table
SLOW_HOOK_NAMES = frozenset({"session_end"})


class HookEvent(BaseModel):
    hook_name: str
    universal_event: UniversalEvent
    metadata: Dict[str, Any] = {}


class HookDispatcher:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def dispatch(self, hook_event: HookEvent) -> Dict[str, Any]:
        """
        Dispatch a hook event to all registered, enabled handlers in priority order.
        Returns a summary dict with handler count and any errors.
        """
        if hook_event.hook_name not in VALID_HOOK_NAMES:
            raise ValueError(f"Unknown hook name: {hook_event.hook_name!r}")

        async with self._pool.acquire() as conn:
            handlers: List[asyncpg.Record] = await conn.fetch(
                """
                SELECT id, hook_name, handler_type, handler_ref, priority, config
                FROM hook_handlers
                WHERE hook_name = $1 AND enabled = true
                ORDER BY priority ASC
                """,
                hook_event.hook_name,
            )

        invoked = 0
        errors: List[str] = []

        for handler in handlers:
            try:
                if hook_event.hook_name in SLOW_HOOK_NAMES:
                    # Write sidecar_jobs row; slow sidecar PM2 processes poll this table
                    await self._enqueue_slow_job(handler, hook_event)
                else:
                    # Fast handler — fire as background task, no await
                    asyncio.create_task(
                        self._invoke_handler(handler, hook_event),
                        name=f"hook-{hook_event.hook_name}-{handler['id']}",
                    )
                invoked += 1
            except Exception as exc:
                log.error(
                    "dispatcher: failed to schedule handler %s: %s",
                    handler["handler_ref"],
                    exc,
                )
                errors.append(str(exc))

        return {
            "hook_name": hook_event.hook_name,
            "handlers_invoked": invoked,
            "errors": errors,
        }

    async def _invoke_handler(
        self,
        handler: asyncpg.Record,
        hook_event: HookEvent,
    ) -> None:
        """Resolve handler_ref to a callable and invoke it."""
        handler_type = handler["handler_type"]
        handler_ref = handler["handler_ref"]
        config: Dict[str, Any] = dict(handler["config"] or {})

        try:
            if handler_type == "python_module":
                # handler_ref is a dotted path: e.g. backend.sidecars.fast.engram.ingest
                module_path, _, func_name = handler_ref.rpartition(".")
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                if asyncio.iscoroutinefunction(func):
                    await func(hook_event.universal_event, config=config)
                else:
                    func(hook_event.universal_event, config=config)
            else:
                log.warning(
                    "dispatcher: unsupported handler_type %r for ref %r",
                    handler_type,
                    handler_ref,
                )
        except Exception as exc:
            log.error(
                "dispatcher: handler %r raised: %s",
                handler_ref,
                exc,
                exc_info=True,
            )

    async def _enqueue_slow_job(
        self,
        handler: asyncpg.Record,
        hook_event: HookEvent,
    ) -> None:
        """Write a sidecar_jobs row for slow-lane processing."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sidecar_jobs
                    (id, sidecar_name, trigger_hook, payload, status, created_at)
                VALUES ($1, $2, $3, $4, 'pending', $5)
                """,
                str(uuid4()),
                handler["handler_ref"],
                hook_event.hook_name,
                hook_event.universal_event.model_dump_json(),
                datetime.now(timezone.utc),
            )
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_dispatcher.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Add FastAPI routes for all hook endpoints**

Open `backend/routers/hooks.py` (create if absent):

```python
"""
Hook endpoint router.
POST /hooks/{hook_name} — receives hook events from Claude Code or any caller.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from backend.hooks.dispatcher import HookDispatcher, HookEvent, VALID_HOOK_NAMES
from backend.schemas.events import UniversalEvent

router = APIRouter(prefix="/hooks", tags=["hooks"])


def get_dispatcher(request: Request) -> HookDispatcher:
    return request.app.state.hook_dispatcher


@router.post("/{hook_name}")
async def handle_hook(
    hook_name: str,
    event: UniversalEvent,
    dispatcher: HookDispatcher = Depends(get_dispatcher),
):
    if hook_name not in VALID_HOOK_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown hook: {hook_name!r}")
    hook_event = HookEvent(hook_name=hook_name, universal_event=event)
    result = await dispatcher.dispatch(hook_event)
    return result
```

- [ ] **Step 7: Register dispatcher on app startup**

In `backend/main.py`, inside the `lifespan` context manager, after the DB pool is created, add:

```python
from backend.hooks.dispatcher import HookDispatcher
from backend.routers import hooks as hooks_router

# inside lifespan, after pool creation:
app.state.hook_dispatcher = HookDispatcher(pool=pool)

# in router registration section:
app.include_router(hooks_router.router)
```

- [ ] **Step 8: Commit**

```bash
git add backend/hooks/__init__.py backend/hooks/dispatcher.py backend/routers/hooks.py backend/main.py tests/test_dispatcher.py
git commit -m "feat: add hook handler dispatcher with FastAPI routes for all six hook names"
```

---

> **Plan-document reviewer dispatch note (Chunk 1):** After completing Chunk 1, verify: (1) `pytest tests/test_schemas.py tests/test_dispatcher.py -v` all pass, (2) `POST /hooks/user_prompt_submit` with a valid `UniversalEvent` body returns `{"hook_name": "user_prompt_submit", "handlers_invoked": 0, "errors": []}` (zero handlers until Chunk 2 seeds them), (3) `POST /hooks/invalid_name` returns 404. If all pass, proceed to Chunk 2.

---

## Chunk 2: Engram + Eidos Fast Sidecars

### Task 3: Engram — Real-Time Stream Embedder

**Files:**
- Create: `backend/sidecars/__init__.py`
- Create: `backend/sidecars/fast/__init__.py`
- Create: `backend/sidecars/fast/engram.py`
- Create: `tests/test_engram.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_engram.py`:
```python
"""
Engram sidecar tests.
Critical invariant: Engram NEVER prunes — all ingested chunks persist.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from backend.schemas.events import UniversalEvent, EventType


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def sample_event():
    return UniversalEvent(
        event_type=EventType.HUMAN_TURN,
        content="What is the status of the memory pipeline?",
        conversation_id="conv-001",
        session_id="sess-001",
        agent_id="generalist",
    )


@pytest.mark.asyncio
async def test_engram_ingest_returns_chunk_id(mock_pool, sample_event):
    pool, conn = mock_pool
    import uuid
    chunk_id = str(uuid.uuid4())
    conn.fetchval.return_value = chunk_id

    with patch("backend.sidecars.fast.engram._embed", new=AsyncMock(return_value=[0.1] * 768)):
        from backend.sidecars.fast.engram import ingest
        result = await ingest(sample_event, pool=pool)

    assert result["chunk_id"] == chunk_id
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_engram_ingest_writes_correct_defaults(mock_pool, sample_event):
    pool, conn = mock_pool
    import uuid
    conn.fetchval.return_value = str(uuid.uuid4())

    with patch("backend.sidecars.fast.engram._embed", new=AsyncMock(return_value=[0.0] * 768)):
        from backend.sidecars.fast.engram import ingest
        await ingest(sample_event, pool=pool)

    call_args = conn.fetchval.call_args
    sql = call_args[0][0]
    params = call_args[0][1:]
    # priority_weight=1.0, provisional=False, confidence=1.0
    assert 1.0 in params   # priority_weight
    assert False in params  # provisional
    assert True in params   # validated


@pytest.mark.asyncio
async def test_engram_never_deletes(mock_pool):
    """
    Invariant: Engram must never issue DELETE on chunks table.
    We verify no DELETE SQL is constructed anywhere in the ingest path.
    """
    pool, conn = mock_pool
    import uuid
    conn.fetchval.return_value = str(uuid.uuid4())

    events = [
        UniversalEvent(
            event_type=EventType.HUMAN_TURN,
            content=f"message {i}",
            conversation_id="c",
            session_id="s",
            agent_id="a",
        )
        for i in range(10)
    ]

    with patch("backend.sidecars.fast.engram._embed", new=AsyncMock(return_value=[0.0] * 768)):
        from backend.sidecars.fast.engram import ingest
        for event in events:
            await ingest(event, pool=pool)

    # Check that no DELETE was called on the connection
    for call in conn.execute.call_args_list:
        sql = call[0][0] if call[0] else ""
        assert "DELETE" not in sql.upper(), "Engram must never DELETE chunks"


@pytest.mark.asyncio
async def test_engram_embed_produces_768_dims():
    """_embed must return a list of exactly 768 floats."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"embedding": [0.1] * 768}),
        )
        from backend.sidecars.fast.engram import _embed
        result = await _embed("hello world")
    assert len(result) == 768


@pytest.mark.asyncio
async def test_engram_latency_budget(mock_pool, sample_event):
    """Engram must complete within 50ms under normal conditions."""
    import time
    pool, conn = mock_pool
    import uuid
    conn.fetchval.return_value = str(uuid.uuid4())

    with patch("backend.sidecars.fast.engram._embed", new=AsyncMock(return_value=[0.0] * 768)):
        from backend.sidecars.fast.engram import ingest
        start = time.monotonic()
        await ingest(sample_event, pool=pool)
        elapsed_ms = (time.monotonic() - start) * 1000

    # With mocked embed + DB, must be well under 50ms
    assert elapsed_ms < 50, f"Engram took {elapsed_ms:.1f}ms — exceeds 50ms budget"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_engram.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars'`

- [ ] **Step 3: Create sidecar package structure**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
mkdir -p backend/sidecars/fast
touch backend/sidecars/__init__.py backend/sidecars/fast/__init__.py
```

- [ ] **Step 4: Create `backend/sidecars/fast/engram.py`**

```python
"""
Engram — Real-Time Stream Embedder (Fast Lane)
Latency budget: <50ms
Cognitive analog: Hippocampus

Ingests ALL events. Never prunes. Returns chunk_id.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
import asyncpg
from datetime import datetime, timezone
from uuid import uuid4

from backend.schemas.events import UniversalEvent
from backend.config import settings

log = logging.getLogger(__name__)

EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768
LATENCY_BUDGET_MS = 50


async def _embed(text: str) -> List[float]:
    """
    Call Ollama to embed text with nomic-embed-text.
    Returns a list of 768 floats.
    """
    url = f"{settings.ollama_url}/api/embeddings"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = client.post  # resolved below — kept as variable for patching
        response = await httpx.AsyncClient(timeout=5.0).post(
            url,
            json={"model": EMBED_MODEL, "prompt": text},
        )
        response.raise_for_status()
        embedding: List[float] = response.json()["embedding"]
    if len(embedding) != EMBED_DIM:
        raise ValueError(
            f"Unexpected embedding dimension: {len(embedding)} (expected {EMBED_DIM})"
        )
    return embedding


async def ingest(
    event: UniversalEvent,
    pool: Optional[asyncpg.Pool] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ingest a UniversalEvent into the chunks table.

    Steps:
      1. Embed event.content via Ollama (768-dim).
      2. INSERT into chunks with default fields.
      3. Return {"chunk_id": ..., "status": "ok", "latency_ms": ...}.

    Critical invariant: this function NEVER issues DELETE on the chunks table.
    """
    t_start = time.monotonic()

    embedding = await _embed(event.content)

    chunk_id_str = str(uuid4())

    # Pool may be passed directly (tests) or resolved from app state (production)
    _pool = pool
    if _pool is None:
        from backend.main import app
        _pool = app.state.pool

    async with _pool.acquire() as conn:
        chunk_id = await conn.fetchval(
            """
            INSERT INTO chunks (
                id,
                session_id,
                conversation_id,
                event_type,
                content,
                embedding,
                priority_weight,
                provisional,
                confidence,
                validated,
                somatic_tags,
                status,
                created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6::vector,
                $7, $8, $9, $10, $11, $12, $13
            )
            RETURNING id
            """,
            chunk_id_str,
            event.session_id,
            event.conversation_id,
            event.event_type,
            event.content,
            str(embedding),
            1.0,           # priority_weight
            False,         # provisional
            1.0,           # confidence
            True,          # validated
            [],            # somatic_tags — populated by Eidos
            "active",      # status
            datetime.now(timezone.utc),
        )

    elapsed_ms = (time.monotonic() - t_start) * 1000
    if elapsed_ms > LATENCY_BUDGET_MS:
        log.warning("engram: latency %.1fms exceeded %dms budget", elapsed_ms, LATENCY_BUDGET_MS)

    log.debug("engram: ingested chunk %s in %.1fms", chunk_id, elapsed_ms)
    return {"chunk_id": str(chunk_id), "status": "ok", "latency_ms": round(elapsed_ms, 2)}
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_engram.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/sidecars/__init__.py backend/sidecars/fast/__init__.py backend/sidecars/fast/engram.py tests/test_engram.py
git commit -m "feat: implement Engram fast sidecar — real-time stream embedder, never prunes"
```

---

### Task 4: Eidos — Signal Classifier + Somatic Tagger

**Files:**
- Create: `backend/sidecars/fast/eidos.py`
- Create: `tests/test_eidos.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_eidos.py`:
```python
"""
Eidos sidecar tests.
Latency budget: 200ms (enforced with asyncio.wait_for).
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.schemas.events import UniversalEvent, EventType

SOMATIC_VOCABULARY = {"energized", "calm", "tense", "curious", "warm", "flat", "distressed"}


@pytest.fixture
def sample_chunk():
    return {
        "chunk_id": "chunk-abc-123",
        "content": "I'm feeling stuck and anxious about this deadline.",
        "event_type": "HUMAN_TURN",
    }


@pytest.mark.asyncio
async def test_eidos_returns_valid_somatic_tags(sample_chunk):
    mock_tags = ["tense", "distressed"]
    with patch("backend.sidecars.fast.eidos._classify_with_haiku", new=AsyncMock(return_value=mock_tags)):
        from backend.sidecars.fast.eidos import classify
        result = await classify(
            chunk_id=sample_chunk["chunk_id"],
            content=sample_chunk["content"],
            pool=MagicMock(),
        )
    assert result["status"] == "ok"
    assert set(result["somatic_tags"]).issubset(SOMATIC_VOCABULARY)


@pytest.mark.asyncio
async def test_eidos_tags_are_from_fixed_vocabulary(sample_chunk):
    """Eidos must only emit tags from the fixed somatic vocabulary."""
    mock_tags = ["curious", "energized"]
    with patch("backend.sidecars.fast.eidos._classify_with_haiku", new=AsyncMock(return_value=mock_tags)):
        from backend.sidecars.fast.eidos import classify
        result = await classify(
            chunk_id=sample_chunk["chunk_id"],
            content=sample_chunk["content"],
            pool=MagicMock(),
        )
    for tag in result["somatic_tags"]:
        assert tag in SOMATIC_VOCABULARY, f"Tag {tag!r} not in somatic vocabulary"


@pytest.mark.asyncio
async def test_eidos_timeout_enforcement():
    """Eidos must timeout at 200ms and return a graceful degraded result."""
    async def slow_classify(*args, **kwargs):
        await asyncio.sleep(10)  # far exceeds budget
        return ["calm"]

    with patch("backend.sidecars.fast.eidos._classify_with_haiku", new=slow_classify):
        from backend.sidecars.fast.eidos import classify
        result = await classify(
            chunk_id="chunk-xyz",
            content="some content",
            pool=MagicMock(),
            timeout_ms=200,
        )
    assert result["status"] == "timeout"
    assert result["somatic_tags"] == []


@pytest.mark.asyncio
async def test_eidos_updates_chunk_somatic_tags():
    """Eidos must UPDATE the chunks row with somatic_tags after classification."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.execute = AsyncMock()

    mock_tags = ["warm"]
    with patch("backend.sidecars.fast.eidos._classify_with_haiku", new=AsyncMock(return_value=mock_tags)):
        from backend.sidecars.fast.eidos import classify
        await classify(chunk_id="chunk-001", content="hello", pool=pool)

    conn.execute.assert_called()
    call_sql = conn.execute.call_args[0][0]
    assert "UPDATE" in call_sql.upper()
    assert "chunks" in call_sql.lower()
    assert "somatic_tags" in call_sql.lower()


@pytest.mark.asyncio
async def test_eidos_writes_sss_snapshot():
    """Eidos must write an sss_snapshots row each time it classifies."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.execute = AsyncMock()

    mock_tags = ["calm"]
    with patch("backend.sidecars.fast.eidos._classify_with_haiku", new=AsyncMock(return_value=mock_tags)):
        from backend.sidecars.fast.eidos import classify
        await classify(
            chunk_id="chunk-001",
            content="test",
            pool=pool,
            session_id="sess-001",
        )

    calls = [str(c) for c in conn.execute.call_args_list]
    assert any("sss_snapshots" in c.lower() for c in calls), \
        "Eidos must write to sss_snapshots table"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_eidos.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.fast.eidos'`

- [ ] **Step 3: Create `backend/sidecars/fast/eidos.py`**

```python
"""
Eidos — Signal Classifier + Somatic Tagger (Fast Lane)
Latency budget: 200ms (hard timeout via asyncio.wait_for)
Cognitive analog: Amygdala

Classifies chunks via Claude Haiku.
Attaches somatic_tags (fixed vocabulary) to the chunk row.
Writes SSS snapshot for RIP Engine integration.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg

log = logging.getLogger(__name__)

SOMATIC_VOCABULARY = frozenset({
    "energized",
    "calm",
    "tense",
    "curious",
    "warm",
    "flat",
    "distressed",
})

LATENCY_BUDGET_MS = 200

_CLASSIFICATION_PROMPT = """\
You are Eidos, the somatic classification subsystem for Ordo (she/her), \
a cognitive memory-augmented assistant. Your task is to read a single \
conversation chunk and return a JSON array of somatic tags that best \
characterize its emotional signal.

Tags must be chosen exclusively from this vocabulary:
  energized, calm, tense, curious, warm, flat, distressed

Return ONLY a JSON array, e.g.: ["curious", "warm"]
Return an empty array [] if the content is emotionally neutral or ambiguous.

Chunk:
{content}
"""


async def _classify_with_haiku(content: str) -> List[str]:
    """
    Call Claude Haiku via LangChain to classify somatic tags.
    Returns a list of validated somatic tag strings.
    """
    import json
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage

    llm = ChatAnthropic(model="claude-haiku-4-5", max_tokens=64, temperature=0.0)
    prompt = _CLASSIFICATION_PROMPT.format(content=content)
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = response.content.strip()

    try:
        tags = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("eidos: failed to parse Haiku response as JSON: %r", raw)
        return []

    # Validate against fixed vocabulary — silently drop unknown tags
    return [t for t in tags if isinstance(t, str) and t in SOMATIC_VOCABULARY]


async def classify(
    chunk_id: str,
    content: str,
    pool: Optional[asyncpg.Pool] = None,
    config: Optional[Dict[str, Any]] = None,
    timeout_ms: int = LATENCY_BUDGET_MS,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify a chunk's somatic signal.

    Steps:
      1. Call Claude Haiku with asyncio.wait_for(timeout=timeout_ms/1000).
      2. On success: UPDATE chunks SET somatic_tags = $1 WHERE id = $2.
      3. Write sss_snapshots row.
      4. Return {"chunk_id", "somatic_tags", "status", "latency_ms"}.
      On timeout: return {"status": "timeout", "somatic_tags": []}.
    """
    t_start = time.monotonic()

    try:
        tags = await asyncio.wait_for(
            _classify_with_haiku(content),
            timeout=timeout_ms / 1000.0,
        )
    except asyncio.TimeoutError:
        elapsed_ms = (time.monotonic() - t_start) * 1000
        log.warning("eidos: classification timed out after %.1fms", elapsed_ms)
        return {
            "chunk_id": chunk_id,
            "somatic_tags": [],
            "status": "timeout",
            "latency_ms": round(elapsed_ms, 2),
        }
    except Exception as exc:
        elapsed_ms = (time.monotonic() - t_start) * 1000
        log.error("eidos: classification error: %s", exc, exc_info=True)
        return {
            "chunk_id": chunk_id,
            "somatic_tags": [],
            "status": "error",
            "latency_ms": round(elapsed_ms, 2),
        }

    # Persist tags to chunks row and write SSS snapshot
    _pool = pool
    if _pool is None:
        from backend.main import app
        _pool = app.state.pool

    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE chunks SET somatic_tags = $1 WHERE id = $2",
            tags,
            chunk_id,
        )
        # Write SSS snapshot (RIP Engine will read this)
        await conn.execute(
            """
            INSERT INTO sss_snapshots (id, session_id, chunk_id, somatic_tags, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            str(uuid4()),
            session_id or "unknown",
            chunk_id,
            tags,
            datetime.now(timezone.utc),
        )

    elapsed_ms = (time.monotonic() - t_start) * 1000
    log.debug("eidos: classified chunk %s → %s in %.1fms", chunk_id, tags, elapsed_ms)
    return {
        "chunk_id": chunk_id,
        "somatic_tags": tags,
        "status": "ok",
        "latency_ms": round(elapsed_ms, 2),
    }
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_eidos.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/sidecars/fast/eidos.py tests/test_eidos.py
git commit -m "feat: implement Eidos fast sidecar — somatic classifier with 200ms timeout and fixed vocabulary"
```

---

### Task 5: Seed Hook Handlers Table

**Files:**
- Create: `backend/db/seed_hook_handlers.sql`
- Create: `tests/test_hook_handler_seed.py`

- [ ] **Step 1: Create `backend/db/seed_hook_handlers.sql`**

```sql
-- Seed hook_handlers for fast-lane sidecars (Phase 4)
-- Run with: psql -U ordo -d ordo -f backend/db/seed_hook_handlers.sql

-- Clear existing fast-lane handlers to allow idempotent re-seeding
DELETE FROM hook_handlers
WHERE handler_ref IN (
    'backend.sidecars.fast.engram.ingest',
    'backend.sidecars.fast.eidos.classify'
);

-- user_prompt_submit: Engram (priority 10) → Eidos (priority 20)
INSERT INTO hook_handlers (id, hook_name, handler_type, handler_ref, priority, enabled, config)
VALUES
    (gen_random_uuid(), 'user_prompt_submit', 'python_module',
     'backend.sidecars.fast.engram.ingest', 10, true, '{}'),
    (gen_random_uuid(), 'user_prompt_submit', 'python_module',
     'backend.sidecars.fast.eidos.classify', 20, true, '{"timeout_ms": 200}'),

-- post_tool_use: Engram (priority 10)
    (gen_random_uuid(), 'post_tool_use', 'python_module',
     'backend.sidecars.fast.engram.ingest', 10, true, '{}'),

-- pre_compact: Engram snapshot (priority 10)
    (gen_random_uuid(), 'pre_compact', 'python_module',
     'backend.sidecars.fast.engram.ingest', 10, true, '{"provisional": true}');
```

- [ ] **Step 2: Apply seed to development database**

```bash
psql -U ordo -d ordo -f "C:/Users/user/AI-Assistant Version 4/backend/db/seed_hook_handlers.sql"
```

Expected: `DELETE 0` (or count if re-running), then `INSERT 0 4`

- [ ] **Step 3: Write a smoke test against test DB**

Create `tests/test_hook_handler_seed.py`:
```python
"""
Verify that hook_handlers seed rows are correctly structured.
Runs against the test database — requires DB to be seeded.
"""
import pytest


def test_seed_sql_file_exists():
    import os
    path = "C:/Users/user/AI-Assistant Version 4/backend/db/seed_hook_handlers.sql"
    assert os.path.exists(path), "Seed SQL file must exist"


def test_seed_sql_contains_all_fast_handlers():
    with open("C:/Users/user/AI-Assistant Version 4/backend/db/seed_hook_handlers.sql") as f:
        content = f.read()
    assert "backend.sidecars.fast.engram.ingest" in content
    assert "backend.sidecars.fast.eidos.classify" in content
    assert "user_prompt_submit" in content
    assert "post_tool_use" in content
    assert "pre_compact" in content


def test_seed_sql_has_no_dangerous_statements():
    with open("C:/Users/user/AI-Assistant Version 4/backend/db/seed_hook_handlers.sql") as f:
        content = f.read()
    # Should only DELETE from hook_handlers (targeted cleanup), not DROP TABLE etc.
    assert "DROP TABLE" not in content.upper()
    assert "TRUNCATE" not in content.upper()
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_hook_handler_seed.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/db/seed_hook_handlers.sql tests/test_hook_handler_seed.py
git commit -m "feat: seed hook_handlers table for Engram and Eidos fast-lane dispatch"
```

---

> **Plan-document reviewer dispatch note (Chunk 2):** After completing Chunk 2, verify: (1) `pytest tests/test_engram.py tests/test_eidos.py tests/test_hook_handler_seed.py -v` all pass, (2) manually call `POST /hooks/user_prompt_submit` with a HUMAN_TURN event and confirm a new row appears in `chunks` table with embedding populated, (3) confirm no DELETE statement appears in Engram code (`grep -n "DELETE" backend/sidecars/fast/engram.py` should return nothing). If all pass, proceed to Chunk 3.

---

## Chunk 3: Anamnesis Gate + Full RIP Engine

### Task 6: Anamnesis — Conjunctive Injection Gate

**Files:**
- Create: `backend/sidecars/fast/anamnesis.py`
- Create: `tests/test_anamnesis.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_anamnesis.py`:
```python
"""
Anamnesis sidecar tests.
Critical invariant: ALL five gate dimensions must pass — a single failure blocks injection.
Psyche injections with bypass_anamnesis=True are never filtered.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.schemas.events import UniversalEvent, EventType


def make_pool_with_chunks(chunks: list) -> tuple:
    """Return (pool, conn) mock where conn.fetch returns `chunks`."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.fetch.return_value = chunks
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    return pool, conn


@pytest.mark.asyncio
async def test_anamnesis_empty_result_when_no_chunks():
    pool, conn = make_pool_with_chunks([])
    with patch("backend.sidecars.fast.anamnesis._embed", new=AsyncMock(return_value=[0.1] * 768)):
        from backend.sidecars.fast.anamnesis import inject
        result = await inject(
            query_content="anything",
            session_id="s",
            conversation_id="c",
            turn_number=10,
            pool=pool,
        )
    assert result["injected_chunks"] == []
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_anamnesis_bypasses_gate_for_psyche_chunks():
    """
    Chunks with bypass_anamnesis=True (Psyche injections) must always pass,
    regardless of gate dimension outcomes.
    """
    pool, conn = make_pool_with_chunks([])
    psyche_chunk = {
        "id": "psyche-001",
        "content": "Soul narrative fragment.",
        "bypass_anamnesis": True,
        "similarity": 0.50,   # below threshold — would normally block
        "turn_number": 5,     # within recency window — would normally block
    }

    with patch("backend.sidecars.fast.anamnesis._embed", new=AsyncMock(return_value=[0.1] * 768)):
        with patch("backend.sidecars.fast.anamnesis._fetch_candidates", new=AsyncMock(return_value=[psyche_chunk])):
            from backend.sidecars.fast.anamnesis import inject
            result = await inject(
                query_content="soul test",
                session_id="s",
                conversation_id="c",
                turn_number=10,
                pool=pool,
            )

    ids = [c["id"] for c in result["injected_chunks"]]
    assert "psyche-001" in ids, "Psyche chunks must bypass the Anamnesis gate"


@pytest.mark.asyncio
async def test_anamnesis_blocks_on_low_similarity():
    """Gate dimension 1: similarity < 0.78 must block injection."""
    low_sim_chunk = {
        "id": "chunk-low-sim",
        "content": "Unrelated content.",
        "bypass_anamnesis": False,
        "similarity": 0.60,   # below 0.78 threshold
        "turn_number": 1,     # old enough (turn_number 1, current turn 20 → 19 turns ago)
        "topic_id": "topic-A",
        "age_turns": 19,
    }

    pool, conn = make_pool_with_chunks([])
    with patch("backend.sidecars.fast.anamnesis._embed", new=AsyncMock(return_value=[0.1] * 768)):
        with patch("backend.sidecars.fast.anamnesis._fetch_candidates", new=AsyncMock(return_value=[low_sim_chunk])):
            from backend.sidecars.fast.anamnesis import inject
            result = await inject(
                query_content="something relevant",
                session_id="s",
                conversation_id="c",
                turn_number=20,
                pool=pool,
            )

    ids = [c["id"] for c in result["injected_chunks"]]
    assert "chunk-low-sim" not in ids, "Low-similarity chunk must be blocked"


@pytest.mark.asyncio
async def test_anamnesis_blocks_on_recency_bias():
    """Gate dimension 4: chunks from within last 5 turns must be blocked."""
    recent_chunk = {
        "id": "chunk-recent",
        "content": "Just said this.",
        "bypass_anamnesis": False,
        "similarity": 0.92,   # high similarity — would pass dim 1
        "turn_number": 18,    # within last 5 turns (current=20, 20-18=2)
        "topic_id": "topic-B",
        "age_turns": 2,
    }

    pool, conn = make_pool_with_chunks([])
    with patch("backend.sidecars.fast.anamnesis._embed", new=AsyncMock(return_value=[0.1] * 768)):
        with patch("backend.sidecars.fast.anamnesis._fetch_candidates", new=AsyncMock(return_value=[recent_chunk])):
            from backend.sidecars.fast.anamnesis import inject
            result = await inject(
                query_content="just said",
                session_id="s",
                conversation_id="c",
                turn_number=20,
                pool=pool,
            )

    ids = [c["id"] for c in result["injected_chunks"]]
    assert "chunk-recent" not in ids, "Recent chunk (within 5 turns) must be blocked"


@pytest.mark.asyncio
async def test_anamnesis_logs_gate_decision():
    """Every gate decision (pass or block) must be logged to injection_log."""
    pool, conn = make_pool_with_chunks([])
    conn.execute = AsyncMock()

    with patch("backend.sidecars.fast.anamnesis._embed", new=AsyncMock(return_value=[0.1] * 768)):
        with patch("backend.sidecars.fast.anamnesis._fetch_candidates", new=AsyncMock(return_value=[])):
            from backend.sidecars.fast.anamnesis import inject
            await inject(
                query_content="test query",
                session_id="s",
                conversation_id="c",
                turn_number=10,
                pool=pool,
            )

    # injection_log INSERT must have been called
    insert_calls = [
        c for c in conn.execute.call_args_list
        if "injection_log" in str(c).lower()
    ]
    assert len(insert_calls) >= 1, "Gate decisions must be logged to injection_log"


@pytest.mark.asyncio
async def test_anamnesis_max_k_is_5():
    """Anamnesis must return at most K=5 chunks."""
    # 8 high-quality chunks — gate should return only 5
    good_chunks = [
        {
            "id": f"chunk-{i:03d}",
            "content": f"High quality relevant memory {i}",
            "bypass_anamnesis": False,
            "similarity": 0.90,
            "turn_number": i,
            "topic_id": "topic-A",
            "age_turns": 50 + i,  # old enough, avoids recency bias
        }
        for i in range(8)
    ]

    pool, conn = make_pool_with_chunks([])
    conn.execute = AsyncMock()

    with patch("backend.sidecars.fast.anamnesis._embed", new=AsyncMock(return_value=[0.1] * 768)):
        with patch("backend.sidecars.fast.anamnesis._fetch_candidates", new=AsyncMock(return_value=good_chunks)):
            with patch("backend.sidecars.fast.anamnesis._passes_gate", new=AsyncMock(return_value=(True, "all_pass"))):
                from backend.sidecars.fast.anamnesis import inject
                result = await inject(
                    query_content="relevant query",
                    session_id="s",
                    conversation_id="c",
                    turn_number=100,
                    pool=pool,
                )

    assert len(result["injected_chunks"]) <= 5, "Anamnesis must return at most K=5 chunks"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_anamnesis.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.fast.anamnesis'`

- [ ] **Step 3: Create `backend/sidecars/fast/anamnesis.py`**

```python
"""
Anamnesis — Conjunctive Injection Gate (Fast Lane)
Latency budget: 450ms
Cognitive analog: Associative recall

Injection is blocked if ANY of five gate dimensions fails.
Biased toward silence — all dimensions must pass.
Logs every gate decision to injection_log.

Gate dimensions:
  1. Similarity threshold: 0.78 base (age-penalized: -0.01 per 10 turns, floor 0.65)
  2. In-context redundancy: 0.92 threshold (skip near-duplicates already injected this turn)
  3. Net-new content: cosine distance from last 20 injected chunks must be > 0.12
  4. Recency bias: skip chunks from within last 5 turns (already in context)
  5. Topic diversity quota: max 3 per topic_node per 10-turn window

Special: chunks with bypass_anamnesis=True (Psyche) are never filtered.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import asyncpg

from backend.sidecars.fast.engram import _embed

log = logging.getLogger(__name__)

LATENCY_BUDGET_MS = 450
K_MAX = 5  # Maximum chunks returned per injection call

# Gate thresholds
SIMILARITY_BASE = 0.78
SIMILARITY_FLOOR = 0.65
SIMILARITY_AGE_PENALTY_PER_10_TURNS = 0.01
REDUNDANCY_THRESHOLD = 0.92      # block if cosine similarity to already-injected > this
NET_NEW_THRESHOLD = 0.12         # cosine distance from last 20 injected must be > this
RECENCY_TURNS = 5                # skip chunks from within last N turns
TOPIC_QUOTA_MAX = 3              # max chunks per topic per 10-turn window
TOPIC_QUOTA_WINDOW = 10          # turn window for topic diversity quota


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _age_penalized_threshold(age_turns: int) -> float:
    penalty = (age_turns // 10) * SIMILARITY_AGE_PENALTY_PER_10_TURNS
    return max(SIMILARITY_FLOOR, SIMILARITY_BASE - penalty)


async def _fetch_candidates(
    embedding: List[float],
    session_id: str,
    pool: asyncpg.Pool,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Fetch top candidate chunks from the vector store via cosine similarity.
    Returns chunks with similarity scores, turn_number, topic_id, age_turns.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.content,
                c.bypass_anamnesis,
                c.turn_number,
                c.topic_id,
                1 - (c.embedding <=> $1::vector) AS similarity,
                (SELECT MAX(turn_number) FROM chunks WHERE session_id = $2) - c.turn_number AS age_turns
            FROM chunks c
            WHERE c.session_id = $2
              AND c.status = 'active'
            ORDER BY c.embedding <=> $1::vector
            LIMIT $3
            """,
            str(embedding),
            session_id,
            limit,
        )
    return [dict(r) for r in rows]


async def _passes_gate(
    chunk: Dict[str, Any],
    query_embedding: List[float],
    current_turn: int,
    injected_this_turn: List[Dict[str, Any]],
    topic_counts: Dict[str, int],
) -> Tuple[bool, str]:
    """
    Evaluate all five gate dimensions for a candidate chunk.
    Returns (passes: bool, reason: str).
    Psyche chunks (bypass_anamnesis=True) always pass.
    """
    # Psyche bypass — unconditional pass
    if chunk.get("bypass_anamnesis"):
        return True, "psyche_bypass"

    age_turns = chunk.get("age_turns", 0) or 0
    similarity = chunk.get("similarity", 0.0) or 0.0

    # Dimension 1: Similarity threshold (age-penalized)
    threshold = _age_penalized_threshold(age_turns)
    if similarity < threshold:
        return False, f"similarity_{similarity:.3f}_below_{threshold:.3f}"

    # Dimension 4: Recency bias (checked early — cheap)
    if age_turns < RECENCY_TURNS:
        return False, f"recency_bias_age_{age_turns}_turns"

    # Dimension 2: In-context redundancy
    for already in injected_this_turn:
        if "embedding" in already:
            redundancy_sim = _cosine_similarity(query_embedding, already["embedding"])
            if redundancy_sim > REDUNDANCY_THRESHOLD:
                return False, f"redundancy_{redundancy_sim:.3f}"

    # Dimension 3: Net-new content
    if injected_this_turn:
        max_similarity_to_injected = max(
            _cosine_similarity(query_embedding, inj.get("embedding", [0.0]))
            for inj in injected_this_turn
        )
        if (1.0 - max_similarity_to_injected) <= NET_NEW_THRESHOLD:
            return False, f"not_net_new_distance_{1.0 - max_similarity_to_injected:.3f}"

    # Dimension 5: Topic diversity quota
    topic_id = chunk.get("topic_id")
    if topic_id:
        window_start = current_turn - TOPIC_QUOTA_WINDOW
        count_in_window = topic_counts.get(topic_id, 0)
        if count_in_window >= TOPIC_QUOTA_MAX:
            return False, f"topic_quota_{topic_id}_{count_in_window}"

    return True, "all_pass"


async def inject(
    query_content: str,
    session_id: str,
    conversation_id: str,
    turn_number: int,
    pool: Optional[asyncpg.Pool] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run the conjunctive injection gate for the current turn.

    Returns up to K=5 chunks that passed all gate dimensions.
    Logs every gate decision (pass or block) to injection_log.
    """
    t_start = time.monotonic()

    _pool = pool
    if _pool is None:
        from backend.main import app
        _pool = app.state.pool

    query_embedding = await _embed(query_content)
    candidates = await _fetch_candidates(query_embedding, session_id, _pool)

    injected: List[Dict[str, Any]] = []
    topic_counts: Dict[str, int] = {}
    gate_log_rows = []

    for chunk in candidates:
        if len(injected) >= K_MAX:
            break

        passes, reason = await _passes_gate(
            chunk=chunk,
            query_embedding=query_embedding,
            current_turn=turn_number,
            injected_this_turn=injected,
            topic_counts=topic_counts,
        )

        gate_log_rows.append({
            "id": str(uuid4()),
            "session_id": session_id,
            "conversation_id": conversation_id,
            "chunk_id": chunk["id"],
            "turn_number": turn_number,
            "passed": passes,
            "block_reason": None if passes else reason,
            "created_at": datetime.now(timezone.utc),
        })

        if passes:
            injected.append(chunk)
            topic_id = chunk.get("topic_id")
            if topic_id:
                topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1

    # Write gate decisions to injection_log (batch insert)
    async with _pool.acquire() as conn:
        for row in gate_log_rows:
            await conn.execute(
                """
                INSERT INTO injection_log
                    (id, session_id, conversation_id, chunk_id, turn_number,
                     passed, block_reason, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                row["id"], row["session_id"], row["conversation_id"],
                row["chunk_id"], row["turn_number"],
                row["passed"], row["block_reason"], row["created_at"],
            )

    elapsed_ms = (time.monotonic() - t_start) * 1000
    if elapsed_ms > LATENCY_BUDGET_MS:
        log.warning("anamnesis: %.1fms exceeded %dms budget", elapsed_ms, LATENCY_BUDGET_MS)

    return {
        "injected_chunks": injected,
        "candidates_evaluated": len(candidates),
        "gate_log_written": len(gate_log_rows),
        "status": "ok",
        "latency_ms": round(elapsed_ms, 2),
    }
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_anamnesis.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/sidecars/fast/anamnesis.py tests/test_anamnesis.py
git commit -m "feat: implement Anamnesis conjunctive injection gate with five gate dimensions and injection_log"
```

---

### Task 7: RIP Engine — Full Implementation

**Files:**
- Modify: `backend/rip/engine.py` (replace Phase 2 skeleton)
- Create: `tests/test_rip_engine.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_rip_engine.py`:
```python
"""
RIP Engine tests — full implementation.
SSS: 6 dimensions. Rupture detection. Relational intent selection.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.rip.engine import RIPEngine, SSS, RelationalIntent


def make_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    return pool, conn


def test_sss_initial_values():
    """All SSS dimensions must initialize to 0.5."""
    sss = SSS()
    assert sss.valence == 0.5
    assert sss.arousal == 0.5
    assert sss.tension == 0.5
    assert sss.curiosity == 0.5
    assert sss.warmth == 0.5
    assert sss.coherence == 0.5


def test_sss_all_six_dimensions_present():
    sss = SSS()
    assert hasattr(sss, "valence")
    assert hasattr(sss, "arousal")
    assert hasattr(sss, "tension")
    assert hasattr(sss, "curiosity")
    assert hasattr(sss, "warmth")
    assert hasattr(sss, "coherence")


def test_relational_intent_priority_ordering():
    """REPAIR must have highest priority (100)."""
    from backend.rip.engine import INTENT_PRIORITY
    assert INTENT_PRIORITY[RelationalIntent.REPAIR] == 100
    assert INTENT_PRIORITY[RelationalIntent.GROUND] == 90
    assert INTENT_PRIORITY[RelationalIntent.WITNESS] == 80
    assert INTENT_PRIORITY[RelationalIntent.CELEBRATE] == 70
    assert INTENT_PRIORITY[RelationalIntent.REFLECT] == 60
    assert INTENT_PRIORITY[RelationalIntent.EXPLORE] == 50
    assert INTENT_PRIORITY[RelationalIntent.INFORM] == 40


def test_update_sss_blends_somatic_tags():
    engine = RIPEngine(pool=MagicMock())
    initial_sss = SSS()
    updated = engine.update_sss(
        current_sss=initial_sss,
        turn_content="This is frustrating and tense.",
        somatic_tags=["tense", "distressed"],
    )
    # tension and distressed → tension and valence should shift
    assert updated.tension > initial_sss.tension
    assert updated.valence < initial_sss.valence


def test_update_sss_warm_tags_increase_warmth():
    engine = RIPEngine(pool=MagicMock())
    sss = SSS()
    updated = engine.update_sss(
        current_sss=sss,
        turn_content="Thank you, this is wonderful.",
        somatic_tags=["warm", "calm"],
    )
    assert updated.warmth > sss.warmth


def test_rupture_detection_triggers_repair_intent():
    """
    If valence < 0.3 AND tension > 0.7 for 2+ consecutive turns, REPAIR must override.
    """
    engine = RIPEngine(pool=MagicMock())
    # First rupture turn
    engine._rupture_consecutive_turns = 1
    rupture_sss = SSS(valence=0.2, tension=0.8, arousal=0.5, curiosity=0.5, warmth=0.5, coherence=0.5)
    intent = engine.get_relational_intent(rupture_sss)
    assert intent == RelationalIntent.REPAIR


def test_no_rupture_below_threshold():
    """If only 1 consecutive rupture turn (< 2 required), should not be REPAIR."""
    engine = RIPEngine(pool=MagicMock())
    engine._rupture_consecutive_turns = 0  # reset
    # Low valence, high tension — but only 1 turn
    sss = SSS(valence=0.25, tension=0.75, arousal=0.5, curiosity=0.5, warmth=0.5, coherence=0.5)
    intent = engine.get_relational_intent(sss)
    # Should not be REPAIR on first rupture turn
    assert intent != RelationalIntent.REPAIR


def test_get_relational_intent_returns_string_name():
    engine = RIPEngine(pool=MagicMock())
    sss = SSS()
    intent = engine.get_relational_intent(sss)
    assert isinstance(intent, RelationalIntent)


@pytest.mark.asyncio
async def test_rip_writes_sss_snapshot():
    """RIPEngine must write an sss_snapshots row each turn."""
    pool, conn = make_pool()
    engine = RIPEngine(pool=pool)
    sss = SSS()
    await engine.persist_sss(sss, session_id="sess-001", turn_number=5)
    conn.execute.assert_called_once()
    call_sql = conn.execute.call_args[0][0]
    assert "sss_snapshots" in call_sql.lower()


@pytest.mark.asyncio
async def test_rip_repair_intent_persists_until_confirmed():
    """REPAIR intent must continue until repair is explicitly confirmed."""
    pool, conn = make_pool()
    engine = RIPEngine(pool=pool)
    engine._rupture_consecutive_turns = 2  # already in rupture
    engine._repair_confirmed = False

    sss = SSS(valence=0.5, tension=0.5, arousal=0.5, curiosity=0.5, warmth=0.5, coherence=0.5)
    intent = engine.get_relational_intent(sss)
    # Even though SSS looks normal now, repair must persist until confirmed
    assert intent == RelationalIntent.REPAIR
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_rip_engine.py -v
```

Expected: `ImportError` or `AttributeError` — Phase 2 skeleton does not have full implementation.

- [ ] **Step 3: Implement `backend/rip/engine.py` (full replacement)**

```python
"""
RIP Engine — Relational Consciousness (Full Implementation)
Replaces Phase 2 skeleton.

SSS: 6 affective dimensions (valence, arousal, tension, curiosity, warmth, coherence).
All initialized to 0.5. Updated per turn via weighted blend of current state and Eidos signals.

Relational intent priority ordering:
  REPAIR(100) > GROUND(90) > WITNESS(80) > CELEBRATE(70) > REFLECT(60) > EXPLORE(50) > INFORM(40)

Rupture detection: valence < 0.3 AND tension > 0.7 for 2+ consecutive turns
→ REPAIR intent, overrides all others until repair confirmed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

# Somatic tag → SSS dimension deltas
# Positive delta = increase dimension, negative = decrease
_TAG_DELTA_MAP: Dict[str, Dict[str, float]] = {
    "energized": {"arousal": +0.15, "valence": +0.10},
    "calm":      {"arousal": -0.10, "tension": -0.10, "valence": +0.05},
    "tense":     {"tension": +0.20, "arousal": +0.10, "valence": -0.10},
    "curious":   {"curiosity": +0.20, "arousal": +0.05},
    "warm":      {"warmth": +0.20, "valence": +0.10},
    "flat":      {"arousal": -0.15, "curiosity": -0.10, "warmth": -0.05},
    "distressed":{"valence": -0.25, "tension": +0.15, "arousal": +0.10, "warmth": -0.10},
}

# SSS blend weight: new signal vs. current state
SSS_BLEND_ALPHA = 0.3  # 30% new signal, 70% current state

# Rupture thresholds
RUPTURE_VALENCE_MAX = 0.3
RUPTURE_TENSION_MIN = 0.7
RUPTURE_CONSECUTIVE_TURNS_REQUIRED = 2


class RelationalIntent(str, Enum):
    REPAIR = "REPAIR"
    GROUND = "GROUND"
    WITNESS = "WITNESS"
    CELEBRATE = "CELEBRATE"
    REFLECT = "REFLECT"
    EXPLORE = "EXPLORE"
    INFORM = "INFORM"


INTENT_PRIORITY: Dict[RelationalIntent, int] = {
    RelationalIntent.REPAIR:    100,
    RelationalIntent.GROUND:    90,
    RelationalIntent.WITNESS:   80,
    RelationalIntent.CELEBRATE: 70,
    RelationalIntent.REFLECT:   60,
    RelationalIntent.EXPLORE:   50,
    RelationalIntent.INFORM:    40,
}


class SSS(BaseModel):
    """Synthetic Somatic State — 6 affective dimensions, all clamped [0.0, 1.0]."""
    valence:   float = Field(default=0.5, ge=0.0, le=1.0)
    arousal:   float = Field(default=0.5, ge=0.0, le=1.0)
    tension:   float = Field(default=0.5, ge=0.0, le=1.0)
    curiosity: float = Field(default=0.5, ge=0.0, le=1.0)
    warmth:    float = Field(default=0.5, ge=0.0, le=1.0)
    coherence: float = Field(default=0.5, ge=0.0, le=1.0)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class RIPEngine:
    """
    Relational Consciousness engine.

    Public API:
      update_sss(current_sss, turn_content, somatic_tags) -> SSS
      get_relational_intent(sss) -> RelationalIntent
      await persist_sss(sss, session_id, turn_number) -> None
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._rupture_consecutive_turns: int = 0
        self._repair_confirmed: bool = True  # no active rupture initially

    def update_sss(
        self,
        current_sss: SSS,
        turn_content: str,
        somatic_tags: List[str],
    ) -> SSS:
        """
        Compute next SSS via weighted blend:
          new_dim = current_dim * (1 - alpha) + signal_dim * alpha
        where signal_dim = current_dim + sum(tag_deltas for tag in somatic_tags).
        """
        # Start from current state
        dims = current_sss.model_dump()

        # Accumulate tag deltas
        signal = dict(dims)  # copy
        for tag in somatic_tags:
            deltas = _TAG_DELTA_MAP.get(tag, {})
            for dim, delta in deltas.items():
                signal[dim] = _clamp(signal[dim] + delta)

        # Weighted blend
        blended = {
            dim: _clamp(dims[dim] * (1 - SSS_BLEND_ALPHA) + signal[dim] * SSS_BLEND_ALPHA)
            for dim in dims
        }

        return SSS(**blended)

    def get_relational_intent(self, sss: SSS) -> RelationalIntent:
        """
        Select the highest-priority applicable relational intent.

        Rupture detection:
          - if valence < 0.3 AND tension > 0.7: increment rupture counter
          - if counter >= 2 AND repair not yet confirmed: REPAIR overrides all
          - else: decrement counter (toward recovery), clear repair flag
        """
        is_rupture_signal = (
            sss.valence < RUPTURE_VALENCE_MAX and sss.tension > RUPTURE_TENSION_MIN
        )

        if is_rupture_signal:
            self._rupture_consecutive_turns += 1
        else:
            # Only decrement — never go below 0
            if self._rupture_consecutive_turns > 0:
                self._rupture_consecutive_turns -= 1

        # REPAIR override: active rupture OR unconfirmed prior rupture
        in_active_rupture = self._rupture_consecutive_turns >= RUPTURE_CONSECUTIVE_TURNS_REQUIRED
        if in_active_rupture or not self._repair_confirmed:
            self._repair_confirmed = False  # must be explicitly confirmed
            log.info(
                "rip: REPAIR intent active (consecutive_turns=%d, confirmed=%s)",
                self._rupture_consecutive_turns,
                self._repair_confirmed,
            )
            return RelationalIntent.REPAIR

        # Normal intent selection based on SSS values
        if sss.warmth > 0.7 and sss.valence > 0.7:
            return RelationalIntent.CELEBRATE
        if sss.tension > 0.6:
            return RelationalIntent.GROUND
        if sss.valence < 0.45:
            return RelationalIntent.WITNESS
        if sss.curiosity > 0.65:
            return RelationalIntent.EXPLORE
        if sss.coherence < 0.45:
            return RelationalIntent.REFLECT
        return RelationalIntent.INFORM

    def confirm_repair(self) -> None:
        """
        Mark an active rupture as repaired.
        Must be called explicitly (e.g. when human acknowledges resolution).
        """
        self._repair_confirmed = True
        self._rupture_consecutive_turns = 0
        log.info("rip: rupture repair confirmed — returning to normal intent selection")

    async def persist_sss(
        self,
        sss: SSS,
        session_id: str,
        turn_number: int,
    ) -> None:
        """Write SSS snapshot to sss_snapshots table."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sss_snapshots
                    (id, session_id, turn_number, valence, arousal, tension,
                     curiosity, warmth, coherence, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                str(uuid4()),
                session_id,
                turn_number,
                sss.valence,
                sss.arousal,
                sss.tension,
                sss.curiosity,
                sss.warmth,
                sss.coherence,
                datetime.now(timezone.utc),
            )
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_rip_engine.py -v
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/rip/engine.py tests/test_rip_engine.py
git commit -m "feat: implement full RIP Engine — SSS 6-dim, rupture detection, relational intent priority ordering"
```

---

### Task 8: Provisional Chunk Abandonment + Integration Wiring

**Files:**
- Create: `backend/sidecars/fast/provisional.py`
- Modify: `backend/hooks/dispatcher.py` (add bypass_anamnesis flag handling note — no code change required; already in schema)
- Create: `tests/test_provisional.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_provisional.py`:
```python
"""
Provisional chunk lifecycle tests.
Invariant: chunks with confidence=0.4 that are not validated within K=5 turns
are demoted to status='abandoned'. They are NEVER deleted.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.sidecars.fast.provisional import abandon_stale_provisional_chunks


def make_pool_with_rows(rows: list):
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.fetch.return_value = rows
    conn.execute = AsyncMock()
    return pool, conn


@pytest.mark.asyncio
async def test_provisional_chunks_are_demoted_not_deleted():
    """
    Stale provisional chunks must be set to status='abandoned', never deleted.
    """
    stale_chunks = [
        {"id": "prov-001", "turn_number": 1, "confidence": 0.4},
        {"id": "prov-002", "turn_number": 2, "confidence": 0.4},
    ]
    pool, conn = make_pool_with_rows(stale_chunks)

    await abandon_stale_provisional_chunks(
        session_id="sess-001",
        current_turn=10,  # 10 - 1 = 9 turns > K=5
        k=5,
        pool=pool,
    )

    # Must UPDATE to 'abandoned', not DELETE
    for call in conn.execute.call_args_list:
        sql = call[0][0]
        assert "DELETE" not in sql.upper(), "Provisional chunks must never be deleted"

    # Must have issued at least one UPDATE with 'abandoned'
    update_calls = [c for c in conn.execute.call_args_list if "UPDATE" in c[0][0].upper()]
    assert len(update_calls) >= 1


@pytest.mark.asyncio
async def test_provisional_chunks_within_k_turns_not_abandoned():
    """
    Provisional chunks within K=5 turns of current turn must NOT be abandoned.
    """
    fresh_chunks = [
        {"id": "prov-003", "turn_number": 7, "confidence": 0.4},  # 10-7=3 turns, within K=5
    ]
    pool, conn = make_pool_with_rows(fresh_chunks)

    # Simulate: fetch returns nothing because query filters for age > K
    conn.fetch.return_value = []  # DB filters them out

    await abandon_stale_provisional_chunks(
        session_id="sess-001",
        current_turn=10,
        k=5,
        pool=pool,
    )

    # No update should be called on fresh provisional chunks
    update_calls = [c for c in conn.execute.call_args_list if "UPDATE" in c[0][0].upper()]
    assert len(update_calls) == 0


@pytest.mark.asyncio
async def test_abandoned_chunks_remain_queryable():
    """
    After abandonment, chunks must still be queryable (status='abandoned').
    They are negative knowledge — not deleted.
    """
    # This test verifies the UPDATE sets status='abandoned', not a DELETE
    stale = [{"id": "prov-004", "turn_number": 1, "confidence": 0.4}]
    pool, conn = make_pool_with_rows(stale)

    await abandon_stale_provisional_chunks(
        session_id="s",
        current_turn=10,
        k=5,
        pool=pool,
    )

    update_calls = [c for c in conn.execute.call_args_list if "UPDATE" in c[0][0].upper()]
    assert len(update_calls) >= 1
    # Check 'abandoned' value is in the call params
    for call in update_calls:
        params = call[0][1:]  # positional params after SQL string
        assert "abandoned" in params, "Demotion must use status='abandoned'"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_provisional.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.fast.provisional'`

- [ ] **Step 3: Create `backend/sidecars/fast/provisional.py`**

```python
"""
Provisional chunk lifecycle management.

Provisional chunks (confidence=0.4, provisional=True) must be validated
within K=5 turns. If not validated, they are demoted to status='abandoned'.

Critical invariant: provisional chunks are NEVER deleted.
Abandoned chunks remain in the DB as negative knowledge — excluded from injection
but queryable for audit and analysis.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)

DEFAULT_K = 5  # Validation window in turns


async def abandon_stale_provisional_chunks(
    session_id: str,
    current_turn: int,
    k: int = DEFAULT_K,
    pool: Optional[asyncpg.Pool] = None,
) -> int:
    """
    Find provisional chunks older than K turns (not yet validated) and
    demote them to status='abandoned'.

    Returns the count of chunks demoted.
    Never issues DELETE — only UPDATE.
    """
    _pool = pool
    if _pool is None:
        from backend.main import app
        _pool = app.state.pool

    cutoff_turn = current_turn - k

    async with _pool.acquire() as conn:
        stale_rows = await conn.fetch(
            """
            SELECT id
            FROM chunks
            WHERE session_id = $1
              AND provisional = true
              AND validated = false
              AND status = 'active'
              AND turn_number <= $2
            """,
            session_id,
            cutoff_turn,
        )

        if not stale_rows:
            return 0

        stale_ids = [r["id"] for r in stale_rows]
        abandoned_at = datetime.now(timezone.utc)

        for chunk_id in stale_ids:
            await conn.execute(
                """
                UPDATE chunks
                SET status = $1, abandoned_at = $2
                WHERE id = $3
                """,
                "abandoned",
                abandoned_at,
                chunk_id,
            )
            log.debug(
                "provisional: demoted chunk %s to abandoned (session=%s, turn=%d)",
                chunk_id,
                session_id,
                current_turn,
            )

    log.info(
        "provisional: abandoned %d stale provisional chunks in session %s at turn %d",
        len(stale_ids),
        session_id,
        current_turn,
    )
    return len(stale_ids)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_provisional.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Run full Phase 4 test suite**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_schemas.py tests/test_dispatcher.py tests/test_engram.py tests/test_eidos.py tests/test_hook_handler_seed.py tests/test_anamnesis.py tests/test_rip_engine.py tests/test_provisional.py -v
```

Expected output: All tests pass. Count: `≥ 36 passed, 0 failed`

- [ ] **Step 6: Commit**

```bash
git add backend/sidecars/fast/provisional.py tests/test_provisional.py
git commit -m "feat: implement provisional chunk abandonment — stale chunks demoted to abandoned, never deleted"
```

- [ ] **Step 7: Register RIP Engine and Anamnesis on app startup**

In `backend/main.py`, inside the `lifespan` context manager:

```python
from backend.rip.engine import RIPEngine
from backend.sidecars.fast.anamnesis import inject as anamnesis_inject

# After pool creation:
app.state.rip_engine = RIPEngine(pool=pool)
```

- [ ] **Step 8: Add Anamnesis handler to hook_handlers seed**

Append to `backend/db/seed_hook_handlers.sql`:

```sql
-- pre_tool_use: Anamnesis injection (priority 10)
INSERT INTO hook_handlers (id, hook_name, handler_type, handler_ref, priority, enabled, config)
VALUES (
    gen_random_uuid(),
    'pre_tool_use',
    'python_module',
    'backend.sidecars.fast.anamnesis.inject',
    10,
    true,
    '{"timeout_ms": 450}'
);
```

- [ ] **Step 9: Final commit**

```bash
git add backend/main.py backend/db/seed_hook_handlers.sql
git commit -m "feat: wire RIP Engine and Anamnesis into app startup and hook_handlers seed"
```

---

> **Plan-document reviewer dispatch note (Chunk 3):** After completing Chunk 3, verify: (1) `pytest tests/ -v` — all Phase 4 tests pass with zero failures, (2) manually trigger the full pipeline via `POST /hooks/user_prompt_submit` and confirm rows appear in `chunks`, `sss_snapshots`, and `injection_log`, (3) run `grep -rn "DELETE FROM chunks" backend/` — must return nothing (Engram never prunes invariant), (4) confirm provisional chunk demotion: seed a chunk with `provisional=true, validated=false, turn_number=1`, call `abandon_stale_provisional_chunks(session_id=..., current_turn=10)`, and verify `SELECT status FROM chunks WHERE id = ...` returns `abandoned` (not a missing row). If all pass, Phase 4 is complete.
