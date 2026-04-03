# Ordo Phase 8: Always-On Services Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three pillars of always-on operation — Quick Actions CRUD + Settings routes, the Heartbeat Scheduler PM2 process, and the Telegram Bridge PM2 process — then surface them in the frontend via a Quick Actions slide-in panel, a Settings modal, and proactive Electron popup windows. After this phase: heartbeat fires every 5 minutes, runs enabled quick actions on their cron schedules, logs all results to `heartbeat_log`; Telegram messages route to the generalist agent and responses are sent back; the Quick Actions panel in the UI is fully functional.

**Architecture:** Three new PM2 processes (`ordo-heartbeat`, `ordo-telegram`) sit beside the existing FastAPI process. The heartbeat is a self-contained asyncio loop that polls the DB, evaluates cron schedules via `croniter`, fires actions, and writes to `heartbeat_log`. The Telegram bridge uses `python-telegram-bot` v20+ async; it POSTs inbound messages to `POST /agents/generalist/invoke` and receives proactive send requests via `POST /telegram/send`. FastAPI gains new routers: `quick_actions.py` (CRUD + manual run), `settings.py` (key-value runtime settings), `notifications.py` (SSE stream). The frontend gains two new panels — `quick-actions.ts` (slide-in) and `settings.ts` (modal) — plus proactive popup logic in `electron/main.ts`.

**Tech Stack:** Python 3.12, FastAPI 0.111+, asyncpg 0.29+, `python-telegram-bot` 20+, `croniter` 1.4+, `APScheduler` 3.10+ (optional fallback), `httpx` 0.27+ (for heartbeat HTTP calls), PM2, Vite + TypeScript, Electron, pytest + pytest-asyncio + httpx

---

## Chunk 1: Quick Actions CRUD + Settings Routes

### Task 1: Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add new dependencies to `backend/requirements.txt`**

Append the following lines to `backend/requirements.txt`:

```
croniter==1.4.1
python-telegram-bot==20.8
httpx==0.27.0
```

- [ ] **Step 2: Install dependencies**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pip install croniter==1.4.1 "python-telegram-bot==20.8" httpx==0.27.0
```

Expected output: All three packages install with no errors.

```bash
python -c "import croniter, telegram, httpx; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(phase-8): add croniter, python-telegram-bot, httpx dependencies"
```

---

### Task 2: Quick Actions Router

**Files:**
- Create: `backend/routers/quick_actions.py`
- Create: `tests/test_quick_actions.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_quick_actions.py`:

```python
import pytest
import pytest_asyncio
import httpx
from backend.main import app


@pytest.fixture
def client():
    from httpx import AsyncClient
    return AsyncClient(app=app, base_url="http://test")


