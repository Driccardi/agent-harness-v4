"""
Anamnesis — Injection Agent
Associative recall without explicit retrieval.
Memories surface at natural pause points via the conjunctive gate.

Core principle: The gate is biased toward silence.
Injection requires a positive case from EVERY dimension.
Any single failure blocks injection entirely.
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from db import client as db
from sidecars.engram.engram import EmbeddingClient

logger = logging.getLogger(__name__)


# ─── Gate check result ────────────────────────────────────────────────────────

@dataclass
class GateCheck:
    name: str
    passed: bool
    reason: str = ""


@dataclass
class GateDecision:
    inject: bool
    chunk_id: Optional[UUID]
    similarity: float = 0.0
    checks: list[GateCheck] = field(default_factory=list)

    @property
    def first_failure(self) -> Optional[GateCheck]:
        return next((c for c in self.checks if not c.passed), None)


# ─── Session state tracker ────────────────────────────────────────────────────

@dataclass
class SessionState:
    session_id: str
    master_session_id: UUID
    turn_index: int = 0
    confusion_score: float = 0.0
    injections_this_turn: int = 0
    injections_this_session: int = 0
    topic_injections: dict[str, int] = field(default_factory=dict)
    recent_injected_chunk_ids: list[str] = field(default_factory=list)
    recent_content_embeddings: list[list[float]] = field(default_factory=list)

    def confusion_tier(self) -> int:
        s = self.confusion_score
        if s < 0.30: return 0   # nominal
        if s < 0.45: return 1   # elevated
        if s < 0.60: return 2   # warning
        if s < 0.75: return 3   # high
        if s < 0.90: return 4   # critical
        return 5                # full stop

    def threshold_offset(self) -> float:
        return [0.00, 0.05, 0.10, 0.15, 0.20, 0.25][self.confusion_tier()]

    def injection_suspended(self) -> bool:
        return self.confusion_tier() >= 4

    def max_injections_this_turn(self) -> int:
        return [3, 3, 2, 1, 0, 0][self.confusion_tier()]


# ─── The Conjunctive Gate ─────────────────────────────────────────────────────

class InjectionGate:
    """
    All 8 conditions must pass for injection to proceed.
    Default posture: do not inject.
    """

    def __init__(self, cfg: dict):
        self.base_threshold = cfg.get("base_similarity_threshold", 0.78)
        self.age_penalty_per_day = cfg.get("age_penalty_per_day", 0.005)
        self.in_context_redundancy = cfg.get("in_context_redundancy_threshold", 0.92)
        self.net_new_threshold = cfg.get("net_new_threshold", 0.88)
        self.recency_window = cfg.get("recency_window_turns", 5)
        self.topic_window = cfg.get("topic_injection_window_turns", 10)
        self.max_topic_inj = cfg.get("max_topic_injections_per_window", 3)

    def _cosine(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb + 1e-9)

    def evaluate(
        self,
        candidate: dict,          # DB row from anamnesis_search
        query_embedding: list[float],
        session: SessionState,
    ) -> GateDecision:

        chunk_id = UUID(str(candidate["chunk_id"]))
        similarity = float(candidate["similarity"])
        topic_labels = candidate.get("topic_labels") or []
        primary_topic = topic_labels[0] if topic_labels else "__unknown__"
        created_at = candidate["created_at"]
        candidate_embedding = candidate.get("embedding")

        checks: list[GateCheck] = []

        # ── 1. Similarity floor ──────────────────────────────────────────────
        min_sim = self.base_threshold + session.threshold_offset()
        checks.append(GateCheck(
            "similarity_floor",
            similarity >= min_sim,
            f"sim={similarity:.3f} threshold={min_sim:.3f}",
        ))

        # ── 2. Not already in context window ────────────────────────────────
        already_in_context = False
        if candidate_embedding and session.recent_content_embeddings:
            max_context_sim = max(
                self._cosine(candidate_embedding, e)
                for e in session.recent_content_embeddings[-10:]
            )
            already_in_context = max_context_sim > self.in_context_redundancy
        checks.append(GateCheck(
            "not_in_context",
            not already_in_context,
            "Memory already recoverable from context window",
        ))

        # ── 3. Temporal confidence (age penalty) ─────────────────────────────
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        age_days = max(0, (now - created_at).days)
        required = self.base_threshold + age_penalty = (age_days * self.age_penalty_per_day)
        checks.append(GateCheck(
            "temporal_confidence",
            similarity >= required,
            f"Age={age_days}d requires sim>={required:.3f}, got {similarity:.3f}",
        ))

        # ── 4. Topic frequency (frequency drift prevention) ──────────────────
        recent_topic_count = session.topic_injections.get(primary_topic, 0)
        checks.append(GateCheck(
            "topic_frequency",
            recent_topic_count < self.max_topic_inj,
            f"Topic '{primary_topic}' injected {recent_topic_count}x this window",
        ))

        # ── 5. Net new information (recency flood prevention) ─────────────────
        is_new = True
        if candidate_embedding and session.recent_content_embeddings:
            for recent_emb in session.recent_content_embeddings[-self.recency_window:]:
                if self._cosine(candidate_embedding, recent_emb) > self.net_new_threshold:
                    is_new = False
                    break
        checks.append(GateCheck(
            "net_new_information",
            is_new,
            "Candidate is restatement of recent content",
        ))

        # ── 6. Not already injected this session ─────────────────────────────
        already_injected = str(chunk_id) in session.recent_injected_chunk_ids
        checks.append(GateCheck(
            "not_already_injected",
            not already_injected,
            "Chunk already injected this session",
        ))

        # ── 7. Turn injection budget ─────────────────────────────────────────
        under_turn_budget = session.injections_this_turn < session.max_injections_this_turn()
        checks.append(GateCheck(
            "turn_budget",
            under_turn_budget,
            f"Turn budget exhausted ({session.injections_this_turn}/{session.max_injections_this_turn()})",
        ))

        # ── 8. Confusion headroom ────────────────────────────────────────────
        checks.append(GateCheck(
            "confusion_headroom",
            not session.injection_suspended(),
            f"Injection suspended at confusion tier {session.confusion_tier()}",
        ))

        all_passed = all(c.passed for c in checks)
        return GateDecision(
            inject=all_passed,
            chunk_id=chunk_id,
            similarity=similarity,
            checks=checks,
        )


# ─── Injection formatter ──────────────────────────────────────────────────────

def format_injection(candidate: dict, chunk_type: str = "episodic") -> str:
    """Format a chunk as an injection memory block."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    created_at = candidate["created_at"]
    age_days = max(0, (now - created_at).days)
    topics = ", ".join(candidate.get("topic_labels") or [])
    content = candidate["content"][:1200].strip()

    return (
        f'<memory type="{chunk_type}" '
        f'relevance="{candidate["similarity"]:.2f}" '
        f'age_days="{age_days}"'
        + (f' topic="{topics}"' if topics else "")
        + f'>\n{content}\n</memory>'
    )


