# Ordo Phase 9: Observability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Phoenix (Arize) OpenTelemetry traces for all LLM calls, add structured JSON logging throughout the backend and slow sidecars, build the sidecar slide-in panel in the Electron UI, and expose token budget state and Phoenix health in the status bar. After this phase: open Phoenix at `http://localhost:6006`, see every LLM call traced with token counts, latency, and full inputs/outputs; open the sidecar panel from the status bar and see real-time sidecar health.

**Architecture:** Phoenix runs as a PM2 process (`ordo-phoenix`) on port 6006. The FastAPI lifespan registers an OpenTelemetry `TracerProvider` pointing at `http://localhost:6006/v1/traces` and instruments LangChain via `LangchainInstrumentor`. Python `logging` (JSON-formatted via `python-json-logger`) writes to rotating log files under `$ORDO_DATA_DIR/logs/`. An ASGI logging middleware captures every request. The sidecar slide-in panel polls `GET /sidecar/status`. The status bar polls `GET /budget` and pings Phoenix for health.

**Tech Stack:** `arize-phoenix`, `arize-phoenix-otel`, `opentelemetry-sdk`, `opentelemetry-instrumentation-langchain`, `python-json-logger`, pytest + pytest-asyncio, TypeScript (Electron/Vite frontend)

---

## Chunk 1: Phoenix PM2 Process + OpenTelemetry Tracing

### Task 1: Validate and Fix the Phoenix PM2 Process

**Files:**
- Modify: `ecosystem.config.js` (update `ordo-phoenix` entry with correct startup command)
- Create: `backend/requirements.txt` (add `arize-phoenix arize-phoenix-otel`)

- [ ] **Step 1: Install arize-phoenix and find the correct startup command**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pip install "arize-phoenix>=4.0.0" "arize-phoenix-otel>=0.1.0"
```

Expected output: Packages install without error. Then probe the correct entry point:

```bash
python -m phoenix.server.main --help
```

Expected: Help text prints, confirming `python -m phoenix.server.main` is the correct invocation. If this fails, try:

```bash
python -c "import phoenix; print(phoenix.__file__)"
# Then check for a 'serve' or 'launch' CLI:
phoenix serve --help 2>/dev/null || python -m phoenix --help 2>/dev/null
```

Record whichever command succeeds — it is the value for `script` in the ecosystem entry below.

- [ ] **Step 2: Update `ecosystem.config.js` — ordo-phoenix entry**

Open `ecosystem.config.js`. Locate the `ordo-phoenix` entry. Replace the `script` and `args` to match the confirmed startup command. The canonical form:

```javascript
{
  name: "ordo-phoenix",
  script: "python",
  args: "-m phoenix.server.main --port 6006",
  interpreter: "none",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  env: {
    PATH: process.env.PATH,
    VIRTUAL_ENV: "C:/Users/user/AI-Assistant Version 4/.venv"
  },
  watch: false,
  restart_delay: 5000,
  autorestart: true,
  max_restarts: 10
},
```

If `phoenix serve` was the correct command instead, set `script: "phoenix"` and `args: "serve --port 6006"` and `interpreter: "none"`.

- [ ] **Step 3: Start the process and verify health**

```bash
pm2 start ecosystem.config.js --only ordo-phoenix
pm2 logs ordo-phoenix --lines 20 --nostream
```

Expected log lines: Phoenix startup messages, including something like `"Listening on http://0.0.0.0:6006"`.

```bash
curl -s http://localhost:6006/healthz || curl -s http://localhost:6006/health
```

Expected: JSON response with `{"status": "ok"}` or an HTTP 200 response. Phoenix's web UI should also respond:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:6006
```

Expected: `200`

- [ ] **Step 4: Pin the confirmed package versions in requirements**

Add to `backend/requirements.txt`:

```
arize-phoenix>=4.0.0
arize-phoenix-otel>=0.1.0
opentelemetry-sdk>=1.24.0
opentelemetry-instrumentation-langchain>=0.1.0
```

- [ ] **Step 5: Commit**

```bash
git add ecosystem.config.js backend/requirements.txt
git commit -m "feat(obs): validate Phoenix PM2 process and pin arize-phoenix deps"
```

---

### Task 2: OpenTelemetry Tracing Module

**Files:**
- Create: `backend/observability/__init__.py`
- Create: `backend/observability/tracing.py`
- Create: `tests/observability/test_tracing.py`

- [ ] **Step 1: Write failing test**

Create `tests/observability/__init__.py` (empty) and `tests/observability/test_tracing.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def test_setup_tracing_returns_tracer_provider():
    """setup_tracing() must return a TracerProvider without raising."""
    with patch("backend.observability.tracing.register") as mock_register:
        mock_register.return_value = MagicMock()
        with patch("backend.observability.tracing.LangchainInstrumentor") as mock_inst:
            mock_inst.return_value.instrument = MagicMock()
            from backend.observability.tracing import setup_tracing
            result = setup_tracing(endpoint="http://localhost:6006/v1/traces")
            mock_register.assert_called_once()
            mock_inst.return_value.instrument.assert_called_once()
            assert result is not None


def test_get_tracer_returns_tracer():
    """get_tracer() must return a usable tracer object."""
    with patch("backend.observability.tracing.register") as mock_register:
        mock_tp = MagicMock()
        mock_register.return_value = mock_tp
        with patch("backend.observability.tracing.LangchainInstrumentor"):
            from importlib import reload
            import backend.observability.tracing as tracing_mod
            reload(tracing_mod)
            tracer = tracing_mod.get_tracer("test.tracer")
            assert tracer is not None


def test_agent_span_sets_attributes():
    """The agent_span context manager must set agent_id on the span."""
    with patch("backend.observability.tracing.register"):
        with patch("backend.observability.tracing.LangchainInstrumentor"):
            from importlib import reload
            import backend.observability.tracing as tracing_mod
            reload(tracing_mod)
            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = lambda s: mock_span
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
            tracing_mod._tracer = mock_tracer
            with tracing_mod.agent_span("test-agent-id"):
                mock_span.set_attribute.assert_called_with("agent_id", "test-agent-id")
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/observability/test_tracing.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.observability'`