@pytest.mark.asyncio
async def test_list_quick_actions_empty(client):
    async with client as c:
        resp = await c.get("/quick_actions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_quick_action(client):
    payload = {
        "name": "Daily Summary",
        "description": "Summarise the day's tasks",
        "action_type": "agent_invoke",
        "config": {"agent_id": "generalist", "prompt": "Summarise today"},
        "schedule": "0 9 * * *",
        "enabled": True,
    }
    async with client as c:
        resp = await c.post("/quick_actions", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Daily Summary"
    assert "id" in body


@pytest.mark.asyncio
async def test_patch_quick_action(client):
    async with client as c:
        create = await c.post("/quick_actions", json={
            "name": "Test Action",
            "description": "",
            "action_type": "http_request",
            "config": {"method": "GET", "url": "http://localhost", "body": None},
            "schedule": "*/5 * * * *",
            "enabled": True,
        })
        action_id = create.json()["id"]
        resp = await c.patch(f"/quick_actions/{action_id}", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_quick_action(client):
    async with client as c:
        create = await c.post("/quick_actions", json={
            "name": "Delete Me",
            "description": "",
            "action_type": "http_request",
            "config": {"method": "GET", "url": "http://localhost", "body": None},
            "schedule": "0 0 * * *",
            "enabled": False,
        })
        action_id = create.json()["id"]
        resp = await c.delete(f"/quick_actions/{action_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_run_quick_action_not_found(client):
    async with client as c:
        resp = await c.post("/quick_actions/00000000-0000-0000-0000-000000000000/run")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_quick_actions.py -v
```

Expected: `ImportError` or `404` failures — router does not exist yet.

- [ ] **Step 3: Create `backend/routers/quick_actions.py`**

```python
"""
Quick Actions CRUD router.

Action types:
  agent_invoke   — config: {agent_id: str, prompt: str}
  task_route     — config: {}  (fires the task router)
  http_request   — config: {method: str, url: str, body: dict | None}
  python_function — config: {module: str, function: str, kwargs: dict}
"""
import importlib
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.db.pool import get_pool

router = APIRouter(prefix="/quick_actions", tags=["quick_actions"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class QuickActionCreate(BaseModel):
    name: str
    description: str = ""
    action_type: str  # agent_invoke | task_route | http_request | python_function
    config: dict[str, Any] = Field(default_factory=dict)
    schedule: str = "*/5 * * * *"   # standard 5-field cron expression
    enabled: bool = True


class QuickActionPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    action_type: str | None = None
    config: dict[str, Any] | None = None
    schedule: str | None = None
    enabled: bool | None = None


class QuickActionOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    action_type: str
    config: dict[str, Any]
    schedule: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Action executor (shared with heartbeat service)
# ---------------------------------------------------------------------------

GENERALIST_INVOKE_URL = "http://localhost:8000/agents/generalist/invoke"
ROUTER_RUN_URL = "http://localhost:8000/router/run"


async def execute_action(action: dict) -> dict:
    """Run a single quick action and return a result dict."""
    action_type = action["action_type"]
    config = action.get("config") or {}

    try:
        if action_type == "agent_invoke":
            agent_id = config.get("agent_id", "generalist")
            prompt = config.get("prompt", "")
            url = f"http://localhost:8000/agents/{agent_id}/invoke"
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, json={"content": prompt, "source": "quick_action"})
                resp.raise_for_status()
                return {"status": "ok", "response": resp.json()}

        elif action_type == "task_route":
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(ROUTER_RUN_URL, json={})
                resp.raise_for_status()
                return {"status": "ok", "response": resp.json()}

        elif action_type == "http_request":
            method = config.get("method", "GET").upper()
            url = config["url"]
            body = config.get("body")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(method, url, json=body)
                return {"status": "ok", "status_code": resp.status_code, "body": resp.text[:2000]}

        elif action_type == "python_function":
            module_path = config["module"]
            function_name = config["function"]
            kwargs = config.get("kwargs", {})
            mod = importlib.import_module(module_path)
            fn = getattr(mod, function_name)
            import asyncio
            if asyncio.iscoroutinefunction(fn):
                result = await fn(**kwargs)
            else:
                result = fn(**kwargs)
            return {"status": "ok", "result": str(result)}

        else:
            return {"status": "error", "error": f"Unknown action_type: {action_type}"}

    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[QuickActionOut])
async def list_quick_actions():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM quick_actions ORDER BY created_at ASC"
        )
    return [dict(r) for r in rows]


@router.post("", response_model=QuickActionOut, status_code=201)
async def create_quick_action(body: QuickActionCreate):
    import json
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    action_id = uuid.uuid4()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO quick_actions (id, name, description, action_type, config, schedule, enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $8)
            RETURNING *
            """,
            action_id,
            body.name,
            body.description,
            body.action_type,
            json.dumps(body.config),
            body.schedule,
            body.enabled,
            now,
        )
    return dict(row)


@router.patch("/{action_id}", response_model=QuickActionOut)
async def patch_quick_action(action_id: uuid.UUID, body: QuickActionPatch):
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM quick_actions WHERE id = $1", action_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Quick action not found")

        updates = body.model_dump(exclude_none=True)
        if not updates:
            return dict(existing)

        set_clauses = []
        values = []
        idx = 1
        for field, value in updates.items():
            if field == "config":
                set_clauses.append(f"{field} = ${idx}::jsonb")
                values.append(json.dumps(value))
            else:
                set_clauses.append(f"{field} = ${idx}")
                values.append(value)
            idx += 1

        set_clauses.append(f"updated_at = ${idx}")
        values.append(datetime.now(timezone.utc))
        idx += 1
        values.append(action_id)

        query = f"UPDATE quick_actions SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *"
        row = await conn.fetchrow(query, *values)
    return dict(row)


@router.delete("/{action_id}", status_code=204)
async def delete_quick_action(action_id: uuid.UUID):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM quick_actions WHERE id = $1", action_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Quick action not found")


@router.post("/{action_id}/run")
async def run_quick_action(action_id: uuid.UUID):
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM quick_actions WHERE id = $1", action_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Quick action not found")

    action = dict(row)
    result = await execute_action(action)

    # Log to heartbeat_log
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO heartbeat_log (id, action_id, run_at, status, result)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            uuid.uuid4(),
            action_id,
            datetime.now(timezone.utc),
            result.get("status", "error"),
            json.dumps(result),
        )

    return result
```

- [ ] **Step 4: Register router in `backend/main.py`**

Open `backend/main.py` and add:

```python
from backend.routers.quick_actions import router as quick_actions_router

app.include_router(quick_actions_router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_quick_actions.py -v
```

Expected:
```
tests/test_quick_actions.py::test_list_quick_actions_empty PASSED
tests/test_quick_actions.py::test_create_quick_action PASSED
tests/test_quick_actions.py::test_patch_quick_action PASSED
tests/test_quick_actions.py::test_delete_quick_action PASSED
tests/test_quick_actions.py::test_run_quick_action_not_found PASSED
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/quick_actions.py tests/test_quick_actions.py backend/main.py
git commit -m "feat(phase-8): add Quick Actions CRUD router with manual run endpoint"
```

---

### Task 3: Settings Router

**Files:**
- Create: `backend/routers/settings.py`
- Create: `tests/test_settings_router.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_settings_router.py`:

```python
import pytest
from httpx import AsyncClient
from backend.main import app


@pytest.fixture
def client():
    return AsyncClient(app=app, base_url="http://test")


@pytest.mark.asyncio
async def test_get_settings_returns_list(client):
    async with client as c:
        resp = await c.get("/settings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_patch_setting(client):
    async with client as c:
        resp = await c.patch(
            "/settings/heartbeat.interval_seconds",
            json={"value": "600"}
        )
    assert resp.status_code in (200, 404)  # 404 if key not seeded yet


@pytest.mark.asyncio
async def test_patch_setting_bad_key(client):
    async with client as c:
        resp = await c.patch(
            "/settings/nonexistent.key.that.does.not.exist",
            json={"value": "abc"}
        )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_settings_router.py -v
```

Expected: `ImportError` or route-not-found errors.

- [ ] **Step 3: Create `backend/routers/settings.py`**

```python
"""
Settings router — thin key/value CRUD over the `settings` table.

Exposed settings (Phase 8):
  heartbeat.interval_seconds   int     default: 300
  task_router.mode             string  default: deterministic
  tts.voice_output_enabled     bool    default: false
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.pool import get_pool

router = APIRouter(prefix="/settings", tags=["settings"])

# Keys that may be read/written via the UI (allowlist — expand as needed)
ALLOWED_KEYS = {
    "heartbeat.interval_seconds",
    "task_router.mode",
    "tts.voice_output_enabled",
}


class SettingOut(BaseModel):
    key: str
    value: str
    description: str | None = None
    updated_at: datetime | None = None


class SettingPatch(BaseModel):
    value: str


@router.get("", response_model=list[SettingOut])
async def list_settings():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value, description, updated_at FROM settings WHERE key = ANY($1::text[]) ORDER BY key",
            list(ALLOWED_KEYS),
        )
    return [dict(r) for r in rows]


@router.patch("/{key}", response_model=SettingOut)
async def patch_setting(key: str, body: SettingPatch):
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found or not editable")

    pool = await get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE settings SET value = $1, updated_at = $2
            WHERE key = $3
            RETURNING key, value, description, updated_at
            """,
            body.value,
            now,
            key,
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found in database")
    return dict(row)
```

- [ ] **Step 4: Register router in `backend/main.py`**

```python
from backend.routers.settings import router as settings_router

app.include_router(settings_router)
```

- [ ] **Step 5: Seed default settings rows**

Add to `backend/db/schema.sql` (or the seeding migration) if not already present:

```sql
INSERT INTO settings (key, value, description) VALUES
  ('heartbeat.interval_seconds', '300',           'Heartbeat tick interval in seconds'),
  ('task_router.mode',           'deterministic', 'Task router mode: deterministic | local_model'),
  ('tts.voice_output_enabled',   'false',         'Enable TTS voice output')
ON CONFLICT (key) DO NOTHING;
```

Run the seed against the development database:

```bash
psql -U ordo -d ordo -c "\i backend/db/schema.sql"
```

Expected: `INSERT 0 3` or `INSERT 3 0` (depends on whether rows existed).

- [ ] **Step 6: Run tests — verify they pass**

```bash
pytest tests/test_settings_router.py -v
```

Expected:
```
tests/test_settings_router.py::test_get_settings_returns_list PASSED
tests/test_settings_router.py::test_patch_setting PASSED
tests/test_settings_router.py::test_patch_setting_bad_key PASSED
```

- [ ] **Step 7: Commit**

```bash
git add backend/routers/settings.py tests/test_settings_router.py backend/main.py backend/db/schema.sql
git commit -m "feat(phase-8): add Settings CRUD router for runtime key-value settings"
```

---

### Task 4: Notifications SSE Route

**Files:**
- Create: `backend/routers/notifications.py`
- Create: `tests/test_notifications.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_notifications.py`:

```python
import pytest
from httpx import AsyncClient
from backend.main import app


@pytest.mark.asyncio
async def test_notifications_stream_connects():
    async with AsyncClient(app=app, base_url="http://test") as c:
        async with c.stream("GET", "/notifications/stream", timeout=2) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_notifications_publish():
    from backend.routers.notifications import publish_notification
    # publish does not raise
    await publish_notification({"type": "popup", "message": "Test"})
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_notifications.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Create `backend/routers/notifications.py`**

```python
"""
Server-Sent Events notification stream.

Electron polls GET /notifications/stream.
When FastAPI calls publish_notification(), the event is broadcast
to all connected SSE clients.

Event format:
  data: {"type": "popup", "message": "...", "title": "..."}
"""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])

# In-process broadcast queue (one asyncio.Queue per connected client)
_subscribers: list[asyncio.Queue] = []


async def publish_notification(event: dict) -> None:
    """Push an event to all connected SSE clients."""
    payload = json.dumps(event)
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        if q in _subscribers:
            _subscribers.remove(q)


async def _event_generator(queue: asyncio.Queue):
    try:
        while True:
            payload = await asyncio.wait_for(queue.get(), timeout=30)
            yield f"data: {payload}\n\n"
    except asyncio.TimeoutError:
        # Send a keep-alive comment so Electron knows the connection is alive
        yield ": keep-alive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)


@router.get("/stream")
async def notification_stream():
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subscribers.append(queue)
    return StreamingResponse(
        _event_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 4: Register router in `backend/main.py`**

```python
from backend.routers.notifications import router as notifications_router

app.include_router(notifications_router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_notifications.py -v
```

Expected:
```
tests/test_notifications.py::test_notifications_stream_connects PASSED
tests/test_notifications.py::test_notifications_publish PASSED
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/notifications.py tests/test_notifications.py backend/main.py
git commit -m "feat(phase-8): add SSE notification stream for Electron proactive popups"
```

---

> **Chunk 1 plan-document-reviewer dispatch:** After completing all Chunk 1 tasks, review `backend/routers/quick_actions.py`, `backend/routers/settings.py`, and `backend/routers/notifications.py` against this plan. Verify: all five Quick Actions routes exist at the correct paths; `execute_action()` covers all four action types; `ALLOWED_KEYS` in settings matches the three settings listed in scope; SSE keep-alive is present; all tests pass (`pytest tests/test_quick_actions.py tests/test_settings_router.py tests/test_notifications.py -v`). Report any deviations before starting Chunk 2.

---

## Chunk 2: Heartbeat Scheduler + Telegram Bridge

### Task 5: Heartbeat Scheduler Service

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/heartbeat.py`
- Create: `tests/test_heartbeat.py`

- [ ] **Step 1: Create services package**

```bash
mkdir -p "C:/Users/user/AI-Assistant Version 4/backend/services"
touch "C:/Users/user/AI-Assistant Version 4/backend/services/__init__.py"
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_heartbeat.py`:

```python
"""
Unit tests for heartbeat scheduler logic.
These tests mock DB and HTTP calls — the scheduler loop is not started.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_is_action_due_matching_cron():
    from backend.services.heartbeat import is_action_due
    # A cron of "* * * * *" is always due
    assert is_action_due("* * * * *") is True


@pytest.mark.asyncio
async def test_is_action_due_non_matching_cron():
    from backend.services.heartbeat import is_action_due
    # 0 3 29 2 * = 3 AM on Feb 29 — almost certainly not now
    result = is_action_due("0 3 29 2 *")
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_write_heartbeat_log_called(monkeypatch):
    from backend.services import heartbeat as hb

    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr(hb, "get_pool", AsyncMock(return_value=mock_pool))

    await hb.write_heartbeat_log(
        conn=mock_conn,
        action_id=None,
        status="ok",
        result={"status": "ok"},
    )
    assert mock_conn.execute.called


@pytest.mark.asyncio
async def test_tick_calls_router(monkeypatch):
    from backend.services import heartbeat as hb

    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])  # no quick actions
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr(hb, "get_pool", AsyncMock(return_value=mock_pool))

    mock_execute = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr(hb, "run_router", mock_execute)

    await hb.tick()

    assert mock_execute.called
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_heartbeat.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.services.heartbeat'`

