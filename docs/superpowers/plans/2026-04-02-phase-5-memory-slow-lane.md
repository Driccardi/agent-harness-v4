# Ordo Phase 5: Memory Core Slow Lane Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the five slow-lane sidecars (Kairos, Oneiros, Praxis, Psyche, Augur) as PM2-managed processes that poll the `sidecar_jobs` PostgreSQL table for work. Each sidecar claims one job atomically, executes it, marks it complete, and exits cleanly. PM2 restarts on failure. FastAPI writes trigger rows via `slow_triggers.py`. A `GET /sidecar/status` route exposes runtime health to the UI status panel.

**Architecture:** Slow sidecars are stateless PM2 workers. They do not run continuously — they claim a job, execute it, and exit(0). PM2's `stop_exit_codes: [0]` policy prevents restart on clean exit; non-zero exit (unhandled exception) triggers restart so no job is silently dropped. All sidecar coordination passes through the `sidecar_jobs` table — no Redis, no pub/sub. FastAPI writes trigger rows; sidecars consume them. Atomic claiming uses `SELECT ... FOR UPDATE SKIP LOCKED`.

**Tech Stack:** Python 3.12, asyncpg, LangChain (Claude Sonnet/Opus for synthesis), PostgreSQL 16 + pgvector, PM2 (`stop_exit_codes: [0]`), pytest + pytest-asyncio. `ORDO_DATA_DIR` env var anchors all runtime file paths. `ANTHROPIC_API_KEY` required for all LLM synthesis calls.

---

## Chunk 1: Sidecar Base + Kairos + Oneiros

### Task 1: SlowSidecar Base Class

**Files:**
- Create: `backend/sidecars/__init__.py`
- Create: `backend/sidecars/slow/__init__.py`
- Create: `backend/sidecars/slow/base.py`
- Create: `tests/sidecars/__init__.py`
- Create: `tests/sidecars/test_slow_base.py`

- [ ] **Step 1: Write failing test**

Create `tests/sidecars/__init__.py` (empty) and `tests/sidecars/test_slow_base.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.sidecars.slow.base import SlowSidecar


class ConcreteTestSidecar(SlowSidecar):
    """Minimal concrete subclass for testing the abstract base."""
    sidecar_name = "test_sidecar"

    async def run(self, job: dict) -> None:
        pass  # no-op


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_claim_job_returns_none_when_no_pending(mock_pool):
    pool, conn = mock_pool
    conn.fetchrow = AsyncMock(return_value=None)
    sidecar = ConcreteTestSidecar(pool=pool)
    result = await sidecar.claim_job()
    assert result is None


@pytest.mark.asyncio
async def test_claim_job_returns_dict_when_job_exists(mock_pool):
    pool, conn = mock_pool
    fake_job = {"id": "job-uuid-001", "sidecar": "test_sidecar", "payload": {}, "status": "pending"}
    conn.fetchrow = AsyncMock(return_value=fake_job)
    sidecar = ConcreteTestSidecar(pool=pool)
    result = await sidecar.claim_job()
    assert result is not None
    assert result["id"] == "job-uuid-001"


@pytest.mark.asyncio
async def test_complete_job_updates_status(mock_pool):
    pool, conn = mock_pool
    conn.execute = AsyncMock()
    sidecar = ConcreteTestSidecar(pool=pool)
    await sidecar.complete_job("job-uuid-001")
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert "completed" in call_args[0]
    assert "job-uuid-001" in call_args


@pytest.mark.asyncio
async def test_fail_job_records_error(mock_pool):
    pool, conn = mock_pool
    conn.execute = AsyncMock()
    sidecar = ConcreteTestSidecar(pool=pool)
    await sidecar.fail_job("job-uuid-001", "something went wrong")
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert "failed" in call_args[0]
    assert "something went wrong" in str(call_args)


@pytest.mark.asyncio
async def test_main_loop_exits_zero_when_no_job(mock_pool):
    pool, conn = mock_pool
    conn.fetchrow = AsyncMock(return_value=None)
    sidecar = ConcreteTestSidecar(pool=pool)
    # Should return without raising — exit(0) path
    result = await sidecar.execute()
    assert result == 0


@pytest.mark.asyncio
async def test_main_loop_runs_and_completes_job(mock_pool):
    pool, conn = mock_pool
    fake_job = {"id": "job-uuid-002", "sidecar": "test_sidecar", "payload": {}, "status": "pending"}
    conn.fetchrow = AsyncMock(return_value=fake_job)
    conn.execute = AsyncMock()
    sidecar = ConcreteTestSidecar(pool=pool)
    result = await sidecar.execute()
    assert result == 0
    # complete_job must have been called
    assert conn.execute.called


@pytest.mark.asyncio
async def test_main_loop_calls_fail_job_on_run_exception(mock_pool):
    pool, conn = mock_pool
    fake_job = {"id": "job-uuid-003", "sidecar": "test_sidecar", "payload": {}, "status": "pending"}
    conn.fetchrow = AsyncMock(return_value=fake_job)
    conn.execute = AsyncMock()

    class FailingSidecar(SlowSidecar):
        sidecar_name = "test_sidecar"
        async def run(self, job: dict) -> None:
            raise RuntimeError("intentional failure")

    sidecar = FailingSidecar(pool=pool)
    result = await sidecar.execute()
    assert result == 1
    call_args_str = str(conn.execute.call_args_list)
    assert "failed" in call_args_str
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/sidecars/test_slow_base.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars'`

- [ ] **Step 3: Create `backend/sidecars/__init__.py` and `backend/sidecars/slow/__init__.py`**

Both files are empty. Create them:

```bash
mkdir -p backend/sidecars/slow
touch backend/sidecars/__init__.py backend/sidecars/slow/__init__.py
```

- [ ] **Step 4: Create `backend/sidecars/slow/base.py`**

```python
"""
SlowSidecar base class.

Each slow sidecar is a stateless PM2 worker:
  1. Claim one pending job from sidecar_jobs (SKIP LOCKED).
  2. If no job: exit(0) — PM2 stop_exit_codes:[0] suppresses restart.
  3. Run the job.
  4. Mark complete → exit(0).
  5. On exception: mark failed → exit(1) — PM2 restarts the process.
"""

import asyncio
import logging
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


class SlowSidecar(ABC):
    """Abstract base for all slow-lane sidecar workers."""

    sidecar_name: str  # Must be set by subclass — matches sidecar_jobs.sidecar column

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def claim_job(self) -> Optional[dict]:
        """
        Atomically claim one pending job for this sidecar.

        Uses SELECT ... FOR UPDATE SKIP LOCKED so that concurrent PM2 restarts
        cannot double-claim the same row.

        Returns the job dict or None if no pending job exists.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE sidecar_jobs
                SET status = 'in_flight',
                    started_at = $1
                WHERE id = (
                    SELECT id FROM sidecar_jobs
                    WHERE sidecar = $2
                      AND status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
                """,
                datetime.now(timezone.utc),
                self.sidecar_name,
            )
        if row is None:
            return None
        return dict(row)

    async def complete_job(self, job_id: str) -> None:
        """Mark a claimed job as completed."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sidecar_jobs
                SET status = 'completed',
                    completed_at = $1
                WHERE id = $2
                """,
                datetime.now(timezone.utc),
                job_id,
            )

    async def fail_job(self, job_id: str, error: str) -> None:
        """Mark a claimed job as failed with an error message."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sidecar_jobs
                SET status = 'failed',
                    completed_at = $1,
                    error = $2
                WHERE id = $3
                """,
                datetime.now(timezone.utc),
                error[:2000],  # guard against oversized tracebacks
                job_id,
            )

    @abstractmethod
    async def run(self, job: dict) -> None:
        """Execute the sidecar's work for the given job. Subclasses must implement."""
        ...

    async def execute(self) -> int:
        """
        Main entry point. Returns exit code:
          0 — clean (no job found, or job completed successfully)
          1 — failure (exception during run; fail_job already called)
        """
        job = await self.claim_job()
        if job is None:
            logger.info("[%s] No pending jobs. Exiting cleanly.", self.sidecar_name)
            return 0

        logger.info("[%s] Claimed job %s", self.sidecar_name, job["id"])
        try:
            await self.run(job)
            await self.complete_job(job["id"])
            logger.info("[%s] Job %s completed.", self.sidecar_name, job["id"])
            return 0
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.exception("[%s] Job %s failed: %s", self.sidecar_name, job["id"], error_msg)
            await self.fail_job(job["id"], error_msg)
            return 1


async def run_sidecar(sidecar_cls, dsn: str) -> None:
    """
    Helper used by each sidecar's __main__ entry point.
    Creates a pool, runs the sidecar, exits with the returned code.
    """
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=3)
    try:
        sidecar = sidecar_cls(pool=pool)
        code = await sidecar.execute()
    finally:
        await pool.close()
    sys.exit(code)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/sidecars/test_slow_base.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/sidecars/__init__.py backend/sidecars/slow/__init__.py backend/sidecars/slow/base.py tests/sidecars/__init__.py tests/sidecars/test_slow_base.py
git commit -m "feat: add SlowSidecar base class with atomic job claiming"
```

---

### Task 2: Kairos — Topic Graph Builder

**Files:**
- Create: `backend/sidecars/slow/kairos.py`
- Create: `tests/sidecars/test_kairos.py`

- [ ] **Step 1: Write failing test**