- [ ] **Step 3: Create `backend/observability/__init__.py`**

```python
# backend/observability/__init__.py
```

- [ ] **Step 4: Create `backend/observability/tracing.py`**

```python
"""
backend/observability/tracing.py
---------------------------------
Phoenix OpenTelemetry tracing setup for Ordo V4.
Call setup_tracing() once during FastAPI lifespan before the DB pool opens.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from phoenix.otel import register
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

logger = logging.getLogger(__name__)

_tracer_provider = None
_tracer = None


def setup_tracing(
    endpoint: str = "http://localhost:6006/v1/traces",
    project_name: str = "ordo",
) -> trace.TracerProvider:
    """
    Register Phoenix as the OTel trace backend and instrument LangChain.

    Must be called before the FastAPI DB pool opens so that all LLM calls
    within the lifespan are captured.

    Args:
        endpoint: Phoenix OTLP HTTP endpoint for trace ingestion.
        project_name: Logical project name shown in Phoenix UI.

    Returns:
        The configured TracerProvider.
    """
    global _tracer_provider, _tracer

    try:
        _tracer_provider = register(
            endpoint=endpoint,
            project_name=project_name,
        )
        logger.info(
            "Phoenix OTel tracing registered",
            extra={"endpoint": endpoint, "project": project_name},
        )
    except Exception as exc:
        logger.warning(
            "Phoenix tracing registration failed — traces will not be captured. "
            "Is ordo-phoenix running on port 6006?",
            extra={"error": str(exc)},
        )
        # Degrade gracefully: return a no-op provider
        _tracer_provider = trace.get_tracer_provider()

    try:
        LangchainInstrumentor().instrument()
        logger.info("LangchainInstrumentor applied — all LLM calls will be traced")
    except Exception as exc:
        logger.warning("LangchainInstrumentor failed", extra={"error": str(exc)})

    _tracer = trace.get_tracer("ordo.backend")
    return _tracer_provider


def get_tracer(name: str = "ordo.backend") -> trace.Tracer:
    """Return a named tracer. safe to call after setup_tracing()."""
    return trace.get_tracer(name)


@contextmanager
def agent_span(agent_id: str, operation: str = "agent.invoke") -> Generator:
    """
    Context manager that wraps an agent invocation in an OTel span.

    Usage:
        with agent_span(agent_id="generalist"):
            result = await agent.invoke(input)

    Attributes set on the span:
        - agent_id: the agent registry ID
        - operation: dotted path name for the span (default: "agent.invoke")
    """
    global _tracer
    if _tracer is None:
        _tracer = get_tracer()

    with _tracer.start_as_current_span(operation) as span:
        span.set_attribute("agent_id", agent_id)
        yield span
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/observability/test_tracing.py -v
```

Expected:
```
tests/observability/test_tracing.py::test_setup_tracing_returns_tracer_provider PASSED
tests/observability/test_tracing.py::test_get_tracer_returns_tracer PASSED
tests/observability/test_tracing.py::test_agent_span_sets_attributes PASSED
3 passed
```

- [ ] **Step 6: Wire setup_tracing() into FastAPI lifespan**

Open `backend/main.py`. In the `lifespan` async context manager, add the tracing call as the first thing before the DB pool opens:

```python
# At the top of backend/main.py, add:
from backend.observability.tracing import setup_tracing
from backend.config import settings

# Inside the lifespan function, before pool creation:
setup_tracing(
    endpoint=f"http://localhost:{settings.phoenix_port}/v1/traces",
    project_name="ordo",
)
```

Ensure `settings.phoenix_port` exists in `backend/config.py` (default `6006`). Add to `Settings` if missing:

```python
phoenix_port: int = Field(default=6006, validation_alias="ORDO_PHOENIX_PORT")
```

- [ ] **Step 7: Commit**

```bash
git add backend/observability/__init__.py backend/observability/tracing.py \
        tests/observability/__init__.py tests/observability/test_tracing.py \
        backend/main.py backend/config.py
git commit -m "feat(obs): add Phoenix OTel tracing module with LangChain instrumentation"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 1, run `make test` (or `pytest tests/ -v --tb=short`) and verify all tests pass. Confirm Phoenix is reachable at `http://localhost:6006` and that a test LLM call (e.g., invoke the generalist agent once) appears as a trace in the Phoenix UI before proceeding to Chunk 2.

---

## Chunk 2: Structured JSON Logging + Request Middleware

### Task 3: Structured JSON Logging Module

**Files:**
- Create: `backend/observability/logging.py`
- Create: `tests/observability/test_logging.py`

- [ ] **Step 1: Install python-json-logger**

```bash
source .venv/Scripts/activate
pip install python-json-logger>=2.0.7
```

