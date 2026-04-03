"""
workers/engram_worker.py
Long-running Redis queue consumer that processes ingestion events.
Runs as a Supervisor-managed process inside the container.

Reads from mc:ingest_queue, embeds content via Ollama,
writes to PostgreSQL chunks table, notifies Eidos queue.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import signal
import sys

logger = logging.getLogger("engram_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)

INGEST_QUEUE = "mc:ingest_queue"
EIDOS_QUEUE  = "mc:eidos_queue"
REEMBED_QUEUE = "mc:reembed_queue"
BATCH_SIZE   = 10
IDLE_SLEEP   = 0.1


async def process_item(item: dict, embedder, r) -> None:
    """Embed a single item and write to PostgreSQL."""
    from db.client import insert_chunk
    from uuid import UUID

    content = item.get("content", "")
    if not content.strip():
        return

    # Embed
    try:
        embedding = await embedder.embed(content)
    except Exception as e:
        logger.warning(f"Embedding failed: {e} — storing without embedding")
        embedding = None

    # Write to DB
    try:
        chunk_id = await insert_chunk(
            master_session_id=UUID(item["master_session_id"]),
            session_id=item["session_id"],
            turn_index=int(item.get("turn_index", 0)),
            source_framework=item.get("source_framework", "unknown"),
            chunk_type=item["chunk_type"],
            content=content,
            raw_event=item.get("raw_event", {}),
            confidence=float(item.get("confidence", 0.5)),
            provisional=bool(item.get("provisional", False)),
            embedding=embedding,
            input_modality=item.get("input_modality"),
            context_pressure=item.get("context_pressure"),
        )
        logger.debug(f"Ingested chunk_id={chunk_id} type={item['chunk_type']}")

        # Notify Eidos for somatic tagging (HUMAN and REASONING chunks)
        if item["chunk_type"] in ("HUMAN", "REASONING", "HUMAN_CORRECTION"):
            await r.lpush(EIDOS_QUEUE, json.dumps({
                "chunk_id": str(chunk_id),
                "content": content[:800],
                "chunk_type": item["chunk_type"],
                "turn_index": item.get("turn_index", 0),
            }))

    except Exception as e:
        logger.error(f"DB write failed: {e}")


async def process_reembed(item: dict, embedder) -> None:
    """Re-embed chunks that were imported without embeddings."""
    from db import client as db

    master_session_id = item.get("master_session_id")
    logger.info(f"Re-embedding chunks for master_session={master_session_id}")

    rows = await db.fetchall(
        "SELECT chunk_id, content FROM chunks "
        "WHERE master_session_id=$1 AND embedding IS NULL AND NOT archived "
        "ORDER BY created_at LIMIT 100",
        master_session_id,
    )

    for row in rows:
        try:
            embedding = await embedder.embed(row["content"])
            await db.execute(
                "UPDATE chunks SET embedding=$1::vector WHERE chunk_id=$2",
                embedding, str(row["chunk_id"]),
            )
        except Exception as e:
            logger.warning(f"Re-embed failed for {row['chunk_id']}: {e}")

    logger.info(f"Re-embedded {len(rows)} chunks for {master_session_id}")


async def main():
    from config import load_config
    from sidecars.engram.engram import EmbeddingClient
    import redis.asyncio as aioredis

    cfg = load_config()
    embed_cfg = cfg.get("embedding", {})

    embedder = EmbeddingClient(
        endpoint=embed_cfg.get("endpoint", "http://127.0.0.1:11434"),
        model=embed_cfg.get("model", "nomic-embed-text"),
    )

    # Wait for Ollama to be ready
    for attempt in range(30):
        try:
            test_emb = await embedder.embed("health check")
            assert len(test_emb) > 0
            logger.info(f"Embedding server ready (dim={len(test_emb)})")
            break
        except Exception as e:
            if attempt == 29:
                logger.error(f"Embedding server never became ready: {e}")
                sys.exit(1)
            await asyncio.sleep(2)

    r = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
    logger.info("Engram worker started — listening on mc:ingest_queue")

    shutdown = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _handle_signal(*_):
        logger.info("Engram worker shutting down")
        shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    while not shutdown.is_set():
        try:
            # Blocking pop with 1s timeout
            result = await r.brpop([INGEST_QUEUE, REEMBED_QUEUE], timeout=1)
            if result is None:
                continue

            queue_name, raw = result

            if queue_name == INGEST_QUEUE:
                item = json.loads(raw)
                await process_item(item, embedder, r)

            elif queue_name == REEMBED_QUEUE:
                item = json.loads(raw)
                await process_reembed(item, embedder)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(1)

    await r.aclose()
    await embedder.close()
    logger.info("Engram worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