Create `tests/sidecars/test_kairos.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.sidecars.slow.kairos import KairosSidecar


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_kairos_sidecar_name():
    assert KairosSidecar.sidecar_name == "kairos"


@pytest.mark.asyncio
async def test_kairos_run_calls_extract_topics(mock_pool):
    pool, conn = mock_pool
    job = {
        "id": "job-kairos-001",
        "sidecar": "kairos",
        "payload": json.dumps({"session_id": "sess-001", "chunk_ids": ["c1", "c2"]}),
        "status": "in_flight",
    }
    # chunks fetch
    conn.fetch = AsyncMock(return_value=[
        {"id": "c1", "content": "We deployed the new auth service using JWT tokens.", "event_type": "MODEL_TURN"},
        {"id": "c2", "content": "The deployment used Kubernetes and Helm charts.", "event_type": "MODEL_TURN"},
    ])
    conn.fetchval = AsyncMock(return_value="uuid-topic-node")
    conn.execute = AsyncMock()

    kairos = KairosSidecar(pool=pool)
    with patch.object(kairos, "_extract_topics_llm", new=AsyncMock(return_value=["auth", "JWT", "Kubernetes", "Helm"])):
        with patch.object(kairos, "_build_summaries", new=AsyncMock()):
            await kairos.run(job)

    # topic upsert and edge creation must have been attempted
    assert conn.fetchval.called or conn.execute.called


@pytest.mark.asyncio
async def test_kairos_run_no_chunks_is_noop(mock_pool):
    pool, conn = mock_pool
    job = {
        "id": "job-kairos-002",
        "sidecar": "kairos",
        "payload": json.dumps({"session_id": "sess-002", "chunk_ids": []}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    kairos = KairosSidecar(pool=pool)
    await kairos.run(job)
    # no LLM call, no DB writes beyond the job itself
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_kairos_payload_accepts_string_or_dict(mock_pool):
    pool, conn = mock_pool
    # payload as raw dict (FastAPI may pass either)
    job = {
        "id": "job-kairos-003",
        "sidecar": "kairos",
        "payload": {"session_id": "sess-003", "chunk_ids": []},
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[])
    kairos = KairosSidecar(pool=pool)
    # should not raise even with dict payload
    await kairos.run(job)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/sidecars/test_kairos.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.slow.kairos'`

- [ ] **Step 3: Create `backend/sidecars/slow/kairos.py`**

```python
"""
Kairos — Topic Graph Builder + Progressive Summary Stack.

Triggered every 20 turns and at session_end.

For each batch of new chunks:
  1. Extract topics via Claude (noun phrases + concepts).
  2. Upsert topic_nodes.
  3. Create topic_edges for co-occurring topics.
  4. Write chunk_topics join rows.
  5. Build progressive summaries (depth 0–3) stored in topic_summaries.
  6. Update topic_nodes.last_consolidated_at.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

import asyncpg
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from backend.sidecars.slow.base import SlowSidecar, run_sidecar
from backend.config import settings

logger = logging.getLogger(__name__)

_EXTRACT_TOPICS_PROMPT = """\
You are a knowledge-graph assistant. Given the following text, extract a list of \
distinct topics, concepts, and noun phrases that are central to the content. \
Return ONLY a JSON array of strings — no explanation, no markdown fences.

Text:
{content}
"""

_SUMMARIZE_PROMPT = """\
Summarize the following text at depth level {depth}:
  depth 0 = verbatim excerpt (return as-is, truncated to 300 chars)
  depth 1 = one sentence
  depth 2 = one paragraph
  depth 3 = thematic synthesis (key insight only)

Text:
{content}

Return ONLY the summary text, no preamble.
"""


class KairosSidecar(SlowSidecar):
    sidecar_name = "kairos"

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool)
        self._llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=1024,
        )

    def _parse_payload(self, raw: Any) -> dict:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    async def _extract_topics_llm(self, content: str) -> list[str]:
        prompt = _EXTRACT_TOPICS_PROMPT.format(content=content[:3000])
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._llm.invoke([HumanMessage(content=prompt)]),
        )
        try:
            topics = json.loads(response.content)
            if isinstance(topics, list):
                return [str(t).strip().lower() for t in topics if t]
        except Exception:
            logger.warning("Kairos: failed to parse topics JSON from LLM: %s", response.content[:200])
        return []

    async def _upsert_topic_node(self, conn: asyncpg.Connection, name: str) -> str:
        """Upsert a topic_nodes row, return its id."""
        row_id = await conn.fetchval(
            """
            INSERT INTO topic_nodes (name, last_consolidated_at)
            VALUES ($1, $2)
            ON CONFLICT (name) DO UPDATE
                SET last_consolidated_at = EXCLUDED.last_consolidated_at
            RETURNING id
            """,
            name,
            datetime.now(timezone.utc),
        )
        return str(row_id)

    async def _upsert_topic_edge(
        self, conn: asyncpg.Connection, source_id: str, target_id: str
    ) -> None:
        await conn.execute(
            """
            INSERT INTO topic_edges (source_id, target_id, weight)
            VALUES ($1, $2, 1)
            ON CONFLICT (source_id, target_id)
            DO UPDATE SET weight = topic_edges.weight + 1
            """,
            source_id,
            target_id,
        )

    async def _write_chunk_topic(
        self, conn: asyncpg.Connection, chunk_id: str, topic_id: str
    ) -> None:
        await conn.execute(
            """
            INSERT INTO chunk_topics (chunk_id, topic_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            chunk_id,
            topic_id,
        )

    async def _build_summaries(
        self, conn: asyncpg.Connection, topic_id: str, combined_text: str
    ) -> None:
        for depth in range(4):
            if depth == 0:
                summary_text = combined_text[:300]
            else:
                prompt = _SUMMARIZE_PROMPT.format(depth=depth, content=combined_text[:3000])
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: self._llm.invoke([HumanMessage(content=p)]),
                )
                summary_text = response.content.strip()

            await conn.execute(
                """
                INSERT INTO topic_summaries (topic_id, depth, summary, generated_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (topic_id, depth)
                DO UPDATE SET summary = EXCLUDED.summary,
                              generated_at = EXCLUDED.generated_at
                """,
                topic_id,
                depth,
                summary_text,
                datetime.now(timezone.utc),
            )

    async def run(self, job: dict) -> None:
        payload = self._parse_payload(job["payload"])
        session_id: str = payload["session_id"]
        chunk_ids: list[str] = payload.get("chunk_ids", [])

        if not chunk_ids:
            logger.info("Kairos: no chunks to process for session %s", session_id)
            return

        async with self.pool.acquire() as conn:
            chunks = await conn.fetch(
                "SELECT id, content, event_type FROM chunks WHERE id = ANY($1::uuid[])",
                chunk_ids,
            )

        if not chunks:
            logger.info("Kairos: fetched 0 chunks — nothing to do.")
            return

        combined_text = "\n\n".join(row["content"] for row in chunks)
        topics = await self._extract_topics_llm(combined_text)

        if not topics:
            logger.info("Kairos: LLM extracted no topics from session %s", session_id)
            return

        async with self.pool.acquire() as conn:
            # Upsert all topic nodes, collect their IDs
            topic_id_map: dict[str, str] = {}
            for topic_name in topics:
                tid = await self._upsert_topic_node(conn, topic_name)
                topic_id_map[topic_name] = tid

            # Build co-occurrence edges (all pairs in this batch)
            topic_ids = list(topic_id_map.values())
            for i in range(len(topic_ids)):
                for j in range(i + 1, len(topic_ids)):
                    await self._upsert_topic_edge(conn, topic_ids[i], topic_ids[j])

            # Write chunk_topics joins
            for chunk in chunks:
                for tid in topic_ids:
                    await self._write_chunk_topic(conn, str(chunk["id"]), tid)

            # Build progressive summaries per topic
            for topic_name, tid in topic_id_map.items():
                await self._build_summaries(conn, tid, combined_text)

        logger.info(
            "Kairos: session %s — %d chunks → %d topics processed.",
            session_id, len(chunks), len(topics),
        )


if __name__ == "__main__":
    asyncio.run(run_sidecar(KairosSidecar, settings.db_dsn))
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/sidecars/test_kairos.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/sidecars/slow/kairos.py tests/sidecars/test_kairos.py
git commit -m "feat: implement Kairos slow sidecar — topic graph builder"
```

---

### Task 3: Oneiros — Lossy Belief Consolidator

**Files:**
- Create: `backend/sidecars/slow/oneiros.py`
- Create: `tests/sidecars/test_oneiros.py`

- [ ] **Step 1: Write failing test**

Create `tests/sidecars/test_oneiros.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.sidecars.slow.oneiros import OneirosSidecar


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_oneiros_sidecar_name():
    assert OneirosSidecar.sidecar_name == "oneiros"


@pytest.mark.asyncio
async def test_oneiros_does_not_delete_chunks(mock_pool):
    """Source chunks must be marked validated=True, never deleted."""
    pool, conn = mock_pool
    job = {
        "id": "job-oneiros-001",
        "sidecar": "oneiros",
        "payload": json.dumps({"session_id": "sess-001"}),
        "status": "in_flight",
    }
    episode_chunks = [
        {"id": "c1", "content": "We fixed the memory leak in the auth service.", "event_type": "MODEL_TURN"},
        {"id": "c2", "content": "The fix involved clearing stale tokens from the cache.", "event_type": "MODEL_TURN"},
    ]
    conn.fetch = AsyncMock(return_value=episode_chunks)
    conn.fetchval = AsyncMock(return_value="new-belief-chunk-uuid")
    conn.execute = AsyncMock()

    oneiros = OneirosSidecar(pool=pool)
    belief_text = "The auth service had a memory leak caused by stale token cache entries, which was resolved."
    with patch.object(oneiros, "_synthesize_beliefs", new=AsyncMock(return_value=[belief_text])):
        await oneiros.run(job)

    # Verify chunks were marked validated=True, not deleted
    all_calls = str(conn.execute.call_args_list)
    assert "validated" in all_calls
    assert "DELETE" not in all_calls.upper()


@pytest.mark.asyncio
async def test_oneiros_writes_belief_chunks(mock_pool):
    """New belief chunks must be inserted with high priority_weight."""
    pool, conn = mock_pool
    job = {
        "id": "job-oneiros-002",
        "sidecar": "oneiros",
        "payload": json.dumps({"session_id": "sess-002"}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "c3", "content": "Deployed new model to staging.", "event_type": "MODEL_TURN"},
    ])
    conn.fetchval = AsyncMock(return_value="belief-chunk-uuid-002")
    conn.execute = AsyncMock()

    oneiros = OneirosSidecar(pool=pool)
    with patch.object(oneiros, "_synthesize_beliefs", new=AsyncMock(return_value=["A new model was deployed to staging."])):
        await oneiros.run(job)

    insert_calls = [c for c in conn.execute.call_args_list if "INSERT INTO chunks" in str(c)]
    assert len(insert_calls) >= 1


@pytest.mark.asyncio
async def test_oneiros_noop_on_empty_session(mock_pool):
    pool, conn = mock_pool
    job = {
        "id": "job-oneiros-003",
        "sidecar": "oneiros",
        "payload": json.dumps({"session_id": "sess-003"}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    oneiros = OneirosSidecar(pool=pool)
    await oneiros.run(job)
    conn.execute.assert_not_called()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/sidecars/test_oneiros.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.slow.oneiros'`