Add to `backend/requirements.txt`:

```
python-json-logger>=2.0.7
```

- [ ] **Step 2: Write failing test**

Create `tests/observability/test_logging.py`:

```python
import logging
import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch


def test_setup_logging_creates_log_dir(tmp_path):
    """setup_logging() must create the log directory if it does not exist."""
    log_dir = tmp_path / "logs"
    assert not log_dir.exists()
    with patch.dict(os.environ, {"ORDO_DATA_DIR": str(tmp_path)}):
        from importlib import reload
        import backend.observability.logging as log_mod
        reload(log_mod)
        log_mod.setup_logging()
        assert log_dir.exists()


def test_root_logger_produces_json(tmp_path):
    """Root logger must emit JSON lines to ordo.log."""
    log_dir = tmp_path / "logs"
    with patch.dict(os.environ, {"ORDO_DATA_DIR": str(tmp_path)}):
        from importlib import reload
        import backend.observability.logging as log_mod
        reload(log_mod)
        log_mod.setup_logging()
        test_logger = logging.getLogger("ordo.test")
        test_logger.info("hello from test", extra={"key": "value"})

        log_file = log_dir / "ordo.log"
        assert log_file.exists()
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert record.get("message") == "hello from test"
        assert "timestamp" in record or "asctime" in record


def test_sidecar_log_goes_to_sidecar_file(tmp_path):
    """setup_logging(sidecar_name) must route to sidecar-{name}.log."""
    with patch.dict(os.environ, {"ORDO_DATA_DIR": str(tmp_path)}):
        from importlib import reload
        import backend.observability.logging as log_mod
        reload(log_mod)
        log_mod.setup_logging(sidecar_name="kairos")
        test_logger = logging.getLogger("ordo.sidecars.kairos")
        test_logger.info("kairos ran")

        sidecar_log = tmp_path / "logs" / "sidecar-kairos.log"
        assert sidecar_log.exists()
        lines = sidecar_log.read_text().strip().splitlines()
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert "kairos" in record.get("message", "")
```

- [ ] **Step 3: Run test — verify it fails**

```bash
pytest tests/observability/test_logging.py -v
```

Expected: `ImportError` or `AttributeError` — `backend.observability.logging` has no `setup_logging`.

- [ ] **Step 4: Create `backend/observability/logging.py`**

```python
"""
backend/observability/logging.py
---------------------------------
Structured JSON logging setup for Ordo V4.

Call setup_logging() in FastAPI lifespan (after setup_tracing, before pool).
Call setup_logging(sidecar_name="kairos") at the top of each slow sidecar's
main loop to route that sidecar's output to its own rotating log file while
also writing to the shared ordo.log.

Log files resolve under $ORDO_DATA_DIR/logs/ (defaults to ./logs/ if unset).
Max file size: 10 MB. Kept backups: 5.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

from pythonjsonlogger import jsonlogger


_LOG_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
_LOG_BACKUP_COUNT = 5
_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"

_configured = False


def _get_log_dir() -> Path:
    data_dir = os.environ.get("ORDO_DATA_DIR", ".")
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _make_json_handler(log_path: Path) -> logging.handlers.RotatingFileHandler:
    handler = logging.handlers.RotatingFileHandler(
        filename=str(log_path),
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    formatter = jsonlogger.JsonFormatter(
        fmt=_LOG_FORMAT,
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    return handler


def setup_logging(
    sidecar_name: str | None = None,
    level: int = logging.INFO,
) -> None:
    """
    Configure structured JSON logging for the Ordo backend.

    When called without arguments (FastAPI lifespan), configures the root
    logger with:
      - RotatingFileHandler → $ORDO_DATA_DIR/logs/ordo.log (JSON)
      - StreamHandler → stdout (JSON, for dev/PM2 log visibility)

    When called with sidecar_name (slow sidecar main loop), additionally
    attaches a sidecar-specific RotatingFileHandler so that sidecar output
    goes to both ordo.log and sidecar-{name}.log.

    Args:
        sidecar_name: If set, also writes to sidecar-{name}.log.
        level: Root logging level (default INFO).
    """
    global _configured
    log_dir = _get_log_dir()

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if called more than once (e.g. in tests)
    if not _configured:
        # Shared ordo.log handler
        main_handler = _make_json_handler(log_dir / "ordo.log")
        root_logger.addHandler(main_handler)

        # Console handler (human-readable JSON for PM2 / dev terminal)
        console_handler = logging.StreamHandler()
        console_formatter = jsonlogger.JsonFormatter(
            fmt=_LOG_FORMAT,
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        _configured = True

    if sidecar_name:
        sidecar_logger = logging.getLogger(f"ordo.sidecars.{sidecar_name}")
        # Prevent duplicate entries from propagation — sidecar still propagates
        # to root (and therefore to ordo.log) via the root handlers set above.
        sidecar_handler = _make_json_handler(log_dir / f"sidecar-{sidecar_name}.log")
        sidecar_logger.addHandler(sidecar_handler)
        sidecar_logger.info(
            f"{sidecar_name} sidecar logging initialized",
            extra={"sidecar": sidecar_name},
        )
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/observability/test_logging.py -v
```

Expected:
```
tests/observability/test_logging.py::test_setup_logging_creates_log_dir PASSED
tests/observability/test_logging.py::test_root_logger_produces_json PASSED
tests/observability/test_logging.py::test_sidecar_log_goes_to_sidecar_file PASSED
3 passed
```