- [ ] **Step 4: Create `backend/services/heartbeat.py`**

```python
"""
Ordo Heartbeat Scheduler — PM2 process `ordo-heartbeat`.

Runs as a standalone asyncio program. Every `heartbeat.interval_seconds`
(default 300):
  1. Fetches all enabled quick_actions from the DB.
  2. Checks each action's cron schedule with croniter.
  3. Executes due actions via execute_action() (imported from quick_actions router).
  4. Always runs run_router() to process the token budget task queue.
  5. Writes results to heartbeat_log.
  6. Updates settings key `heartbeat.next_run_at`.

Run directly:
  python -m backend.services.heartbeat

Environment: must be able to reach PostgreSQL (same .env as FastAPI).
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from croniter import croniter

# Re-use the shared DB pool helper
from backend.db.pool import get_pool
from backend.routers.quick_actions import execute_action

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [heartbeat] %(levelname)s %(message)s",
)
log = logging.getLogger("heartbeat")

ROUTER_RUN_URL = "http://localhost:8000/router/run"
DEFAULT_INTERVAL = 300  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_action_due(schedule: str, base_dt: datetime | None = None) -> bool:
    """Return True if the cron expression `schedule` matches the current minute."""
    if base_dt is None:
        base_dt = datetime.now(timezone.utc)
    try:
        # croniter: check if the expression was due within the last 60 seconds
        cron = croniter(schedule, base_dt)
        prev_run = cron.get_prev(datetime)
        delta = (base_dt - prev_run).total_seconds()
        return delta < 60
    except Exception as exc:
        log.warning("Could not parse cron '%s': %s", schedule, exc)
        return False


async def write_heartbeat_log(
    conn,
    action_id: uuid.UUID | None,
    status: str,
    result: dict,
) -> None:
    await conn.execute(
        """
        INSERT INTO heartbeat_log (id, action_id, run_at, status, result)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
        uuid.uuid4(),
        action_id,
        datetime.now(timezone.utc),
        status,
        json.dumps(result),
    )


async def run_router() -> dict:
    """Fire POST /router/run — returns the router response dict."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(ROUTER_RUN_URL, json={})
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error("Task router call failed: %s", exc)
        return {"status": "error", "error": str(exc)}


async def get_interval() -> int:
    """Read heartbeat.interval_seconds from settings table."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM settings WHERE key = 'heartbeat.interval_seconds'"
            )
            if row:
                return int(row["value"])
    except Exception:
        pass
    return DEFAULT_INTERVAL


async def set_next_run_at(next_run: datetime) -> None:
    """Persist heartbeat.next_run_at to the settings table."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO settings (key, value, description)
                VALUES ('heartbeat.next_run_at', $1, 'Next scheduled heartbeat tick (UTC ISO)')
                ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = NOW()
                """,
                next_run.isoformat(),
            )
    except Exception as exc:
        log.warning("Could not persist next_run_at: %s", exc)


# ---------------------------------------------------------------------------
# Core tick
# ---------------------------------------------------------------------------

async def tick() -> None:
    """Execute one heartbeat tick."""
    log.info("Heartbeat tick started")
    pool = await get_pool()

    async with pool.acquire() as conn:
        actions = await conn.fetch(
            "SELECT * FROM quick_actions WHERE enabled = TRUE ORDER BY created_at ASC"
        )

    now = datetime.now(timezone.utc)

    # 1. Run due quick actions
    for row in actions:
        action = dict(row)
        if not is_action_due(action.get("schedule", "* * * * *"), base_dt=now):
            log.debug("Action '%s' not due — skipping", action["name"])
            continue

        log.info("Running action '%s' (type=%s)", action["name"], action["action_type"])
        result = await execute_action(action)
        status = result.get("status", "error")

        async with pool.acquire() as conn:
            await write_heartbeat_log(conn, action["id"], status, result)

        log.info("Action '%s' → %s", action["name"], status)

    # 2. Always run the task router
    log.info("Running task router")
    router_result = await run_router()
    async with pool.acquire() as conn:
        await write_heartbeat_log(conn, None, router_result.get("status", "ok"), router_result)

    log.info("Heartbeat tick complete")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main() -> None:
    log.info("Ordo Heartbeat Scheduler starting")
    while True:
        interval = await get_interval()

        try:
            await tick()
        except Exception as exc:
            log.error("Unhandled error in tick: %s", exc, exc_info=True)

        from datetime import timedelta
        next_run = datetime.now(timezone.utc) + timedelta(seconds=interval)
        await set_next_run_at(next_run)
        log.info("Next tick in %ds (at %s UTC)", interval, next_run.isoformat())
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_heartbeat.py -v
```