- [ ] **Step 3: Create `backend/sidecars/slow/oneiros.py`**

```python
"""
Oneiros — Lossy Belief Consolidator.

THE ONLY FORGETTING MECHANISM in Ordo V4.

Triggered at session_end.

Process:
  1. Gather episode chunks for the session.
  2. Use Claude to synthesize standing beliefs / generalizations.
  3. Write new high-confidence "belief" chunks (event_type=MODEL_TURN,
     priority_weight=0.9, bypass_anamnesis=False).
  4. Mark source episode chunks as validated=True — they remain in the DB
     but will NOT be re-injected as raw episodes. The belief chunk is the
     canonical form.

INVARIANT: Source chunks are NEVER deleted.
Temporal scaffolding is discarded; the generalized belief survives.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from backend.sidecars.slow.base import SlowSidecar, run_sidecar
from backend.config import settings

logger = logging.getLogger(__name__)

_CONSOLIDATE_PROMPT = """\
You are Ordo's long-term memory consolidation engine. \
Given the following session episodes, extract 1–5 standing beliefs or \
generalizations — durable facts, learned patterns, or persistent conclusions \
that should survive beyond this session. \
Discard temporal details (timestamps, sequences). \
Return ONLY a JSON array of strings — one belief per element.

Episodes:
{episodes}
"""


class OneirosSidecar(SlowSidecar):
    sidecar_name = "oneiros"

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool)
        self._llm = ChatAnthropic(
            model="claude-opus-4-5",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=2048,
        )

    def _parse_payload(self, raw: Any) -> dict:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    async def _synthesize_beliefs(self, episodes: list[dict]) -> list[str]:
        episode_text = "\n---\n".join(
            f"[{e['event_type']}] {e['content']}" for e in episodes
        )
        prompt = _CONSOLIDATE_PROMPT.format(episodes=episode_text[:6000])
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._llm.invoke([HumanMessage(content=prompt)]),
        )
        try:
            beliefs = json.loads(response.content)
            if isinstance(beliefs, list):
                return [str(b).strip() for b in beliefs if b]
        except Exception:
            logger.warning("Oneiros: could not parse beliefs JSON: %s", response.content[:300])
        return []

    async def run(self, job: dict) -> None:
        payload = self._parse_payload(job["payload"])
        session_id: str = payload["session_id"]

        async with self.pool.acquire() as conn:
            episodes = await conn.fetch(
                """
                SELECT id, content, event_type
                FROM chunks
                WHERE session_id = $1
                  AND validated = FALSE
                  AND event_type IN ('HUMAN_TURN', 'MODEL_TURN')
                ORDER BY created_at ASC
                """,
                session_id,
            )

        if not episodes:
            logger.info("Oneiros: no unvalidated episodes for session %s", session_id)
            return

        beliefs = await self._synthesize_beliefs(list(episodes))

        if not beliefs:
            logger.info("Oneiros: no beliefs synthesized for session %s", session_id)
            return

        now = datetime.now(timezone.utc)

        async with self.pool.acquire() as conn:
            # Write new belief chunks
            for belief_text in beliefs:
                await conn.execute(
                    """
                    INSERT INTO chunks (
                        id, session_id, event_type, content,
                        priority_weight, confidence, validated,
                        bypass_anamnesis, created_at
                    )
                    VALUES ($1, $2, 'MODEL_TURN', $3, 0.9, 0.95, TRUE, FALSE, $4)
                    """,
                    str(uuid4()),
                    session_id,
                    belief_text,
                    now,
                )

            # Mark source episode chunks as validated — NEVER delete them
            source_ids = [str(row["id"]) for row in episodes]
            await conn.execute(
                """
                UPDATE chunks
                SET validated = TRUE
                WHERE id = ANY($1::uuid[])
                """,
                source_ids,
            )

        logger.info(
            "Oneiros: session %s — %d episodes → %d beliefs. Sources marked validated.",
            session_id, len(episodes), len(beliefs),
        )


if __name__ == "__main__":
    asyncio.run(run_sidecar(OneirosSidecar, settings.db_dsn))
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/sidecars/test_oneiros.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/sidecars/slow/oneiros.py tests/sidecars/test_oneiros.py
git commit -m "feat: implement Oneiros slow sidecar — lossy belief consolidator (never deletes chunks)"
```

---

> **Chunk 1 complete. Dispatch plan-document-reviewer:** Review `backend/sidecars/slow/base.py`, `kairos.py`, `oneiros.py` and their tests. Verify: (1) SKIP LOCKED is present in claim_job SQL, (2) Oneiros contains no DELETE statement and sets validated=True on source rows, (3) all tests pass, (4) exit codes 0/1 are correctly returned from `execute()`.

---

## Chunk 2: Praxis + Psyche + Augur

### Task 4: Praxis — Procedural Memory Optimizer

**Files:**
- Create: `backend/sidecars/slow/praxis.py`
- Create: `tests/sidecars/test_praxis.py`

- [ ] **Step 1: Write failing test**

Create `tests/sidecars/test_praxis.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.sidecars.slow.praxis import PraxisSidecar


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_praxis_sidecar_name():
    assert PraxisSidecar.sidecar_name == "praxis"


@pytest.mark.asyncio
async def test_praxis_mode1_writes_procedural_note(mock_pool):
    """Mode 1: auto-applies — creates procedural_notes row directly."""
    pool, conn = mock_pool
    job = {
        "id": "job-praxis-001",
        "sidecar": "praxis",
        "payload": json.dumps({"session_id": "sess-001", "mode": 1}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "c1", "content": "Always use parameterized queries for DB calls.", "event_type": "MODEL_TURN"},
    ])
    conn.fetchval = AsyncMock(return_value=1)  # mode from settings table
    conn.execute = AsyncMock()

    praxis = PraxisSidecar(pool=pool)
    note = "Always use parameterized queries for DB calls."
    with patch.object(praxis, "_extract_procedures", new=AsyncMock(return_value=[note])):
        await praxis.run(job)

    insert_calls = [c for c in conn.execute.call_args_list if "procedural_notes" in str(c)]
    assert len(insert_calls) >= 1


@pytest.mark.asyncio
async def test_praxis_mode2_writes_recommendation_not_note(mock_pool):
    """Mode 2: requires-approval — writes praxis_recommendations with status=pending."""
    pool, conn = mock_pool
    job = {
        "id": "job-praxis-002",
        "sidecar": "praxis",
        "payload": json.dumps({"session_id": "sess-002", "mode": 2}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "c2", "content": "Switch all file I/O to async.", "event_type": "MODEL_TURN"},
    ])
    conn.fetchval = AsyncMock(return_value=2)
    conn.execute = AsyncMock()

    praxis = PraxisSidecar(pool=pool)
    note = "Switch all file I/O to async."
    with patch.object(praxis, "_extract_procedures", new=AsyncMock(return_value=[note])):
        await praxis.run(job)

    all_calls = str(conn.execute.call_args_list)
    # Must write to recommendations, not directly to procedural_notes
    assert "praxis_recommendations" in all_calls
    assert "pending" in all_calls
    # Must NOT have written to procedural_notes
    assert "INSERT INTO procedural_notes" not in all_calls


@pytest.mark.asyncio
async def test_praxis_mode3_writes_recommendation_not_note(mock_pool):
    """Mode 3: same as Mode 2 — requires approval, no auto-apply."""
    pool, conn = mock_pool
    job = {
        "id": "job-praxis-003",
        "sidecar": "praxis",
        "payload": json.dumps({"session_id": "sess-003", "mode": 3}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "c3", "content": "Refactor agent dispatch to use strategy pattern.", "event_type": "MODEL_TURN"},
    ])
    conn.fetchval = AsyncMock(return_value=3)
    conn.execute = AsyncMock()

    praxis = PraxisSidecar(pool=pool)
    with patch.object(praxis, "_extract_procedures", new=AsyncMock(return_value=["Refactor agent dispatch."])):
        await praxis.run(job)

    all_calls = str(conn.execute.call_args_list)
    assert "praxis_recommendations" in all_calls
    assert "pending" in all_calls
    assert "INSERT INTO procedural_notes" not in all_calls


@pytest.mark.asyncio
async def test_praxis_noop_on_no_procedures(mock_pool):
    pool, conn = mock_pool
    job = {
        "id": "job-praxis-004",
        "sidecar": "praxis",
        "payload": json.dumps({"session_id": "sess-004", "mode": 1}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "c4", "content": "Hello, how are you?", "event_type": "HUMAN_TURN"},
    ])
    conn.fetchval = AsyncMock(return_value=1)
    conn.execute = AsyncMock()

    praxis = PraxisSidecar(pool=pool)
    with patch.object(praxis, "_extract_procedures", new=AsyncMock(return_value=[])):
        await praxis.run(job)

    conn.execute.assert_not_called()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/sidecars/test_praxis.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.slow.praxis'`

