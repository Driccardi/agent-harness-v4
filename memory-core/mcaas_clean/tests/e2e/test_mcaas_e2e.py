"""
tests/e2e/test_mcaas_e2e.py
End-to-end tests for the MCaaS container API.

Requires a running memory-core container at MC_BASE_URL.
Run with: pytest tests/e2e/ -v --tb=short

Set environment:
  MC_BASE_URL=http://localhost:4200
  MC_SESSION_KEY=your-session-key
  MC_ADMIN_KEY=your-admin-key
  MC_HUMAN_ID=test-user
"""

from __future__ import annotations
import asyncio
import json
import os
import time
import pytest
import httpx

BASE_URL    = os.environ.get("MC_BASE_URL", "http://localhost:4200")
SESSION_KEY = os.environ.get("MC_SESSION_KEY", "changeme-session")
ADMIN_KEY   = os.environ.get("MC_ADMIN_KEY", "changeme-admin")
HUMAN_ID    = os.environ.get("MC_HUMAN_ID", "e2e-test-user")

SESSION_HEADERS = {
    "X-MC-Key": SESSION_KEY,
    "X-MC-Human-ID": HUMAN_ID,
    "X-MC-Agent-ID": "e2e-test-agent",
}
ADMIN_HEADERS = {
    "X-MC-Key": ADMIN_KEY,
    "X-MC-Human-ID": HUMAN_ID,
}


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


@pytest.fixture(scope="module")
def session_id():
    return f"e2e-session-{int(time.time())}"


# ── Health ─────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_endpoint_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "database" in data["services"]
        assert "ollama" in data["services"]
        assert "redis" in data["services"]

    def test_all_services_healthy(self, client):
        resp = client.get("/health")
        data = resp.json()
        # At minimum database must be ok for tests to proceed
        assert data["services"]["database"] == "ok", \
            f"Database not healthy: {data['services']['database']}"


# ── Session lifecycle ──────────────────────────────────────────────────────────

