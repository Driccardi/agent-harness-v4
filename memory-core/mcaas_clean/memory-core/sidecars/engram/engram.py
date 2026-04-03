"""
Engram — Real-Time Stream Embedder
Hippocampal analog: fast, continuous, no-loss ingestion of all stream events.

Design principles:
- NEVER pruning. No event is dropped. Oneiros handles forgetting.
- Priority weights applied per signal taxonomy.
- Reasoning blocks are embedded immediately with provisional=True.
- Latency target: <50ms per chunk.
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID

import httpx

from db import client as db

logger = logging.getLogger(__name__)


# ─── Signal taxonomy ──────────────────────────────────────────────────────────

class ChunkType(str, Enum):
    HUMAN = "HUMAN"
    MODEL = "MODEL"
    TOOL_IN = "TOOL_IN"
    TOOL_OUT = "TOOL_OUT"
    REASONING = "REASONING"
    SYSTEM = "SYSTEM"


PRIORITY_WEIGHTS: dict[ChunkType, float] = {
    ChunkType.HUMAN:     1.00,
    ChunkType.MODEL:     0.85,
    ChunkType.TOOL_OUT:  0.80,
    ChunkType.TOOL_IN:   0.65,
    ChunkType.REASONING: 0.40,   # provisional=True
    ChunkType.SYSTEM:    0.30,
}


# ─── Stream event ─────────────────────────────────────────────────────────────

@dataclass
class StreamEvent:
    hook_type: str                       # PreToolUse | PostToolUse | UserPromptSubmit | ...
    session_id: str
    master_session_id: UUID
    turn_index: int
    timestamp: str
    model: Optional[str] = None
    context_tokens: int = 0

    # Content fields (at most one is populated per event type)
    human_content: Optional[str] = None
    model_content: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None
    system_content: Optional[str] = None

    # Proprioception
    input_modality: Optional[str] = None
    input_route: Optional[str] = None
    quota_pressure: Optional[float] = None

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_hook_payload(cls, payload: dict, master_session_id: UUID) -> list["StreamEvent"]:
        """Parse a hook payload into one or more stream events."""
        events = []
        base = dict(
            hook_type=payload.get("hook_type", ""),
            session_id=payload.get("session_id", ""),
            master_session_id=master_session_id,
            turn_index=payload.get("turn_index", 0),
            timestamp=payload.get("timestamp", ""),
            model=payload.get("model"),
            context_tokens=payload.get("context_tokens", 0),
            raw=payload,
        )

        hook = payload.get("hook_type", "")

        if hook == "UserPromptSubmit":
            content = payload.get("user_message", "")
            if content:
                events.append(cls(
                    **base,
                    human_content=content,
                    input_modality=payload.get("input_modality", "TEXT"),
                    input_route=payload.get("input_route", "DIRECT"),
                ))

        elif hook in ("PreToolUse", "PostToolUse"):
            tool_name = payload.get("tool_name", "")
            tool_input = payload.get("tool_input", {})
            tool_output = payload.get("tool_output")

            # Tool input chunk
            if tool_input:
                events.append(cls(
                    **base,
                    tool_name=tool_name,
                    tool_input=tool_input,
                ))
            # Tool output chunk
            if tool_output is not None:
                events.append(cls(
                    **base,
                    tool_name=tool_name,
                    tool_output=tool_output,
                ))

        return events


# ─── Embedding client ─────────────────────────────────────────────────────────

class EmbeddingClient:
    """Wraps Ollama (or any compatible) embedding API."""

    def __init__(self, endpoint: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=10.0)

    async def embed(self, text: str) -> list[float]:
        t0 = time.monotonic()
        response = await self._client.post(
            f"{self.endpoint}/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        response.raise_for_status()
        data = response.json()
        latency_ms = (time.monotonic() - t0) * 1000
        if latency_ms > 100:
            logger.warning(f"Embedding latency high: {latency_ms:.1f}ms")
        return data["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.gather(*[self.embed(t) for t in texts])

    async def close(self):
        await self._client.aclose()


# ─── Eidos notification queue ─────────────────────────────────────────────────

class EidosQueue:
    """Lightweight async queue to notify Eidos of fresh reasoning chunks."""
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    async def put(self, chunk_id: UUID, content: str) -> None:
        try:
            self._queue.put_nowait({"chunk_id": str(chunk_id), "content": content})
        except asyncio.QueueFull:
            logger.warning("Eidos queue full — dropping chunk notification")

    async def get(self) -> Optional[dict]:
        return await self._queue.get()

    def qsize(self) -> int:
        return self._queue.qsize()


# ─── Engram core ──────────────────────────────────────────────────────────────

class Engram:
    """
    Real-time stream embedder.
    Ingests every hook event and persists to the chunks table.
    No pruning. No loss. No exceptions.
    """

    def __init__(
        self,
        embedder: Optional[EmbeddingClient] = None,
        eidos_queue: Optional[EidosQueue] = None,
    ):
        self.embedder = embedder or EmbeddingClient()
        self.eidos_queue = eidos_queue or EidosQueue()

    def _classify_event(self, event: StreamEvent) -> ChunkType:
        if event.human_content:
            return ChunkType.HUMAN
        if event.reasoning_content:
            return ChunkType.REASONING
        if event.model_content:
            return ChunkType.MODEL
        if event.system_content:
            return ChunkType.SYSTEM
        if event.tool_output is not None:
            return ChunkType.TOOL_OUT
        if event.tool_input is not None:
            return ChunkType.TOOL_IN
        return ChunkType.SYSTEM

    def _extract_content(self, event: StreamEvent, chunk_type: ChunkType) -> str:
        match chunk_type:
            case ChunkType.HUMAN:
                return event.human_content or ""
            case ChunkType.REASONING:
                return event.reasoning_content or ""
            case ChunkType.MODEL:
                return event.model_content or ""
            case ChunkType.SYSTEM:
                return event.system_content or ""
            case ChunkType.TOOL_OUT:
                return json.dumps(event.tool_output, ensure_ascii=False)[:4000]
            case ChunkType.TOOL_IN:
                payload = {"tool": event.tool_name, "input": event.tool_input}
                return json.dumps(payload, ensure_ascii=False)[:2000]
            case _:
                return ""

    async def ingest(self, event: StreamEvent) -> Optional[UUID]:
        """
        Embed and persist a single stream event.
        Returns chunk_id on success, None if content is empty.
        """
        t0 = time.monotonic()

        chunk_type = self._classify_event(event)
        content = self._extract_content(event, chunk_type)

        if not content.strip():
            return None

        provisional = chunk_type == ChunkType.REASONING
        confidence = PRIORITY_WEIGHTS[chunk_type]

        try:
            embedding = await self.embedder.embed(content)
        except Exception as e:
            logger.error(f"Embedding failed for {chunk_type}: {e}")
            # Store without embedding rather than losing the chunk
            embedding = None

        context_pressure = (
            event.context_tokens / 200_000  # max context assumption
            if event.context_tokens else None
        )

        chunk_id = await db.insert_chunk(
            master_session_id=event.master_session_id,
            session_id=event.session_id,
            turn_index=event.turn_index,
            source_framework="claude_code",
            chunk_type=chunk_type.value,
            content=content,
            raw_event=event.raw,
            confidence=confidence,
            provisional=provisional,
            embedding=embedding,
            input_modality=event.input_modality,
            context_pressure=context_pressure,
        )

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.debug(
            f"Engram ingested chunk_id={chunk_id} type={chunk_type.value} "
            f"provisional={provisional} elapsed={elapsed_ms:.1f}ms"
        )

        # Notify Eidos for somatic enrichment
        if provisional or chunk_type == ChunkType.HUMAN:
            await self.eidos_queue.put(chunk_id, content)

        return chunk_id

    async def ingest_events(self, events: list[StreamEvent]) -> list[Optional[UUID]]:
        """Ingest multiple events concurrently (still preserves all)."""
        return await asyncio.gather(*[self.ingest(e) for e in events])

    async def validate_chunk(self, chunk_id: UUID) -> None:
        """Promote a provisional chunk to validated."""
        await db.execute(
            "UPDATE chunks SET provisional=FALSE, validated=TRUE, confidence=0.85 "
            "WHERE chunk_id=$1",
            str(chunk_id),
        )

    async def abandon_chunk(self, chunk_id: UUID) -> None:
        """Mark a provisional chunk as abandoned (negative knowledge)."""
        await db.execute(
            "UPDATE chunks SET confidence=0.10, validated=FALSE WHERE chunk_id=$1",
            str(chunk_id),
        )