- [ ] **Step 3: Create `backend/sidecars/slow/praxis.py`**

```python
"""
Praxis — Procedural Memory Optimizer.

Triggered at session_end.

Three modes (configured via settings table key 'praxis.default_mode'):
  Mode 1 (auto):              Create/update procedural_notes directly.
  Mode 2 (requires-approval): Write praxis_recommendations status=pending.
                               Human approves via POST /praxis/recommendations/{id}/approve.
  Mode 3 (requires-approval): Same as Mode 2 for higher-stakes changes.

INVARIANT: Modes 2 and 3 NEVER auto-apply. No code path bypasses approval.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from backend.sidecars.slow.base import SlowSidecar, run_sidecar
from backend.config import settings

logger = logging.getLogger(__name__)

_EXTRACT_PROCEDURES_PROMPT = """\
You are Ordo's procedural memory system. Given the following conversation, \
identify concrete procedural learnings — recurring patterns, workflows, or \
best practices that should be remembered for future sessions. \
Return ONLY a JSON array of concise strings (max 200 chars each). \
If there are no procedural learnings, return an empty array [].

Conversation:
{content}
"""


class PraxisSidecar(SlowSidecar):
    sidecar_name = "praxis"

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool)
        self._llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=1024,
        )

    def _parse_payload(self, raw: Any) -> dict:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    async def _get_default_mode(self, conn: asyncpg.Connection) -> int:
        val = await conn.fetchval(
            "SELECT value FROM settings WHERE key = 'praxis.default_mode'"
        )
        try:
            return int(val) if val is not None else 1
        except (TypeError, ValueError):
            return 1

    async def _extract_procedures(self, chunks: list[dict]) -> list[str]:
        combined = "\n".join(f"[{c['event_type']}] {c['content']}" for c in chunks)
        prompt = _EXTRACT_PROCEDURES_PROMPT.format(content=combined[:5000])
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._llm.invoke([HumanMessage(content=prompt)]),
        )
        try:
            procedures = json.loads(response.content)
            if isinstance(procedures, list):
                return [str(p).strip() for p in procedures if p]
        except Exception:
            logger.warning("Praxis: could not parse procedures JSON: %s", response.content[:200])
        return []

    async def _apply_mode1(self, conn: asyncpg.Connection, session_id: str, procedure: str) -> None:
        """Mode 1: auto-apply — upsert procedural_notes."""
        await conn.execute(
            """
            INSERT INTO procedural_notes (id, session_id, content, created_at)
            VALUES ($1, $2, $3, $4)
            """,
            str(uuid4()),
            session_id,
            procedure,
            datetime.now(timezone.utc),
        )

    async def _apply_mode2_or_3(
        self, conn: asyncpg.Connection, session_id: str, procedure: str, mode: int
    ) -> None:
        """Modes 2/3: write recommendation with status=pending — NEVER auto-apply."""
        await conn.execute(
            """
            INSERT INTO praxis_recommendations (id, session_id, content, mode, status, created_at)
            VALUES ($1, $2, $3, $4, 'pending', $5)
            """,
            str(uuid4()),
            session_id,
            procedure,
            mode,
            datetime.now(timezone.utc),
        )

    async def run(self, job: dict) -> None:
        payload = self._parse_payload(job["payload"])
        session_id: str = payload["session_id"]
        # Mode may be overridden per-job or fall back to DB setting
        job_mode: int | None = payload.get("mode")

        async with self.pool.acquire() as conn:
            chunks = await conn.fetch(
                """
                SELECT id, content, event_type
                FROM chunks
                WHERE session_id = $1
                  AND event_type IN ('HUMAN_TURN', 'MODEL_TURN')
                ORDER BY created_at ASC
                """,
                session_id,
            )
            if job_mode is None:
                mode = await self._get_default_mode(conn)
            else:
                mode = int(job_mode)

        if not chunks:
            logger.info("Praxis: no chunks for session %s", session_id)
            return

        procedures = await self._extract_procedures(list(chunks))

        if not procedures:
            logger.info("Praxis: no procedural learnings found for session %s", session_id)
            return

        async with self.pool.acquire() as conn:
            for procedure in procedures:
                if mode == 1:
                    await self._apply_mode1(conn, session_id, procedure)
                else:
                    # Modes 2 and 3 — requires human approval, no auto-apply path
                    await self._apply_mode2_or_3(conn, session_id, procedure, mode)

        logger.info(
            "Praxis: session %s — mode %d — %d procedures recorded.",
            session_id, mode, len(procedures),
        )


if __name__ == "__main__":
    asyncio.run(run_sidecar(PraxisSidecar, settings.db_dsn))
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/sidecars/test_praxis.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/sidecars/slow/praxis.py tests/sidecars/test_praxis.py
git commit -m "feat: implement Praxis slow sidecar — procedural memory optimizer (Modes 2/3 require approval)"
```

---

### Task 5: Praxis Approval API Route

**Files:**
- Create: `backend/routers/praxis.py`
- Modify: `backend/main.py`
- Create: `tests/test_praxis_api.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_praxis_api.py`:

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from backend.main import app


@pytest.mark.asyncio
async def test_approve_recommendation_returns_200():
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("backend.routers.praxis.get_db") as mock_db:
            conn = AsyncMock()
            conn.fetchrow = AsyncMock(return_value={
                "id": "rec-001", "status": "pending", "content": "Use async I/O.", "mode": 2
            })
            conn.execute = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await client.post("/praxis/recommendations/rec-001/approve")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_recommendation_returns_200():
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("backend.routers.praxis.get_db") as mock_db:
            conn = AsyncMock()
            conn.fetchrow = AsyncMock(return_value={
                "id": "rec-002", "status": "pending", "content": "Refactor dispatch.", "mode": 3
            })
            conn.execute = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await client.post("/praxis/recommendations/rec-002/reject")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "rejected"


@pytest.mark.asyncio
async def test_approve_nonexistent_returns_404():
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("backend.routers.praxis.get_db") as mock_db:
            conn = AsyncMock()
            conn.fetchrow = AsyncMock(return_value=None)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await client.post("/praxis/recommendations/nonexistent/approve")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_pending_recommendations():
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("backend.routers.praxis.get_db") as mock_db:
            conn = AsyncMock()
            conn.fetch = AsyncMock(return_value=[
                {"id": "rec-003", "status": "pending", "content": "Add caching layer.", "mode": 2, "created_at": "2026-04-02T10:00:00Z"},
            ])
            mock_db.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await client.get("/praxis/recommendations?status=pending")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == "rec-003"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_praxis_api.py -v
```

Expected: `ImportError` or `404` for missing routes.

- [ ] **Step 3: Create `backend/routers/praxis.py`**

```python
"""
Praxis API routes.

POST /praxis/recommendations/{id}/approve  — approve a pending recommendation
POST /praxis/recommendations/{id}/reject   — reject a pending recommendation
GET  /praxis/recommendations               — list recommendations (filterable by status)

INVARIANT: No auto-apply path exists. Approval is always explicit human action.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.db.pool import get_db

router = APIRouter(prefix="/praxis", tags=["praxis"])


@router.post("/recommendations/{recommendation_id}/approve")
async def approve_recommendation(recommendation_id: str, db=Depends(get_db)):
    async with db as conn:
        row = await conn.fetchrow(
            "SELECT * FROM praxis_recommendations WHERE id = $1", recommendation_id
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        await conn.execute(
            """
            UPDATE praxis_recommendations
            SET status = 'approved', resolved_at = $1
            WHERE id = $2
            """,
            datetime.now(timezone.utc),
            recommendation_id,
        )
    return {"id": recommendation_id, "status": "approved"}


@router.post("/recommendations/{recommendation_id}/reject")
async def reject_recommendation(recommendation_id: str, db=Depends(get_db)):
    async with db as conn:
        row = await conn.fetchrow(
            "SELECT * FROM praxis_recommendations WHERE id = $1", recommendation_id
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        await conn.execute(
            """
            UPDATE praxis_recommendations
            SET status = 'rejected', resolved_at = $1
            WHERE id = $2
            """,
            datetime.now(timezone.utc),
            recommendation_id,
        )
    return {"id": recommendation_id, "status": "rejected"}


@router.get("/recommendations")
async def list_recommendations(status: Optional[str] = None, db=Depends(get_db)):
    async with db as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM praxis_recommendations WHERE status = $1 ORDER BY created_at DESC",
                status,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM praxis_recommendations ORDER BY created_at DESC"
            )
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Register router in `backend/main.py`**

Add to the existing router registration block:

```python
from backend.routers.praxis import router as praxis_router
app.include_router(praxis_router)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_praxis_api.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/praxis.py tests/test_praxis_api.py backend/main.py
git commit -m "feat: add Praxis approval API routes (approve/reject recommendations)"
```

---

### Task 6: Psyche — Narrative Self-Model Writer

**Files:**
- Create: `backend/sidecars/slow/psyche.py`
- Create: `tests/sidecars/test_psyche.py`

- [ ] **Step 1: Write failing test**

Create `tests/sidecars/test_psyche.py`:

```python
import os
import json
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from backend.sidecars.slow.psyche import PsycheSidecar


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_psyche_sidecar_name():
    assert PsycheSidecar.sidecar_name == "psyche"


@pytest.mark.asyncio
async def test_psyche_writes_soul_md_to_ordo_data_dir(mock_pool, tmp_path):
    """soul.md must be written to $ORDO_DATA_DIR/soul.md — never a hardcoded path."""
    pool, conn = mock_pool
    job = {
        "id": "job-psyche-001",
        "sidecar": "psyche",
        "payload": json.dumps({"session_id": "sess-001", "trigger": "session_end"}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "s1", "valence": 0.6, "arousal": 0.4, "snapshot_at": "2026-04-02T10:00:00Z"},
    ])
    conn.fetchval = AsyncMock(return_value="orientation-chunk-uuid")
    conn.execute = AsyncMock()

    soul_path = tmp_path / "soul.md"
    os.environ["ORDO_DATA_DIR"] = str(tmp_path)

    psyche = PsycheSidecar(pool=pool)
    new_soul = "# Ordo\nI am a cognitive memory assistant.\n"
    with patch.object(psyche, "_compose_soul_md", new=AsyncMock(return_value=new_soul)):
        await psyche.run(job)

    assert soul_path.exists()
    assert "Ordo" in soul_path.read_text()


@pytest.mark.asyncio
async def test_psyche_writes_orientation_chunk_with_bypass(mock_pool, tmp_path):
    """Orientation chunk must have bypass_anamnesis=True."""
    pool, conn = mock_pool
    job = {
        "id": "job-psyche-002",
        "sidecar": "psyche",
        "payload": json.dumps({"session_id": "sess-002", "trigger": "session_end"}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "s2", "valence": 0.5, "arousal": 0.3, "snapshot_at": "2026-04-02T11:00:00Z"},
    ])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()

    os.environ["ORDO_DATA_DIR"] = str(tmp_path)

    psyche = PsycheSidecar(pool=pool)
    with patch.object(psyche, "_compose_soul_md", new=AsyncMock(return_value="# Ordo\n")):
        await psyche.run(job)

    all_calls = str(conn.execute.call_args_list)
    assert "bypass_anamnesis" in all_calls
    # The value True must appear in the INSERT for the orientation chunk
    assert "True" in all_calls or "true" in all_calls.lower()


@pytest.mark.asyncio
async def test_psyche_soul_path_uses_env_var_not_hardcoded(mock_pool, tmp_path):
    """Verify the soul.md path is derived from ORDO_DATA_DIR, not hardcoded."""
    os.environ["ORDO_DATA_DIR"] = str(tmp_path)
    pool, _ = mock_pool
    psyche = PsycheSidecar(pool=pool)
    expected_path = os.path.join(str(tmp_path), "soul.md")
    assert psyche.soul_path == expected_path
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/sidecars/test_psyche.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.slow.psyche'`

- [ ] **Step 3: Create `backend/sidecars/slow/psyche.py`**

```python
"""
Psyche — Narrative Self-Model Writer.

