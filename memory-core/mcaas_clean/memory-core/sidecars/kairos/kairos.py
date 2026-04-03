"""
Kairos — Topic Consolidator
Cortical consolidation analog: builds the topic knowledge graph,
runs the provisional chunk validation lifecycle, and maintains
progressive summary stacks.

Named for the Greek god of the opportune moment.
Fires every K=20 turns and at SessionEnd.
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


# ─── Topic naming prompt ──────────────────────────────────────────────────────

TOPIC_NAMING_PROMPT = """You are a knowledge organizer for an AI agent's memory system.

Given a cluster of text fragments from an agent's working session, produce:
1. A short topic label (3-6 words, noun phrase, specific not generic)
2. A list of 5-8 keywords that define this cluster
3. The topic type:
   - active_project: ongoing, multi-session work on a specific deliverable
   - recurring_domain: a subject area the agent revisits regularly
   - one_off_session: a task addressed once, likely complete
   - completed_task: a task that has reached a clear resolution

Text fragments:
{fragments}

Respond ONLY with JSON:
{{
  "label": "<short topic label>",
  "keywords": ["word1", "word2", ...],
  "topic_type": "<type>"
}}"""


SUMMARY_PROMPTS = {
    1: """Summarize the following memory chunks as a coherent prose paragraph (150-300 words).
Preserve key decisions, outcomes, and constraints. Use past tense.

Chunks:
{chunks}

Summary:""",

    2: """Summarize the following memory chunks in 2-3 sentences. Focus only on the most
durable facts and decisions.

Chunks:
{chunks}

Brief summary:""",

    3: """Extract 5-8 keywords from these memory chunks. Single words or short phrases only.

Chunks:
{chunks}

