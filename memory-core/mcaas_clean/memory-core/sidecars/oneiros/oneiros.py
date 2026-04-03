"""
Oneiros — Lossy Belief Consolidator
Named for the Greek personification of dreams.

Oneiros reads the full episodic corpus for a topic and writes
generalized standing beliefs — replacing specific events with durable knowledge.

This is NOT summarization. Summarization preserves event structure.
Oneiros GENERALIZES — extracting patterns and beliefs from the episodic record,
discarding the temporal scaffolding that produced them.

"The agent remembers what it learned, not everything that happened."
"""

from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import anthropic

from db import client as db

logger = logging.getLogger(__name__)


CONSOLIDATION_SYSTEM = """You are performing memory consolidation for an AI agent's long-term memory.

You will be given all episodic memory fragments associated with a specific topic,
accumulated across many sessions. Your task is to read them in full and produce
consolidated belief statements that capture what was durably learned — not what
happened, but what is now known.

CONSOLIDATION PRINCIPLES:
- Preserve MEANING and DIRECTION. Discard SPECIFICS and TEMPORAL ANCHORS.
- Write in present tense as standing beliefs, not past tense as events.
- Capture constraints and negative knowledge explicitly:
  "Approach X does not work for this system because Y."
- Flag uncertainty honestly ("likely", "in most cases", "the agent has observed but not confirmed").
- Identify any open questions that require future investigation.
- This consolidation will REPLACE the episodic chunks — be complete.

The output is what the agent should know, not what the agent experienced.

OUTPUT FORMAT:
Return a JSON array of belief statements, each with:
{
  "belief": "The standing belief as a clear declarative sentence",
  "confidence": 0.0-1.0,
  "type": "factual|constraint|preference|pattern|open_question",
  "basis": "Brief description of the episodic evidence behind this belief",
  "freshness_sensitivity": "stable|moderate|volatile"
}

Respond ONLY with the JSON array. No preamble, no explanation, no markdown fences."""


@dataclass
class RetentionPolicy:
    max_raw_chunks: int
    consolidate_at: int


DEFAULT_RETENTION_POLICIES = {
    "active_project":   RetentionPolicy(max_raw_chunks=500, consolidate_at=200),
    "recurring_domain": RetentionPolicy(max_raw_chunks=200, consolidate_at=100),
    "one_off_session":  RetentionPolicy(max_raw_chunks=50,  consolidate_at=30),
    "completed_task":   RetentionPolicy(max_raw_chunks=20,  consolidate_at=10),
}


@dataclass
class ConsolidationResult:
    topic_node_id: UUID
    topic_label: str
    beliefs_written: int = 0
    chunks_archived: int = 0
    compression_ratio: float = 0.0
    skipped: bool = False
    skip_reason: str = ""


