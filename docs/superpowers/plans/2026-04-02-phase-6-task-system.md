# Ordo Phase 6: Task System + Token Budget Router Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete task management system — Task CRUD, Agent Message Bus, and Token Budget Router — so that a task can be created, assigned to the generalist agent via the message bus, picked up within 10 seconds, executed, marked complete, and its token usage logged to the database.

**Architecture:** Three new router modules (`tasks.py`, `agent_messages.py`) and two new service modules (`task_router.py`, `db/token_windows.py`) sit inside the existing FastAPI application. The generalist agent runs a 10-second polling background task against the `agent_messages` table. No Redis — all coordination is PostgreSQL-backed. A shutdown recovery pass re-queues any `in_flight` task executions on startup.

**Tech Stack:** Python 3.12, FastAPI 0.111+, asyncpg 0.29+, pydantic 2.7+, PostgreSQL 16, pytest + pytest-asyncio, httpx. Ollama (optional, local-model routing mode only).

---

## Chunk 1: Task CRUD + Agent Message Bus

### Task 1: Task CRUD Router

**Files:**
- Create: `backend/routers/tasks.py`
- Modify: `backend/main.py`
- Create: `tests/test_tasks.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tasks.py`:
```python
import pytest
import pytest_asyncio
import httpx
from uuid import uuid4
from tests.conftest import async_client


@pytest.mark.asyncio
async def test_create_task(async_client):
    payload = {
        "title": "Test task",
        "description": "Do something",
        "priority": 2,
        "estimated_tokens": 1000,
    }
    resp = await async_client.post("/tasks", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test task"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_tasks(async_client):
    resp = await async_client.get("/tasks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status(async_client):
    resp = await async_client.get("/tasks?status=pending")
    assert resp.status_code == 200
    for task in resp.json():
        assert task["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task(async_client):
    create_resp = await async_client.post("/tasks", json={"title": "Fetch me", "priority": 1})
    task_id = create_resp.json()["id"]
    resp = await async_client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_get_task_not_found(async_client):
    resp = await async_client.get(f"/tasks/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_task_status(async_client):
    create_resp = await async_client.post("/tasks", json={"title": "Patch me", "priority": 1})
    task_id = create_resp.json()["id"]
    resp = await async_client.patch(f"/tasks/{task_id}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_delete_task_soft(async_client):
    create_resp = await async_client.post("/tasks", json={"title": "Delete me", "priority": 1})
    task_id = create_resp.json()["id"]
    resp = await async_client.delete(f"/tasks/{task_id}")
    assert resp.status_code == 200
    # Soft delete: task still fetchable but archived_at is set
    get_resp = await async_client.get(f"/tasks/{task_id}")
    assert get_resp.json()["archived_at"] is not None


@pytest.mark.asyncio
async def test_add_and_list_attachments(async_client):
    create_resp = await async_client.post("/tasks", json={"title": "Attach me", "priority": 1})
    task_id = create_resp.json()["id"]
    attach_resp = await async_client.post(
        f"/tasks/{task_id}/attachments",
        json={"filename": "note.txt", "content_type": "text/plain", "size_bytes": 42, "storage_path": "/tmp/note.txt"},
    )
    assert attach_resp.status_code == 201
    list_resp = await async_client.get(f"/tasks/{task_id}/attachments")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["filename"] == "note.txt"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_tasks.py -v
```

Expected: `ImportError` or `404 Not Found` — router not yet registered.

- [ ] **Step 3: Create `backend/routers/tasks.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db.pool import get_conn

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── Schemas ────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 1
    due_at: Optional[datetime] = None
    estimated_tokens: Optional[int] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None


class TaskPatch(BaseModel):
    status: Optional[str] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    actual_tokens_used: Optional[int] = None
    completed_at: Optional[datetime] = None


class AttachmentCreate(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    storage_path: str


# ── Helpers ────────────────────────────────────────────────────────────────

VALID_STATUSES = {"pending", "in_progress", "completed", "failed", "cancelled"}


def _row_to_dict(row) -> dict:
    return dict(row)


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_tasks(
    status: Optional[str] = Query(None),
    owner_type: Optional[str] = Query(None),
    assigned_agent_id: Optional[uuid.UUID] = Query(None),
    conn=Depends(get_conn),
):
    """List tasks with optional filters. Excludes archived tasks unless status filter is explicit."""
    conditions = ["archived_at IS NULL"]
    params: list = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if owner_type:
        conditions.append(f"owner_type = ${idx}")
        params.append(owner_type)
        idx += 1
    if assigned_agent_id:
        conditions.append(f"assigned_agent_id = ${idx}")
        params.append(assigned_agent_id)
        idx += 1

    where = " AND ".join(conditions)
    rows = await conn.fetch(
        f"SELECT * FROM tasks WHERE {where} ORDER BY priority DESC, created_at ASC",
        *params,
    )
    return [_row_to_dict(r) for r in rows]


@router.post("", status_code=201)
async def create_task(body: TaskCreate, conn=Depends(get_conn)):
    row = await conn.fetchrow(
        """
        INSERT INTO tasks (title, description, priority, due_at, estimated_tokens,
                           assigned_agent_id, conversation_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        body.title,
        body.description,
        body.priority,
        body.due_at,
        body.estimated_tokens,
        body.assigned_agent_id,
        body.conversation_id,
    )
    return _row_to_dict(row)


@router.get("/{task_id}")
async def get_task(task_id: uuid.UUID, conn=Depends(get_conn)):
    row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _row_to_dict(row)


@router.patch("/{task_id}")
async def patch_task(task_id: uuid.UUID, body: TaskPatch, conn=Depends(get_conn)):
    existing = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.status and body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status '{body.status}'")

    updates: list[str] = []
    params: list = []
    idx = 1

    if body.status is not None:
        updates.append(f"status = ${idx}"); params.append(body.status); idx += 1
    if body.assigned_agent_id is not None:
        updates.append(f"assigned_agent_id = ${idx}"); params.append(body.assigned_agent_id); idx += 1
    if body.actual_tokens_used is not None:
        updates.append(f"actual_tokens_used = ${idx}"); params.append(body.actual_tokens_used); idx += 1
    if body.completed_at is not None:
        updates.append(f"completed_at = ${idx}"); params.append(body.completed_at); idx += 1

    if not updates:
        return _row_to_dict(existing)

    params.append(task_id)
    row = await conn.fetchrow(
        f"UPDATE tasks SET {', '.join(updates)} WHERE id = ${idx} RETURNING *",
        *params,
    )
    return _row_to_dict(row)


@router.delete("/{task_id}")
async def delete_task(task_id: uuid.UUID, conn=Depends(get_conn)):
    existing = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")
    row = await conn.fetchrow(
        "UPDATE tasks SET archived_at = NOW() WHERE id = $1 RETURNING *",
        task_id,
    )
    return _row_to_dict(row)


@router.post("/{task_id}/attachments", status_code=201)
async def add_attachment(task_id: uuid.UUID, body: AttachmentCreate, conn=Depends(get_conn)):
    existing = await conn.fetchrow("SELECT id FROM tasks WHERE id = $1", task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")
    row = await conn.fetchrow(
        """
        INSERT INTO task_attachments (task_id, filename, content_type, size_bytes, storage_path)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        task_id,
        body.filename,
        body.content_type,
        body.size_bytes,
        body.storage_path,
    )
    return _row_to_dict(row)


@router.get("/{task_id}/attachments")
async def list_attachments(task_id: uuid.UUID, conn=Depends(get_conn)):
    existing = await conn.fetchrow("SELECT id FROM tasks WHERE id = $1", task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")
    rows = await conn.fetch(
        "SELECT * FROM task_attachments WHERE task_id = $1 ORDER BY created_at ASC",
        task_id,
    )
    return [_row_to_dict(r) for r in rows]
```

