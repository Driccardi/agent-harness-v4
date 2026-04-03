"""
mc_client.py — Memory-Core Client Library
pip install memory-core-client  (or copy this file directly)

Usage:
    from mc_client import MemoryCoreClient, UniversalEvent, EventType

    client = MemoryCoreClient(
        base_url="http://localhost:4200",
        session_key=os.environ["MC_SESSION_KEY"],
        human_id=os.environ["MC_HUMAN_ID"],
    )

    # Ingest an event
    await client.ingest(UniversalEvent(
        event_type=EventType.HUMAN_TURN,
        content="Can you help me debug this?",
        session_id="session-123",
        framework="claude_code",
    ))

    # Get injection for a hook point
    injection = await client.get_injection(
        hook_type="PreToolUse",
        session_id="session-123",
        tool_name="bash",
    )
    print(injection.system_message)
"""

from __future__ import annotations
import asyncio
import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Any
from uuid import UUID, uuid4

import httpx


# ─── Event Types ─────────────────────────────────────────────────────────────

class EventType(str, Enum):
    HUMAN_TURN      = "HUMAN_TURN"
    MODEL_TURN      = "MODEL_TURN"
    MODEL_REASONING = "MODEL_REASONING"   # extended thinking
    TOOL_USE        = "TOOL_USE"
    TOOL_RESULT     = "TOOL_RESULT"
    SKILL_INVOKE    = "SKILL_INVOKE"
    SKILL_RESULT    = "SKILL_RESULT"
    SYSTEM_MESSAGE  = "SYSTEM_MESSAGE"
    SESSION_START   = "SESSION_START"
    SESSION_END     = "SESSION_END"
    HUMAN_CORRECTION = "HUMAN_CORRECTION"


# ─── Universal Event ──────────────────────────────────────────────────────────

@dataclass
class UniversalEvent:
    """
    The normalized event schema. Every adapter translates its framework's
    native events into this format before calling the API.
    """
    # Identity (required)
    human_id: str = ""
    agent_id: str = "default-agent"
    session_id: str = ""
    framework: str = "unknown"

    # Classification (required)
    event_type: EventType = EventType.HUMAN_TURN
    turn_index: int = 0
    timestamp: str = ""

    # Content (at most one populated per event)
    content: Optional[str] = None         # human/model text
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None

    # Machine proprioception (optional)
    context_tokens: Optional[int] = None
    max_tokens: Optional[int] = None
    input_modality: Optional[str] = None  # TEXT|VOICE|FILE_UPLOAD|API
    model_name: Optional[str] = None
    latency_ms: Optional[int] = None

    # Pass-through framework metadata
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            from datetime import datetime, timezone
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return {k: v for k, v in d.items() if v is not None}


# ─── Injection Response ───────────────────────────────────────────────────────

@dataclass
class InjectionResponse:
    inject: bool = False
    system_message: Optional[str] = None
    additional_context: Optional[str] = None
    confusion_tier: int = 0
    psyche_steering: Optional[str] = None
    orchestration_hints: list = field(default_factory=list)
    session_arc: Optional[dict] = None

    @classmethod
    def from_dict(cls, data: dict) -> "InjectionResponse":
        return cls(
            inject=data.get("inject", False),
            system_message=data.get("system_message"),
            additional_context=data.get("additional_context"),
            confusion_tier=data.get("confusion_tier", 0),
            psyche_steering=data.get("psyche_steering"),
            orchestration_hints=data.get("orchestration_hints", []),
            session_arc=data.get("session_arc"),
        )

    @classmethod
    def empty(cls) -> "InjectionResponse":
        return cls(inject=False)


# ─── Session Start Response ───────────────────────────────────────────────────

@dataclass
class SessionStartResponse:
    master_session_id: str = ""
    orient_injection: Optional[str] = None
    open_loops: list = field(default_factory=list)
    augur_briefing: Optional[str] = None
    session_gap_hours: float = 0.0


# ─── Client ───────────────────────────────────────────────────────────────────

