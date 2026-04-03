"""
Augur — Predictive Engine
Named for the Roman practice of divination through observation of natural patterns.

Learns behavioral patterns from session history and generates:
- Intent predictions for the next human turn
- Pre-fetch queries for Anamnesis
- Emergent orchestration hints from skill sequence patterns
- Speculative execution workers for high-confidence predictions

The prediction is not "what do people generally ask next."
It is "what does THIS person typically do next, in THIS kind of context,
based on EVERYTHING I have observed about them."
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import anthropic

from db import client as db
from sidecars.engram.engram import EmbeddingClient

logger = logging.getLogger(__name__)


# ─── Intent class vocabulary ──────────────────────────────────────────────────

INTENT_CLASSES = {
    0:  "orient/context-restore",
    1:  "task-assignment",
    2:  "clarification-question",
    3:  "approval",
    4:  "correction",
    5:  "status-check",
    6:  "scope-expansion",
    7:  "scope-reduction",
    8:  "deep-dive-request",
    9:  "pivot",
    10: "completion-acknowledgment",
    11: "content-provision",
    12: "emotional-expression",
    13: "meta-conversation",
    14: "session-end-signal",
}

INTENT_CLASSES_REVERSE = {v: k for k, v in INTENT_CLASSES.items()}


# ─── N-gram sequence index ────────────────────────────────────────────────────

@dataclass
class SequenceHit:
    skill_name: str
    probability: float
    session_count: int
    evidence_sessions: list[str] = field(default_factory=list)


class BehavioralNgramIndex:
    """
    Builds a probability distribution over next interactions
    given the last N interactions.
    """

    def __init__(self, max_n: int = 4):
        self.max_n = max_n
        # counts[(context_tuple)][next_skill] = count
        self.counts: dict = defaultdict(lambda: defaultdict(int))
        self.session_refs: dict = defaultdict(lambda: defaultdict(list))

    def record_sequence(
        self,
        skill_sequence: list[str],
        session_id: str,
    ) -> None:
        """Record all n-gram patterns from a skill sequence."""
        for n in range(1, self.max_n + 1):
            for i in range(len(skill_sequence) - n):
                context = tuple(skill_sequence[i:i + n])
                next_skill = skill_sequence[i + n]
                self.counts[context][next_skill] += 1
                if session_id not in self.session_refs[context][next_skill]:
                    self.session_refs[context][next_skill].append(session_id)

    def predict(
        self,
        recent_skills: list[str],
        min_observations: int = 3,
        min_probability: float = 0.65,
    ) -> list[SequenceHit]:
        """Predict the next likely skill given recent skill sequence."""
        hits = []

        for n in range(min(self.max_n, len(recent_skills)), 0, -1):
            context = tuple(recent_skills[-n:])
            if context not in self.counts:
                continue

            total = sum(self.counts[context].values())
            candidates = sorted(
                self.counts[context].items(),
                key=lambda x: -x[1],
            )

            for skill, count in candidates:
                prob = count / total
                session_count = len(self.session_refs[context][skill])
                if count >= min_observations and prob >= min_probability:
                    hits.append(SequenceHit(
                        skill_name=skill,
                        probability=prob,
                        session_count=session_count,
                        evidence_sessions=self.session_refs[context][skill][:3],
                    ))

            if hits:
                break  # use highest-n match

        return sorted(hits, key=lambda h: -h.probability)

    def prune(
        self,
        max_age_sessions: int = 100,
        min_probability: float = 0.40,
    ) -> int:
        """Remove stale low-probability patterns."""
        pruned = 0
        contexts_to_delete = []

        for context, next_skills in self.counts.items():
            total = sum(next_skills.values())
            skills_to_delete = [
                skill for skill, count in next_skills.items()
                if count / total < min_probability
            ]
            for skill in skills_to_delete:
                del self.counts[context][skill]
                pruned += 1
            if not self.counts[context]:
                contexts_to_delete.append(context)

        for ctx in contexts_to_delete:
            del self.counts[ctx]

        return pruned


# ─── Session arc inference ────────────────────────────────────────────────────

SESSION_ARC_PROMPT = """You are analyzing an AI agent session to infer the human's intent and session phase.

Given the recent interaction sequence for THIS specific human:
{interaction_sequence}

Current session context: {session_context}