# ─── Anamnesis core ───────────────────────────────────────────────────────────

class Anamnesis:
    """
    Injection agent — ambient associative recall.
    Fires at hook pause points, delivers relevant memories to the model
    without the model requesting them.
    """

    def __init__(self, cfg: dict, embedder: Optional[EmbeddingClient] = None):
        self.cfg = cfg
        self.embedder = embedder or EmbeddingClient()
        self.gate = InjectionGate(cfg)
        self.latency_budget = cfg.get("hook_latency_budget_ms", 450) / 1000

    async def run(
        self,
        hook_payload: dict,
        session: SessionState,
        psyche_steering: Optional[str] = None,
    ) -> str:
        """
        Main entry point. Returns injection XML string (may be empty).
        Psyche steering bypasses the gate unconditionally.
        """
        t0 = time.monotonic()

        injections: list[str] = []

        # ── Psyche bypass (unconditional, gate-bypassing) ────────────────────
        if psyche_steering:
            injections.append(psyche_steering)
            logger.debug("Psyche steering injected (gate bypass)")

        # ── Standard associative retrieval ───────────────────────────────────
        if session.injection_suspended():
            tier = session.confusion_tier()
            if tier >= 5:
                advisory = (
                    "<system_advisory>Confusion score critical. "
                    "Consider summarizing current state before proceeding.</system_advisory>"
                )
                injections.append(advisory)
            logger.info(f"Injection suspended at confusion tier {tier}")
        else:
            # Build query from current context
            query_text = self._extract_query_context(hook_payload)
            if query_text:
                try:
                    async with asyncio.timeout(self.latency_budget - 0.05):
                        query_embedding = await self.embedder.embed(query_text)
                        candidates = await db.anamnesis_search(
                            embedding=query_embedding,
                            master_session_id=session.master_session_id,
                            current_session_id=session.session_id,
                            confidence_floor=0.50,
                            recency_days=self.cfg.get("recency_days_default", 90),
                            similarity_floor=self.gate.base_threshold - 0.10,
                            limit=20,  # fetch more, gate will filter
                        )

                        for candidate in candidates:
                            if session.injections_this_turn >= session.max_injections_this_turn():
                                break
                            decision = self.gate.evaluate(candidate, query_embedding, session)
                            await self._log_gate_decision(decision, session, hook_payload)

                            if decision.inject:
                                injections.append(format_injection(candidate))
                                session.injections_this_turn += 1
                                session.injections_this_session += 1
                                cid = str(decision.chunk_id)
                                session.recent_injected_chunk_ids.append(cid)
                                # Track topic frequency
                                for label in (candidate.get("topic_labels") or []):
                                    session.topic_injections[label] = \
                                        session.topic_injections.get(label, 0) + 1

                except asyncio.TimeoutError:
                    logger.warning(f"Anamnesis timeout after {self.latency_budget:.1f}s")

        elapsed = time.monotonic() - t0
        logger.debug(f"Anamnesis injections={len(injections)} elapsed={elapsed*1000:.1f}ms")

        return "\n\n".join(injections)

    def _extract_query_context(self, payload: dict) -> str:
        """Extract the richest query context from the hook payload."""
        parts = []
        hook = payload.get("hook_type", "")

        if hook == "UserPromptSubmit":
            parts.append(payload.get("user_message", ""))
        elif hook in ("PreToolUse", "PostToolUse"):
            tool_name = payload.get("tool_name", "")
            tool_input = payload.get("tool_input", {})
            if tool_name:
                parts.append(f"Tool: {tool_name}")
            if isinstance(tool_input, dict):
                # Grab most meaningful fields
                for key in ("command", "query", "path", "content", "description"):
                    if key in tool_input:
                        parts.append(str(tool_input[key])[:500])

        return " ".join(parts)[:2000]

    async def _log_gate_decision(
        self, decision: GateDecision, session: SessionState, payload: dict
    ) -> None:
        try:
            gate_checks_json = json.dumps([
                {"name": c.name, "passed": c.passed, "reason": c.reason}
                for c in decision.checks
            ])
            await db.execute(
                db.INSERT_INJECTION_LOG,
                str(session.master_session_id),
                session.session_id,
                session.turn_index,
                payload.get("hook_type", ""),
                str(decision.chunk_id) if decision.chunk_id else None,
                decision.similarity,
                decision.inject,
                decision.first_failure.reason if not decision.inject and decision.first_failure else None,
                session.confusion_tier(),
                gate_checks_json,
            )
        except Exception as e:
            logger.warning(f"Failed to log gate decision: {e}")