- [ ] **Step 6: Wire setup_logging() into FastAPI lifespan**

In `backend/main.py`, inside the `lifespan` function, call `setup_logging()` immediately after `setup_tracing()`:

```python
from backend.observability.logging import setup_logging

# In lifespan, after setup_tracing():
setup_logging()
```

- [ ] **Step 7: Commit**

```bash
git add backend/observability/logging.py backend/requirements.txt \
        tests/observability/test_logging.py backend/main.py
git commit -m "feat(obs): structured JSON logging module with rotating file handlers"
```

---

### Task 4: FastAPI Request Logging Middleware

**Files:**
- Create: `backend/observability/middleware.py`
- Create: `tests/observability/test_middleware.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write failing test**

Create `tests/observability/test_middleware.py`:

```python
import pytest
import time
import logging
import json
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def homepage(request):
    return JSONResponse({"ok": True})


def make_test_app():
    from backend.observability.middleware import LoggingMiddleware
    app = Starlette(routes=[Route("/test", homepage)])
    app.add_middleware(LoggingMiddleware)
    return app


def test_middleware_logs_request(caplog):
    """LoggingMiddleware must emit a JSON-compatible log record per request."""
    with caplog.at_level(logging.INFO, logger="ordo.http"):
        client = TestClient(make_test_app())
        response = client.get("/test")
        assert response.status_code == 200

    # Find the access log record
    access_records = [r for r in caplog.records if r.name == "ordo.http"]
    assert len(access_records) == 1
    record = access_records[0]
    assert hasattr(record, "method") and record.method == "GET"
    assert hasattr(record, "path") and record.path == "/test"
    assert hasattr(record, "status_code") and record.status_code == 200
    assert hasattr(record, "duration_ms")
    assert float(record.duration_ms) >= 0


def test_middleware_captures_agent_id_header(caplog):
    """LoggingMiddleware must capture X-Agent-Id header when present."""
    with caplog.at_level(logging.INFO, logger="ordo.http"):
        client = TestClient(make_test_app())
        client.get("/test", headers={"X-Agent-Id": "generalist"})

    access_records = [r for r in caplog.records if r.name == "ordo.http"]
    assert len(access_records) == 1
    assert access_records[0].agent_id == "generalist"


def test_middleware_records_500_status(caplog):
    """LoggingMiddleware must log 5xx responses correctly."""
    async def failing(request):
        raise RuntimeError("boom")

    from backend.observability.middleware import LoggingMiddleware
    from starlette.middleware.errors import ServerErrorMiddleware
    app = Starlette(routes=[Route("/fail", failing)])
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ServerErrorMiddleware, debug=False)

    with caplog.at_level(logging.INFO, logger="ordo.http"):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/fail")

    access_records = [r for r in caplog.records if r.name == "ordo.http"]
    assert len(access_records) == 1
    assert access_records[0].status_code == 500
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/observability/test_middleware.py -v
```

Expected: `ImportError: cannot import name 'LoggingMiddleware' from 'backend.observability.middleware'`

- [ ] **Step 3: Create `backend/observability/middleware.py`**

```python
"""
backend/observability/middleware.py
------------------------------------
ASGI middleware that emits a structured JSON log record for every HTTP request.

Fields logged per request:
  method       — HTTP verb
  path         — URL path (no query string)
  status_code  — response status
  duration_ms  — float, wall-clock time from first byte received to response sent
  agent_id     — value of X-Agent-Id request header (if present, else None)

The logger name is "ordo.http" so log records can be filtered independently
from application logs.

Add to FastAPI with:
    from backend.observability.middleware import LoggingMiddleware
    app.add_middleware(LoggingMiddleware)
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("ordo.http")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured request/response logging middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        status_code = 500  # default — overwritten on success

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            agent_id = request.headers.get("X-Agent-Id")

            logger.info(
                f"{request.method} {request.url.path} {status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "agent_id": agent_id,
                },
            )

        return response
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/observability/test_middleware.py -v
```

Expected:
```
tests/observability/test_middleware.py::test_middleware_logs_request PASSED
tests/observability/test_middleware.py::test_middleware_captures_agent_id_header PASSED
tests/observability/test_middleware.py::test_middleware_records_500_status PASSED
3 passed
```

- [ ] **Step 5: Register middleware in backend/main.py**

```python
from backend.observability.middleware import LoggingMiddleware

# After app = FastAPI(...):
app.add_middleware(LoggingMiddleware)
```

- [ ] **Step 6: Commit**

```bash
git add backend/observability/middleware.py backend/main.py \
        tests/observability/test_middleware.py
git commit -m "feat(obs): ASGI request logging middleware with structured JSON fields"
```

---

### Task 5: Sidecar-Level Logging Integration

**Files:**
- Modify: `backend/sidecars/kairos.py`
- Modify: `backend/sidecars/oneiros.py`
- Modify: `backend/sidecars/praxis.py`
- Modify: `backend/sidecars/psyche.py`
- Modify: `backend/sidecars/augur.py`

- [ ] **Step 1: Add setup_logging(sidecar_name=...) to each slow sidecar main loop**

For each slow sidecar file, locate the `if __name__ == "__main__":` block (or the top-level `async def main()` entry point) and add the logging setup call as the first statement. Pattern for each sidecar:

```python
# At the top of sidecars/kairos.py (and each other slow sidecar):
from backend.observability.logging import setup_logging

# In the main() function or __main__ block, as the very first line:
setup_logging(sidecar_name="kairos")   # replace "kairos" with the sidecar name
logger = logging.getLogger("ordo.sidecars.kairos")
```

Apply the same pattern to: `oneiros`, `praxis`, `psyche`, `augur`, substituting the sidecar name in both the `setup_logging` call and the `getLogger` path.

- [ ] **Step 2: Verify by running one sidecar dry-run**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
python -c "
from backend.observability.logging import setup_logging
import logging
setup_logging(sidecar_name='kairos')
logging.getLogger('ordo.sidecars.kairos').info('dry-run test')
print('OK')
"
```

Expected: `OK` printed. Verify that `$ORDO_DATA_DIR/logs/sidecar-kairos.log` was created and contains a JSON line.

- [ ] **Step 3: Commit**

```bash
git add backend/sidecars/kairos.py backend/sidecars/oneiros.py \
        backend/sidecars/praxis.py backend/sidecars/psyche.py \
        backend/sidecars/augur.py
git commit -m "feat(obs): wire structured JSON logging into all slow sidecar main loops"
```

---

### Task 6: Sidecar Status API Route

**Files:**
- Create: `backend/routers/sidecars.py`
- Create: `tests/test_sidecar_status.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_sidecar_status.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
import datetime


MOCK_STATUS_ROWS = [
    {
        "name": "kairos",
        "last_run_at": datetime.datetime(2026, 4, 3, 10, 0, 0),
        "last_job_status": "completed",
        "turn_count_since_last_run": 5,
        "last_output_preview": "Built 3 new topic nodes from conversation batch.",
    },
    {
        "name": "oneiros",
        "last_run_at": None,
        "last_job_status": "never_run",
        "turn_count_since_last_run": 0,
        "last_output_preview": None,
    },
]


@pytest.mark.asyncio
async def test_sidecar_status_returns_list():
    """GET /sidecar/status returns a list of sidecar status objects."""
    with patch("backend.routers.sidecars.fetch_sidecar_statuses", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = MOCK_STATUS_ROWS
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sidecar/status")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2


@pytest.mark.asyncio
async def test_sidecar_status_fields():
    """Each sidecar status object has required fields."""
    with patch("backend.routers.sidecars.fetch_sidecar_statuses", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = MOCK_STATUS_ROWS
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sidecar/status")
        data = response.json()
        first = data[0]
        assert "name" in first
        assert "last_run_at" in first
        assert "last_job_status" in first
        assert "turn_count_since_last_run" in first
        assert "last_output_preview" in first


@pytest.mark.asyncio
async def test_sidecar_status_preview_truncated():
    """last_output_preview must be at most 100 characters."""
    long_row = {**MOCK_STATUS_ROWS[0], "last_output_preview": "x" * 200}
    with patch("backend.routers.sidecars.fetch_sidecar_statuses", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [long_row]
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sidecar/status")
        data = response.json()
        assert len(data[0]["last_output_preview"]) <= 100
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_sidecar_status.py -v
```

Expected: `ImportError` or 404 — route does not exist yet.

- [ ] **Step 3: Create `backend/routers/sidecars.py`**

```python
"""
backend/routers/sidecars.py
----------------------------
Sidecar status API.