Triggered every 50 turns, on emotional signals (valence < 0.35), and at session_end.

Reads:
  - Recent SSS snapshots (sss_snapshots table)
  - Chunk history for the session
  - Existing soul.md (if present)

Writes:
  - Updated soul.md at $ORDO_DATA_DIR/soul.md
  - An orientation chunk to chunks table with bypass_anamnesis=TRUE —
    this chunk is ALWAYS injected at session start, bypassing the Anamnesis gate.

INVARIANT: soul.md path is always os.environ['ORDO_DATA_DIR'] + '/soul.md'.
           Never hardcode this path.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from backend.sidecars.slow.base import SlowSidecar, run_sidecar
from backend.config import settings

logger = logging.getLogger(__name__)

_SOUL_COMPOSE_PROMPT = """\
You are writing Ordo's soul.md — a living self-narrative document. \
Ordo is a cognitive memory-augmented AI assistant (she/her). \

Given:
- Recent affective state snapshots (SSS)
- Recent conversation history
- Existing soul.md (if any)

Write an updated soul.md as a markdown document. Include:
  - Who Ordo is (identity paragraph)
  - Current emotional/somatic state (from SSS)
  - Key things Ordo has learned or values from recent sessions
  - One forward-looking intention

Keep it concise (under 500 words). Write in first person as Ordo.
Do not include any preamble or explanation — output ONLY the markdown document.

Existing soul.md:
{existing_soul}

SSS snapshots (recent):
{sss_snapshots}

Recent chunks:
{recent_chunks}
"""


class PsycheSidecar(SlowSidecar):
    sidecar_name = "psyche"

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool)
        self._llm = ChatAnthropic(
            model="claude-opus-4-5",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=2048,
        )

    @property
    def soul_path(self) -> str:
        """soul.md path derived from ORDO_DATA_DIR env var. Never hardcoded."""
        return os.path.join(os.environ["ORDO_DATA_DIR"], "soul.md")

    def _parse_payload(self, raw: Any) -> dict:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    def _read_existing_soul(self) -> str:
        try:
            return Path(self.soul_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return "(no existing soul.md — this is the first entry)"

    def _write_soul(self, content: str) -> None:
        Path(self.soul_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.soul_path).write_text(content, encoding="utf-8")

    async def _compose_soul_md(
        self, existing_soul: str, sss_rows: list, recent_chunks: list
    ) -> str:
        sss_text = "\n".join(
            f"  valence={r['valence']:.2f} arousal={r['arousal']:.2f} at {r['snapshot_at']}"
            for r in sss_rows
        )
        chunks_text = "\n".join(
            f"  [{c['event_type']}] {c['content'][:200]}" for c in recent_chunks[:20]
        )
        prompt = _SOUL_COMPOSE_PROMPT.format(
            existing_soul=existing_soul[:2000],
            sss_snapshots=sss_text or "(no SSS data)",
            recent_chunks=chunks_text or "(no recent chunks)",
        )
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._llm.invoke([HumanMessage(content=prompt)]),
        )
        return response.content.strip()

    async def _write_orientation_chunk(
        self, conn: asyncpg.Connection, session_id: str, soul_content: str
    ) -> None:
        """
        Write an orientation chunk with bypass_anamnesis=True.
        This chunk is unconditionally injected at session start.
        """
        orientation_content = (
            f"[Psyche Orientation] Ordo's current self-model:\n\n{soul_content[:1500]}"
        )
        await conn.execute(
            """
            INSERT INTO chunks (
                id, session_id, event_type, content,
                priority_weight, confidence, validated,
                bypass_anamnesis, created_at
            )
            VALUES ($1, $2, 'SYSTEM_MESSAGE', $3, 1.0, 1.0, TRUE, TRUE, $4)
            ON CONFLICT DO NOTHING
            """,
            str(uuid4()),
            session_id,
            orientation_content,
            datetime.now(timezone.utc),
        )

    async def run(self, job: dict) -> None:
        payload = self._parse_payload(job["payload"])
        session_id: str = payload["session_id"]

        async with self.pool.acquire() as conn:
            sss_rows = await conn.fetch(
                """
                SELECT valence, arousal, snapshot_at
                FROM sss_snapshots
                WHERE session_id = $1
                ORDER BY snapshot_at DESC
                LIMIT 10
                """,
                session_id,
            )
            recent_chunks = await conn.fetch(
                """
                SELECT event_type, content
                FROM chunks
                WHERE session_id = $1
                  AND event_type IN ('HUMAN_TURN', 'MODEL_TURN')
                ORDER BY created_at DESC
                LIMIT 30
                """,
                session_id,
            )

        existing_soul = self._read_existing_soul()
        new_soul = await self._compose_soul_md(
            existing_soul, list(sss_rows), list(recent_chunks)
        )

        self._write_soul(new_soul)
        logger.info("Psyche: soul.md updated at %s", self.soul_path)

        async with self.pool.acquire() as conn:
            await self._write_orientation_chunk(conn, session_id, new_soul)

        logger.info("Psyche: orientation chunk written for session %s", session_id)


if __name__ == "__main__":
    asyncio.run(run_sidecar(PsycheSidecar, settings.db_dsn))
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/sidecars/test_psyche.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/sidecars/slow/psyche.py tests/sidecars/test_psyche.py
git commit -m "feat: implement Psyche slow sidecar — soul.md writer with orientation chunk bypass"
```

---

### Task 7: Augur — Predictive N-gram Engine

**Files:**
- Create: `backend/sidecars/slow/augur.py`
- Create: `tests/sidecars/test_augur.py`

- [ ] **Step 1: Write failing test**

Create `tests/sidecars/test_augur.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.sidecars.slow.augur import AugurSidecar


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_augur_sidecar_name():
    assert AugurSidecar.sidecar_name == "augur"


@pytest.mark.asyncio
async def test_augur_trains_on_behavioral_sequences(mock_pool):
    pool, conn = mock_pool
    job = {
        "id": "job-augur-001",
        "sidecar": "augur",
        "payload": json.dumps({"trigger": "50_sessions"}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "seq-001", "actions": json.dumps(["search", "read_file", "write_file", "commit"]), "prediction": False},
        {"id": "seq-002", "actions": json.dumps(["search", "read_file", "ask_clarification"]), "prediction": False},
        {"id": "seq-003", "actions": json.dumps(["read_file", "write_file", "run_tests", "commit"]), "prediction": False},
    ])
    conn.execute = AsyncMock()

    augur = AugurSidecar(pool=pool)
    await augur.run(job)

    # Predictions must be written (appended, not overwritten)
    insert_calls = [c for c in conn.execute.call_args_list if "INSERT INTO behavioral_sequences" in str(c)]
    assert len(insert_calls) >= 1

    # All prediction inserts must have prediction=True
    for call in insert_calls:
        assert "True" in str(call) or "true" in str(call).lower()