- [ ] **Step 4: Register router in `backend/main.py`**

In `backend/main.py`, add to the router registration block (after existing router imports):
```python
from backend.routers.tasks import router as tasks_router
# ...
app.include_router(tasks_router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_tasks.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/tasks.py backend/main.py tests/test_tasks.py
git commit -m "feat: add Task CRUD router with soft delete and attachments"
```

---

### Task 2: Agent Message Bus Router

**Files:**
- Create: `backend/routers/agent_messages.py`
- Modify: `backend/main.py`
- Create: `tests/test_agent_messages.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_agent_messages.py`:
```python
import pytest
from uuid import uuid4
from tests.conftest import async_client


@pytest.mark.asyncio
async def test_create_message(async_client):
    payload = {
        "from_agent_id": "generalist",
        "to_agent_id": "generalist",
        "message_type": "task_assignment",
        "payload": {"task_id": str(uuid4())},
    }
    resp = await async_client.post("/agent_messages", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["message_type"] == "task_assignment"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_broadcast_message(async_client):
    """to_agent_id is nullable — omitting it creates a broadcast."""
    payload = {
        "from_agent_id": "system",
        "message_type": "broadcast",
        "payload": {"text": "hello"},
    }
    resp = await async_client.post("/agent_messages", json=payload)
    assert resp.status_code == 201
    assert resp.json()["to_agent_id"] is None


@pytest.mark.asyncio
async def test_poll_pending_messages(async_client):
    agent_id = "test_agent_poll"
    # Create a message addressed to our agent
    create_resp = await async_client.post("/agent_messages", json={
        "from_agent_id": "system",
        "to_agent_id": agent_id,
        "message_type": "status_update",
        "payload": {"note": "ping"},
    })
    assert create_resp.status_code == 201

    poll_resp = await async_client.get(f"/agent_messages/pending/{agent_id}")
    assert poll_resp.status_code == 200
    ids = [m["id"] for m in poll_resp.json()]
    assert create_resp.json()["id"] in ids


@pytest.mark.asyncio
async def test_ack_message(async_client):
    create_resp = await async_client.post("/agent_messages", json={
        "from_agent_id": "system",
        "to_agent_id": "acker",
        "message_type": "result",
        "payload": {},
    })
    msg_id = create_resp.json()["id"]

    ack_resp = await async_client.post(f"/agent_messages/{msg_id}/ack")
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ack"
    assert ack_resp.json()["ack_at"] is not None


@pytest.mark.asyncio
async def test_fail_message(async_client):
    create_resp = await async_client.post("/agent_messages", json={
        "from_agent_id": "system",
        "to_agent_id": "failer",
        "message_type": "task_assignment",
        "payload": {},
    })
    msg_id = create_resp.json()["id"]
    initial_retries = create_resp.json()["retry_count"]

    fail_resp = await async_client.post(f"/agent_messages/{msg_id}/fail")
    assert fail_resp.status_code == 200
    assert fail_resp.json()["status"] == "failed"
    assert fail_resp.json()["retry_count"] == initial_retries + 1


@pytest.mark.asyncio
async def test_acked_message_not_in_poll(async_client):
    agent_id = "test_agent_acked"
    create_resp = await async_client.post("/agent_messages", json={
        "from_agent_id": "system",
        "to_agent_id": agent_id,
        "message_type": "result",
        "payload": {},
    })
    msg_id = create_resp.json()["id"]
    await async_client.post(f"/agent_messages/{msg_id}/ack")

    poll_resp = await async_client.get(f"/agent_messages/pending/{agent_id}")
    ids = [m["id"] for m in poll_resp.json()]
    assert msg_id not in ids
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_agent_messages.py -v
```

Expected: `404 Not Found` or `ImportError` — router not registered.