GET /sidecar/status
    Returns per-sidecar: name, last_run_at, last_job_status,
    turn_count_since_last_run, last_output_preview (first 100 chars).

Data source: sidecar_jobs table — one row per completed or in-flight job.
The query returns the most recent job row for each sidecar name.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sidecar", tags=["sidecars"])

KNOWN_SIDECARS = ["kairos", "oneiros", "praxis", "psyche", "augur"]


class SidecarStatusItem(BaseModel):
    name: str
    last_run_at: str | None
    last_job_status: str
    turn_count_since_last_run: int
    last_output_preview: str | None


async def fetch_sidecar_statuses(pool: Any) -> list[dict]:
    """
    Query the sidecar_jobs table for the most recent job per sidecar.
    Returns a list of dicts with sidecar status fields.
    Falls back to a "never_run" entry for any sidecar not found in the table.
    """
    query = """
        SELECT DISTINCT ON (sidecar_name)
            sidecar_name                        AS name,
            completed_at                        AS last_run_at,
            status                              AS last_job_status,
            turn_count_at_trigger               AS turn_count_since_last_run,
            LEFT(result_summary, 100)           AS last_output_preview
        FROM sidecar_jobs
        ORDER BY sidecar_name, created_at DESC
    """
    rows = await pool.fetch(query)
    results = {row["name"]: dict(row) for row in rows}

    # Ensure all known sidecars appear — fill missing with never_run
    output = []
    for name in KNOWN_SIDECARS:
        if name in results:
            entry = results[name]
            # Truncate preview defensively
            if entry.get("last_output_preview"):
                entry["last_output_preview"] = entry["last_output_preview"][:100]
            # Serialize datetime to ISO string
            if entry.get("last_run_at") and hasattr(entry["last_run_at"], "isoformat"):
                entry["last_run_at"] = entry["last_run_at"].isoformat()
        else:
            entry = {
                "name": name,
                "last_run_at": None,
                "last_job_status": "never_run",
                "turn_count_since_last_run": 0,
                "last_output_preview": None,
            }
        output.append(entry)

    return output


@router.get("/status", response_model=list[SidecarStatusItem])
async def get_sidecar_status(request: Request):
    """
    Return the status of all 5 slow sidecars.

    Polls the sidecar_jobs table — no live process introspection.
    The last completed job row per sidecar is used.
    """
    pool = request.app.state.pool
    statuses = await fetch_sidecar_statuses(pool)
    return statuses