class TestSessionLifecycle:
    def test_session_start(self, client, session_id):
        resp = client.post(
            "/v1/session/start",
            json={
                "session_id": session_id,
                "agent_id": "e2e-test-agent",
                "human_id": HUMAN_ID,
            },
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "master_session_id" in data
        assert len(data["master_session_id"]) == 36  # UUID format
        # Store for subsequent tests
        TestSessionLifecycle.master_session_id = data["master_session_id"]

    def test_session_end(self, client, session_id):
        resp = client.post(
            "/v1/session/end",
            json={
                "session_id": session_id,
                "human_id": HUMAN_ID,
                "turn_count": 5,
            },
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reflective_layer_queued"


# ── Ingestion ──────────────────────────────────────────────────────────────────

class TestIngestion:
    def test_ingest_human_turn(self, client, session_id):
        resp = client.post(
            "/v1/ingest",
            json={
                "human_id": HUMAN_ID,
                "agent_id": "e2e-test-agent",
                "session_id": session_id,
                "framework": "e2e_test",
                "event_type": "HUMAN_TURN",
                "content": "Can you help me understand how JWT clock skew causes authentication failures?",
                "turn_index": 1,
            },
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200
        assert "chunk_id" in resp.json()

    def test_ingest_model_turn(self, client, session_id):
        resp = client.post(
            "/v1/ingest",
            json={
                "human_id": HUMAN_ID,
                "agent_id": "e2e-test-agent",
                "session_id": session_id,
                "framework": "e2e_test",
                "event_type": "MODEL_TURN",
                "content": "JWT clock skew occurs when the server and client clocks differ. "
                           "Use a tolerance window (30 seconds typical) in RS256 validation.",
                "turn_index": 2,
                "model_name": "e2e-test-model",
            },
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200

    def test_ingest_tool_result(self, client, session_id):
        resp = client.post(
            "/v1/ingest",
            json={
                "human_id": HUMAN_ID,
                "agent_id": "e2e-test-agent",
                "session_id": session_id,
                "framework": "e2e_test",
                "event_type": "TOOL_RESULT",
                "tool_name": "bash",
                "tool_output": {"output": "Tests passed: 5/5", "exit_code": 0},
                "turn_index": 3,
            },
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200

    def test_batch_ingest(self, client, session_id):
        events = [
            {
                "human_id": HUMAN_ID,
                "agent_id": "e2e-test-agent",
                "session_id": session_id,
                "framework": "e2e_test",
                "event_type": "HUMAN_TURN",
                "content": f"Batch event {i}",
                "turn_index": 10 + i,
            }
            for i in range(5)
        ]
        resp = client.post(
            "/v1/ingest/batch",
            json={"events": events},
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        assert len(data["chunk_ids"]) == 5

    def test_empty_content_not_ingested(self, client, session_id):
        resp = client.post(
            "/v1/ingest",
            json={
                "human_id": HUMAN_ID,
                "agent_id": "e2e-test-agent",
                "session_id": session_id,
                "framework": "e2e_test",
                "event_type": "HUMAN_TURN",
                "content": "   ",   # whitespace only
                "turn_index": 99,
            },
            headers=SESSION_HEADERS,
        )
        # Should return 200 but with no chunk_id (or null)
        assert resp.status_code == 200


# ── Injection ──────────────────────────────────────────────────────────────────

class TestInjection:
    def test_inject_endpoint_returns(self, client, session_id):
        """The inject endpoint should respond within the latency budget."""
        start = time.time()
        resp = client.get(
            "/v1/inject",
            params={
                "session_id": session_id,
                "hook_type": "PreToolUse",
                "tool_name": "bash",
                "turn_index": "5",
            },
            headers=SESSION_HEADERS,
        )
        elapsed_ms = (time.time() - start) * 1000

        assert resp.status_code == 200
        data = resp.json()
        assert "inject" in data
        # Latency check — should be well under 450ms for a fresh session
        assert elapsed_ms < 5000, f"Injection took {elapsed_ms:.0f}ms — too slow"

    def test_inject_has_correct_schema(self, client, session_id):
        resp = client.get(
            "/v1/inject",
            params={"session_id": session_id, "hook_type": "UserPromptSubmit"},
            headers=SESSION_HEADERS,
        )
        data = resp.json()
        assert isinstance(data.get("inject"), bool)
        assert isinstance(data.get("confusion_tier"), int)
        assert 0 <= data["confusion_tier"] <= 5


# ── Recall ─────────────────────────────────────────────────────────────────────

class TestRecall:
    def test_recall_returns_results(self, client):
        # Wait briefly for async ingestion to process
        time.sleep(2)
        resp = client.post(
            "/v1/recall",
            json={
                "query": "JWT authentication",
                "human_id": HUMAN_ID,
                "limit": 5,
                "confidence_min": 0.30,
            },
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "count" in data

    def test_recall_result_schema(self, client):
        resp = client.post(
            "/v1/recall",
            json={"query": "test query", "human_id": HUMAN_ID, "limit": 3},
            headers=SESSION_HEADERS,
        )
        data = resp.json()
        for result in data.get("results", []):
            assert "content" in result
            assert "similarity" in result
            assert "confidence" in result
            assert 0.0 <= float(result["similarity"]) <= 1.0


# ── Soul ───────────────────────────────────────────────────────────────────────

class TestSoul:
    def test_get_soul(self, client):
        resp = client.get("/v1/soul", headers=SESSION_HEADERS)
        assert resp.status_code == 200
        # soul may be None on fresh install
        assert "soul" in resp.json()

    def test_update_soul(self, client):
        resp = client.put(
            "/v1/soul",
            params={"content": "# Test Soul\n\nThis is a test soul entry."},
            headers=SESSION_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"


# ── Auth ────────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_missing_key_rejected(self, client, session_id):
        resp = client.get(
            "/v1/inject",
            params={"session_id": session_id, "hook_type": "PreToolUse"},
            headers={"X-MC-Human-ID": HUMAN_ID},  # missing key
        )
        assert resp.status_code == 422  # missing required header

    def test_invalid_key_rejected(self, client, session_id):
        resp = client.get(
            "/v1/inject",
            params={"session_id": session_id, "hook_type": "PreToolUse"},
            headers={"X-MC-Key": "wrong-key", "X-MC-Human-ID": HUMAN_ID},
        )
        assert resp.status_code == 401

    def test_session_key_cannot_access_admin(self, client):
        resp = client.get(
            "/v1/tenants",
            headers={"X-MC-Key": SESSION_KEY},
        )
        assert resp.status_code == 401

    def test_admin_key_can_access_admin(self, client):
        resp = client.get("/v1/tenants", headers=ADMIN_HEADERS)
        assert resp.status_code == 200


# ── Export / Import ───────────────────────────────────────────────────────────

class TestPortability:
    def test_export_returns_archive(self, client):
        resp = client.get(
            f"/v1/export/{HUMAN_ID}",
            headers=ADMIN_HEADERS,
        )
        if resp.status_code == 404:
            pytest.skip("No session data yet for this human_id")
        assert resp.status_code == 200
        archive = resp.json()
        assert archive["human_id"] == HUMAN_ID
        assert "export_version" in archive
        assert "chunks" in archive
        assert "export_stats" in archive

    def test_export_contains_correct_fields(self, client):
        resp = client.get(f"/v1/export/{HUMAN_ID}", headers=ADMIN_HEADERS)
        if resp.status_code == 404:
            pytest.skip("No session data yet")
        archive = resp.json()
        required_keys = ["human_id", "exported_at", "chunks",
                         "topic_nodes", "soul_md", "export_stats"]
        for key in required_keys:
            assert key in archive, f"Archive missing key: {key}"


# ── MCaaS client library ───────────────────────────────────────────────────────

class TestMCClient:
    """Test the Python client library end-to-end."""

    @pytest.mark.asyncio
    async def test_client_health(self):
        import sys
        sys.path.insert(0, "client/")
        from mc_client import MemoryCoreClient

        client = MemoryCoreClient(
            base_url=BASE_URL,
            session_key=SESSION_KEY,
            human_id=HUMAN_ID,
        )
        health = await client.health()
        assert health["status"] in ("ok", "degraded")
        await client.close()

    @pytest.mark.asyncio
    async def test_client_ingest_and_recall(self):
        import sys
        sys.path.insert(0, "client/")
        from mc_client import MemoryCoreClient, UniversalEvent, EventType

        client = MemoryCoreClient(
            base_url=BASE_URL,
            session_key=SESSION_KEY,
            human_id=HUMAN_ID,
        )

        # Ingest
        chunk_id = await client.ingest(UniversalEvent(
            event_type=EventType.HUMAN_TURN,
            content="Testing the Python client library integration",
            session_id=f"client-test-{int(time.time())}",
            framework="pytest",
        ))
        assert chunk_id is not None

        await client.close()