Keywords (comma-separated):""",
}


# ─── Provisional lifecycle constants ─────────────────────────────────────────

VALIDATION_SIGNALS = [
    "acts on the idea",
    "references in output",
    "tool call aligns",
    "explicitly builds on",
]

ABANDONMENT_SIGNALS = [
    "contradicts",
    "different approach",
    "not the right",
    "actually no",
    "that's wrong",
    "pivot",
]


@dataclass
class ClusterCandidate:
    chunk_ids: list[UUID]
    embeddings: list[list[float]]
    contents: list[str]
    centroid: list[float] = field(default_factory=list)


class Kairos:
    """
    Topic consolidator.
    Clusters recent chunks into topics, builds the knowledge graph,
    runs provisional chunk lifecycle, maintains progressive summaries.
    """

    def __init__(
        self,
        cfg: dict,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self.cfg = cfg
        self.min_cluster_size = cfg.get("min_cluster_size", 3)
        self.provisional_validation_window = cfg.get("provisional_validation_window_turns", 5)
        self.model = os.environ.get("ATLAS_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.client = client or anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )

    def _centroid(self, embeddings: list[list[float]]) -> list[float]:
        """Compute mean embedding vector (centroid of a cluster)."""
        if not embeddings:
            return []
        dim = len(embeddings[0])
        centroid = [0.0] * dim
        for emb in embeddings:
            for i, v in enumerate(emb):
                centroid[i] += v
        n = len(embeddings)
        centroid = [v / n for v in centroid]
        # L2 normalize
        norm = sum(v * v for v in centroid) ** 0.5
        return [v / (norm + 1e-9) for v in centroid]

    def _cosine(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb + 1e-9)

    async def _name_topic(self, contents: list[str]) -> dict:
        """Use LLM to name a topic cluster."""
        fragments = "\n---\n".join(c[:300] for c in contents[:8])
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": TOPIC_NAMING_PROMPT.format(
                    fragments=fragments
                )}],
                timeout=8.0,
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Topic naming failed: {e}")
            return {
                "label": "Unnamed Topic",
                "keywords": [],
                "topic_type": "one_off_session",
            }

    async def _build_summary(self, node_id: UUID, depth: int, chunks: list[dict]) -> None:
        """Build a progressive summary at a specific depth."""
        contents = "\n\n".join(
            f"[{c['chunk_type']}]: {c['content'][:400]}" for c in chunks
        )
        prompt = SUMMARY_PROMPTS.get(depth, "")
        if not prompt:
            return

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt.format(chunks=contents)}],
                timeout=15.0,
            )
            summary_text = response.content[0].text.strip()

            await db.execute(
                """
                INSERT INTO topic_summaries (node_id, depth, summary_text, updated_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (node_id, depth) DO UPDATE
                    SET summary_text=$3, updated_at=now()
                """,
                str(node_id), depth, summary_text,
            )
        except Exception as e:
            logger.warning(f"Summary depth {depth} failed for {node_id}: {e}")

    async def run_consolidation(
        self,
        master_session_id: UUID,
        session_id: str,
        since_turn: int = 0,
    ) -> int:
        """
        Main consolidation run. Clusters recent chunks into topic nodes.
        Returns number of topics created or updated.
        """
        # Fetch recent unprocessed validated chunks with embeddings
        chunks = await db.fetchall(
            """
            SELECT c.chunk_id, c.content, c.chunk_type, c.confidence, c.embedding
            FROM chunks c
            WHERE c.master_session_id = $1
              AND c.session_id = $2
              AND c.turn_index >= $3
              AND c.provisional = FALSE
              AND c.archived = FALSE
              AND c.embedding IS NOT NULL
            ORDER BY c.turn_index ASC
            """,
            str(master_session_id), session_id, since_turn,
        )

        if len(chunks) < self.min_cluster_size:
            logger.debug(f"Kairos: only {len(chunks)} chunks, skipping consolidation")
            return 0

        # Simple greedy clustering by embedding similarity
        # Production: replace with HDBSCAN (sklearn or hdbscan package)
        clustered = self._greedy_cluster(chunks)

        topics_updated = 0
        for cluster in clustered:
            if len(cluster) < self.min_cluster_size:
                continue

            contents = [c["content"] for c in cluster]
            embeddings = [list(c["embedding"]) for c in cluster if c.get("embedding")]

            if not embeddings:
                continue

            centroid = self._centroid(embeddings)
            naming = await self._name_topic(contents)
            label = naming.get("label", "Unnamed Topic")
            keywords = naming.get("keywords", [])
            topic_type = naming.get("topic_type", "one_off_session")

            # Find or create topic node
            existing = await db.fetchone(
                """
                SELECT node_id FROM topic_nodes
                WHERE master_session_id = $1
                  AND 1 - (centroid <=> $2::vector) > 0.85
                LIMIT 1
                """,
                str(master_session_id), centroid,
            )

            if existing:
                node_id = UUID(str(existing["node_id"]))
                await db.execute(
                    """
                    UPDATE topic_nodes
                    SET last_active=now(), session_count=session_count+1,
                        chunk_count=chunk_count+$1
                    WHERE node_id=$2
                    """,
                    len(cluster), str(node_id),
                )
            else:
                row = await db.fetchone(
                    """
                    INSERT INTO topic_nodes
                        (master_session_id, label, keywords, centroid, topic_type, chunk_count)
                    VALUES ($1, $2, $3, $4::vector, $5, $6)
                    RETURNING node_id
                    """,
                    str(master_session_id), label, keywords, centroid,
                    topic_type, len(cluster),
                )
                node_id = UUID(str(row["node_id"]))

            # Link chunks to topic
            for chunk in cluster:
                try:
                    await db.execute(
                        """
                        INSERT INTO chunk_topics (chunk_id, node_id, confidence)
                        VALUES ($1, $2, 0.75)
                        ON CONFLICT (chunk_id, node_id) DO NOTHING
                        """,
                        str(chunk["chunk_id"]), str(node_id),
                    )
                except Exception:
                    pass

            # Build progressive summaries (depth 1, 2, 3)
            chunk_dicts = [dict(c) for c in cluster]
            for depth in [1, 2, 3]:
                await self._build_summary(node_id, depth, chunk_dicts)

            topics_updated += 1
            logger.debug(f"Kairos: updated topic '{label}' ({len(cluster)} chunks)")

        return topics_updated

    def _greedy_cluster(self, chunks: list) -> list[list]:
        """
        Simple greedy similarity clustering.
        Replace with HDBSCAN in production for better cluster quality.
        """
        SIMILARITY_THRESHOLD = 0.72
        clusters: list[list] = []
        assigned = set()

        for i, chunk in enumerate(chunks):
            if i in assigned:
                continue
            if not chunk.get("embedding"):
                continue

            cluster = [chunk]
            assigned.add(i)

            for j, other in enumerate(chunks):
                if j in assigned or not other.get("embedding"):
                    continue
                sim = self._cosine(list(chunk["embedding"]), list(other["embedding"]))
                if sim >= SIMILARITY_THRESHOLD:
                    cluster.append(other)
                    assigned.add(j)

            clusters.append(cluster)

        return clusters

    async def validate_provisional_chunks(
        self,
        master_session_id: UUID,
        session_id: str,
        current_turn: int,
    ) -> tuple[int, int]:
        """
        Check provisional chunks for validation or abandonment.
        Returns (validated_count, abandoned_count).
        """
        K = self.provisional_validation_window

        # Chunks that are provisional and old enough to evaluate
        old_provisionals = await db.fetchall(
            """
            SELECT chunk_id, content, turn_index
            FROM chunks
            WHERE master_session_id = $1 AND session_id = $2
              AND provisional = TRUE AND validated = FALSE
              AND turn_index < $3
            ORDER BY turn_index ASC
            """,
            str(master_session_id), session_id, current_turn - K,
        )

        validated = 0
        abandoned = 0

        for prov in old_provisionals:
            chunk_id = str(prov["chunk_id"])
            prov_content = prov["content"].lower()

            # Check if subsequent model output validates this chunk
            subsequent = await db.fetchall(
                """
                SELECT content, chunk_type FROM chunks
                WHERE master_session_id = $1 AND session_id = $2
                  AND turn_index > $3 AND turn_index <= $4
                  AND chunk_type IN ('MODEL', 'TOOL_IN')
                ORDER BY turn_index ASC
                LIMIT 10
                """,
                str(master_session_id), session_id,
                int(prov["turn_index"]), current_turn,
            )

            strong_validation = any(
                signal in s["content"].lower()
                for s in subsequent
                for signal in ["as i noted", "as mentioned", "following up on",
                               "building on", "per my earlier"]
            )

            abandonment = any(
                signal in s["content"].lower()
                for s in subsequent
                for signal in ABANDONMENT_SIGNALS
            )

            if strong_validation:
                await db.execute(
                    "UPDATE chunks SET provisional=FALSE, validated=TRUE, confidence=0.85 WHERE chunk_id=$1",
                    chunk_id,
                )
                validated += 1
            elif abandonment or not subsequent:
                # Abandoned: preserve as negative knowledge at low confidence
                await db.execute(
                    "UPDATE chunks SET confidence=0.10 WHERE chunk_id=$1",
                    chunk_id,
                )
                abandoned += 1

        if validated + abandoned > 0:
            logger.info(
                f"Kairos provisional lifecycle: "
                f"validated={validated} abandoned={abandoned}"
            )

        return validated, abandoned