```

- [ ] **Step 4: Register the router in backend/main.py**

```python
from backend.routers.sidecars import router as sidecars_router

# After existing router registrations:
app.include_router(sidecars_router)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_sidecar_status.py -v
```

Expected:
```
tests/test_sidecar_status.py::test_sidecar_status_returns_list PASSED
tests/test_sidecar_status.py::test_sidecar_status_fields PASSED
tests/test_sidecar_status.py::test_sidecar_status_preview_truncated PASSED
3 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/sidecars.py backend/main.py tests/test_sidecar_status.py
git commit -m "feat(obs): GET /sidecar/status route — per-sidecar health from sidecar_jobs table"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 2, run the full test suite (`pytest tests/ -v --tb=short`) and confirm all tests pass. Manually verify that `$ORDO_DATA_DIR/logs/ordo.log` is being written in JSON format by making a request to the running FastAPI server and tailing the log. Confirm `GET /sidecar/status` returns the correct shape via `curl http://localhost:8000/sidecar/status`. Then proceed to Chunk 3.

---

## Chunk 3: UI Panels — Sidecar Slide-In, Token Budget, Phoenix Status Bar

### Task 7: Sidecar Slide-In Panel

**Files:**
- Create: `frontend/src/panels/sidecars.ts`
- Modify: `frontend/src/status-bar.ts` (wire the "●8/8 sidecars" click handler)

- [ ] **Step 1: Create `frontend/src/panels/sidecars.ts`**

This panel is activated when the user clicks the "●8/8 sidecars" indicator in the status bar. It fetches `GET /sidecar/status`, renders a table, and auto-refreshes every 30 seconds. Slow sidecars have a "Run now" button.

```typescript
// frontend/src/panels/sidecars.ts
// Sidecar slide-in panel — status, last-run, turn counter, last output.

const API_BASE = "http://localhost:8000";
const POLL_INTERVAL_MS = 30_000;
const SLOW_SIDECARS = new Set(["kairos", "oneiros", "praxis", "psyche", "augur"]);

interface SidecarStatus {
  name: string;
  last_run_at: string | null;
  last_job_status: string;
  turn_count_since_last_run: number;
  last_output_preview: string | null;
}

/**
 * Renders the sidecar slide-in panel into the provided container element.
 * Call mount() to attach it, unmount() when the panel is hidden.
 */
export class SidecarPanel {
  private container: HTMLElement;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private expandedRows: Set<string> = new Set();

  constructor(container: HTMLElement) {
    this.container = container;
  }

  mount(): void {
    this.render();
    this.pollTimer = setInterval(() => this.render(), POLL_INTERVAL_MS);
  }

  unmount(): void {
    if (this.pollTimer !== null) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private async fetchStatus(): Promise<SidecarStatus[]> {
    const response = await fetch(`${API_BASE}/sidecar/status`);
    if (!response.ok) {
      throw new Error(`Sidecar status fetch failed: ${response.status}`);
    }
    return response.json() as Promise<SidecarStatus[]>;
  }

  private statusDot(jobStatus: string): string {
    switch (jobStatus) {
      case "completed":  return '<span class="dot dot--green" title="OK">●</span>';
      case "in_flight":  return '<span class="dot dot--yellow" title="Running">●</span>';
      case "failed":     return '<span class="dot dot--red" title="Failed">●</span>';
      case "never_run":  return '<span class="dot dot--gray" title="Never run">○</span>';
      default:           return '<span class="dot dot--gray">○</span>';
    }
  }

  private formatTimestamp(iso: string | null): string {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  private async triggerRunNow(sidecarName: string): Promise<void> {
    try {
      const resp = await fetch(`${API_BASE}/sidecar/${sidecarName}/trigger`, {
        method: "POST",
      });
      if (!resp.ok) {
        console.warn(`Run-now for ${sidecarName} failed: ${resp.status}`);
      }
    } catch (err) {
      console.error(`Run-now error for ${sidecarName}:`, err);
    }
    // Refresh panel after triggering
    await this.render();
  }

  private async render(): Promise<void> {
    let statuses: SidecarStatus[];
    try {
      statuses = await this.fetchStatus();
    } catch (err) {
      this.container.innerHTML = `<p class="panel-error">Could not load sidecar status: ${err}</p>`;
      return;
    }

    const rows = statuses.map((s) => {
      const isExpanded = this.expandedRows.has(s.name);
      const expandedClass = isExpanded ? "row--expanded" : "";
      const previewText = s.last_output_preview ?? "(no output)";

      const runNowButton = SLOW_SIDECARS.has(s.name)
        ? `<button class="btn-run-now" data-sidecar="${s.name}">Run now</button>`
        : "";

      const expandedContent = isExpanded
        ? `<tr class="row-expanded-content" data-name="${s.name}">
             <td colspan="5"><pre class="output-preview">${previewText}</pre></td>
           </tr>`
        : "";

      return `
        <tr class="sidecar-row ${expandedClass}" data-name="${s.name}">
          <td>${this.statusDot(s.last_job_status)}</td>
          <td class="col-name">${s.name}</td>
          <td>${this.formatTimestamp(s.last_run_at)}</td>
          <td>${s.turn_count_since_last_run}</td>
          <td>${runNowButton}</td>
        </tr>
        ${expandedContent}
      `;
    }).join("");

    this.container.innerHTML = `
      <div class="sidecar-panel">
        <h2 class="panel-title">Sidecar Status</h2>
        <table class="sidecar-table">
          <thead>
            <tr>
              <th></th>
              <th>Sidecar</th>
              <th>Last Run</th>
              <th>Turns Since</th>
              <th></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
        <p class="panel-footer">Auto-refreshes every 30 seconds</p>
      </div>
    `;

    // Attach click handlers for row expand/collapse
    this.container.querySelectorAll<HTMLTableRowElement>("tr.sidecar-row").forEach((row) => {
      row.addEventListener("click", (e) => {
        const name = row.dataset.name!;
        // Don't expand when clicking "Run now"
        if ((e.target as HTMLElement).classList.contains("btn-run-now")) return;
        if (this.expandedRows.has(name)) {
          this.expandedRows.delete(name);
        } else {
          this.expandedRows.add(name);
        }
        void this.render();
      });
    });

    // Attach "Run now" button handlers
    this.container.querySelectorAll<HTMLButtonElement>(".btn-run-now").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const name = btn.dataset.sidecar!;
        void this.triggerRunNow(name);
      });
    });
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx tsc --noEmit
```