- [ ] **Step 3: Create `backend/routers/agent_messages.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.db.pool import get_conn

router = APIRouter(prefix="/agent_messages", tags=["agent_messages"])

VALID_MESSAGE_TYPES = {"task_assignment", "result", "status_update", "broadcast"}
DEFAULT_TTL_HOURS = 24


# ── Schemas ────────────────────────────────────────────────────────────────

class AgentMessageCreate(BaseModel):
    from_agent_id: str
    to_agent_id: Optional[str] = None
    conversation_id: Optional[uuid.UUID] = None
    message_type: str
    payload: dict = {}
    ttl_hours: int = DEFAULT_TTL_HOURS


# ── Helpers ────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    return dict(row)


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_message(body: AgentMessageCreate, conn=Depends(get_conn)):
    if body.message_type not in VALID_MESSAGE_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid message_type '{body.message_type}'")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=body.ttl_hours)
    row = await conn.fetchrow(
        """
        INSERT INTO agent_messages
            (from_agent_id, to_agent_id, conversation_id, message_type, payload, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        body.from_agent_id,
        body.to_agent_id,
        body.conversation_id,
        body.message_type,
        body.payload,
        expires_at,
    )
    return _row_to_dict(row)


@router.get("/pending/{agent_id}")
async def poll_pending(agent_id: str, conn=Depends(get_conn)):
    """Return unacknowledged messages for agent_id that have not expired.

    Returns messages where:
    - to_agent_id = agent_id (direct) OR to_agent_id IS NULL (broadcast)
    - status IN ('pending', 'delivered')
    - expires_at > now()
    """
    now = datetime.now(timezone.utc)
    rows = await conn.fetch(
        """
        SELECT * FROM agent_messages
        WHERE (to_agent_id = $1 OR to_agent_id IS NULL)
          AND status IN ('pending', 'delivered')
          AND expires_at > $2
        ORDER BY created_at ASC
        """,
        agent_id,
        now,
    )
    # Mark as delivered
    ids = [r["id"] for r in rows if r["status"] == "pending"]
    if ids:
        await conn.execute(
            "UPDATE agent_messages SET status = 'delivered' WHERE id = ANY($1::uuid[])",
            ids,
        )
    return [_row_to_dict(r) for r in rows]


@router.post("/{message_id}/ack")
async def ack_message(message_id: uuid.UUID, conn=Depends(get_conn)):
    row = await conn.fetchrow("SELECT * FROM agent_messages WHERE id = $1", message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Message not found")
    updated = await conn.fetchrow(
        """
        UPDATE agent_messages
        SET status = 'ack', ack_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        message_id,
    )
    return _row_to_dict(updated)


@router.post("/{message_id}/fail")
async def fail_message(message_id: uuid.UUID, conn=Depends(get_conn)):
    row = await conn.fetchrow("SELECT * FROM agent_messages WHERE id = $1", message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Message not found")
    updated = await conn.fetchrow(
        """
        UPDATE agent_messages
        SET status = 'failed', retry_count = retry_count + 1
        WHERE id = $1
        RETURNING *
        """,
        message_id,
    )
    return _row_to_dict(updated)
```

- [ ] **Step 4: Register router in `backend/main.py`**

Add to the router registration block:
```python
from backend.routers.agent_messages import router as agent_messages_router
# ...
app.include_router(agent_messages_router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_agent_messages.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/agent_messages.py backend/main.py tests/test_agent_messages.py
git commit -m "feat: add Agent Message Bus router with poll, ack, and fail endpoints"
```

---

### Task 3: Generalist Agent Poll Loop

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/generalist_poll.py`
- Modify: `backend/main.py`
- Create: `tests/test_generalist_poll.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_generalist_poll.py`:
```python
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from backend.agents.generalist_poll import process_task_assignment


@pytest.mark.asyncio
async def test_process_task_assignment_marks_in_progress_then_completed(mocker):
    """process_task_assignment should update task to in_progress, invoke harness, then completed."""
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"id": "task-uuid", "title": "Do thing", "estimated_tokens": 500})
    fake_conn.execute = AsyncMock()

    mock_invoke = mocker.patch(
        "backend.agents.generalist_poll.invoke_agent_harness",
        new=AsyncMock(return_value={"tokens_used": 420}),
    )

    from uuid import uuid4
    task_id = str(uuid4())
    msg = {"id": str(uuid4()), "payload": {"task_id": task_id}}

    await process_task_assignment(msg, fake_conn)

    # Should have patched task status to in_progress first
    first_call_sql = fake_conn.execute.call_args_list[0][0][0]
    assert "in_progress" in first_call_sql

    # Should have invoked the harness
    mock_invoke.assert_awaited_once()

    # Should have patched task to completed
    last_call_sql = fake_conn.execute.call_args_list[-1][0][0]
    assert "completed" in last_call_sql
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_generalist_poll.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.agents.generalist_poll'`

- [ ] **Step 3: Create `backend/agents/__init__.py`**

```bash
touch "C:/Users/user/AI-Assistant Version 4/backend/agents/__init__.py"
```

- [ ] **Step 4: Create `backend/agents/generalist_poll.py`**

```python
"""
Generalist agent poll loop.

Runs as an asyncio background task inside FastAPI. Polls agent_messages
every POLL_INTERVAL_S seconds for messages addressed to 'generalist'.
On task_assignment messages: marks task in_progress, invokes the agent
harness, marks completed, records token usage.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.db.pool import get_pool
from backend.db.token_windows import record_token_usage

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 10
AGENT_ID = "generalist"


async def invoke_agent_harness(task: dict) -> dict:
    """
    Placeholder for LangGraph agent harness invocation (Phase 2+).
    Returns a dict with at minimum {'tokens_used': int}.
    Replace this stub with the real harness call when Phase 2 lands.
    """
    logger.info("agent_harness invoked for task %s (stub)", task.get("id"))
    await asyncio.sleep(0)  # yield to event loop
    return {"tokens_used": task.get("estimated_tokens") or 0}


async def process_task_assignment(msg: dict, conn: asyncpg.Connection) -> None:
    """Handle a single task_assignment message end-to-end."""
    payload = msg.get("payload", {})
    task_id = payload.get("task_id")
    if not task_id:
        logger.warning("task_assignment message %s missing task_id in payload", msg.get("id"))
        return

    task = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1::uuid", task_id)
    if task is None:
        logger.warning("task_assignment references unknown task %s", task_id)
        return

    # Mark in_progress
    await conn.execute(
        "UPDATE tasks SET status = 'in_progress' WHERE id = $1::uuid",
        task_id,
    )
    logger.info("task %s set to in_progress", task_id)

    try:
        result = await invoke_agent_harness(dict(task))
        tokens_used = result.get("tokens_used", 0)

        # Record token usage
        await record_token_usage(
            conn=conn,
            model_id=None,   # resolved inside record_token_usage if None
            tokens=tokens_used,
            conversation_id=task["conversation_id"] if "conversation_id" in task.keys() else None,
            task_id=task_id,
        )

        # Mark completed
        await conn.execute(
            """
            UPDATE tasks
            SET status = 'completed',
                completed_at = $1,
                actual_tokens_used = $2
            WHERE id = $3::uuid
            """,
            datetime.now(timezone.utc),
            tokens_used,
            task_id,
        )
        logger.info("task %s completed, tokens_used=%d", task_id, tokens_used)

    except Exception as exc:
        logger.error("task %s failed during harness invocation: %s", task_id, exc)
        await conn.execute(
            "UPDATE tasks SET status = 'failed' WHERE id = $1::uuid",
            task_id,
        )


async def _poll_once(pool: asyncpg.Pool) -> None:
    """Single poll iteration — fetch pending messages and process task_assignments."""
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        rows = await conn.fetch(
            """
            SELECT * FROM agent_messages
            WHERE (to_agent_id = $1 OR to_agent_id IS NULL)
              AND status IN ('pending', 'delivered')
              AND expires_at > $2
            ORDER BY created_at ASC
            """,
            AGENT_ID,
            now,
        )
        for row in rows:
            msg = dict(row)
            # Mark delivered immediately so duplicate polls don't re-process
            await conn.execute(
                "UPDATE agent_messages SET status = 'delivered' WHERE id = $1",
                msg["id"],
            )
            if msg["message_type"] == "task_assignment":
                await process_task_assignment(msg, conn)
                # Ack after successful processing
                await conn.execute(
                    "UPDATE agent_messages SET status = 'ack', ack_at = NOW() WHERE id = $1",
                    msg["id"],
                )
            else:
                logger.debug("generalist received message type=%s — no handler", msg["message_type"])


async def run_poll_loop() -> None:
    """Background asyncio task. Runs indefinitely until cancelled."""
    logger.info("generalist poll loop started (interval=%ds)", POLL_INTERVAL_S)
    pool = await get_pool()
    while True:
        try:
            await _poll_once(pool)
        except asyncio.CancelledError:
            logger.info("generalist poll loop cancelled")
            raise
        except Exception as exc:
            logger.error("poll loop error (will retry): %s", exc)
        await asyncio.sleep(POLL_INTERVAL_S)
```

