"""
Atlas Database Client
Async PostgreSQL connection pool with typed query helpers.
Uses asyncpg for performance; pgvector types handled via custom codec.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, List, Optional
from uuid import UUID

import asyncpg
from asyncpg import Pool

logger = logging.getLogger(__name__)

# ─── Connection pool singleton ────────────────────────────────────────────────

_pool: Optional[Pool] = None


async def get_pool() -> Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("ATLAS_DB_HOST", "localhost"),
            port=int(os.getenv("ATLAS_DB_PORT", "5432")),
            database=os.getenv("ATLAS_DB_NAME", "atlas"),
            user=os.getenv("ATLAS_DB_USER", "atlas"),
            password=os.getenv("ATLAS_DB_PASSWORD", "dev"),
            min_size=2,
            max_size=int(os.getenv("ATLAS_DB_POOL_SIZE", "10")),
            command_timeout=30,
            init=_init_connection,
        )
    return _pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register pgvector codec and JSON codec on each new connection."""
    await conn.execute("SET search_path TO public")
    # Register vector type — asyncpg doesn't know about pgvector natively
    await conn.set_type_codec(
        "vector",
        encoder=_encode_vector,
        decoder=_decode_vector,
        schema="public",
        format="text",
    )


def _encode_vector(value: list[float]) -> str:
    return "[" + ",".join(str(x) for x in value) + "]"


def _decode_vector(value: str) -> list[float]:
    return [float(x) for x in value.strip("[]").split(",")]


@asynccontextmanager
async def connection():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def transaction():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


# ─── Query helpers ────────────────────────────────────────────────────────────

async def fetchone(query: str, *args) -> Optional[asyncpg.Record]:
    async with connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchall(query: str, *args) -> List[asyncpg.Record]:
    async with connection() as conn:
        return await conn.fetch(query, *args)


async def execute(query: str, *args) -> str:
    async with connection() as conn:
        return await conn.execute(query, *args)


async def executemany(query: str, args_list: list) -> None:
    async with connection() as conn:
        await conn.executemany(query, args_list)


# ─── Named queries ────────────────────────────────────────────────────────────

ANAMNESIS_SEARCH = """
SELECT
    c.chunk_id,
    c.content,
    c.chunk_type,
    c.confidence,
    c.created_at,
    c.session_id,
    c.somatic_register,
    c.somatic_valence,
    1 - (c.embedding <=> $1::vector) AS similarity,
    array_agg(DISTINCT tn.label) FILTER (WHERE tn.label IS NOT NULL) AS topic_labels
FROM chunks c
LEFT JOIN chunk_topics ct ON c.chunk_id = ct.chunk_id
LEFT JOIN topic_nodes tn  ON ct.node_id = tn.node_id
WHERE
    c.master_session_id = $2
    AND c.session_id != $3
    AND c.confidence >= $4
    AND c.provisional = FALSE
    AND c.archived = FALSE
    AND c.created_at > now() - ($5 * INTERVAL '1 day')
    AND 1 - (c.embedding <=> $1::vector) >= $6
GROUP BY c.chunk_id
ORDER BY similarity DESC
LIMIT $7
"""

INSERT_CHUNK = """
INSERT INTO chunks (
    master_session_id, session_id, turn_index, source_framework,
    chunk_type, content, raw_event,
    confidence, provisional,
    embedding,
    somatic_register, somatic_valence, somatic_energy,
    input_modality, context_pressure
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
RETURNING chunk_id
"""

GET_LATEST_SSS = """
SELECT * FROM sss_snapshots
WHERE master_session_id = $1
ORDER BY created_at DESC
LIMIT 1
"""

INSERT_INJECTION_LOG = """
INSERT INTO injection_log (
    master_session_id, session_id, turn_index, hook_type,
    chunk_id, similarity, injected, rejection_reason, confusion_tier, gate_checks
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
"""

GET_OPEN_LOOPS = """
SELECT loop_id, description, opened_at, last_seen
FROM open_loops
WHERE master_session_id = $1 AND resolved = FALSE
ORDER BY last_seen DESC
LIMIT 10
"""


async def anamnesis_search(
    embedding: list[float],
    master_session_id: UUID,
    current_session_id: str,
    confidence_floor: float,
    recency_days: int,
    similarity_floor: float,
    limit: int = 10,
) -> List[asyncpg.Record]:
    return await fetchall(
        ANAMNESIS_SEARCH,
        embedding,
        str(master_session_id),
        current_session_id,
        confidence_floor,
        recency_days,
        similarity_floor,
        limit,
    )


async def insert_chunk(
    master_session_id: UUID,
    session_id: str,
    turn_index: int,
    source_framework: str,
    chunk_type: str,
    content: str,
    raw_event: dict,
    confidence: float,
    provisional: bool,
    embedding: list[float],
    somatic_register: Optional[str] = None,
    somatic_valence: Optional[int] = None,
    somatic_energy: Optional[int] = None,
    input_modality: Optional[str] = None,
    context_pressure: Optional[float] = None,
) -> UUID:
    row = await fetchone(
        INSERT_CHUNK,
        str(master_session_id),
        session_id,
        turn_index,
        source_framework,
        chunk_type,
        content,
        json.dumps(raw_event),
        confidence,
        provisional,
        embedding,
        somatic_register,
        somatic_valence,
        somatic_energy,
        input_modality,
        context_pressure,
    )
    return UUID(str(row["chunk_id"]))


async def close():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