class Oneiros:
    """
    Lossy belief consolidator.
    Reads episodic corpus, writes generalized beliefs, archives raw chunks.
    """

    def __init__(
        self,
        cfg: dict,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self.cfg = cfg
        self.model = cfg.get("model",
                             os.environ.get("ATLAS_CLAUDE_MODEL_LARGE", "claude-sonnet-4-6"))
        self.min_chunks = cfg.get("min_chunks_for_consolidation", 10)
        self.client = client or anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )

        # Load retention policies from config or use defaults
        raw_policies = cfg.get("topic_retention_policies", {})
        self.retention_policies = {
            k: RetentionPolicy(**v) if isinstance(v, dict) else v
            for k, v in raw_policies.items()
        } if raw_policies else DEFAULT_RETENTION_POLICIES

    def _get_policy(self, topic_type: Optional[str]) -> RetentionPolicy:
        return self.retention_policies.get(
            topic_type or "one_off_session",
            DEFAULT_RETENTION_POLICIES["one_off_session"]
        )

    async def should_consolidate(self, node_id: UUID) -> tuple[bool, Optional[str]]:
        """
        Check if a topic node is ready for consolidation.
        Returns (should_consolidate, reason_to_skip).
        """
        row = await db.fetchone(
            """
            SELECT tn.chunk_count, tn.topic_type,
                   COUNT(c.chunk_id) as actual_count
            FROM topic_nodes tn
            LEFT JOIN chunk_topics ct ON ct.node_id = tn.node_id
            LEFT JOIN chunks c ON c.chunk_id = ct.chunk_id
                AND NOT c.archived AND NOT c.provisional
            WHERE tn.node_id = $1
            GROUP BY tn.node_id, tn.chunk_count, tn.topic_type
            """,
            str(node_id),
        )

        if not row:
            return False, "Topic node not found"

        actual_count = int(row["actual_count"] or 0)
        topic_type = row.get("topic_type")
        policy = self._get_policy(topic_type)

        if actual_count < self.min_chunks:
            return False, f"Only {actual_count} chunks, minimum is {self.min_chunks}"

        if actual_count < policy.consolidate_at:
            return False, f"Chunk count {actual_count} below consolidation threshold {policy.consolidate_at}"

        return True, None

    async def consolidate_topic(self, node_id: UUID) -> ConsolidationResult:
        """
        Run consolidation for a single topic node.
        Reads all episodic chunks, writes beliefs, archives originals.
        """
        # Fetch topic metadata
        topic_row = await db.fetchone(
            "SELECT label, topic_type FROM topic_nodes WHERE node_id = $1",
            str(node_id),
        )
        if not topic_row:
            return ConsolidationResult(
                topic_node_id=node_id,
                topic_label="unknown",
                skipped=True,
                skip_reason="Topic not found",
            )

        topic_label = topic_row["label"]

        should, skip_reason = await self.should_consolidate(node_id)
        if not should:
            return ConsolidationResult(
                topic_node_id=node_id,
                topic_label=topic_label,
                skipped=True,
                skip_reason=skip_reason or "Policy threshold not reached",
            )

        # Fetch all chunks for this topic (chronological)
        chunks = await db.fetchall(
            """
            SELECT c.chunk_id, c.content, c.chunk_type, c.confidence,
                   c.created_at, c.somatic_register, c.somatic_valence
            FROM chunks c
            JOIN chunk_topics ct ON c.chunk_id = ct.chunk_id
            WHERE ct.node_id = $1
              AND NOT c.archived AND NOT c.provisional
            ORDER BY c.created_at ASC
            """,
            str(node_id),
        )

        if len(chunks) < self.min_chunks:
            return ConsolidationResult(
                topic_node_id=node_id,
                topic_label=topic_label,
                skipped=True,
                skip_reason=f"Only {len(chunks)} valid chunks",
            )

        # Build corpus for LLM
        corpus_lines = []
        for c in chunks:
            chunk_type = c["chunk_type"]
            content = c["content"][:500]
            somatic = c.get("somatic_register", "")
            somatic_str = f" [{somatic}]" if somatic else ""
            date_str = c["created_at"].strftime("%Y-%m-%d") if c.get("created_at") else "?"
            corpus_lines.append(f"[{date_str}][{chunk_type}]{somatic_str}: {content}")

        corpus = "\n".join(corpus_lines)

        logger.info(
            f"Oneiros consolidating topic='{topic_label}' "
            f"chunks={len(chunks)}"
        )

        # Run consolidation
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=CONSOLIDATION_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"Topic: {topic_label}\n\n{corpus}"
                }],
            )

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()

            beliefs = json.loads(raw)

        except json.JSONDecodeError as e:
            logger.error(f"Oneiros JSON parse error for topic '{topic_label}': {e}")
            return ConsolidationResult(
                topic_node_id=node_id,
                topic_label=topic_label,
                skipped=True,
                skip_reason=f"LLM output parse error: {e}",
            )
        except Exception as e:
            logger.error(f"Oneiros consolidation failed for '{topic_label}': {e}")
            return ConsolidationResult(
                topic_node_id=node_id,
                topic_label=topic_label,
                skipped=True,
                skip_reason=str(e),
            )

        # Write consolidated belief chunks
        new_chunk_ids = []
        for belief in beliefs:
            if not isinstance(belief, dict) or "belief" not in belief:
                continue

            # Insert as CONSOLIDATED_BELIEF type chunk
            try:
                chunk_id = await db.insert_chunk(
                    master_session_id=UUID(str(
                        (await db.fetchone(
                            "SELECT master_session_id FROM topic_nodes WHERE node_id=$1",
                            str(node_id)
                        ))["master_session_id"]
                    )),
                    session_id="__oneiros__",
                    turn_index=0,
                    source_framework="oneiros",
                    chunk_type="CONSOLIDATED_BELIEF",
                    content=belief["belief"],
                    raw_event={
                        "type": belief.get("type", "factual"),
                        "basis": belief.get("basis", ""),
                        "freshness_sensitivity": belief.get("freshness_sensitivity", "stable"),
                        "replaces_chunk_count": len(chunks),
                    },
                    confidence=float(belief.get("confidence", 0.75)),
                    provisional=False,
                    embedding=None,  # Will be embedded by Engram in background
                )
                new_chunk_ids.append(chunk_id)

                # Associate with topic node
                await db.execute(
                    "INSERT INTO chunk_topics (chunk_id, node_id, confidence) VALUES ($1,$2,$3)",
                    str(chunk_id), str(node_id), float(belief.get("confidence", 0.75)),
                )
            except Exception as e:
                logger.warning(f"Failed to write belief chunk: {e}")

        # Archive original episodic chunks
        chunk_ids = [str(c["chunk_id"]) for c in chunks]
        if chunk_ids:
            placeholders = ",".join(f"${i+1}" for i in range(len(chunk_ids)))
            await db.execute(
                f"UPDATE chunks SET archived=TRUE, archived_at=now() WHERE chunk_id IN ({placeholders})",
                *chunk_ids,
            )

        compression_ratio = len(chunks) / max(1, len(new_chunk_ids))
        logger.info(
            f"Oneiros completed topic='{topic_label}': "
            f"{len(chunks)} chunks → {len(new_chunk_ids)} beliefs "
            f"(ratio={compression_ratio:.1f}x)"
        )

        return ConsolidationResult(
            topic_node_id=node_id,
            topic_label=topic_label,
            beliefs_written=len(new_chunk_ids),
            chunks_archived=len(chunks),
            compression_ratio=compression_ratio,
        )

    async def run_session_end(self, master_session_id: UUID) -> list[ConsolidationResult]:
        """
        Run Oneiros for all topics in this master session that qualify.
        Called at SessionEnd hook.
        """
        # Find all topics that might qualify
        topic_nodes = await db.fetchall(
            """
            SELECT tn.node_id, tn.label, tn.topic_type,
                   COUNT(c.chunk_id) as chunk_count
            FROM topic_nodes tn
            LEFT JOIN chunk_topics ct ON ct.node_id = tn.node_id
            LEFT JOIN chunks c ON c.chunk_id = ct.chunk_id
                AND NOT c.archived AND NOT c.provisional
            WHERE tn.master_session_id = $1
            GROUP BY tn.node_id
            HAVING COUNT(c.chunk_id) >= $2
            """,
            str(master_session_id),
            self.min_chunks,
        )

        results = []
        for row in topic_nodes:
            node_id = UUID(str(row["node_id"]))
            result = await self.consolidate_topic(node_id)
            results.append(result)

        consolidated = [r for r in results if not r.skipped]
        logger.info(
            f"Oneiros session-end run: {len(consolidated)}/{len(results)} topics consolidated"
        )
        return results
