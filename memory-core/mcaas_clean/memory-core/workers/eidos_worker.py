"""
workers/eidos_worker.py
Async somatic tagger — drains mc:eidos_queue.
Tags fresh HUMAN and REASONING chunks with somatic registers.
"""

from __future__ import annotations
import asyncio
import json
import logging
import signal
import sys
from uuid import UUID

logger = logging.getLogger("eidos_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

EIDOS_QUEUE = "mc:eidos_queue"


async def main():
    from config import load_config
    from sidecars.eidos.eidos import Eidos
    import redis.asyncio as aioredis

    cfg = load_config()
    eidos = Eidos()

    r = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
    logger.info("Eidos worker started — listening on mc:eidos_queue")

    shutdown = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _handle_signal(*_):
        shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    while not shutdown.is_set():
        try:
            result = await r.brpop([EIDOS_QUEUE], timeout=2)
            if result is None:
                continue

            _, raw = result
            item = json.loads(raw)

            await eidos.tag_chunk(
                chunk_id=UUID(item["chunk_id"]),
                content=item["content"],
                chunk_type=item.get("chunk_type", "MODEL"),
                turn_index=int(item.get("turn_index", 0)),
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Eidos worker error: {e}")
            await asyncio.sleep(1)

    await r.aclose()
    logger.info("Eidos worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
