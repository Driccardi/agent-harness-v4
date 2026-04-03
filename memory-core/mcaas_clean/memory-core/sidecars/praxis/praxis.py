"""
Praxis — Procedural Memory Optimizer
Named for the Greek concept of practice becoming embodied knowledge.

Observes skill invocation patterns, produces procedural notes (Mode 1),
proposes refactoring recommendations (Mode 2), and detects deterministic
reasoning paths that can be replaced with scripts (Mode 3).

CRITICAL SAFETY CONSTRAINT:
Mode 2 and Mode 3 changes ALWAYS require human-in-the-loop approval.
Autonomous modification of procedural memory (skill files) is prohibited.
Procedural notes (Mode 1) are ephemeral and additive — safe to auto-apply.
"""

from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import anthropic

from db import client as db

logger = logging.getLogger(__name__)


# ─── Data models ──────────────────────────────────────────────────────────────

@dataclass
class InvocationRecord:
    skill_name: str
    session_id: str
    turns_to_complete: Optional[int]
    human_corrections: int
    task_completed: Optional[bool]
    tool_sequence: list[str]
    outcome_notes: Optional[str]


@dataclass
class ProceduralNote:
    skill_name: str
    note_text: str
    confidence: float
    based_on_sessions: int


@dataclass
class RefactoringRecommendation:
    skill_name: str
    mode: int  # 2 or 3
    title: str
    description: str
    proposed_diff: Optional[str]
    evidence_sessions: int
    confidence: float


# ─── Prompts ──────────────────────────────────────────────────────────────────

PATTERN_ANALYSIS_PROMPT = """You are analyzing skill invocation patterns for an AI agent's procedural memory optimizer.

Skill name: {skill_name}
Number of invocations analyzed: {count}
Average turns to complete: {avg_turns:.1f}
Human correction rate: {correction_rate:.1%}
Task completion rate: {completion_rate:.1%}

Tool sequences used across invocations:
{tool_sequences}

Outcome notes:
{outcome_notes}

Your task: Identify patterns that would improve future invocations of this skill.
Produce a procedural note — a brief, actionable observation that would help
the agent perform better next time this skill is invoked.

Focus on:
- What approaches consistently work vs. fail
- Ordering of operations that matters
- Common mistakes to avoid
- Context-specific adaptations that improve outcomes

Keep the note under 100 words. Write in second person ("When doing X, first check Y...").
Write ONLY the note text, no preamble."""


DETERMINISM_DETECTION_PROMPT = """You are analyzing skill invocations to detect deterministic reasoning paths.

Skill name: {skill_name}
{count} invocations have followed nearly identical tool sequences:

{sequences}

These sequences are {similarity:.0%} similar on average.

Question: Could this reasoning path be replaced with a deterministic script?
A deterministic path is one where the LLM reasoning adds no value — the same
tool calls in the same order produce the correct result every time.

Respond with JSON:
{{
  "is_deterministic": true/false,
  "confidence": 0.0-1.0,
  "rationale": "<one sentence>",
  "proposed_script": "<bash script if deterministic, else null>"
}}"""