Expected:
```
tests/test_heartbeat.py::test_is_action_due_matching_cron PASSED
tests/test_heartbeat.py::test_is_action_due_non_matching_cron PASSED
tests/test_heartbeat.py::test_write_heartbeat_log_called PASSED
tests/test_heartbeat.py::test_tick_calls_router PASSED
```

- [ ] **Step 6: Register PM2 process in `ecosystem.config.js`**

Open `ecosystem.config.js` (project root) and add the heartbeat entry to the `apps` array:

```js
{
  name: "ordo-heartbeat",
  script: "python",
  args: "-m backend.services.heartbeat",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  env: {
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4",
  },
  restart_delay: 5000,
  autorestart: true,
  watch: false,
},
```

- [ ] **Step 7: Smoke test — start heartbeat manually**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
python -m backend.services.heartbeat
```

Expected: Logs show `Heartbeat tick started`, task router is called, `Next tick in 300s` appears. Press Ctrl+C to stop.

- [ ] **Step 8: Commit**

```bash
git add backend/services/__init__.py backend/services/heartbeat.py tests/test_heartbeat.py ecosystem.config.js
git commit -m "feat(phase-8): add Heartbeat Scheduler service and PM2 process config"
```

---

### Task 6: Telegram Bridge Service

**Files:**
- Create: `backend/services/telegram_bridge.py`
- Create: `backend/routers/telegram.py`
- Create: `tests/test_telegram.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_telegram.py`:

```python
"""
Tests for the Telegram send route and bridge helpers.
Bot token is intentionally absent — tests verify stub-mode behaviour.
"""
import pytest
from httpx import AsyncClient
from backend.main import app