- [ ] **Step 5: Start the poll loop in `backend/main.py` lifespan**

In `backend/main.py`, inside the `lifespan` async context manager, after the recovery bootstrap:
```python
import asyncio
from backend.agents.generalist_poll import run_poll_loop

# Inside lifespan, after recovery bootstrap:
poll_task = asyncio.create_task(run_poll_loop())
yield
poll_task.cancel()
try:
    await poll_task
except asyncio.CancelledError:
    pass
```

- [ ] **Step 6: Run test — verify it passes**

```bash
pytest tests/test_generalist_poll.py -v
```

Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/agents/__init__.py backend/agents/generalist_poll.py backend/main.py tests/test_generalist_poll.py
git commit -m "feat: add generalist agent 10-second poll loop for task_assignment messages"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 1, invoke `superpowers:plan-document-reviewer` passing this file path and chunk number so progress is logged before proceeding to Chunk 2.

---

## Chunk 2: Token Budget Router + Window Reset

### Task 4: Token Window Reset Module

**Files:**
- Create: `backend/db/token_windows.py`
- Modify: `backend/main.py`
- Create: `tests/test_token_windows.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_windows.py`:
```python
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock
from backend.db.token_windows import check_and_reset_windows, record_token_usage


@pytest.mark.asyncio
async def test_check_and_reset_windows_resets_expired():
    """Models with window_reset_at in the past should have tokens_used reset to 0."""
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    fake_model = {
        "id": "model-uuid-1",
        "window_duration_hours": 5,
        "window_reset_at": past,
    }
    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[fake_model])
    fake_conn.execute = AsyncMock()

    await check_and_reset_windows(fake_conn)

    # Should have called execute to reset tokens and set new window_reset_at
    assert fake_conn.execute.called
    call_sql = fake_conn.execute.call_args_list[0][0][0]
    assert "tokens_used_this_window" in call_sql
    assert "window_reset_at" in call_sql


@pytest.mark.asyncio
async def test_check_and_reset_windows_skips_unexpired():
    """Models whose reset is still in the future are not touched."""
    future = datetime.now(timezone.utc) + timedelta(hours=3)
    fake_model = {
        "id": "model-uuid-2",
        "window_duration_hours": 5,
        "window_reset_at": future,
    }
    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[fake_model])
    fake_conn.execute = AsyncMock()

    await check_and_reset_windows(fake_conn)

    fake_conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_record_token_usage_inserts_log_row():
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()

    await record_token_usage(
        conn=fake_conn,
        model_id="model-uuid-1",
        tokens=500,
        conversation_id=None,
        task_id="task-uuid-1",
    )

    assert fake_conn.execute.call_count >= 1
    first_sql = fake_conn.execute.call_args_list[0][0][0]
    assert "token_usage_log" in first_sql


@pytest.mark.asyncio
async def test_record_token_usage_increments_window():
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()

    await record_token_usage(
        conn=fake_conn,
        model_id="model-uuid-1",
        tokens=300,
        conversation_id=None,
        task_id=None,
    )

    sqls = [c[0][0] for c in fake_conn.execute.call_args_list]
    assert any("tokens_used_this_window" in s for s in sqls)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_token_windows.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.db.token_windows'`

- [ ] **Step 3: Create `backend/db/token_windows.py`**

```python
"""
Token window reset logic and token usage recording.

check_and_reset_windows() — called at FastAPI startup. Resets
tokens_used_this_window to 0 for any model whose window_reset_at has passed,
then sets a new window_reset_at = now + window_duration_hours.

record_token_usage() — inserts a token_usage_log row and increments
models.tokens_used_this_window for the relevant model.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


async def check_and_reset_windows(conn: asyncpg.Connection) -> None:
    """Reset token windows for all models past their reset time."""
    rows = await conn.fetch(
        "SELECT id, window_duration_hours, window_reset_at FROM models"
    )
    now = datetime.now(timezone.utc)

    for row in rows:
        reset_at = row["window_reset_at"]
        if reset_at is None or reset_at <= now:
            duration_hours = row["window_duration_hours"] or 5
            new_reset_at = now + timedelta(hours=duration_hours)
            await conn.execute(
                """
                UPDATE models
                SET tokens_used_this_window = 0,
                    window_reset_at = $1
                WHERE id = $2
                """,
                new_reset_at,
                row["id"],
            )
            logger.info(
                "token window reset for model %s — next reset at %s",
                row["id"],
                new_reset_at.isoformat(),
            )


async def record_token_usage(
    conn: asyncpg.Connection,
    model_id: Optional[str],
    tokens: int,
    conversation_id: Optional[str],
    task_id: Optional[str],
) -> None:
    """Insert a token_usage_log row and increment the model's window counter."""
    if tokens <= 0:
        return

    # Insert log row
    await conn.execute(
        """
        INSERT INTO token_usage_log
            (model_id, tokens_used, conversation_id, task_id, recorded_at)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        model_id,
        tokens,
        conversation_id,
        task_id,
    )

    # Increment window counter (skip if no model_id — e.g. stub calls)
    if model_id is not None:
        await conn.execute(
            """
            UPDATE models
            SET tokens_used_this_window = tokens_used_this_window + $1
            WHERE id = $2
            """,
            tokens,
            model_id,
        )
        logger.debug("recorded %d tokens for model %s", tokens, model_id)
```

