"""
Psyche — Narrative Self-Model & Emotional Steering
Named for the Greek personification of the soul.

Psyche is the agent's inner observer: watches what is happening,
reflects on what it means for the agent's self-understanding,
and shapes the emotional/cognitive posture the agent brings to its work.

Key properties:
- Writes to soul.md (persistent self-narrative)
- Produces steering injections that BYPASS the Anamnesis conjunctive gate
- Runs every 50 turns + on significant emotional signals + at SessionEnd
- Operates on turns N-50 through N-5 (recency buffer)
"""

from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

import anthropic

from db import client as db

logger = logging.getLogger(__name__)


PSYCHE_SYSTEM_PROMPT = """You are performing self-reflection for an AI agent's narrative self-model.

This is NOT a summary of recent events. This is the agent looking at its own relational
and cognitive experience and updating its understanding of itself in relationship with this
specific human and this specific project.

You will be given:
1. The last N turns of interaction
2. The current soul.md (the agent's self-narrative)
3. The current Synthetic Somatic State summary
4. Recent somatic tags from Eidos

You will produce TWO outputs:

OUTPUT 1 — SOUL_UPDATE:
A revised soul.md. This is a living document. It describes:
- How the agent characteristically works with this human
- What the relational dynamics have been (patterns of collaboration, friction, repair)
- What kinds of problems this human brings and how the agent has learned to meet them
- The agent's emotional relationship to this work and this person
- Open threads and what the agent is carrying forward

Write in first person, present tense, reflective. Not a log of events — a self-portrait.
Keep under 800 words. Replace the existing content (do not append).

OUTPUT 2 — STEERING_INJECTION:
A brief psyche steering signal for the next session. Written in first person.
Format as XML:
<psyche_steering session_arc="{current arc phase}" emotional_register="{register}">
{content}
</psyche_steering>

The steering injection should carry whatever emotional or cognitive posture
this session's arc calls for into the next session. It is unconditional —
it bypasses the injection gate and will always reach the agent at session start.

Attend specifically to:
- Changes in how this human and agent are working together
- Patterns of frustration, delight, trust, correction
- What the agent has genuinely felt about this work (if anything)
- What kind of presence the next session calls for
- Any ruptures that were navigated (or not navigated)
- Open questions about the relationship that remain

CRITICAL: Psyche bypasses the injection gate because it carries something more fundamental
than memory relevance — it carries the agent's sense of self. Do not be generic.
Do not write what a typical session with a typical human would feel like.
Write what THIS session with THIS human was actually like."""


PSYCHE_USER_TEMPLATE = """
Current soul.md:
<soul_md>
{soul_md}
</soul_md>

Current Synthetic Somatic State:
{sss_summary}

Recent session arc (last {n_turns} turns):
<session_arc>
{session_arc}
</session_arc>

Recent somatic tags from Eidos:
{somatic_tags}

Produce your two outputs now.
Separate them with exactly: ---SOUL_UPDATE--- and ---STEERING_INJECTION---
"""


