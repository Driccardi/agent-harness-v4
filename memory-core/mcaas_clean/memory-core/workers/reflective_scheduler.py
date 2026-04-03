"""
workers/reflective_scheduler.py
The reflective layer scheduler.

Two triggers:
  1. Redis queue (mc:reflective_queue) — fired by session end events
  2. Time-based — Kairos every K=20 turns, Oneiros/Psyche/Augur nightly equivalent

This is the Default Mode Network analog: runs when the agent is "at rest",
processes experience into knowledge.
"""

from __future__ import annotations
import asyncio
import json
import logging
import signal
import time
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger("reflective_scheduler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

REFLECTIVE_QUEUE = "mc:reflective_queue"
KAIROS_INTERVAL_SECONDS = 300        # Run Kairos every 5 minutes if there are new chunks
DEEP_REFLECTIVE_INTERVAL_SECONDS = 3600 * 4  # Deep reflection every 4 hours


async def run_kairos_for_session(master_session_id: UUID, session_id: str) -> None:
    """Run Kairos topic consolidation for a session."""
    from config import load_config
    from sidecars.kairos.kairos import Kairos

    cfg = load_config()
    kairos = Kairos(cfg.get("kairos", {}))

    try:
        topics_updated = await kairos.run_consolidation(
            master_session_id=master_session_id,
            session_id=session_id,
        )
        validated, abandoned = await kairos.validate_provisional_chunks(
            master_session_id=master_session_id,
            session_id=session_id,
            current_turn=9999,  # evaluate all pending
        )
        logger.info(
            f"Kairos: master={str(master_session_id)[:8]} "
            f"topics={topics_updated} validated={validated} abandoned={abandoned}"
        )
    except Exception as e:
        logger.error(f"Kairos error: {e}")


async def run_full_reflective(master_session_id: UUID, session_id: str, human_id: str) -> None:
    """Run the complete reflective layer for a session end event."""
    from config import load_config
    from sidecars.oneiros.oneiros import Oneiros
    from sidecars.psyche.psyche import Psyche
    from sidecars.praxis.praxis import Praxis
    from sidecars.augur.augur import Augur
    from rip.engine import RIPEngine

    cfg = load_config()

    logger.info(f"Full reflective run: master={str(master_session_id)[:8]} session={session_id[:16]}")

    # 1. Kairos — topic consolidation
    await run_kairos_for_session(master_session_id, session_id)

    # 2. Praxis — procedural memory optimization
    try:
        praxis = Praxis(cfg.get("praxis", {}))
        await praxis.run_session_end(master_session_id)
    except Exception as e:
        logger.error(f"Praxis error: {e}")

    # 3. Oneiros — belief consolidation
    try:
        oneiros = Oneiros(cfg.get("oneiros", {}))
        results = await oneiros.run_session_end(master_session_id)
        consolidated = [r for r in results if not r.skipped]
        if consolidated:
            logger.info(f"Oneiros: consolidated {len(consolidated)} topics")
    except Exception as e:
        logger.error(f"Oneiros error: {e}")

    # 4. Psyche — self-reflection and soul.md update
    try:
        rip = RIPEngine(cfg.get("rip", {}))
        sss = await rip.load_latest_sss(master_session_id)
        sss_summary = "\n".join(f"{k}: {v}" for k, v in sss.to_dict().items())

        psyche = Psyche(cfg.get("psyche", {}))
        steering = await psyche.reflect(
            master_session_id=master_session_id,
            session_id=session_id,
            sss_summary=sss_summary,
        )
        if steering:
            # Store steering injection for next session start
            import redis.asyncio as aioredis
            r_client = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
            await r_client.setex(
                f"mc:psyche_steering:{human_id}",
                86400,  # 24 hour TTL
                steering,
            )
            await r_client.aclose()
            logger.info("Psyche: soul.md updated, steering stored")
    except Exception as e:
        logger.error(f"Psyche error: {e}")

    # 5. Augur — behavioral pattern mining
    try:
        augur = Augur(cfg.get("augur", {}))
        await augur.mine_session_patterns(master_session_id, session_id)
    except Exception as e:
        logger.error(f"Augur error: {e}")

    logger.info(f"Full reflective run complete: master={str(master_session_id)[:8]}")


async def process_queue_item(item: dict) -> None:
    """Process a single item from the reflective queue."""
    trigger = item.get("trigger", "session_end")
    master_session_id = UUID(item["master_session_id"])
    session_id = item.get("session_id", "")
    human_id = item.get("human_id", "default")

    if trigger == "session_end":
        await run_full_reflective(master_session_id, session_id, human_id)
    elif trigger == "kairos_only":
        await run_kairos_for_session(master_session_id, session_id)


async def periodic_kairos_sweep() -> None:
    """
    Every KAIROS_INTERVAL_SECONDS, check for sessions with unprocessed chunks
    and run Kairos on them. This catches chunks from long-running sessions
    that haven't ended yet.
    """
    from db import client as db

    while True:
        await asyncio.sleep(KAIROS_INTERVAL_SECONDS)
        try:
            # Find sessions with recent unprocessed chunks
            rows = await db.fetchall(
                """
                SELECT DISTINCT ms.id as master_session_id,
                                c.session_id,
                                ms.human_id
                FROM master_sessions ms
                JOIN chunks c ON c.master_session_id = ms.id
                WHERE c.created_at > now() - INTERVAL '10 minutes'
                  AND NOT c.archived
                  AND c.chunk_type NOT IN ('CONSOLIDATED_BELIEF')
                LIMIT 10
                """
            )
            for row in rows:
                await run_kairos_for_session(
                    UUID(str(row["master_session_id"])),
                    row["session_id"],
                )
        except Exception as e:
            logger.debug(f"Periodic Kairos sweep error: {e}")


async def main():
    import redis.asyncio as aioredis

    r = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
    logger.info("Reflective scheduler started")

    shutdown = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _handle_signal(*_):
        shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    # Start periodic Kairos sweep as background task
    kairos_task = asyncio.create_task(periodic_kairos_sweep())

    while not shutdown.is_set():
        try:
            result = await r.brpop([REFLECTIVE_QUEUE], timeout=5)
            if result is None:
                continue

            _, raw = result
            item = json.loads(raw)
            logger.info(f"Processing reflective item: {item.get('trigger')} "
                        f"session={item.get('session_id', '')[:16]}")

            # Run in background — don't block the queue
            asyncio.create_task(process_queue_item(item))

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Reflective scheduler error: {e}")
            await asyncio.sleep(2)

    kairos_task.cancel()
    await r.aclose()
    logger.info("Reflective scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