Infer:
1. The human's overall goal for this session (be specific, not generic)
2. Sub-goals that have been completed or are in progress
3. The current session phase (orient/plan/implement/test/review/cleanup)
4. What constitutes completion of the session goal
5. Your confidence in this inference

Respond ONLY with JSON:
{{
  "inferred_goal": "...",
  "sub_goals": ["completed: ...", "in_progress: ...", "upcoming: ..."],
  "current_phase": "...",
  "completion_criteria": "...",
  "confidence": 0.0-1.0
}}"""


# ─── Augur core ───────────────────────────────────────────────────────────────

@dataclass
class PredictionResult:
    intent_class: int
    intent_label: str
    probability: float
    top_3: list[dict]
    session_arc: Optional[dict] = None
    sequence_hints: list[SequenceHit] = field(default_factory=list)
    prefetch_query_embedding: Optional[list[float]] = None


class Augur:
    """
    Predictive engine.
    Learns from behavioral history; anticipates next interactions.
    """

    def __init__(
        self,
        cfg: dict,
        embedder: Optional[EmbeddingClient] = None,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self.cfg = cfg
        self.embedder = embedder or EmbeddingClient()
        self.model = os.environ.get("ATLAS_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.client = client or anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self.sequence_index = BehavioralNgramIndex(
            max_n=cfg.get("ngram_max_n", 4)
        )
        self.min_observations = cfg.get("sequence_min_observations", 3)
        self.min_probability = cfg.get("sequence_min_probability", 0.65)

        # Speculative execution thresholds
        self.spec_idempotent_threshold = cfg.get("speculative_idempotent_threshold", 0.55)
        self.spec_nonidempotent_threshold = cfg.get("speculative_nonidempotent_threshold", 0.85)

    async def predict_next_intent(
        self,
        master_session_id: UUID,
        recent_turns: int = 10,
    ) -> Optional[PredictionResult]:
        """
        Predict the intent class of the next human turn.
        Uses heuristic rule-based classification until ML models are trained.
        """
        # Fetch recent interactions for pattern matching
        rows = await db.fetchall(
            """
            SELECT chunk_type, content, somatic_register
            FROM chunks
            WHERE master_session_id = $1
              AND NOT provisional AND NOT archived
            ORDER BY created_at DESC
            LIMIT $2
            """,
            str(master_session_id), recent_turns * 3,
        )

        if not rows:
            return None

        # Heuristic intent classification (pre-ML)
        # In Phase 9, replace with Model A inference
        recent_content = " ".join(r["content"][:200] for r in rows[:5]).lower()

        intent_class = 1  # default: task-assignment
        probability = 0.50

        if any(w in recent_content for w in ["done", "complete", "finished", "great", "perfect"]):
            intent_class = 10  # completion-acknowledgment
            probability = 0.65
        elif any(w in recent_content for w in ["what about", "also", "and can you"]):
            intent_class = 6   # scope-expansion
            probability = 0.60
        elif any(w in recent_content for w in ["actually", "no, wait", "instead"]):
            intent_class = 4   # correction
            probability = 0.65
        elif any(w in recent_content for w in ["how", "why", "explain", "tell me more"]):
            intent_class = 8   # deep-dive-request
            probability = 0.55

        top_3 = [
            {"intent": INTENT_CLASSES[intent_class], "probability": probability},
            {"intent": INTENT_CLASSES[(intent_class + 1) % 15], "probability": 0.20},
            {"intent": INTENT_CLASSES[(intent_class + 2) % 15], "probability": 0.10},
        ]

        return PredictionResult(
            intent_class=intent_class,
            intent_label=INTENT_CLASSES[intent_class],
            probability=probability,
            top_3=top_3,
        )

    async def get_sequence_hints(
        self,
        master_session_id: UUID,
        recent_skills: list[str],
    ) -> list[SequenceHit]:
        """Get orchestration hints from behavioral sequence patterns."""
        return self.sequence_index.predict(
            recent_skills,
            min_observations=self.min_observations,
            min_probability=self.min_probability,
        )

    def format_orchestration_hint(self, hit: SequenceHit) -> str:
        """Format a sequence hint as an injection."""
        return (
            f'<orchestration_hint probability="{hit.probability:.0%}" '
            f'basis="{hit.session_count}_sessions">\n'
            f"In similar contexts, the next step has been to invoke '{hit.skill_name}'.\n"
            f"This is a pattern observation, not an instruction.\n"
            f"Follow if it serves the current goal.\n"
            f"</orchestration_hint>"
        )

    async def infer_session_arc(
        self,
        master_session_id: UUID,
        session_id: str,
    ) -> Optional[dict]:
        """Infer the session arc and current phase using LLM analysis."""
        rows = await db.fetchall(
            """
            SELECT chunk_type, content
            FROM chunks
            WHERE master_session_id = $1 AND session_id = $2
              AND chunk_type IN ('HUMAN', 'MODEL')
              AND NOT provisional AND NOT archived
            ORDER BY created_at DESC
            LIMIT 20
            """,
            str(master_session_id), session_id,
        )

        if not rows:
            return None

        sequence = "\n".join(
            f"[{r['chunk_type']}]: {r['content'][:200]}"
            for r in reversed(rows)
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=400,
                messages=[{"role": "user", "content": SESSION_ARC_PROMPT.format(
                    interaction_sequence=sequence,
                    session_context="",
                )}],
                timeout=8.0,
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Augur session arc inference failed: {e}")
            return None

    async def session_start_briefing(
        self,
        master_session_id: UUID,
    ) -> Optional[str]:
        """
        Generate a session-start prediction briefing.
        Returns injection string if useful predictions exist.
        """
        # Load recent behavioral sequences for this human
        rows = await db.fetchall(
            """
            SELECT skill_invoked, followed_by_skill, session_id
            FROM behavioral_sequences
            WHERE master_session_id = $1 AND skill_invoked IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 200
            """,
            str(master_session_id),
        )

        if not rows:
            return None

        # Rebuild sequence index from DB
        sessions: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            if row["skill_invoked"]:
                sessions[row["session_id"]].append(row["skill_invoked"])

        for session_id, skills in sessions.items():
            self.sequence_index.record_sequence(skills, session_id)

        # Get last-session skills for context
        last_session_skills = list(sessions.values())[-1] if sessions else []
        hints = self.sequence_index.predict(
            last_session_skills,
            min_observations=self.min_observations,
            min_probability=self.min_probability,
        )

        if not hints:
            return None

        lines = ["<augur_briefing type='session_start'>"]
        lines.append("Based on prior session patterns, likely next skill:")
        for hit in hints[:2]:
            lines.append(
                f"  → {hit.skill_name} "
                f"({hit.probability:.0%} probability, {hit.session_count} sessions)"
            )
        lines.append("</augur_briefing>")

        return "\n".join(lines)

    async def record_behavioral_sequence(
        self,
        master_session_id: UUID,
        session_id: str,
        turn_index: int,
        interaction_type: str,
        skill_invoked: Optional[str] = None,
        followed_by_skill: Optional[str] = None,
        intent_class: Optional[int] = None,
        session_phase: Optional[int] = None,
    ) -> None:
        """Record an interaction to the behavioral sequence log."""
        try:
            await db.execute(
                """
                INSERT INTO behavioral_sequences
                    (master_session_id, session_id, turn_index, interaction_type,
                     skill_invoked, followed_by_skill, intent_class, session_phase)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                str(master_session_id), session_id, turn_index, interaction_type,
                skill_invoked, followed_by_skill, intent_class, session_phase,
            )
        except Exception as e:
            logger.warning(f"Failed to record behavioral sequence: {e}")

    async def mine_session_patterns(
        self,
        master_session_id: UUID,
        session_id: str,
    ) -> None:
        """
        Post-session behavioral mining.
        Extracts skill sequences and updates the N-gram index.
        """
        rows = await db.fetchall(
            """
            SELECT skill_invoked, created_at
            FROM behavioral_sequences
            WHERE master_session_id = $1 AND session_id = $2
              AND skill_invoked IS NOT NULL
            ORDER BY created_at ASC
            """,
            str(master_session_id), session_id,
        )

        if not rows:
            return

        skill_sequence = [r["skill_invoked"] for r in rows]
        self.sequence_index.record_sequence(skill_sequence, session_id)

        pruned = self.sequence_index.prune(
            max_age_sessions=self.cfg.get("stale_pattern_max_sessions", 100),
            min_probability=self.cfg.get("stale_pattern_min_probability", 0.40),
        )

        logger.info(
            f"Augur mined session {session_id}: "
            f"{len(skill_sequence)} skills, pruned {pruned} stale patterns"
        )