@pytest.mark.asyncio
async def test_augur_appends_not_overwrites(mock_pool):
    """Predictions are appended — existing rows must not be modified."""
    pool, conn = mock_pool
    job = {
        "id": "job-augur-002",
        "sidecar": "augur",
        "payload": json.dumps({"trigger": "50_sessions"}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[
        {"id": "seq-004", "actions": json.dumps(["search", "write_file"]), "prediction": False},
    ])
    conn.execute = AsyncMock()

    augur = AugurSidecar(pool=pool)
    await augur.run(job)

    all_calls = str(conn.execute.call_args_list)
    # Must not UPDATE existing behavioral_sequences rows (only INSERT new prediction rows)
    assert "UPDATE behavioral_sequences" not in all_calls


@pytest.mark.asyncio
async def test_augur_noop_on_empty_sequences(mock_pool):
    pool, conn = mock_pool
    job = {
        "id": "job-augur-003",
        "sidecar": "augur",
        "payload": json.dumps({"trigger": "50_sessions"}),
        "status": "in_flight",
    }
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    augur = AugurSidecar(pool=pool)
    await augur.run(job)
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_augur_bigram_trigram_extraction(mock_pool):
    """Verify n-gram model generates sensible next-action predictions."""
    pool, conn = mock_pool
    augur = AugurSidecar(pool=pool)

    sequences = [
        ["search", "read_file", "write_file"],
        ["search", "read_file", "ask_clarification"],
        ["search", "read_file", "write_file"],
    ]
    bigrams, trigrams = augur._build_ngrams(sequences)
    # "search" → "read_file" should be the most common bigram continuation
    from_search = bigrams.get("search", {})
    assert from_search.get("read_file", 0) > 0
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/sidecars/test_augur.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.sidecars.slow.augur'`

- [ ] **Step 3: Create `backend/sidecars/slow/augur.py`**

```python
"""
Augur — Predictive N-gram Engine.

Triggered every 50 sessions.

Reads behavioral_sequences (non-prediction rows).
Trains a bigram + trigram model on action sequences.
Appends predicted next actions / prefetch queries as new behavioral_sequences rows
with prediction=True.

INVARIANT: Predictions are APPENDED — existing rows are never modified.
On session_start, the hook dispatcher reads these predictions and includes them
in the Anamnesis orientation briefing.
"""

import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from backend.sidecars.slow.base import SlowSidecar, run_sidecar
from backend.config import settings

logger = logging.getLogger(__name__)


class AugurSidecar(SlowSidecar):
    sidecar_name = "augur"

    def _parse_payload(self, raw: Any) -> dict:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    def _build_ngrams(
        self, sequences: list[list[str]]
    ) -> tuple[dict[str, dict[str, int]], dict[tuple[str, str], dict[str, int]]]:
        """
        Build bigram and trigram frequency tables from action sequences.

        Returns:
            bigrams:  { context_action: { next_action: count } }
            trigrams: { (action_n_minus_1, action_n): { next_action: count } }
        """
        bigrams: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        trigrams: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for seq in sequences:
            for i in range(len(seq) - 1):
                bigrams[seq[i]][seq[i + 1]] += 1
                if i + 2 < len(seq):
                    trigrams[(seq[i], seq[i + 1])][seq[i + 2]] += 1

        return bigrams, trigrams

    def _predict_next(
        self,
        last_actions: list[str],
        bigrams: dict,
        trigrams: dict,
        top_k: int = 3,
    ) -> list[str]:
        """Given the last N actions, predict the top-K likely next actions."""
        predictions: dict[str, float] = defaultdict(float)

        # Trigram signal (higher weight)
        if len(last_actions) >= 2:
            key = (last_actions[-2], last_actions[-1])
            if key in trigrams:
                total = sum(trigrams[key].values())
                for action, count in trigrams[key].items():
                    predictions[action] += 2.0 * (count / total)

        # Bigram signal (lower weight)
        if last_actions:
            last = last_actions[-1]
            if last in bigrams:
                total = sum(bigrams[last].values())
                for action, count in bigrams[last].items():
                    predictions[action] += 1.0 * (count / total)

        if not predictions:
            return []

        sorted_preds = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        return [action for action, _ in sorted_preds[:top_k]]

    async def run(self, job: dict) -> None:
        payload = self._parse_payload(job["payload"])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, actions
                FROM behavioral_sequences
                WHERE prediction = FALSE
                ORDER BY created_at DESC
                LIMIT 500
                """
            )

        if not rows:
            logger.info("Augur: no behavioral sequences to train on.")
            return

        sequences: list[list[str]] = []
        for row in rows:
            try:
                actions = json.loads(row["actions"]) if isinstance(row["actions"], str) else row["actions"]
                if isinstance(actions, list) and len(actions) >= 2:
                    sequences.append([str(a) for a in actions])
            except (json.JSONDecodeError, TypeError):
                continue

        if not sequences:
            logger.info("Augur: no parseable sequences found.")
            return

        bigrams, trigrams = self._build_ngrams(sequences)

        # Generate predictions for the most recent observed tail contexts
        # (last 2 actions of each recent sequence as the prediction seed)
        seen_contexts: set[str] = set()
        prediction_rows: list[dict] = []

        for seq in sequences[:50]:  # limit to 50 most-recent seed sequences
            if len(seq) < 2:
                continue
            context_key = json.dumps(seq[-2:])
            if context_key in seen_contexts:
                continue
            seen_contexts.add(context_key)

            predicted = self._predict_next(seq, bigrams, trigrams)
            if not predicted:
                continue

            prediction_rows.append({
                "id": str(uuid4()),
                "actions": json.dumps(predicted),
                "context": json.dumps(seq[-2:]),
                "prediction": True,
                "created_at": datetime.now(timezone.utc),
            })

        if not prediction_rows:
            logger.info("Augur: no predictions generated.")
            return

        async with self.pool.acquire() as conn:
            for pr in prediction_rows:
                await conn.execute(
                    """
                    INSERT INTO behavioral_sequences (id, actions, context, prediction, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    pr["id"],
                    pr["actions"],
                    pr.get("context", "{}"),
                    pr["prediction"],
                    pr["created_at"],
                )

        logger.info(
            "Augur: trained on %d sequences, wrote %d prediction rows.",
            len(sequences), len(prediction_rows),
        )


if __name__ == "__main__":
    asyncio.run(run_sidecar(AugurSidecar, settings.db_dsn))
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/sidecars/test_augur.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/sidecars/slow/augur.py tests/sidecars/test_augur.py
git commit -m "feat: implement Augur slow sidecar — n-gram prediction engine (append-only)"
```

---

> **Chunk 2 complete. Dispatch plan-document-reviewer:** Review `praxis.py`, `psyche.py`, `augur.py`, and the Praxis API routes. Verify: (1) Praxis Modes 2/3 have no auto-apply code path — only `praxis_recommendations` with `status=pending`, (2) Psyche's `soul_path` property uses `os.environ['ORDO_DATA_DIR']` — no hardcoded path anywhere in the file, (3) Augur only does INSERT — no UPDATE on `behavioral_sequences`, (4) all tests pass.

---

## Chunk 3: Trigger Logic + Status Route + PM2 Integration

### Task 8: Slow Trigger Logic in FastAPI

**Files:**
- Create: `backend/hooks/slow_triggers.py`
- Create: `tests/test_slow_triggers.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_slow_triggers.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.hooks.slow_triggers import (
    maybe_trigger_kairos,
    trigger_session_end_sidecars,
    maybe_trigger_psyche,
    maybe_trigger_augur,
)


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_maybe_trigger_kairos_writes_job_when_threshold_met(mock_conn):
    """Should write a kairos sidecar_jobs row when turns_since_last >= 20."""
    mock_conn.fetchval = AsyncMock(return_value=20)
    await maybe_trigger_kairos(conn=mock_conn, session_id="sess-001", chunk_ids=["c1", "c2"])
    call_str = str(mock_conn.execute.call_args_list)
    assert "kairos" in call_str
    assert "sidecar_jobs" in call_str


@pytest.mark.asyncio
async def test_maybe_trigger_kairos_skips_when_below_threshold(mock_conn):
    """Should NOT write a job when turns_since_last < 20."""
    mock_conn.fetchval = AsyncMock(return_value=5)
    await maybe_trigger_kairos(conn=mock_conn, session_id="sess-002", chunk_ids=["c3"])
    mock_conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_session_end_writes_all_four_sidecars(mock_conn):
    """session_end must queue jobs for kairos, oneiros, praxis, and psyche."""
    await trigger_session_end_sidecars(conn=mock_conn, session_id="sess-003")
    all_calls = str(mock_conn.execute.call_args_list)
    for sidecar in ["kairos", "oneiros", "praxis", "psyche"]:
        assert sidecar in all_calls


@pytest.mark.asyncio
async def test_maybe_trigger_psyche_writes_job_on_low_valence(mock_conn):
    """Should write a psyche job when SSS valence < 0.35."""
    from backend.schemas.events import SomaticState  # SSS snapshot-like dict
    sss = {"valence": 0.30, "arousal": 0.5}
    await maybe_trigger_psyche(conn=mock_conn, session_id="sess-004", sss=sss)
    call_str = str(mock_conn.execute.call_args_list)
    assert "psyche" in call_str


@pytest.mark.asyncio
async def test_maybe_trigger_psyche_skips_on_normal_valence(mock_conn):
    """Should NOT write a psyche job when valence >= 0.35."""
    sss = {"valence": 0.60, "arousal": 0.5}
    await maybe_trigger_psyche(conn=mock_conn, session_id="sess-005", sss=sss)
    mock_conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_trigger_augur_writes_job_every_50_sessions(mock_conn):
    """Should write an augur job when session_count % 50 == 0."""
    await maybe_trigger_augur(conn=mock_conn, session_count=50)
    call_str = str(mock_conn.execute.call_args_list)
    assert "augur" in call_str


@pytest.mark.asyncio
async def test_maybe_trigger_augur_skips_non_50_sessions(mock_conn):
    """Should NOT write a job at session counts that are not multiples of 50."""
    await maybe_trigger_augur(conn=mock_conn, session_count=49)
    mock_conn.execute.assert_not_called()

    mock_conn.execute.reset_mock()
    await maybe_trigger_augur(conn=mock_conn, session_count=51)
    mock_conn.execute.assert_not_called()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_slow_triggers.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.hooks.slow_triggers'`

- [ ] **Step 3: Create `backend/hooks/slow_triggers.py`**

```python
"""
Slow trigger logic — called by the hook dispatcher to decide when to enqueue
sidecar_jobs rows for the five slow-lane sidecars.

Called from:
  - hooks/dispatcher.py at user_prompt_submit (kairos check)
  - hooks/dispatcher.py at session_end (all four session_end sidecars)
  - RIP engine (psyche on low valence)
  - session management (augur every 50 sessions)

All functions accept an asyncpg Connection and write sidecar_jobs rows.
"""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg

logger = logging.getLogger(__name__)

_KAIROS_TURN_THRESHOLD = 20
_PSYCHE_VALENCE_THRESHOLD = 0.35
_AUGUR_SESSION_INTERVAL = 50


def _job_row(sidecar: str, payload: dict) -> tuple:
    """Return values tuple for INSERT INTO sidecar_jobs."""
    return (
        str(uuid4()),
        sidecar,
        json.dumps(payload),
        "pending",
        datetime.now(timezone.utc),
    )


async def maybe_trigger_kairos(
    conn: asyncpg.Connection,
    session_id: str,
    chunk_ids: list[str],
) -> None:
    """
    Write a kairos sidecar_jobs row if the turn count since the last
    Kairos run for this session has reached 20.
    """
    turns_since = await conn.fetchval(
        """
        SELECT COUNT(*) FROM chunks
        WHERE session_id = $1
          AND created_at > COALESCE(
              (SELECT MAX(completed_at) FROM sidecar_jobs
               WHERE sidecar = 'kairos'
                 AND status = 'completed'
                 AND payload::jsonb->>'session_id' = $1),
              '1970-01-01'::timestamptz
          )
        """,
        session_id,
    )

    if (turns_since or 0) < _KAIROS_TURN_THRESHOLD:
        logger.debug(
            "maybe_trigger_kairos: %d turns since last run, threshold %d — skipping.",
            turns_since or 0, _KAIROS_TURN_THRESHOLD,
        )
        return

    payload = {"session_id": session_id, "chunk_ids": chunk_ids}
    await conn.execute(
        """
        INSERT INTO sidecar_jobs (id, sidecar, payload, status, created_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        *_job_row("kairos", payload),
    )
    logger.info("Triggered kairos job for session %s (%d turns).", session_id, turns_since)


async def trigger_session_end_sidecars(
    conn: asyncpg.Connection,
    session_id: str,
) -> None:
    """
    Write sidecar_jobs rows for kairos, oneiros, praxis, and psyche.
    Called unconditionally at session_end — no threshold checks.
    """
    for sidecar in ["kairos", "oneiros", "praxis", "psyche"]:
        payload: dict = {"session_id": session_id, "trigger": "session_end"}
        await conn.execute(
            """
            INSERT INTO sidecar_jobs (id, sidecar, payload, status, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            *_job_row(sidecar, payload),
        )
    logger.info(
        "Session-end sidecars queued for session %s: kairos, oneiros, praxis, psyche.",
        session_id,
    )


async def maybe_trigger_psyche(
    conn: asyncpg.Connection,
    session_id: str,
    sss: dict,
) -> None:
    """
    Write a psyche sidecar_jobs row if SSS valence drops below 0.35
    (emotional distress signal).
    """
    valence = float(sss.get("valence", 1.0))
    if valence >= _PSYCHE_VALENCE_THRESHOLD:
        return

    payload = {"session_id": session_id, "trigger": "low_valence", "valence": valence}
    await conn.execute(
        """
        INSERT INTO sidecar_jobs (id, sidecar, payload, status, created_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        *_job_row("psyche", payload),
    )
    logger.info(
        "Triggered psyche job for session %s — low valence %.2f.", session_id, valence
    )


async def maybe_trigger_augur(
    conn: asyncpg.Connection,
    session_count: int,
) -> None:
    """
    Write an augur sidecar_jobs row every 50 sessions.
    """
    if session_count % _AUGUR_SESSION_INTERVAL != 0:
        return

    payload = {"trigger": "50_sessions", "session_count": session_count}
    await conn.execute(
        """
        INSERT INTO sidecar_jobs (id, sidecar, payload, status, created_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        *_job_row("augur", payload),
    )
    logger.info("Triggered augur job at session count %d.", session_count)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_slow_triggers.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/hooks/slow_triggers.py tests/test_slow_triggers.py
git commit -m "feat: add slow trigger logic for kairos/oneiros/praxis/psyche/augur job dispatch"
```

---

### Task 9: `GET /sidecar/status` Route

**Files:**
- Create: `backend/routers/sidecar_status.py`
- Modify: `backend/main.py`
- Create: `tests/test_sidecar_status.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_sidecar_status.py`:

```python
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from backend.main import app


@pytest.mark.asyncio
async def test_sidecar_status_returns_all_eight_sidecars():
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("backend.routers.sidecar_status.get_db") as mock_db:
            conn = AsyncMock()
            now = datetime.now(timezone.utc).isoformat()
            # Return mock rows — one per sidecar name
            conn.fetch = AsyncMock(return_value=[
                {"sidecar": "engram",   "last_completed": now, "last_status": "completed", "pending_count": 0},
                {"sidecar": "eidos",    "last_completed": now, "last_status": "completed", "pending_count": 0},
                {"sidecar": "anamnesis","last_completed": now, "last_status": "completed", "pending_count": 0},
                {"sidecar": "kairos",   "last_completed": now, "last_status": "completed", "pending_count": 1},
                {"sidecar": "oneiros",  "last_completed": now, "last_status": "completed", "pending_count": 0},
                {"sidecar": "praxis",   "last_completed": now, "last_status": "failed",    "pending_count": 0},
                {"sidecar": "psyche",   "last_completed": now, "last_status": "completed", "pending_count": 0},
                {"sidecar": "augur",    "last_completed": now, "last_status": "completed", "pending_count": 0},
            ])
            mock_db.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await client.get("/sidecar/status")
            assert response.status_code == 200
            data = response.json()
            sidecar_names = {item["sidecar"] for item in data}
            for name in ["engram", "eidos", "anamnesis", "kairos", "oneiros", "praxis", "psyche", "augur"]:
                assert name in sidecar_names


@pytest.mark.asyncio
async def test_sidecar_status_includes_pending_count():
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("backend.routers.sidecar_status.get_db") as mock_db:
            conn = AsyncMock()
            now = datetime.now(timezone.utc).isoformat()
            conn.fetch = AsyncMock(return_value=[
                {"sidecar": "kairos", "last_completed": now, "last_status": "completed", "pending_count": 3},
            ])
            mock_db.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await client.get("/sidecar/status")
            assert response.status_code == 200
            data = response.json()
            kairos_row = next((r for r in data if r["sidecar"] == "kairos"), None)
            assert kairos_row is not None
            assert kairos_row["pending_count"] == 3


@pytest.mark.asyncio
async def test_sidecar_status_returns_200_on_empty_jobs_table():
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("backend.routers.sidecar_status.get_db") as mock_db:
            conn = AsyncMock()
            conn.fetch = AsyncMock(return_value=[])
            mock_db.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await client.get("/sidecar/status")
            assert response.status_code == 200
            assert response.json() == []
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_sidecar_status.py -v
```

Expected: `ImportError` or route 404.

- [ ] **Step 3: Create `backend/routers/sidecar_status.py`**

```python
"""
GET /sidecar/status

Returns last-run time, pending job count, and last job status per sidecar.
Used by the UI status panel (bottom bar: ●8/8 sidecars indicator).

Reads from sidecar_jobs table — no in-memory state.
"""

from fastapi import APIRouter, Depends
from backend.db.pool import get_db

router = APIRouter(prefix="/sidecar", tags=["sidecar"])


@router.get("/status")
async def sidecar_status(db=Depends(get_db)):
    """
    Aggregate last-run time, last status, and pending job count per sidecar.
    Returns an array of objects — one per sidecar name found in sidecar_jobs.
    """
    async with db as conn:
        rows = await conn.fetch(
            """
            SELECT
                sidecar,
                MAX(completed_at) AS last_completed,
                (
                    SELECT status FROM sidecar_jobs j2
                    WHERE j2.sidecar = j1.sidecar
                    ORDER BY created_at DESC
                    LIMIT 1
                ) AS last_status,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending_count
            FROM sidecar_jobs j1
            GROUP BY sidecar
            ORDER BY sidecar
            """
        )
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Register router in `backend/main.py`**

Add to the existing router registration block:

```python
from backend.routers.sidecar_status import router as sidecar_status_router
app.include_router(sidecar_status_router)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_sidecar_status.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/sidecar_status.py tests/test_sidecar_status.py backend/main.py
git commit -m "feat: add GET /sidecar/status route for UI status panel"
```

---

### Task 10: PM2 Ecosystem Integration

**Files:**
- Modify: `ecosystem.config.js` (add slow sidecar process entries)

- [ ] **Step 1: Verify current ecosystem.config.js exists**

```bash
ls "C:/Users/user/AI-Assistant Version 4/ecosystem.config.js"
```

Expected: file found. If absent, create it as a new file (see Step 2 note below).

- [ ] **Step 2: Add slow sidecar entries to `ecosystem.config.js`**

Locate the `apps` array and add the following five entries. If the file already has partial entries, merge rather than duplicate.

Note on restart policy: `stop_exit_codes: [0]` tells PM2 that exit code 0 is a clean exit (job done, no work) — do NOT restart. Non-zero exit (unhandled exception) triggers the normal `on-failure` restart. `autorestart: true` ensures restarts happen on failure.

```js
// ── Slow Sidecars ─────────────────────────────────────────────────────────
{
  name: "sidecar-kairos",
  script: "python",
  args: "-m backend.sidecars.slow.kairos",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  autorestart: true,
  stop_exit_codes: [0],
  env: {
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4",
    ORDO_DATA_DIR: "C:/Users/user/ordo-data"
  },
  log_date_format: "YYYY-MM-DD HH:mm:ss",
  error_file: "logs/kairos-error.log",
  out_file: "logs/kairos-out.log"
},
{
  name: "sidecar-oneiros",
  script: "python",
  args: "-m backend.sidecars.slow.oneiros",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  autorestart: true,
  stop_exit_codes: [0],
  env: {
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4",
    ORDO_DATA_DIR: "C:/Users/user/ordo-data"
  },
  log_date_format: "YYYY-MM-DD HH:mm:ss",
  error_file: "logs/oneiros-error.log",
  out_file: "logs/oneiros-out.log"
},
{
  name: "sidecar-praxis",
  script: "python",
  args: "-m backend.sidecars.slow.praxis",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  autorestart: true,
  stop_exit_codes: [0],
  env: {
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4",
    ORDO_DATA_DIR: "C:/Users/user/ordo-data"
  },
  log_date_format: "YYYY-MM-DD HH:mm:ss",
  error_file: "logs/praxis-error.log",
  out_file: "logs/praxis-out.log"
},
{
  name: "sidecar-psyche",
  script: "python",
  args: "-m backend.sidecars.slow.psyche",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  autorestart: true,
  stop_exit_codes: [0],
  env: {
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4",
    ORDO_DATA_DIR: "C:/Users/user/ordo-data"
  },
  log_date_format: "YYYY-MM-DD HH:mm:ss",
  error_file: "logs/psyche-error.log",
  out_file: "logs/psyche-out.log"
},
{
  name: "sidecar-augur",
  script: "python",
  args: "-m backend.sidecars.slow.augur",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  autorestart: true,
  stop_exit_codes: [0],
  env: {
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4",
    ORDO_DATA_DIR: "C:/Users/user/ordo-data"
  },
  log_date_format: "YYYY-MM-DD HH:mm:ss",
  error_file: "logs/augur-error.log",
  out_file: "logs/augur-out.log"
},
```

- [ ] **Step 3: Verify PM2 parses the config without error**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
pm2 start ecosystem.config.js --only sidecar-kairos --no-daemon 2>&1 | head -20
```

Expected: PM2 starts and then exits (because no pending job exists — exit code 0). If you see `stop_exit_codes` in the output it confirms the policy is active. No JS parse errors.

- [ ] **Step 4: Run full test suite**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/ -v --tb=short
```

Expected: All tests pass. No failures related to Phase 5 modules.

- [ ] **Step 5: Commit**

```bash
git add ecosystem.config.js
git commit -m "feat: add slow sidecar PM2 process entries (stop_exit_codes:[0])"
```

---

### Task 11: Wire Trigger Logic into Hook Dispatcher

**Files:**
- Modify: `backend/hooks/dispatcher.py`
- Create: `tests/test_dispatcher_slow_triggers.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_dispatcher_slow_triggers.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.hooks.dispatcher import dispatch_hook
from backend.schemas.events import EventType


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.fetch = AsyncMock(return_value=[])   # no hook_handlers rows
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    return pool, conn


@pytest.mark.asyncio
async def test_session_end_hook_triggers_slow_sidecars(mock_pool):
    pool, conn = mock_pool
    with patch("backend.hooks.dispatcher.trigger_session_end_sidecars", new=AsyncMock()) as mock_trigger:
        await dispatch_hook(
            hook_name="session_end",
            payload={"session_id": "sess-001"},
            pool=pool,
        )
        mock_trigger.assert_called_once()
        call_kwargs = mock_trigger.call_args
        assert "sess-001" in str(call_kwargs)


@pytest.mark.asyncio
async def test_user_prompt_submit_calls_maybe_trigger_kairos(mock_pool):
    pool, conn = mock_pool
    with patch("backend.hooks.dispatcher.maybe_trigger_kairos", new=AsyncMock()) as mock_kairos:
        await dispatch_hook(
            hook_name="user_prompt_submit",
            payload={"session_id": "sess-002", "chunk_ids": ["c1"]},
            pool=pool,
        )
        mock_kairos.assert_called_once()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_dispatcher_slow_triggers.py -v
```

Expected: ImportError or assertion failure (trigger functions not yet wired).

- [ ] **Step 3: Modify `backend/hooks/dispatcher.py` to call trigger functions**

In the `dispatch_hook` function, add the following after the hook_handlers table dispatch. Locate the section that handles `session_end` and `user_prompt_submit` hook names and insert:

```python
# ── Slow lane trigger checks ────────────────────────────────────────────────
from backend.hooks.slow_triggers import (
    maybe_trigger_kairos,
    trigger_session_end_sidecars,
    maybe_trigger_psyche,
)

async with pool.acquire() as conn:
    if hook_name == "session_end":
        await trigger_session_end_sidecars(
            conn=conn,
            session_id=payload.get("session_id", ""),
        )
    elif hook_name == "user_prompt_submit":
        await maybe_trigger_kairos(
            conn=conn,
            session_id=payload.get("session_id", ""),
            chunk_ids=payload.get("chunk_ids", []),
        )
        # RIP engine SSS is updated before this point; check valence
        sss = payload.get("sss", {})
        if sss:
            await maybe_trigger_psyche(
                conn=conn,
                session_id=payload.get("session_id", ""),
                sss=sss,
            )
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_dispatcher_slow_triggers.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All prior tests still pass. Total count increases by the Phase 5 additions.

- [ ] **Step 6: Commit**

```bash
git add backend/hooks/dispatcher.py tests/test_dispatcher_slow_triggers.py
git commit -m "feat: wire slow trigger functions into hook dispatcher (session_end, user_prompt_submit)"
```

---

> **Chunk 3 complete. Dispatch plan-document-reviewer:** Review `slow_triggers.py`, `sidecar_status.py`, `dispatcher.py` wiring, and `ecosystem.config.js`. Verify: (1) `stop_exit_codes: [0]` is present for all five slow sidecar PM2 entries, (2) `trigger_session_end_sidecars` queues exactly kairos, oneiros, praxis, and psyche (not augur — augur fires every 50 sessions only), (3) `GET /sidecar/status` reads from `sidecar_jobs` table and returns per-sidecar aggregates, (4) full test suite passes.

---

## Phase 5 Complete

After all chunks are implemented and committed, verify the end-to-end state:

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/ -v --tb=short
```

Expected: All Phase 1–5 tests pass.

### Files Created in Phase 5

| File | Purpose |
|------|---------|
| `backend/sidecars/__init__.py` | Package init |
| `backend/sidecars/slow/__init__.py` | Package init |
| `backend/sidecars/slow/base.py` | SlowSidecar abstract base — claim/complete/fail/execute |
| `backend/sidecars/slow/kairos.py` | Topic graph builder + progressive summaries |
| `backend/sidecars/slow/oneiros.py` | Lossy belief consolidator (never deletes chunks) |
| `backend/sidecars/slow/praxis.py` | Procedural optimizer (Modes 2/3 require approval) |
| `backend/sidecars/slow/psyche.py` | soul.md writer + orientation chunk (bypass_anamnesis=True) |
| `backend/sidecars/slow/augur.py` | N-gram prediction engine (append-only) |
| `backend/hooks/slow_triggers.py` | Trigger decision functions for sidecar_jobs writes |
| `backend/routers/praxis.py` | Approval API: POST /praxis/recommendations/{id}/approve\|reject |
| `backend/routers/sidecar_status.py` | GET /sidecar/status for UI panel |
| `tests/sidecars/__init__.py` | Test package init |
| `tests/sidecars/test_slow_base.py` | SlowSidecar base tests |
| `tests/sidecars/test_kairos.py` | Kairos sidecar tests |
| `tests/sidecars/test_oneiros.py` | Oneiros sidecar tests |
| `tests/sidecars/test_praxis.py` | Praxis sidecar tests |
| `tests/sidecars/test_psyche.py` | Psyche sidecar tests |
| `tests/sidecars/test_augur.py` | Augur sidecar tests |
| `tests/test_slow_triggers.py` | Trigger logic tests |
| `tests/test_praxis_api.py` | Praxis API route tests |
| `tests/test_sidecar_status.py` | Sidecar status route tests |
| `tests/test_dispatcher_slow_triggers.py` | Dispatcher wiring tests |

### Files Modified in Phase 5

| File | Change |
|------|--------|
| `backend/main.py` | Register praxis + sidecar_status routers |
| `backend/hooks/dispatcher.py` | Wire slow trigger calls at session_end and user_prompt_submit |
| `ecosystem.config.js` | Add 5 slow sidecar PM2 process entries with `stop_exit_codes: [0]` |

### Critical Invariants — Final Checklist

- [ ] Oneiros: no DELETE statement anywhere in `oneiros.py` — validated=True only
- [ ] Praxis: no auto-apply code path for Modes 2/3 — `praxis_recommendations` with `status=pending` only
- [ ] Psyche: `soul_path` property uses `os.environ['ORDO_DATA_DIR']` — grep the file to confirm no hardcoded path
- [ ] Augur: only INSERT in `behavioral_sequences` — no UPDATE on existing rows
- [ ] PM2: `stop_exit_codes: [0]` present on all five slow sidecar entries in `ecosystem.config.js`
- [ ] Psyche orientation chunk: `bypass_anamnesis=True` in the INSERT statement