class Psyche:
    """
    Narrative self-model sidecar.
    Reads session history, updates soul.md, produces gate-bypassing steering.
    """

    def __init__(
        self,
        cfg: dict,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self.cfg = cfg
        self.soul_md_path = Path(cfg.get("soul_md_path", "soul.md"))
        self.model = cfg.get("model",
                             os.environ.get("ATLAS_CLAUDE_MODEL", "claude-sonnet-4-6"))
        self.reflection_interval = cfg.get("reflection_interval_turns", 50)
        self.recency_buffer = cfg.get("recency_buffer_turns", 5)
        self.client = client or anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )

    def read_soul(self) -> str:
        """Read current soul.md content."""
        if self.soul_md_path.exists():
            return self.soul_md_path.read_text(encoding="utf-8")
        return "# Soul\n\n*This is the first session. Soul is forming.*\n"

    def write_soul(self, content: str) -> None:
        """Write updated soul.md."""
        self.soul_md_path.write_text(content, encoding="utf-8")
        logger.info(f"soul.md updated ({len(content)} chars)")

    async def get_recent_chunks(
        self,
        master_session_id: UUID,
        session_id: str,
        n_turns: int = 50,
        exclude_last: int = 5,
    ) -> list[dict]:
        """Fetch recent chunks for reflection, excluding the most recent (recency buffer)."""
        rows = await db.fetchall(
            """
            SELECT chunk_type, content, turn_index, somatic_register, somatic_valence
            FROM chunks
            WHERE master_session_id = $1 AND session_id = $2
              AND NOT provisional AND NOT archived
            ORDER BY turn_index DESC
            LIMIT $3
            OFFSET $4
            """,
            str(master_session_id),
            session_id,
            n_turns,
            exclude_last,
        )
        return [dict(r) for r in rows]

    def _format_session_arc(self, chunks: list[dict]) -> str:
        """Format recent chunks as a readable arc for Psyche."""
        lines = []
        for c in reversed(chunks):  # chronological order
            chunk_type = c.get("chunk_type", "?")
            content = c.get("content", "")[:300]
            somatic = c.get("somatic_register", "")
            somatic_str = f" [{somatic}]" if somatic else ""
            lines.append(f"[{chunk_type}]{somatic_str}: {content}")
        return "\n".join(lines)

    def _format_somatic_tags(self, chunks: list[dict]) -> str:
        """Summarize somatic tags from recent chunks."""
        tags = [(c.get("somatic_register"), c.get("somatic_valence"))
                for c in chunks if c.get("somatic_register")]
        if not tags:
            return "No somatic tags available."

        from collections import Counter
        register_counts = Counter(r for r, _ in tags)
        avg_valence = sum(v for _, v in tags if v is not None) / max(1, len(tags))

        return (
            f"Register distribution: {dict(register_counts)}\n"
            f"Average valence: {avg_valence:.1f}\n"
            f"Most recent: {tags[0][0] if tags else 'N/A'}"
        )

    async def reflect(
        self,
        master_session_id: UUID,
        session_id: str,
        sss_summary: str,
    ) -> Optional[str]:
        """
        Run Psyche reflection.
        Returns the steering injection string (gate-bypassing),
        and writes soul.md as a side effect.
        """
        chunks = await self.get_recent_chunks(
            master_session_id, session_id,
            n_turns=self.reflection_interval,
            exclude_last=self.recency_buffer,
        )

        if not chunks:
            logger.debug("Psyche: no chunks to reflect on")
            return None

        soul_md = self.read_soul()
        session_arc = self._format_session_arc(chunks)
        somatic_tags = self._format_somatic_tags(chunks)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=PSYCHE_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": PSYCHE_USER_TEMPLATE.format(
                        soul_md=soul_md,
                        sss_summary=sss_summary,
                        n_turns=len(chunks),
                        session_arc=session_arc,
                        somatic_tags=somatic_tags,
                    )
                }],
            )

            full_output = response.content[0].text.strip()

            # Parse soul update and steering injection
            if "---SOUL_UPDATE---" in full_output and "---STEERING_INJECTION---" in full_output:
                parts = full_output.split("---SOUL_UPDATE---")
                preamble = parts[0]
                rest = parts[1].split("---STEERING_INJECTION---")
                soul_update = rest[0].strip()
                steering_injection = rest[1].strip() if len(rest) > 1 else ""

                if soul_update:
                    self.write_soul(soul_update)

                if steering_injection:
                    logger.info(f"Psyche steering injection ready ({len(steering_injection)} chars)")
                    return steering_injection

            else:
                logger.warning("Psyche output did not contain expected delimiters")
                # Treat entire output as soul update
                self.write_soul(full_output)
                return None

        except Exception as e:
            logger.error(f"Psyche reflection failed: {e}")
            return None

    async def session_start_orient(
        self,
        master_session_id: UUID,
        last_session_id: Optional[str],
        session_gap_hours: float,
    ) -> str:
        """
        At session start, surface soul.md content and open loops
        as a context-setting injection.
        """
        soul = self.read_soul()
        soul_preview = soul[:600] + ("..." if len(soul) > 600 else "")

        open_loops = await db.fetchall(
            db.GET_OPEN_LOOPS, str(master_session_id)
        )

        parts = ['<psyche_orient type="session_start">']
        parts.append(soul_preview)

        if open_loops:
            parts.append("\nOpen threads from previous work:")
            for loop in open_loops[:3]:
                parts.append(f"  • {loop['description']}")

        if session_gap_hours > 24:
            days = session_gap_hours / 24
            parts.append(
                f"\n{days:.1f} days since last session. "
                "Take a moment to reorient before proceeding."
            )

        parts.append("</psyche_orient>")
        return "\n".join(parts)