- [ ] **Step 4: Call `check_and_reset_windows` in `backend/main.py` lifespan**

In `backend/main.py`, inside the `lifespan` startup block, after existing recovery bootstrap and before `yield`:
```python
from backend.db.token_windows import check_and_reset_windows

async with pool.acquire() as conn:
    await check_and_reset_windows(conn)
    logger.info("token window reset check complete")
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_token_windows.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/db/token_windows.py backend/main.py tests/test_token_windows.py
git commit -m "feat: add token window reset module and token usage recording"
```

---

### Task 5: Token Budget Router

**Files:**
- Create: `backend/task_router.py`
- Create: `tests/test_task_router.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_task_router.py`:
```python
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock
from backend.task_router import get_available_budget, route_tasks, _priority_score


def make_task(priority: int, days_until_due: float, estimated_tokens: int, task_id: str = "t1"):
    due_at = datetime.now(timezone.utc) + timedelta(days=days_until_due) if days_until_due > 0 else None
    return {
        "id": task_id,
        "priority": priority,
        "due_at": due_at,
        "estimated_tokens": estimated_tokens,
        "status": "pending",
    }


def test_priority_score_higher_priority_wins():
    high = make_task(priority=5, days_until_due=10, estimated_tokens=100, task_id="h")
    low = make_task(priority=1, days_until_due=10, estimated_tokens=100, task_id="l")
    assert _priority_score(high) > _priority_score(low)


def test_priority_score_urgent_deadline_wins_over_distant():
    urgent = make_task(priority=2, days_until_due=0.1, estimated_tokens=100, task_id="u")
    distant = make_task(priority=2, days_until_due=30, estimated_tokens=100, task_id="d")
    assert _priority_score(urgent) > _priority_score(distant)


def test_route_tasks_greedy_bin_pack():
    tasks = [
        make_task(priority=3, days_until_due=1, estimated_tokens=3000, task_id="a"),
        make_task(priority=2, days_until_due=2, estimated_tokens=2000, task_id="b"),
        make_task(priority=1, days_until_due=5, estimated_tokens=6000, task_id="c"),
    ]
    # Budget of 5000 — should fit 'a' (3000) + 'b' (2000) but not 'c' (6000)
    assigned = route_tasks(tasks, budget=5000)
    ids = [t["id"] for t in assigned]
    assert "a" in ids
    assert "b" in ids
    assert "c" not in ids


def test_route_tasks_skips_task_exceeding_budget():
    tasks = [make_task(priority=5, days_until_due=1, estimated_tokens=10000, task_id="big")]
    assigned = route_tasks(tasks, budget=5000)
    assert assigned == []


def test_route_tasks_no_estimated_tokens_defaults_to_zero_cost():
    task = {
        "id": "free",
        "priority": 1,
        "due_at": None,
        "estimated_tokens": None,
        "status": "pending",
    }
    assigned = route_tasks([task], budget=100)
    assert len(assigned) == 1


@pytest.mark.asyncio
async def test_get_available_budget_resets_expired_window():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    fake_model = {
        "id": "m1",
        "token_budget_per_window": 10000,
        "tokens_used_this_window": 4000,
        "window_reset_at": past,
        "window_duration_hours": 5,
    }
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value=fake_model)
    fake_conn.execute = AsyncMock()

    budget = await get_available_budget(fake_conn, model_id="m1")
    # After reset, tokens_used_this_window = 0, so budget = 10000
    assert budget == 10000
    fake_conn.execute.assert_called()


@pytest.mark.asyncio
async def test_get_available_budget_within_window():
    future = datetime.now(timezone.utc) + timedelta(hours=3)
    fake_model = {
        "id": "m1",
        "token_budget_per_window": 10000,
        "tokens_used_this_window": 3000,
        "window_reset_at": future,
        "window_duration_hours": 5,
    }
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value=fake_model)
    fake_conn.execute = AsyncMock()

    budget = await get_available_budget(fake_conn, model_id="m1")
    assert budget == 7000
    fake_conn.execute.assert_not_called()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_task_router.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.task_router'`

- [ ] **Step 3: Create `backend/task_router.py`**