Expected: No errors. If `SidecarPanel` imports cause errors, check that `tsconfig.json` includes `frontend/src/panels/`.

- [ ] **Step 3: Wire the "●8/8 sidecars" click handler in status-bar.ts**

Open `frontend/src/status-bar.ts`. Locate the sidecar indicator element (it should already render the text or count). Add a click handler that instantiates `SidecarPanel` and shows the slide-in container:

```typescript
import { SidecarPanel } from "./panels/sidecars";

// Assume sidecarIndicator is the DOM element for "●8/8 sidecars"
// and slideInContainer is the panel mount point (already in the DOM, hidden by default)

let sidecarPanel: SidecarPanel | null = null;

sidecarIndicator.addEventListener("click", () => {
  const container = document.getElementById("slide-in-panel")!;
  const isVisible = container.classList.contains("visible");

  if (isVisible) {
    container.classList.remove("visible");
    sidecarPanel?.unmount();
    sidecarPanel = null;
  } else {
    container.classList.add("visible");
    sidecarPanel = new SidecarPanel(container);
    sidecarPanel.mount();
  }
});
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/panels/sidecars.ts frontend/src/status-bar.ts
git commit -m "feat(obs): sidecar slide-in panel with auto-refresh, expand rows, run-now buttons"
```

---

### Task 8: Token Budget Status Bar Display

**Files:**
- Modify: `frontend/src/status-bar.ts`

- [ ] **Step 1: Add budget polling to status-bar.ts**

The status bar already exists. Add a `pollBudget()` function that calls `GET /budget` every 60 seconds and updates the budget indicator element. The display format is: `"Anthropic: 45K/100K (resets in 2h30m)"`.

Add to `frontend/src/status-bar.ts`:

```typescript
// --- Token Budget Display ---

interface BudgetEntry {
  provider: string;
  tokens_used: number;
  token_budget: number;
  window_reset_at: string;  // ISO datetime
}

function formatTokens(n: number): string {
  return n >= 1000 ? `${Math.round(n / 1000)}K` : String(n);
}

function formatResetCountdown(resetAt: string): string {
  const diff = new Date(resetAt).getTime() - Date.now();
  if (diff <= 0) return "resetting";
  const totalMinutes = Math.floor(diff / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours}h${minutes}m` : `${minutes}m`;
}

function budgetColor(used: number, budget: number): string {
  const pct = budget > 0 ? used / budget : 0;
  if (pct < 0.5)  return "budget--green";
  if (pct < 0.8)  return "budget--yellow";
  return "budget--red";
}

async function fetchBudget(): Promise<BudgetEntry[]> {
  const resp = await fetch(`${API_BASE}/budget`);
  if (!resp.ok) throw new Error(`Budget fetch failed: ${resp.status}`);
  return resp.json() as Promise<BudgetEntry[]>;
}

function renderBudget(entries: BudgetEntry[], container: HTMLElement): void {
  const items = entries.map((e) => {
    const used = formatTokens(e.tokens_used);
    const total = formatTokens(e.token_budget);
    const countdown = formatResetCountdown(e.window_reset_at);
    const colorClass = budgetColor(e.tokens_used, e.token_budget);
    return `<span class="budget-item ${colorClass}" title="Resets in ${countdown}">`
      + `${e.provider}: ${used}/${total} (${countdown})`
      + `</span>`;
  }).join(" · ");
  container.innerHTML = items || "—";
}

export function startBudgetPolling(container: HTMLElement): void {
  const poll = async () => {
    try {
      const entries = await fetchBudget();
      renderBudget(entries, container);
    } catch {
      container.textContent = "budget unavailable";
    }
  };
  void poll();
  setInterval(poll, 60_000);
}
```

Then call `startBudgetPolling(budgetContainer)` in status-bar initialization, where `budgetContainer` is the DOM element reserved for the budget display.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/status-bar.ts
git commit -m "feat(obs): token budget status bar — polls GET /budget, color-coded green/yellow/red"
```

---

### Task 9: Phoenix Health Link in Status Bar

**Files:**
- Modify: `frontend/src/status-bar.ts`

- [ ] **Step 1: Add Phoenix health probe and link to status-bar.ts**