class MemoryCoreClient:
    """
    Async client for the Memory-Core container API.
    Thread-safe. Reuse one instance per process.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:4200",
        session_key: str = "",
        human_id: str = "",
        agent_id: str = "default-agent",
        timeout: float = 5.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.human_id = human_id or os.environ.get("MC_HUMAN_ID", "default")
        self.agent_id = agent_id
        self._headers = {
            "X-MC-Key": session_key or os.environ.get("MC_SESSION_KEY", ""),
            "X-MC-Human-ID": self.human_id,
            "X-MC-Agent-ID": agent_id,
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=timeout,
        )

    async def ingest(self, event: UniversalEvent) -> Optional[str]:
        """
        Ingest a single event. Fire-and-forget pattern.
        Returns chunk_id on success, None on failure (non-fatal).
        """
        if not event.human_id:
            event.human_id = self.human_id
        if not event.agent_id:
            event.agent_id = self.agent_id

        try:
            resp = await self._client.post("/v1/ingest", json=event.to_dict())
            resp.raise_for_status()
            return resp.json().get("chunk_id")
        except Exception as e:
            # Ingestion failures are non-fatal — agent must not be blocked
            import logging
            logging.getLogger(__name__).warning(f"MC ingest failed: {e}")
            return None

    async def ingest_batch(self, events: list[UniversalEvent]) -> list[Optional[str]]:
        """Batch ingest up to 100 events."""
        payload = [e.to_dict() for e in events]
        try:
            resp = await self._client.post("/v1/ingest/batch", json={"events": payload})
            resp.raise_for_status()
            return resp.json().get("chunk_ids", [])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"MC batch ingest failed: {e}")
            return [None] * len(events)

    async def get_injection(
        self,
        hook_type: str,
        session_id: str,
        tool_name: str = "",
        turn_index: int = 0,
    ) -> InjectionResponse:
        """
        Get memory injection for current hook point.
        This is the latency-sensitive path — must return within hook budget.
        """
        try:
            params = {
                "session_id": session_id,
                "hook_type": hook_type,
                "turn_index": str(turn_index),
            }
            if tool_name:
                params["tool_name"] = tool_name

            resp = await self._client.get("/v1/inject", params=params)
            resp.raise_for_status()
            return InjectionResponse.from_dict(resp.json())
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"MC injection failed: {e}")
            return InjectionResponse.empty()

    async def session_start(
        self,
        session_id: str,
        project_id: str = "",
    ) -> SessionStartResponse:
        """Notify session start. Returns orient injection and open loops."""
        try:
            resp = await self._client.post("/v1/session/start", json={
                "session_id": session_id,
                "agent_id": self.agent_id,
                "human_id": self.human_id,
                "project_id": project_id,
            })
            resp.raise_for_status()
            data = resp.json()
            return SessionStartResponse(
                master_session_id=data.get("master_session_id", ""),
                orient_injection=data.get("orient_injection"),
                open_loops=data.get("open_loops", []),
                augur_briefing=data.get("augur_briefing"),
                session_gap_hours=data.get("session_gap_hours", 0.0),
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"MC session_start failed: {e}")
            return SessionStartResponse()

    async def session_end(self, session_id: str, turn_count: int = 0) -> None:
        """Notify session end. Triggers reflective layer (async in container)."""
        try:
            await self._client.post("/v1/session/end", json={
                "session_id": session_id,
                "turn_count": turn_count,
                "human_id": self.human_id,
            })
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"MC session_end failed: {e}")

    async def recall(
        self,
        query: str,
        limit: int = 10,
        confidence_min: float = 0.60,
        recency_days: int = 90,
    ) -> list[dict]:
        """Semantic recall. Returns ranked chunk list."""
        try:
            resp = await self._client.post("/v1/recall", json={
                "query": query,
                "human_id": self.human_id,
                "limit": limit,
                "confidence_min": confidence_min,
                "recency_days": recency_days,
            })
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception:
            return []

    async def get_soul(self) -> str:
        """Read soul.md for this human."""
        try:
            resp = await self._client.get("/v1/soul")
            resp.raise_for_status()
            return resp.json().get("soul", "")
        except Exception:
            return ""

    async def health(self) -> dict:
        """Check container health."""
        try:
            resp = await self._client.get("/health", timeout=3.0)
            return resp.json()
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    async def close(self):
        await self._client.aclose()

    def get_injection_sync(
        self,
        hook_type: str,
        session_id: str,
        tool_name: str = "",
        turn_index: int = 0,
    ) -> InjectionResponse:
        """Synchronous wrapper for use in non-async hook scripts."""
        return asyncio.run(self.get_injection(hook_type, session_id, tool_name, turn_index))

    def ingest_sync(self, event: UniversalEvent) -> Optional[str]:
        """Synchronous wrapper."""
        return asyncio.run(self.ingest(event))

    def session_start_sync(self, session_id: str, project_id: str = "") -> SessionStartResponse:
        return asyncio.run(self.session_start(session_id, project_id))

    def session_end_sync(self, session_id: str, turn_count: int = 0) -> None:
        asyncio.run(self.session_end(session_id, turn_count))


# ─── Convenience factory ──────────────────────────────────────────────────────

def client_from_env() -> MemoryCoreClient:
    """Create a client from environment variables."""
    return MemoryCoreClient(
        base_url=os.environ.get("MC_BASE_URL", "http://localhost:4200"),
        session_key=os.environ.get("MC_SESSION_KEY", ""),
        human_id=os.environ.get("MC_HUMAN_ID", "default"),
        agent_id=os.environ.get("MC_AGENT_ID", "default-agent"),
    )