```python
"""
Token Budget Router.

get_available_budget(conn, model_id) -> int
    Reads models.token_budget_per_window - models.tokens_used_this_window.
    If window_reset_at is in the past, resets the window first.

route_tasks(pending_tasks, budget) -> list[Task]
    Deterministic mode: sort by priority score + deadline proximity, then
    greedy bin-pack against the budget. Returns the assignable subset.

run_router(conn) -> list[Task]
    Orchestrates: get pending tasks, resolve budget, route, send
    task_assignment agent_messages for each assigned task.

Priority score formula:
    priority * 10 + (1 / max(days_until_due, 0.1)) * 5
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


# ── Priority Scoring ───────────────────────────────────────────────────────

def _priority_score(task: dict) -> float:
    """Higher score = schedule first."""
    base = task.get("priority", 1) * 10
    due_at = task.get("due_at")
    if due_at is not None:
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days = max((due_at - now).total_seconds() / 86400, 0.1)
        urgency = (1 / days) * 5
    else:
        urgency = 0.0
    return base + urgency


# ── Greedy Bin-Pack ────────────────────────────────────────────────────────

def route_tasks(pending_tasks: list[dict], budget: int) -> list[dict]:
    """Sort by priority score descending, greedily pack into budget."""
    sorted_tasks = sorted(pending_tasks, key=_priority_score, reverse=True)
    assigned: list[dict] = []
    remaining = budget

    for task in sorted_tasks:
        cost = task.get("estimated_tokens") or 0
        if cost <= remaining:
            assigned.append(task)
            remaining -= cost

    return assigned


# ── Budget Query ───────────────────────────────────────────────────────────

async def get_available_budget(conn: asyncpg.Connection, model_id: str) -> int:
    """Return available token budget for model_id, resetting window if expired."""
    row = await conn.fetchrow("SELECT * FROM models WHERE id = $1", model_id)
    if row is None:
        logger.warning("get_available_budget: model %s not found, returning 0", model_id)
        return 0

    now = datetime.now(timezone.utc)
    reset_at = row["window_reset_at"]
    tokens_used = row["tokens_used_this_window"] or 0

    if reset_at is None or reset_at <= now:
        # Window expired — reset
        duration_hours = row["window_duration_hours"] or 5
        new_reset_at = now + timedelta(hours=duration_hours)
        await conn.execute(
            """
            UPDATE models
            SET tokens_used_this_window = 0, window_reset_at = $1
            WHERE id = $2
            """,
            new_reset_at,
            model_id,
        )
        tokens_used = 0
        logger.info("budget window reset for model %s", model_id)

    budget = (row["token_budget_per_window"] or 0) - tokens_used
    return max(budget, 0)


# ── Default Model Resolution ───────────────────────────────────────────────

async def _get_default_model_id(conn: asyncpg.Connection) -> Optional[str]:
    """Return the id of the first active model, or None."""
    row = await conn.fetchrow(
        "SELECT id FROM models WHERE is_active = true ORDER BY created_at ASC LIMIT 1"
    )
    return str(row["id"]) if row else None


# ── Main Router Orchestration ──────────────────────────────────────────────

async def run_router(conn: asyncpg.Connection) -> list[dict]:
    """
    Main entry point called by heartbeat and the POST /router/run endpoint.

    1. Resolve default model + budget.
    2. Fetch all pending, unarchived tasks.
    3. Run route_tasks() for the assignable subset.
    4. For each assigned task: send a task_assignment agent_message.
    5. Return the list of assigned tasks.
    """
    model_id = await _get_default_model_id(conn)
    if model_id is None:
        logger.warning("run_router: no active models found — skipping routing")
        return []

    budget = await get_available_budget(conn, model_id)
    logger.info("run_router: model=%s available_budget=%d", model_id, budget)

    pending_rows = await conn.fetch(
        "SELECT * FROM tasks WHERE status = 'pending' AND archived_at IS NULL"
    )
    pending_tasks = [dict(r) for r in pending_rows]

    if not pending_tasks:
        logger.info("run_router: no pending tasks")
        return []

    assigned = route_tasks(pending_tasks, budget=budget)

    for task in assigned:
        task_id = str(task["id"])
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        await conn.execute(
            """
            INSERT INTO agent_messages
                (from_agent_id, to_agent_id, message_type, payload, expires_at)
            VALUES ('router', 'generalist', 'task_assignment', $1, $2)
            """,
            {"task_id": task_id},
            expires_at,
        )
        logger.info("run_router: queued task_assignment for task %s", task_id)

    logger.info("run_router: assigned %d / %d tasks", len(assigned), len(pending_tasks))
    return assigned
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_task_router.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/task_router.py tests/test_task_router.py
git commit -m "feat: add deterministic Token Budget Router with greedy bin-pack scheduling"
```

---

### Task 6: Local Model Routing Mode (Optional Extension)

**Files:**
- Modify: `backend/task_router.py`
- Create: `tests/test_task_router_local_model.py`

> **Note:** This task implements the `local_model` routing mode. It is only active when the `settings` table has `task_router.mode = 'local_model'` AND Ollama is running. The deterministic mode remains the default and is always available as fallback.

- [ ] **Step 1: Write failing test**

Create `tests/test_task_router_local_model.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.task_router import route_tasks_local_model


@pytest.mark.asyncio
async def test_local_model_returns_ordered_task_list(mocker):
    """route_tasks_local_model should POST to Ollama and parse response."""
    tasks = [
        {"id": "t1", "title": "Task A", "priority": 1, "estimated_tokens": 100, "due_at": None},
        {"id": "t2", "title": "Task B", "priority": 3, "estimated_tokens": 200, "due_at": None},
    ]
    mock_post = mocker.patch(
        "backend.task_router.httpx.AsyncClient.post",
        new=AsyncMock(return_value=mocker.Mock(
            status_code=200,
            json=lambda: {
                "response": '{"ordered_task_ids": ["t2", "t1"]}'
            },
        )),
    )
    result = await route_tasks_local_model(tasks, budget=5000, ollama_url="http://localhost:11434")
    assert [t["id"] for t in result] == ["t2", "t1"]
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_task_router_local_model.py -v
```

Expected: `ImportError` — `route_tasks_local_model` does not exist yet.

- [ ] **Step 3: Add `route_tasks_local_model` to `backend/task_router.py`**

Append to `backend/task_router.py`:
```python
import httpx
import json as _json


async def route_tasks_local_model(
    pending_tasks: list[dict],
    budget: int,
    ollama_url: str = "http://localhost:11434",
    model: str = "mistral",
) -> list[dict]:
    """
    Send task list + budget state to a local Ollama model for prioritized order.
    Falls back to deterministic route_tasks() if Ollama is unavailable or
    the response cannot be parsed.

    The Ollama prompt requests a JSON response:
        {"ordered_task_ids": ["<id>", ...]}
    listing only tasks that fit within the budget.
    """
    task_summary = [
        {
            "id": str(t["id"]),
            "title": t.get("title", ""),
            "priority": t.get("priority", 1),
            "estimated_tokens": t.get("estimated_tokens") or 0,
            "due_at": t["due_at"].isoformat() if t.get("due_at") else None,
        }
        for t in pending_tasks
    ]
    prompt = (
        f"You are a task scheduler. Available token budget: {budget}.\n"
        f"Tasks (JSON):\n{_json.dumps(task_summary, indent=2)}\n\n"
        "Return ONLY valid JSON: {\"ordered_task_ids\": [\"<id>\", ...]}\n"
        "Include only tasks whose estimated_tokens fit within the budget. "
        "Order by urgency and priority. Highest priority / soonest deadline first."
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            parsed = _json.loads(raw)
            ordered_ids = parsed.get("ordered_task_ids", [])
            id_to_task = {str(t["id"]): t for t in pending_tasks}
            return [id_to_task[oid] for oid in ordered_ids if oid in id_to_task]

    except Exception as exc:
        logger.warning(
            "local_model routing failed (%s) — falling back to deterministic", exc
        )
        return route_tasks(pending_tasks, budget=budget)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_task_router_local_model.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/task_router.py tests/test_task_router_local_model.py
git commit -m "feat: add optional local-model routing mode via Ollama with deterministic fallback"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 2, invoke `superpowers:plan-document-reviewer` passing this file path and chunk number so progress is logged before proceeding to Chunk 3.

---

## Chunk 3: Router Endpoint + Shutdown Recovery + Budget API

### Task 7: `POST /router/run` and `GET /budget` Endpoints

**Files:**
- Create: `backend/routers/router_budget.py`
- Modify: `backend/main.py`
- Create: `tests/test_router_budget.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_router_budget.py`:
```python
import pytest
from tests.conftest import async_client