class Praxis:
    """
    Procedural memory optimizer.
    Reads skill invocation log, produces notes and recommendations.
    """

    def __init__(
        self,
        cfg: dict,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self.cfg = cfg
        self.min_invocations = cfg.get("min_invocations_for_analysis", 5)
        self.determinism_threshold = cfg.get("determinism_similarity_threshold", 0.92)
        self.rec_threshold = cfg.get("refactoring_recommendation_threshold", 0.80)
        self.note_display_threshold = cfg.get("note_display_threshold", 0.55)
        self.note_confidence_increment = cfg.get("note_confidence_increment", 0.05)
        self.note_confidence_decay = cfg.get("note_confidence_decay", 0.03)
        self.note_expiry_threshold = cfg.get("note_expiry_threshold", 0.30)
        self.model = os.environ.get("ATLAS_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.client = client or anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )

    async def get_skill_invocations(
        self,
        master_session_id: UUID,
        skill_name: str,
        limit: int = 20,
    ) -> list[dict]:
        rows = await db.fetchall(
            """
            SELECT skill_name, session_id, turns_to_complete,
                   human_corrections, task_completed, tool_sequence, outcome_notes
            FROM skill_invocations
            WHERE master_session_id = $1 AND skill_name = $2
            ORDER BY invoked_at DESC
            LIMIT $3
            """,
            str(master_session_id), skill_name, limit,
        )
        return [dict(r) for r in rows]

    def _sequence_similarity(self, seq_a: list, seq_b: list) -> float:
        """Simple sequence similarity: overlap / max_length."""
        if not seq_a or not seq_b:
            return 0.0
        overlap = sum(1 for a, b in zip(seq_a, seq_b) if a == b)
        return overlap / max(len(seq_a), len(seq_b))

    def _avg_sequence_similarity(self, sequences: list[list]) -> float:
        if len(sequences) < 2:
            return 0.0
        total = 0.0
        count = 0
        for i in range(len(sequences)):
            for j in range(i + 1, len(sequences)):
                total += self._sequence_similarity(sequences[i], sequences[j])
                count += 1
        return total / count if count > 0 else 0.0

    async def analyze_skill(
        self,
        master_session_id: UUID,
        skill_name: str,
    ) -> Optional[ProceduralNote]:
        """
        Analyze a skill's invocation history and produce a procedural note.
        """
        invocations = await self.get_skill_invocations(master_session_id, skill_name)

        if len(invocations) < self.min_invocations:
            logger.debug(
                f"Praxis: {skill_name} has only {len(invocations)} invocations, "
                f"need {self.min_invocations}"
            )
            return None

        # Compute metrics
        turns_list = [inv["turns_to_complete"] for inv in invocations
                      if inv.get("turns_to_complete") is not None]
        avg_turns = sum(turns_list) / len(turns_list) if turns_list else 0.0

        corrections_list = [inv["human_corrections"] or 0 for inv in invocations]
        correction_rate = sum(corrections_list) / max(1, len(corrections_list) * 3)

        completed_list = [inv["task_completed"] for inv in invocations
                          if inv.get("task_completed") is not None]
        completion_rate = sum(completed_list) / len(completed_list) if completed_list else 0.5

        tool_sequences = [inv.get("tool_sequence") or [] for inv in invocations]
        outcome_notes = "\n".join(
            f"- {inv['outcome_notes']}" for inv in invocations[:5]
            if inv.get("outcome_notes")
        )
        sequences_str = "\n".join(
            f"  {i+1}. {' → '.join(seq[:8])}"
            for i, seq in enumerate(tool_sequences[:5]) if seq
        )

        # Check for determinism
        avg_sim = self._avg_sequence_similarity(tool_sequences)
        if avg_sim >= self.determinism_threshold:
            await self._propose_determinism_replacement(
                master_session_id, skill_name, tool_sequences, avg_sim
            )

        # Generate procedural note
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": PATTERN_ANALYSIS_PROMPT.format(
                    skill_name=skill_name,
                    count=len(invocations),
                    avg_turns=avg_turns,
                    correction_rate=correction_rate,
                    completion_rate=completion_rate,
                    tool_sequences=sequences_str or "(no tool sequences recorded)",
                    outcome_notes=outcome_notes or "(no outcome notes)",
                )}],
                timeout=10.0,
            )
            note_text = response.content[0].text.strip()

            if not note_text:
                return None

            note = ProceduralNote(
                skill_name=skill_name,
                note_text=note_text,
                confidence=0.55,  # starts at display threshold
                based_on_sessions=len(invocations),
            )

            # Persist to database
            await db.execute(
                """
                INSERT INTO procedural_notes
                    (skill_name, master_session_id, note_text, confidence, invocation_count)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
                """,
                skill_name, str(master_session_id),
                note_text, note.confidence, len(invocations),
            )

            logger.info(
                f"Praxis: generated procedural note for '{skill_name}' "
                f"(based on {len(invocations)} invocations)"
            )
            return note

        except Exception as e:
            logger.error(f"Praxis note generation failed for '{skill_name}': {e}")
            return None

    async def _propose_determinism_replacement(
        self,
        master_session_id: UUID,
        skill_name: str,
        sequences: list[list],
        avg_sim: float,
    ) -> None:
        """Mode 3: Propose replacing deterministic reasoning with a script."""
        sequences_str = "\n".join(
            f"  {' → '.join(s[:10])}" for s in sequences[:5] if s
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": DETERMINISM_DETECTION_PROMPT.format(
                    skill_name=skill_name,
                    count=len(sequences),
                    sequences=sequences_str,
                    similarity=avg_sim,
                )}],
                timeout=10.0,
            )

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)

            if data.get("is_deterministic") and data.get("confidence", 0) >= 0.75:
                # Store as Mode 3 refactoring recommendation
                await db.execute(
                    """
                    INSERT INTO praxis_recommendations
                        (master_session_id, skill_name, mode, title, description,
                         proposed_diff, evidence_sessions, confidence)
                    VALUES ($1, $2, 3, $3, $4, $5, $6, $7)
                    """,
                    str(master_session_id),
                    skill_name,
                    f"Script extraction candidate: {skill_name}",
                    data.get("rationale", ""),
                    data.get("proposed_script"),
                    len(sequences),
                    float(data.get("confidence", 0.75)),
                )
                logger.info(
                    f"Praxis: Mode 3 recommendation created for '{skill_name}' "
                    f"(determinism={avg_sim:.2f})"
                )
        except Exception as e:
            logger.warning(f"Praxis determinism detection failed: {e}")

    async def get_notes_for_skill(
        self,
        master_session_id: UUID,
        skill_name: str,
    ) -> list[dict]:
        """
        Called by Anamnesis at skill invocation to get applicable notes.
        Returns notes above the display confidence threshold.
        """
        rows = await db.fetchall(
            """
            SELECT note_id, note_text, confidence
            FROM procedural_notes
            WHERE master_session_id = $1 AND skill_name = $2
              AND active = TRUE AND confidence >= $3
            ORDER BY confidence DESC
            LIMIT 3
            """,
            str(master_session_id), skill_name, self.note_display_threshold,
        )
        return [dict(r) for r in rows]

    async def update_note_outcome(
        self,
        note_id: UUID,
        improved: bool,
    ) -> None:
        """
        Update note confidence based on outcome.
        Notes that help accumulate confidence; notes that don't decay.
        """
        if improved:
            await db.execute(
                """
                UPDATE procedural_notes
                SET confidence = LEAST(1.0, confidence + $1),
                    invocation_count = invocation_count + 1
                WHERE note_id = $2
                """,
                self.note_confidence_increment, str(note_id),
            )
        else:
            await db.execute(
                """
                UPDATE procedural_notes
                SET confidence = GREATEST(0.0, confidence - $1),
                    invocation_count = invocation_count + 1,
                    active = CASE WHEN confidence - $1 < $2 THEN FALSE ELSE active END
                WHERE note_id = $3
                """,
                self.note_confidence_decay, self.note_expiry_threshold, str(note_id),
            )

    async def run_session_end(self, master_session_id: UUID) -> None:
        """
        Analyze all skills invoked this session.
        Called at SessionEnd hook.
        """
        # Get distinct skills used this session
        rows = await db.fetchall(
            """
            SELECT DISTINCT skill_name FROM skill_invocations
            WHERE master_session_id = $1
            ORDER BY skill_name
            """,
            str(master_session_id),
        )

        for row in rows:
            skill_name = row["skill_name"]
            await self.analyze_skill(master_session_id, skill_name)