Phoenix is a local process. The status bar shows "Phoenix ●" — green if `http://localhost:6006` responds, red if not. Clicking it calls `shell.openExternal("http://localhost:6006")` (Electron) or `window.open` (browser LAN client fallback).

Add to `frontend/src/status-bar.ts`:

```typescript
// --- Phoenix Health Link ---

const PHOENIX_URL = "http://localhost:6006";

async function checkPhoenixHealth(): Promise<boolean> {
  try {
    const resp = await fetch(`${PHOENIX_URL}/healthz`, {
      method: "GET",
      signal: AbortSignal.timeout(2000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

function renderPhoenixIndicator(container: HTMLElement, healthy: boolean): void {
  const colorClass = healthy ? "phoenix--green" : "phoenix--red";
  const label = healthy ? "Phoenix ●" : "Phoenix ○";
  container.innerHTML = `<span class="phoenix-link ${colorClass}" title="Open Phoenix UI">${label}</span>`;
  container.onclick = () => {
    // Electron environment: use shell.openExternal
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const electronAPI = (window as any).electronAPI;
    if (electronAPI?.openExternal) {
      electronAPI.openExternal(PHOENIX_URL);
    } else {
      // LAN browser fallback
      window.open(PHOENIX_URL, "_blank");
    }
  };
}

export function startPhoenixHealthPolling(container: HTMLElement): void {
  const poll = async () => {
    const healthy = await checkPhoenixHealth();
    renderPhoenixIndicator(container, healthy);
  };
  void poll();
  // Check every 60 seconds — Phoenix is a local process, unlikely to flap
  setInterval(poll, 60_000);
}
```

Call `startPhoenixHealthPolling(phoenixContainer)` in status-bar initialization.

- [ ] **Step 2: Expose openExternal in Electron preload**

Open `frontend/electron/preload.ts` (or `preload.js`). Add the IPC bridge for `openExternal` if not already present:

```typescript
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  // ... existing methods ...
  openExternal: (url: string) => ipcRenderer.invoke("open-external", url),
});
```

Open `frontend/electron/main.ts` (or `main.js`). Register the IPC handler:

```typescript
import { shell, ipcMain } from "electron";

ipcMain.handle("open-external", async (_event, url: string) => {
  await shell.openExternal(url);
});
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: End-to-end smoke test**

With all PM2 processes running:

```bash
pm2 status
```

Expected: `ordo-phoenix` shows `online`.

Open the Electron app. The status bar should show "Phoenix ●" in green. Click it — Phoenix UI at `http://localhost:6006` should open in the default browser.

Make a conversation turn through the FastAPI backend. Go to Phoenix UI → Traces. Confirm:
- A trace appears named `agent.invoke` (or the LangChain trace from `LangchainInstrumentor`)
- The trace has LLM spans with token counts and duration
- Inputs and outputs are visible in the span detail

Tail the log file:

```bash
tail -f "$ORDO_DATA_DIR/logs/ordo.log"
```

Expected: JSON lines appearing with `method`, `path`, `status_code`, `duration_ms` for each request.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/status-bar.ts frontend/electron/preload.ts frontend/electron/main.ts
git commit -m "feat(obs): Phoenix health indicator in status bar with Electron shell.openExternal"
```

---

### Task 10: Full Observability Stack Smoke Test

**Files:**
- No new files. This task validates the entire Phase 9 stack end-to-end.

- [ ] **Step 1: Run the full test suite**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/ -v --tb=short
```

Expected: All tests pass, including:
- `tests/observability/test_tracing.py` — 3 passed
- `tests/observability/test_logging.py` — 3 passed
- `tests/observability/test_middleware.py` — 3 passed
- `tests/test_sidecar_status.py` — 3 passed

- [ ] **Step 2: Verify PM2 process list**

```bash
pm2 status
```

Expected: `ordo-phoenix` is `online`. `fastapi` is `online`. All slow sidecar PM2 processes are `online` or `stopped` (they are event-driven, not always running).

- [ ] **Step 3: Verify Phoenix UI trace capture**

```bash
# Make a test request to the agent endpoint
curl -s -X POST http://localhost:8000/agents/generalist/invoke \
     -H "Content-Type: application/json" \
     -d '{"input": "Hello Ordo, this is a Phase 9 observability test."}' | head -c 200
```

Open `http://localhost:6006` in the browser. Navigate to Traces. Confirm the agent invocation trace appears with:
- LLM call spans (model name, token counts, latency)
- `agent.invoke` parent span with `agent_id` attribute
- Full input/output visible

- [ ] **Step 4: Verify structured logs**

```bash
tail -n 5 "$ORDO_DATA_DIR/logs/ordo.log" | python -m json.tool
```

Expected: Valid JSON objects with `timestamp`, `level`, `message`, and HTTP fields.

- [ ] **Step 5: Verify sidecar slide-in panel**

In the Electron app, click "●8/8 sidecars" in the status bar. The slide-in panel should appear with a table of 5 sidecar rows (kairos, oneiros, praxis, psyche, augur). Rows without any run history show `last_job_status: never_run` and `○`.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat(obs): Phase 9 observability stack — Phoenix traces, JSON logs, sidecar panel, budget bar"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 3, run `pytest tests/ -v --tb=short` one final time and confirm 0 failures. Manually complete the Step 3 Phoenix trace verification. Confirm the sidecar panel loads and auto-refreshes. Confirm the budget bar updates on a 60-second cycle. This completes Phase 9. Tag the commit: `git tag v4.0.0-phase9-complete`.