@pytest.mark.asyncio
async def test_get_budget_returns_list(async_client):
    resp = await async_client.get("/budget")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # If any models exist, each entry should have expected fields
    for entry in data:
        assert "model_id" in entry
        assert "model_name" in entry
        assert "provider" in entry
        assert "budget_per_window" in entry
        assert "tokens_used" in entry
        assert "tokens_remaining" in entry
        assert "window_reset_at" in entry


@pytest.mark.asyncio
async def test_post_router_run_returns_list(async_client):
    """POST /router/run should return a dict with assigned_tasks list."""
    resp = await async_client.post("/router/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "assigned_tasks" in data
    assert isinstance(data["assigned_tasks"], list)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_router_budget.py -v
```

Expected: `404 Not Found` — endpoints not registered.

- [ ] **Step 3: Create `backend/routers/router_budget.py`**

```python
"""
Router + Budget endpoints.

GET  /budget       — per-model token budget state for the UI status bar
POST /router/run   — manual "Route Now" trigger
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from backend.db.pool import get_conn
from backend.task_router import run_router

router = APIRouter(tags=["router_budget"])
logger = logging.getLogger(__name__)


@router.get("/budget")
async def get_budget(conn=Depends(get_conn)):
    """Return per-model token budget state."""
    rows = await conn.fetch(
        """
        SELECT
            id              AS model_id,
            name            AS model_name,
            provider,
            token_budget_per_window AS budget_per_window,
            tokens_used_this_window AS tokens_used,
            (token_budget_per_window - tokens_used_this_window) AS tokens_remaining,
            window_reset_at
        FROM models
        ORDER BY provider, name
        """
    )
    result = []
    for row in rows:
        entry = dict(row)
        # Clamp tokens_remaining to 0 minimum
        entry["tokens_remaining"] = max(entry["tokens_remaining"] or 0, 0)
        result.append(entry)
    return result


@router.post("/router/run")
async def manual_route(conn=Depends(get_conn)):
    """Manually trigger the Task Router. Returns the list of newly assigned tasks."""
    assigned = await run_router(conn)
    return {
        "assigned_tasks": assigned,
        "count": len(assigned),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Register router in `backend/main.py`**

```python
from backend.routers.router_budget import router as router_budget_router
# ...
app.include_router(router_budget_router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_router_budget.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/router_budget.py backend/main.py tests/test_router_budget.py
git commit -m "feat: add GET /budget and POST /router/run endpoints"
```

---

### Task 8: Shutdown Recovery — Task Execution Re-queue

**Files:**
- Modify: `backend/startup/recovery.py`
- Create: `tests/test_recovery_tasks.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_recovery_tasks.py`:
```python
import pytest
from unittest.mock import AsyncMock
from backend.startup.recovery import recover_in_flight_task_executions


@pytest.mark.asyncio
async def test_recover_requeues_in_flight_task_executions():
    """In-flight task_execution operations should become new task_assignment messages."""
    in_flight_row = {
        "id": "ifo-uuid-1",
        "operation_type": "task_execution",
        "status": "in_flight",
        "payload": {"task_id": "task-uuid-1"},
        "retry_count": 0,
    }
    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[in_flight_row])
    fake_conn.execute = AsyncMock()

    await recover_in_flight_task_executions(fake_conn)

    calls = [c[0][0] for c in fake_conn.execute.call_args_list]
    # Should have inserted a new agent_messages row
    assert any("agent_messages" in s for s in calls)
    # Should have marked original row recovered
    assert any("recovered" in s for s in calls)


@pytest.mark.asyncio
async def test_recover_skips_non_task_execution_operations():
    """Operations that are not task_execution type should not be re-queued as agent_messages."""
    sidecar_row = {
        "id": "ifo-uuid-2",
        "operation_type": "sidecar_kairos",
        "status": "in_flight",
        "payload": {},
        "retry_count": 0,
    }
    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[sidecar_row])
    fake_conn.execute = AsyncMock()

    await recover_in_flight_task_executions(fake_conn)

    # No agent_messages insert for sidecar operations
    calls = [c[0][0] for c in fake_conn.execute.call_args_list]
    assert not any("agent_messages" in s for s in calls)


@pytest.mark.asyncio
async def test_recover_no_in_flight_operations():
    """No-op when there are no in-flight operations."""
    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[])
    fake_conn.execute = AsyncMock()

    await recover_in_flight_task_executions(fake_conn)

    fake_conn.execute.assert_not_called()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_recovery_tasks.py -v
```

Expected: `ImportError` or `AttributeError` — `recover_in_flight_task_executions` not yet defined.

- [ ] **Step 3: Add `recover_in_flight_task_executions` to `backend/startup/recovery.py`**

Open `backend/startup/recovery.py` and append the following function (preserve all existing code):
```python
import logging
from datetime import datetime, timezone, timedelta

import asyncpg

logger = logging.getLogger(__name__)


async def recover_in_flight_task_executions(conn: asyncpg.Connection) -> None:
    """
    Called at FastAPI startup after the existing recovery bootstrap.

    Queries in_flight_operations WHERE status = 'in_flight' AND
    operation_type = 'task_execution'. For each:
      1. Insert a new agent_messages row (task_assignment) with the task_id from payload.
      2. Mark the original in_flight_operations row as status='recovered'.

    Non-task_execution operations are handled by the pre-existing sidecar recovery path
    and are intentionally skipped here.
    """
    rows = await conn.fetch(
        """
        SELECT * FROM in_flight_operations
        WHERE status = 'in_flight'
          AND operation_type = 'task_execution'
        """
    )

    if not rows:
        return

    logger.info("recovery: found %d in-flight task_execution operations", len(rows))

    for row in rows:
        payload = row["payload"] or {}
        task_id = payload.get("task_id")
        ifo_id = row["id"]

        if task_id:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            await conn.execute(
                """
                INSERT INTO agent_messages
                    (from_agent_id, to_agent_id, message_type, payload, expires_at)
                VALUES ('recovery', 'generalist', 'task_assignment', $1, $2)
                """,
                {"task_id": str(task_id)},
                expires_at,
            )
            logger.info("recovery: re-queued task_assignment for task %s", task_id)

        await conn.execute(
            "UPDATE in_flight_operations SET status = 'recovered' WHERE id = $1",
            ifo_id,
        )
        logger.info("recovery: marked in_flight_operations %s as recovered", ifo_id)
```

- [ ] **Step 4: Call recovery function in `backend/main.py` lifespan**

In `backend/main.py`, inside the lifespan startup block, after the existing recovery bootstrap:
```python
from backend.startup.recovery import recover_in_flight_task_executions

async with pool.acquire() as conn:
    await recover_in_flight_task_executions(conn)
    logger.info("task execution recovery complete")
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_recovery_tasks.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/startup/recovery.py backend/main.py tests/test_recovery_tasks.py
git commit -m "feat: recover in-flight task executions on startup via agent_messages re-queue"
```

---

### Task 9: Full Integration Test — Task Lifecycle End-to-End

**Files:**
- Create: `tests/test_task_lifecycle_e2e.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_task_lifecycle_e2e.py`:
```python
"""
End-to-end task lifecycle test.

Requires a running PostgreSQL database (ordo_test). Uses a real asyncpg
connection and a real FastAPI test client. The generalist poll loop is NOT
started — we call process_task_assignment directly to avoid timing dependencies.

Flow:
  1. Create task via POST /tasks
  2. POST /router/run  (or manually insert agent_message for the task)
  3. Directly invoke process_task_assignment
  4. GET /tasks/{id}  -> status = 'completed', actual_tokens_used set
  5. GET /budget       -> returns valid list
"""
import pytest
from tests.conftest import async_client


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_task_lifecycle(async_client):
    # 1. Create a task
    create_resp = await async_client.post("/tasks", json={
        "title": "E2E lifecycle task",
        "priority": 3,
        "estimated_tokens": 250,
    })
    assert create_resp.status_code == 201
    task = create_resp.json()
    task_id = task["id"]

    # 2. Trigger the router manually
    route_resp = await async_client.post("/router/run")
    assert route_resp.status_code == 200

    # 3. Manually insert task_assignment message (ensures processing regardless of model seed state)
    msg_resp = await async_client.post("/agent_messages", json={
        "from_agent_id": "test_runner",
        "to_agent_id": "generalist",
        "message_type": "task_assignment",
        "payload": {"task_id": task_id},
    })
    assert msg_resp.status_code == 201
    msg_id = msg_resp.json()["id"]

    # 4. Directly invoke the poll handler (bypasses 10-second timing)
    from backend.agents.generalist_poll import process_task_assignment
    from backend.db.pool import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await process_task_assignment({"id": msg_id, "payload": {"task_id": task_id}}, conn)

    # 5. Verify task is completed
    get_resp = await async_client.get(f"/tasks/{task_id}")
    assert get_resp.status_code == 200
    final_task = get_resp.json()
    assert final_task["status"] == "completed"
    assert final_task["completed_at"] is not None

    # 6. Budget endpoint should return a list (may be empty if no models seeded)
    budget_resp = await async_client.get("/budget")
    assert budget_resp.status_code == 200
    assert isinstance(budget_resp.json(), list)
```

- [ ] **Step 2: Run the integration test**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_task_lifecycle_e2e.py -v -m integration
```

Expected: `1 passed`

If this fails due to missing pool/database, verify `ordo_test` database is created and schema is applied:
```bash
psql -U ordo -d ordo_test -f backend/db/schema.sql
```
Then re-run.

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected output (exact counts depend on seed state):
```
tests/test_config.py                    PASSED
tests/test_tasks.py                     8 passed
tests/test_agent_messages.py            6 passed
tests/test_generalist_poll.py           1 passed
tests/test_token_windows.py             4 passed
tests/test_task_router.py               7 passed
tests/test_task_router_local_model.py   1 passed
tests/test_router_budget.py             2 passed
tests/test_recovery_tasks.py            3 passed
tests/test_task_lifecycle_e2e.py        1 passed
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_task_lifecycle_e2e.py
git commit -m "test: add end-to-end task lifecycle integration test"
```

---

### Task 10: Heartbeat Integration

**Files:**
- Modify: `backend/services/heartbeat.py`

> **Note:** This task wires `run_router()` into the existing heartbeat scheduler so routing fires automatically on every heartbeat tick (>=5 min cadence defined in Phase 1). The heartbeat service must already exist from a prior phase.

- [ ] **Step 1: Add router call to `backend/services/heartbeat.py`**

In the heartbeat tick handler, add after existing tick logic:
```python
from backend.task_router import run_router
from backend.db.pool import get_pool

# Inside the tick coroutine, after existing heartbeat work:
pool = await get_pool()
async with pool.acquire() as conn:
    assigned = await run_router(conn)
    if assigned:
        logger.info("heartbeat router: assigned %d tasks", len(assigned))
```

- [ ] **Step 2: Verify heartbeat still imports cleanly**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
python -c "from backend.services.heartbeat import run_heartbeat; print('heartbeat import OK')"
```

Expected: `heartbeat import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/heartbeat.py
git commit -m "feat: wire Token Budget Router into heartbeat tick"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 3, invoke `superpowers:plan-document-reviewer` passing this file path and chunk number so the full Phase 6 implementation is logged as complete.

---

## Phase 6 Completion Checklist

After all chunks are done, verify the following manually:

- [ ] `GET /tasks` returns `[]` on a clean database
- [ ] `POST /tasks` -> `GET /tasks/{id}` round-trips correctly
- [ ] `PATCH /tasks/{id}` with `{"status": "in_progress"}` updates the row
- [ ] `DELETE /tasks/{id}` sets `archived_at`, task still fetchable
- [ ] `POST /agent_messages` -> `GET /agent_messages/pending/generalist` returns the message
- [ ] `POST /agent_messages/{id}/ack` sets `status=ack`
- [ ] `GET /budget` returns `[]` when no models, or a list with expected fields when models exist
- [ ] `POST /router/run` returns `{"assigned_tasks": [], "count": 0, "triggered_at": "..."}` on clean DB
- [ ] FastAPI startup log shows "token window reset check complete" and "task execution recovery complete"
- [ ] Full pytest suite passes with 0 failures

## Acceptance Criteria

Phase 6 is **done** when:

1. All 10 tasks are checked off.
2. `pytest tests/ -v` exits with 0 failures.
3. A task can be created via `POST /tasks`, a `task_assignment` agent_message is sent (via `POST /router/run` or manually), the generalist poll loop picks it up within 10 seconds, marks it `completed`, and `actual_tokens_used` is recorded in the `tasks` table.
4. `GET /budget` returns a valid JSON list without errors.
5. `POST /router/run` returns a valid JSON object with `assigned_tasks` and `count`.
6. Server startup logs show both token window reset and task execution recovery running cleanly.