@pytest.mark.asyncio
async def test_telegram_send_without_token_returns_503():
    """Without a configured bot token the route must return 503."""
    import os
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)

    async with AsyncClient(app=app, base_url="http://test") as c:
        resp = await c.post(
            "/telegram/send",
            json={"chat_id": "123456", "text": "Hello"},
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_telegram_send_validates_payload():
    async with AsyncClient(app=app, base_url="http://test") as c:
        resp = await c.post("/telegram/send", json={})
    # 422 Unprocessable Entity — missing required fields
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_telegram.py -v
```

Expected: `ImportError` or route-not-found errors.

- [ ] **Step 3: Create `backend/routers/telegram.py`**

This router handles the FastAPI-side `POST /telegram/send` route. The actual bot loop lives in the separate PM2 process.

```python
"""
Telegram proactive send route.

Agents (or quick actions) call POST /telegram/send to push a message
to the user's Telegram chat without waiting for an inbound message.

If the bot token is not configured the route returns 503 (stub mode).
"""
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("telegram_router")
router = APIRouter(prefix="/telegram", tags=["telegram"])


class TelegramSendRequest(BaseModel):
    chat_id: str
    text: str


def _get_bot_token() -> str | None:
    """Resolve bot token: env var first, then model_api_keys table (async callers use the helper)."""
    return os.environ.get("TELEGRAM_BOT_TOKEN")


@router.post("/send", status_code=200)
async def send_telegram_message(body: TelegramSendRequest):
    token = _get_bot_token()

    if not token:
        # Try DB fallback
        try:
            from backend.db.pool import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT key_value FROM model_api_keys WHERE provider = 'telegram' LIMIT 1"
                )
                if row:
                    token = row["key_value"]
        except Exception as exc:
            log.warning("Could not read telegram token from DB: %s", exc)

    if not token:
        log.warning("Telegram bot token not configured — running in stub mode")
        raise HTTPException(
            status_code=503,
            detail="Telegram bot token not configured. Set TELEGRAM_BOT_TOKEN or add a model_api_keys row with provider='telegram'.",
        )

    try:
        from telegram import Bot
        bot = Bot(token=token)
        await bot.send_message(chat_id=body.chat_id, text=body.text)
        return {"status": "sent", "chat_id": body.chat_id}
    except Exception as exc:
        log.error("Failed to send Telegram message: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 4: Create `backend/services/telegram_bridge.py`**

```python
"""
Ordo Telegram Bridge — PM2 process `ordo-telegram`.

Runs as a standalone python-telegram-bot Application.
On inbound message: POSTs to POST /agents/generalist/invoke,
sends the response back to the same chat.

Run directly:
  python -m backend.services.telegram_bridge

Requires TELEGRAM_BOT_TOKEN env var (or model_api_keys table row).
If not found, logs a warning and exits gracefully (PM2 will restart
after restart_delay; operator should set the token then restart).
"""
import asyncio
import logging
import os

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [telegram] %(levelname)s %(message)s",
)
log = logging.getLogger("telegram_bridge")

FASTAPI_BASE = "http://localhost:8000"
GENERALIST_INVOKE_URL = f"{FASTAPI_BASE}/agents/generalist/invoke"


async def _get_token() -> str | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    # DB fallback
    try:
        from backend.db.pool import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT key_value FROM model_api_keys WHERE provider = 'telegram' LIMIT 1"
            )
            if row:
                return row["key_value"]
    except Exception as exc:
        log.warning("DB token lookup failed: %s", exc)
    return None


async def handle_message(update, context) -> None:
    """Route an inbound Telegram message to the generalist agent."""
    message = update.message
    if not message or not message.text:
        return

    chat_id = str(message.chat_id)
    text = message.text
    log.info("Inbound message from chat %s: %r", chat_id, text[:80])

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                GENERALIST_INVOKE_URL,
                json={
                    "content": text,
                    "conversation_id": chat_id,
                    "source": "telegram",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.error("Agent invoke failed: %s", exc)
        await message.reply_text("Sorry, I encountered an error processing your message.")
        return

    # Extract agent reply — adapt key name to match generalist invoke response schema
    reply = (
        data.get("response")
        or data.get("output")
        or data.get("content")
        or str(data)
    )
    if not isinstance(reply, str):
        reply = str(reply)

    await message.reply_text(reply[:4096])  # Telegram message limit


async def main() -> None:
    from telegram.ext import Application, MessageHandler, filters

    token = await _get_token()
    if not token:
        log.error(
            "TELEGRAM_BOT_TOKEN not set and not found in model_api_keys. "
            "Telegram bridge starting in stub mode — will retry on next PM2 restart."
        )
        # Sleep indefinitely so PM2 does not rapid-restart
        await asyncio.sleep(3600)
        return

    log.info("Starting Telegram bot application")
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Telegram bridge ready — polling for messages")
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Register Telegram router in `backend/main.py`**

```python
from backend.routers.telegram import router as telegram_router

app.include_router(telegram_router)
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
pytest tests/test_telegram.py -v
```

Expected:
```
tests/test_telegram.py::test_telegram_send_without_token_returns_503 PASSED
tests/test_telegram.py::test_telegram_send_validates_payload PASSED
```

- [ ] **Step 7: Register PM2 process in `ecosystem.config.js`**

Add to the `apps` array:

```js
{
  name: "ordo-telegram",
  script: "python",
  args: "-m backend.services.telegram_bridge",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  env: {
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4",
  },
  restart_delay: 10000,
  autorestart: true,
  watch: false,
},
```

- [ ] **Step 8: Smoke test Telegram bridge (requires bot token)**

If `TELEGRAM_BOT_TOKEN` is set:

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
python -m backend.services.telegram_bridge
```

Expected: `Telegram bridge ready — polling for messages`. Send a message to the bot from Telegram — the bridge should POST to the generalist agent and reply. Press Ctrl+C to stop.

If no token is set yet, skip; PM2 will run in stub mode.

- [ ] **Step 9: Start PM2 processes**

```bash
pm2 start ecosystem.config.js --only ordo-heartbeat,ordo-telegram
pm2 save
```

Expected:
```
[PM2] Starting ordo-heartbeat
[PM2] Starting ordo-telegram
[PM2] Saving current process list
```

- [ ] **Step 10: Commit**

```bash
git add backend/services/telegram_bridge.py backend/routers/telegram.py tests/test_telegram.py backend/main.py ecosystem.config.js
git commit -m "feat(phase-8): add Telegram Bridge service and proactive /telegram/send route"
```

---

> **Chunk 2 plan-document-reviewer dispatch:** After completing all Chunk 2 tasks, review `backend/services/heartbeat.py` and `backend/services/telegram_bridge.py` against this plan. Verify: `is_action_due()` uses croniter with a 60-second window; `tick()` always calls `run_router()` regardless of quick action results; `write_heartbeat_log()` records `action_id=None` for router calls; Telegram bridge falls back to stub mode (1-hour sleep) when no token found; PM2 processes are registered in `ecosystem.config.js` with `autorestart: true`; both `ordo-heartbeat` and `ordo-telegram` appear in `pm2 list`. Run `pytest tests/test_heartbeat.py tests/test_telegram.py -v` and confirm all tests pass before starting Chunk 3.

---

## Chunk 3: Frontend Panels + Proactive Electron Popups

### Task 7: Quick Actions Slide-In Panel

**Files:**
- Create: `frontend/src/panels/quick-actions.ts`
- Modify: `frontend/src/main.ts` (or equivalent sidebar entry point)

- [ ] **Step 1: Create `frontend/src/panels/` directory**

```bash
mkdir -p "C:/Users/user/AI-Assistant Version 4/frontend/src/panels"
```

- [ ] **Step 2: Create `frontend/src/panels/quick-actions.ts`**

```typescript
/**
 * Quick Actions slide-in panel.
 *
 * Triggered by the "⚡ Quick" sidebar button.
 * Slides in from the right using CSS transform translateX.
 *
 * API surface used:
 *   GET  /quick_actions               — list all actions
 *   POST /quick_actions               — create action
 *   PATCH /quick_actions/{id}         — update (enable/disable)
 *   POST /quick_actions/{id}/run      — manually trigger
 */

const API_BASE = "http://localhost:8000";

interface QuickAction {
  id: string;
  name: string;
  description: string;
  action_type: string;
  config: Record<string, unknown>;
  schedule: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const PANEL_STYLES = `
  #qa-panel-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 900;
    opacity: 0;
    transition: opacity 0.2s ease;
    pointer-events: none;
  }
  #qa-panel-overlay.visible {
    opacity: 1;
    pointer-events: auto;
  }
  #qa-panel {
    position: fixed;
    top: 0;
    right: 0;
    height: 100%;
    width: 380px;
    background: var(--color-bg-surface, #1e1e2e);
    box-shadow: -4px 0 24px rgba(0,0,0,0.4);
    z-index: 901;
    transform: translateX(100%);
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
    padding: 1.25rem;
    gap: 1rem;
    overflow-y: auto;
  }
  #qa-panel.open {
    transform: translateX(0);
  }
  .qa-action-card {
    background: var(--color-bg-elevated, #2a2a3e);
    border-radius: 8px;
    padding: 0.875rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .qa-action-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .qa-action-name {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--color-text-primary, #cdd6f4);
  }
  .qa-action-meta {
    font-size: 0.75rem;
    color: var(--color-text-muted, #6c7086);
  }
  .qa-action-controls {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin-top: 0.25rem;
  }
  .qa-run-btn {
    background: var(--color-accent, #89b4fa);
    color: #1e1e2e;
    border: none;
    border-radius: 5px;
    padding: 0.3rem 0.75rem;
    font-size: 0.8rem;
    cursor: pointer;
    font-weight: 600;
    transition: opacity 0.15s;
  }
  .qa-run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .qa-toggle {
    cursor: pointer;
    accent-color: var(--color-accent, #89b4fa);
    width: 16px;
    height: 16px;
  }
  .qa-status-badge {
    font-size: 0.7rem;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    font-weight: 600;
  }
  .qa-status-badge.ok { background: #a6e3a1; color: #1e1e2e; }
  .qa-status-badge.error { background: #f38ba8; color: #1e1e2e; }
  .qa-add-form {
    background: var(--color-bg-elevated, #2a2a3e);
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .qa-add-form input, .qa-add-form select {
    background: var(--color-bg-input, #313244);
    border: 1px solid var(--color-border, #45475a);
    border-radius: 5px;
    padding: 0.4rem 0.65rem;
    color: var(--color-text-primary, #cdd6f4);
    font-size: 0.85rem;
    width: 100%;
    box-sizing: border-box;
  }
  .qa-add-submit {
    background: var(--color-accent, #89b4fa);
    color: #1e1e2e;
    border: none;
    border-radius: 5px;
    padding: 0.45rem;
    font-weight: 600;
    cursor: pointer;
    font-size: 0.85rem;
  }
`;

function injectStyles(): void {
  if (document.getElementById("qa-panel-styles")) return;
  const style = document.createElement("style");
  style.id = "qa-panel-styles";
  style.textContent = PANEL_STYLES;
  document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------

function buildPanel(): { overlay: HTMLElement; panel: HTMLElement } {
  const overlay = document.createElement("div");
  overlay.id = "qa-panel-overlay";

  const panel = document.createElement("div");
  panel.id = "qa-panel";
  panel.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;">
      <h2 style="margin:0;font-size:1rem;color:var(--color-text-primary,#cdd6f4);">⚡ Quick Actions</h2>
      <button id="qa-close-btn" style="background:none;border:none;color:var(--color-text-muted,#6c7086);font-size:1.25rem;cursor:pointer;">✕</button>
    </div>
    <div id="qa-action-list" style="display:flex;flex-direction:column;gap:0.75rem;"></div>
    <details style="margin-top:0.5rem;">
      <summary style="cursor:pointer;font-size:0.85rem;color:var(--color-text-muted,#6c7086);">+ Add action</summary>
      <form id="qa-add-form" class="qa-add-form" style="margin-top:0.75rem;">
        <input name="name" placeholder="Name" required />
        <input name="description" placeholder="Description (optional)" />
        <select name="action_type">
          <option value="agent_invoke">agent_invoke</option>
          <option value="task_route">task_route</option>
          <option value="http_request">http_request</option>
          <option value="python_function">python_function</option>
        </select>
        <input name="schedule" placeholder="Cron schedule (e.g. 0 9 * * *)" value="*/5 * * * *" required />
        <button type="submit" class="qa-add-submit">Create Action</button>
      </form>
    </details>
  `;

  document.body.appendChild(overlay);
  document.body.appendChild(panel);

  overlay.addEventListener("click", closePanel);
  panel.querySelector("#qa-close-btn")!.addEventListener("click", closePanel);

  return { overlay, panel };
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function fetchActions(): Promise<QuickAction[]> {
  const resp = await fetch(`${API_BASE}/quick_actions`);
  if (!resp.ok) throw new Error(`Failed to fetch quick actions: ${resp.status}`);
  return resp.json();
}

async function toggleAction(id: string, enabled: boolean): Promise<void> {
  await fetch(`${API_BASE}/quick_actions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

async function runAction(id: string): Promise<{ status: string; error?: string }> {
  const resp = await fetch(`${API_BASE}/quick_actions/${id}/run`, { method: "POST" });
  return resp.json();
}

async function createAction(payload: Partial<QuickAction>): Promise<QuickAction> {
  const resp = await fetch(`${API_BASE}/quick_actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(`Create failed: ${resp.status}`);
  return resp.json();
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

async function renderActions(container: HTMLElement): Promise<void> {
  container.innerHTML = `<div style="font-size:0.8rem;color:var(--color-text-muted,#6c7086);">Loading…</div>`;
  let actions: QuickAction[];
  try {
    actions = await fetchActions();
  } catch {
    container.innerHTML = `<div style="color:#f38ba8;font-size:0.8rem;">Failed to load actions.</div>`;
    return;
  }

  if (actions.length === 0) {
    container.innerHTML = `<div style="font-size:0.8rem;color:var(--color-text-muted,#6c7086);">No quick actions configured yet.</div>`;
    return;
  }

  container.innerHTML = "";
  for (const action of actions) {
    const card = document.createElement("div");
    card.className = "qa-action-card";
    card.dataset.id = action.id;
    card.innerHTML = `
      <div class="qa-action-header">
        <span class="qa-action-name">${escapeHtml(action.name)}</span>
        <span class="qa-status-badge" id="qa-status-${action.id}"></span>
      </div>
      ${action.description ? `<div class="qa-action-meta">${escapeHtml(action.description)}</div>` : ""}
      <div class="qa-action-meta">${escapeHtml(action.action_type)} · <code style="font-size:0.7rem;">${escapeHtml(action.schedule)}</code></div>
      <div class="qa-action-controls">
        <button class="qa-run-btn" data-action-id="${action.id}">Run Now</button>
        <label style="display:flex;align-items:center;gap:0.3rem;font-size:0.75rem;color:var(--color-text-muted,#6c7086);">
          <input type="checkbox" class="qa-toggle" data-action-id="${action.id}" ${action.enabled ? "checked" : ""} />
          Enabled
        </label>
      </div>
    `;
    container.appendChild(card);

    // Wire Run Now
    card.querySelector(".qa-run-btn")!.addEventListener("click", async (e) => {
      const btn = e.currentTarget as HTMLButtonElement;
      btn.disabled = true;
      btn.textContent = "Running…";
      const badge = document.getElementById(`qa-status-${action.id}`)!;
      try {
        const result = await runAction(action.id);
        badge.textContent = result.status === "ok" ? "ok" : "error";
        badge.className = `qa-status-badge ${result.status === "ok" ? "ok" : "error"}`;
      } finally {
        btn.disabled = false;
        btn.textContent = "Run Now";
      }
    });

    // Wire toggle
    card.querySelector(".qa-toggle")!.addEventListener("change", async (e) => {
      const cb = e.currentTarget as HTMLInputElement;
      await toggleAction(action.id, cb.checked);
    });
  }
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ---------------------------------------------------------------------------
// Open / close
// ---------------------------------------------------------------------------

let _panelBuilt = false;
let _overlay: HTMLElement;
let _panel: HTMLElement;

function ensureBuilt(): void {
  if (_panelBuilt) return;
  injectStyles();
  const { overlay, panel } = buildPanel();
  _overlay = overlay;
  _panel = panel;
  _panelBuilt = true;

  const form = panel.querySelector<HTMLFormElement>("#qa-add-form")!;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(form);
    try {
      await createAction({
        name: data.get("name") as string,
        description: data.get("description") as string,
        action_type: data.get("action_type") as string,
        schedule: data.get("schedule") as string,
        config: {},
        enabled: true,
      });
      form.reset();
      const container = _panel.querySelector<HTMLElement>("#qa-action-list")!;
      await renderActions(container);
    } catch (err) {
      alert(`Failed to create action: ${err}`);
    }
  });
}

export async function openQuickActionsPanel(): Promise<void> {
  ensureBuilt();
  _overlay.classList.add("visible");
  _panel.classList.add("open");
  const container = _panel.querySelector<HTMLElement>("#qa-action-list")!;
  await renderActions(container);
}

export function closePanel(): void {
  if (!_panelBuilt) return;
  _overlay.classList.remove("visible");
  _panel.classList.remove("open");
}
```

- [ ] **Step 3: Wire sidebar button in `frontend/src/main.ts`**

Locate the sidebar button element for "⚡ Quick" and add:

```typescript
import { openQuickActionsPanel } from "./panels/quick-actions";

const quickBtn = document.querySelector<HTMLButtonElement>("#sidebar-quick-btn");
if (quickBtn) {
  quickBtn.addEventListener("click", () => openQuickActionsPanel());
}
```

- [ ] **Step 4: Build frontend and verify no TypeScript errors**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm run build
```

Expected: Build succeeds with 0 TypeScript errors. No `error TS` lines in output.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/panels/quick-actions.ts frontend/src/main.ts
git commit -m "feat(phase-8): add Quick Actions slide-in panel with CRUD and Run Now"
```

---

### Task 8: Settings Modal

**Files:**
- Create: `frontend/src/panels/settings.ts`
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: Create `frontend/src/panels/settings.ts`**

```typescript
/**
 * Settings modal panel.
 *
 * Triggered by the "⚙ Settings" sidebar button.
 * Fetches runtime settings from GET /settings and allows inline edit
 * via PATCH /settings/{key}.
 *
 * Phase 8 settings shown:
 *   heartbeat.interval_seconds
 *   task_router.mode
 *   tts.voice_output_enabled
 */

const API_BASE = "http://localhost:8000";

interface Setting {
  key: string;
  value: string;
  description: string | null;
  updated_at: string | null;
}

const MODAL_STYLES = `
  #settings-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 950;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
  }
  #settings-modal-backdrop.visible {
    opacity: 1;
    pointer-events: auto;
  }
  #settings-modal {
    background: var(--color-bg-surface, #1e1e2e);
    border-radius: 12px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    width: 480px;
    max-width: 96vw;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    transform: scale(0.95);
    transition: transform 0.2s ease;
  }
  #settings-modal-backdrop.visible #settings-modal {
    transform: scale(1);
  }
  .setting-row {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .setting-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--color-text-primary, #cdd6f4);
    font-family: monospace;
  }
  .setting-description {
    font-size: 0.75rem;
    color: var(--color-text-muted, #6c7086);
  }
  .setting-value-row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .setting-input {
    flex: 1;
    background: var(--color-bg-input, #313244);
    border: 1px solid var(--color-border, #45475a);
    border-radius: 5px;
    padding: 0.4rem 0.65rem;
    color: var(--color-text-primary, #cdd6f4);
    font-size: 0.85rem;
    font-family: monospace;
  }
  .setting-save-btn {
    background: var(--color-accent, #89b4fa);
    color: #1e1e2e;
    border: none;
    border-radius: 5px;
    padding: 0.4rem 0.8rem;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .setting-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .setting-saved-indicator {
    font-size: 0.75rem;
    color: #a6e3a1;
    opacity: 0;
    transition: opacity 0.3s;
  }
  .setting-saved-indicator.show { opacity: 1; }
`;

function injectStyles(): void {
  if (document.getElementById("settings-modal-styles")) return;
  const s = document.createElement("style");
  s.id = "settings-modal-styles";
  s.textContent = MODAL_STYLES;
  document.head.appendChild(s);
}

async function fetchSettings(): Promise<Setting[]> {
  const resp = await fetch(`${API_BASE}/settings`);
  if (!resp.ok) throw new Error(`Failed to load settings: ${resp.status}`);
  return resp.json();
}

async function patchSetting(key: string, value: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/settings/${encodeURIComponent(key)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!resp.ok) throw new Error(`Save failed: ${resp.status}`);
}

function buildModal(): HTMLElement {
  const backdrop = document.createElement("div");
  backdrop.id = "settings-modal-backdrop";
  backdrop.innerHTML = `
    <div id="settings-modal">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <h2 style="margin:0;font-size:1rem;color:var(--color-text-primary,#cdd6f4);">⚙ Settings</h2>
        <button id="settings-close-btn" style="background:none;border:none;color:var(--color-text-muted,#6c7086);font-size:1.25rem;cursor:pointer;">✕</button>
      </div>
      <div id="settings-rows" style="display:flex;flex-direction:column;gap:1rem;"></div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeSettingsModal();
  });
  backdrop.querySelector("#settings-close-btn")!.addEventListener("click", closeSettingsModal);
  return backdrop;
}

async function renderSettings(container: HTMLElement): Promise<void> {
  container.innerHTML = `<div style="font-size:0.8rem;color:var(--color-text-muted,#6c7086);">Loading settings…</div>`;
  let settings: Setting[];
  try {
    settings = await fetchSettings();
  } catch {
    container.innerHTML = `<div style="color:#f38ba8;font-size:0.8rem;">Failed to load settings.</div>`;
    return;
  }

  container.innerHTML = "";
  for (const s of settings) {
    const row = document.createElement("div");
    row.className = "setting-row";
    const indicatorId = `saved-${s.key.replace(/\./g, "-")}`;
    row.innerHTML = `
      <span class="setting-label">${s.key}</span>
      ${s.description ? `<span class="setting-description">${s.description}</span>` : ""}
      <div class="setting-value-row">
        <input class="setting-input" type="text" value="${escapeAttr(s.value)}" data-key="${s.key}" />
        <button class="setting-save-btn" data-key="${s.key}">Save</button>
        <span class="setting-saved-indicator" id="${indicatorId}">✓ saved</span>
      </div>
    `;
    const btn = row.querySelector<HTMLButtonElement>(".setting-save-btn")!;
    const input = row.querySelector<HTMLInputElement>(".setting-input")!;
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await patchSetting(s.key, input.value.trim());
        const indicator = document.getElementById(indicatorId)!;
        indicator.classList.add("show");
        setTimeout(() => indicator.classList.remove("show"), 2000);
      } catch (err) {
        alert(`Failed to save ${s.key}: ${err}`);
      } finally {
        btn.disabled = false;
      }
    });
    container.appendChild(row);
  }
}

function escapeAttr(str: string): string {
  return str.replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

let _modalBuilt = false;
let _backdrop: HTMLElement;

function ensureBuilt(): void {
  if (_modalBuilt) return;
  injectStyles();
  _backdrop = buildModal();
  _modalBuilt = true;
}

export async function openSettingsModal(): Promise<void> {
  ensureBuilt();
  _backdrop.classList.add("visible");
  const container = _backdrop.querySelector<HTMLElement>("#settings-rows")!;
  await renderSettings(container);
}

export function closeSettingsModal(): void {
  if (!_modalBuilt) return;
  _backdrop.classList.remove("visible");
}
```

- [ ] **Step 2: Wire sidebar button in `frontend/src/main.ts`**

```typescript
import { openSettingsModal } from "./panels/settings";

const settingsBtn = document.querySelector<HTMLButtonElement>("#sidebar-settings-btn");
if (settingsBtn) {
  settingsBtn.addEventListener("click", () => openSettingsModal());
}
```

- [ ] **Step 3: Build frontend and verify no TypeScript errors**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm run build
```

Expected: Build succeeds with 0 TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/panels/settings.ts frontend/src/main.ts
git commit -m "feat(phase-8): add Settings modal panel with inline runtime setting editor"
```

---

### Task 9: Proactive Electron Popups via SSE

**Files:**
- Modify: `frontend/electron/main.ts`

- [ ] **Step 1: Read the current `frontend/electron/main.ts`**

Open `frontend/electron/main.ts` and locate the `app.whenReady()` block and the `createWindow()` function. The additions go after the main window is created.

- [ ] **Step 2: Add SSE polling and popup window logic to `frontend/electron/main.ts`**

Add the following block after the main `BrowserWindow` is created inside `app.whenReady()` (or in a dedicated function called from there):

```typescript
import { BrowserWindow, app, ipcMain } from "electron";
import * as http from "http";

// ---------------------------------------------------------------------------
// SSE notification listener — connects to GET /notifications/stream
// ---------------------------------------------------------------------------

const NOTIFICATION_STREAM_URL = "http://localhost:8000/notifications/stream";

function startNotificationListener(): void {
  function connect(): void {
    const req = http.get(NOTIFICATION_STREAM_URL, (res) => {
      let buf = "";

      res.on("data", (chunk: Buffer) => {
        buf += chunk.toString();
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const payload = line.slice(6).trim();
            if (!payload) continue;
            try {
              const event = JSON.parse(payload);
              if (event.type === "popup") {
                showPopupWindow(event.title ?? "Ordo", event.message ?? "");
              }
            } catch {
              // ignore malformed events
            }
          }
        }
      });

      res.on("end", () => {
        // Server closed stream — reconnect after a short delay
        setTimeout(connect, 3000);
      });

      res.on("error", () => {
        setTimeout(connect, 5000);
      });
    });

    req.on("error", () => {
      // FastAPI not yet up — retry
      setTimeout(connect, 5000);
    });

    req.setTimeout(0); // no timeout — keep-alive stream
  }

  connect();
}

// ---------------------------------------------------------------------------
// Popup window factory
// ---------------------------------------------------------------------------

function showPopupWindow(title: string, message: string): void {
  const popup = new BrowserWindow({
    width: 360,
    height: 140,
    alwaysOnTop: true,
    frame: false,
    resizable: false,
    skipTaskbar: true,
    transparent: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Build an inline HTML page for the notification
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8" />
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: system-ui, sans-serif;
          background: #1e1e2e;
          color: #cdd6f4;
          padding: 1rem 1.25rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          height: 100vh;
          -webkit-app-region: drag;
        }
        h3 { font-size: 0.85rem; color: #89b4fa; }
        p { font-size: 0.8rem; color: #bac2de; line-height: 1.4; }
        button {
          align-self: flex-end;
          background: #89b4fa;
          color: #1e1e2e;
          border: none;
          border-radius: 5px;
          padding: 0.3rem 0.9rem;
          font-size: 0.75rem;
          font-weight: 600;
          cursor: pointer;
          -webkit-app-region: no-drag;
        }
      </style>
    </head>
    <body>
      <h3>${escapeHtmlInline(title)}</h3>
      <p>${escapeHtmlInline(message)}</p>
      <button onclick="window.close()">Dismiss</button>
    </body>
    </html>
  `;

  popup.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);

  // Position in bottom-right corner
  const { screen } = require("electron");
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  popup.setPosition(width - 380, height - 160);

  // Auto-dismiss after 8 seconds
  setTimeout(() => {
    if (!popup.isDestroyed()) popup.close();
  }, 8000);
}

function escapeHtmlInline(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Call this from app.whenReady():
// startNotificationListener();
```

- [ ] **Step 3: Call `startNotificationListener()` from `app.whenReady()`**

In the existing `app.whenReady().then(async () => { ... })` block, add the call after the main window is created:

```typescript
startNotificationListener();
```

- [ ] **Step 4: Build frontend to catch TypeScript errors**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm run build
```

Expected: Build succeeds with 0 TypeScript errors.

- [ ] **Step 5: Integration smoke test**

With FastAPI running (`pm2 start ecosystem.config.js --only fastapi`) and Electron launched:

```bash
# In a separate terminal, publish a test notification
curl -s -X POST http://localhost:8000/notifications/stream \
  -H "Content-Type: application/json" \
  -d '{"type":"popup","title":"Test","message":"Phase 8 popup working"}'
```

Wait 1-2 seconds. Expected: A small `alwaysOnTop` popup window appears in the bottom-right corner of the screen with the title "Test" and the message body. It auto-dismisses after 8 seconds.

> Note: Publishing requires a route or a direct call to `publish_notification()`. Add a temporary debug endpoint to `backend/routers/notifications.py` for this test if needed:
>
> ```python
> @router.post("/publish")
> async def debug_publish(event: dict):
>     await publish_notification(event)
>     return {"status": "published"}
> ```

- [ ] **Step 6: Commit**

```bash
git add frontend/electron/main.ts
git commit -m "feat(phase-8): add SSE-driven proactive Electron popup windows"
```

---

### Task 10: Full Phase 8 Test Suite + PM2 Save

**Files:**
- No new files — runs all Phase 8 tests together.

- [ ] **Step 1: Run full Phase 8 test suite**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_quick_actions.py tests/test_settings_router.py tests/test_notifications.py tests/test_heartbeat.py tests/test_telegram.py -v --tb=short
```

Expected: All tests pass. Example output:

```
tests/test_quick_actions.py::test_list_quick_actions_empty PASSED
tests/test_quick_actions.py::test_create_quick_action PASSED
tests/test_quick_actions.py::test_patch_quick_action PASSED
tests/test_quick_actions.py::test_delete_quick_action PASSED
tests/test_quick_actions.py::test_run_quick_action_not_found PASSED
tests/test_settings_router.py::test_get_settings_returns_list PASSED
tests/test_settings_router.py::test_patch_setting PASSED
tests/test_settings_router.py::test_patch_setting_bad_key PASSED
tests/test_notifications.py::test_notifications_stream_connects PASSED
tests/test_notifications.py::test_notifications_publish PASSED
tests/test_heartbeat.py::test_is_action_due_matching_cron PASSED
tests/test_heartbeat.py::test_is_action_due_non_matching_cron PASSED
tests/test_heartbeat.py::test_write_heartbeat_log_called PASSED
tests/test_heartbeat.py::test_tick_calls_router PASSED
tests/test_telegram.py::test_telegram_send_without_token_returns_503 PASSED
tests/test_telegram.py::test_telegram_send_validates_payload PASSED

16 passed in X.XXs
```

- [ ] **Step 2: Start all Phase 8 PM2 processes**

```bash
pm2 start ecosystem.config.js --only ordo-heartbeat,ordo-telegram
pm2 save
```

Expected:
```
[PM2] Starting ordo-heartbeat
[PM2] Starting ordo-telegram
[PM2] Saving current process list
```

Verify both are running:

```bash
pm2 list
```

Expected: Both `ordo-heartbeat` and `ordo-telegram` show status `online`.

- [ ] **Step 3: Verify heartbeat writes to DB**

Wait 5 minutes (or temporarily set `heartbeat.interval_seconds` to 30 via the Settings modal), then:

```bash
psql -U ordo -d ordo -c "SELECT action_id, run_at, status, result FROM heartbeat_log ORDER BY run_at DESC LIMIT 5;"
```

Expected: At least one row with `status=ok` and a `run_at` timestamp within the last few minutes.

- [ ] **Step 4: Final commit**

```bash
git add ecosystem.config.js
git commit -m "chore(phase-8): save PM2 process list with ordo-heartbeat and ordo-telegram"
```

---

> **Chunk 3 plan-document-reviewer dispatch:** After completing all Chunk 3 tasks, review `frontend/src/panels/quick-actions.ts`, `frontend/src/panels/settings.ts`, and `frontend/electron/main.ts` against this plan. Verify: Quick Actions panel uses CSS `translateX` slide-in animation; "Run Now" disables button during execution and shows status badge; Settings modal shows exactly the three Phase 8 keys; SSE listener reconnects on stream close (3s delay) and on connection error (5s delay); popup window is `alwaysOnTop: true`, 360×140, auto-dismisses after 8 seconds; `pm2 list` shows `ordo-heartbeat` and `ordo-telegram` as `online`; all 16 Phase 8 tests pass. Report any deviations.
