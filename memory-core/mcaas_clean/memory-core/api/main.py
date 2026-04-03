"""
memory-core/api/main.py
MCaaS FastAPI application — the only public surface of the container.
All routes are under /v1/ for versioning stability.
"""

from __future__ import annotations
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db import client as db
from config import load_config

logger = logging.getLogger(__name__)
cfg = load_config()


# ── Startup / shutdown ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Memory-Core API starting up")
    # Warm the DB pool
    await db.get_pool()
    yield
    logger.info("Memory-Core API shutting down")
    await db.close()


app = FastAPI(
    title="Memory-Core API",
    description="Cognitive substrate as a service. Universal LLM memory infrastructure.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ───────────────────────────────────────────────────────────────────────

SESSION_KEY = os.environ.get("MC_SESSION_KEY", "changeme-session")
ADMIN_KEY   = os.environ.get("MC_ADMIN_KEY",   "changeme-admin")


def get_human_id(x_mc_human_id: str = Header(...)) -> str:
    if not x_mc_human_id:
        raise HTTPException(status_code=400, detail="X-MC-Human-ID header required")
    return x_mc_human_id


def require_key(x_mc_key: str = Header(...)):
    if x_mc_key not in (SESSION_KEY, ADMIN_KEY):
        raise HTTPException(status_code=401, detail="Invalid key")


def require_admin(x_mc_key: str = Header(...)):
    if x_mc_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Admin key required")


# ── Request / response models ──────────────────────────────────────────────────

class UniversalEventIn(BaseModel):
    human_id: str
    agent_id: str = "default-agent"
    session_id: str
    framework: str = "unknown"
    event_type: str
    turn_index: int = 0
    timestamp: Optional[str] = None
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None
    context_tokens: Optional[int] = None
    max_tokens: Optional[int] = None
    input_modality: Optional[str] = None
    model_name: Optional[str] = None
    latency_ms: Optional[int] = None
    metadata: dict = Field(default_factory=dict)


class BatchIngestIn(BaseModel):
    events: list[UniversalEventIn]


class SessionStartIn(BaseModel):
    session_id: str
    agent_id: str = "default-agent"
    human_id: str
    project_id: Optional[str] = None


class SessionEndIn(BaseModel):
    session_id: str
    human_id: str
    turn_count: int = 0


class RecallIn(BaseModel):
    query: str
    human_id: str
    limit: int = 10
    confidence_min: float = 0.60
    recency_days: int = 90
    topic_filter: Optional[str] = None


class ImportIn(BaseModel):
    archive: dict
    mode: str = "merge"   # "merge" | "replace"


# ── Helpers ────────────────────────────────────────────────────────────────────

async def get_or_create_master_session(
    human_id: str,
    agent_id: str,
    project_id: Optional[str] = None,
) -> tuple[UUID, float]:
    """Returns (master_session_id, gap_hours_since_last_session)."""
    from datetime import datetime, timezone

    row = await db.fetchone(
        "SELECT id, last_active FROM master_sessions "
        "WHERE human_id=$1 AND agent_id=$2 LIMIT 1",
        human_id, agent_id,
    )

    if row:
        last = row["last_active"]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        gap_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        await db.execute(
            "UPDATE master_sessions SET last_active=now(), "
            "total_sessions=total_sessions+1 WHERE id=$1",
            str(row["id"]),
        )
        return UUID(str(row["id"])), gap_hours

    # Create new master session
    new_row = await db.fetchone(
        "INSERT INTO master_sessions (agent_id, human_id, project_id) "
        "VALUES ($1,$2,$3) RETURNING id",
        agent_id, human_id, project_id,
    )
    return UUID(str(new_row["id"])), 0.0


async def ingest_event_internal(event: UniversalEventIn, master_session_id: UUID) -> Optional[str]:
    """Core ingestion logic shared by /v1/ingest and /v1/ingest/batch."""
    from sidecars.engram.engram import (
        Engram, StreamEvent, EidosQueue, ChunkType, PRIORITY_WEIGHTS
    )
    import redis.asyncio as aioredis

    # Map universal event type to internal ChunkType
    TYPE_MAP = {
        "HUMAN_TURN":       ChunkType.HUMAN,
        "MODEL_TURN":       ChunkType.MODEL,
        "MODEL_REASONING":  ChunkType.REASONING,
        "TOOL_USE":         ChunkType.TOOL_IN,
        "TOOL_RESULT":      ChunkType.TOOL_OUT,
        "SKILL_INVOKE":     ChunkType.TOOL_IN,
        "SKILL_RESULT":     ChunkType.TOOL_OUT,
        "SYSTEM_MESSAGE":   ChunkType.SYSTEM,
        "HUMAN_CORRECTION": ChunkType.HUMAN,
    }

    chunk_type = TYPE_MAP.get(event.event_type, ChunkType.SYSTEM)
    provisional = chunk_type == ChunkType.REASONING

    # Build content string
    if event.content:
        content = event.content
    elif event.tool_output is not None:
        content = json.dumps(event.tool_output, ensure_ascii=False)[:4000]
    elif event.tool_input is not None:
        content = json.dumps({"tool": event.tool_name, "input": event.tool_input})[:2000]
    else:
        return None

    if not content.strip():
        return None

    # Push to Redis queue for async Engram worker
    try:
        r = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
        await r.lpush("mc:ingest_queue", json.dumps({
            "master_session_id": str(master_session_id),
            "session_id": event.session_id,
            "turn_index": event.turn_index,
            "chunk_type": chunk_type.value,
            "content": content,
            "confidence": PRIORITY_WEIGHTS[chunk_type],
            "provisional": provisional,
            "source_framework": event.framework,
            "model_name": event.model_name,
            "input_modality": event.input_modality,
            "context_pressure": (
                event.context_tokens / (event.max_tokens or 200000)
                if event.context_tokens else None
            ),
            "raw_event": event.model_dump(),
        }))
        await r.aclose()
    except Exception as e:
        logger.warning(f"Redis push failed, falling back to sync: {e}")
        # Fallback: direct DB write without embedding (embedding added async later)
        from db.client import insert_chunk
        chunk_id = await insert_chunk(
            master_session_id=master_session_id,
            session_id=event.session_id,
            turn_index=event.turn_index,
            source_framework=event.framework,
            chunk_type=chunk_type.value,
            content=content,
            raw_event=event.model_dump(),
            confidence=PRIORITY_WEIGHTS[chunk_type],
            provisional=provisional,
            embedding=None,
        )
        return str(chunk_id)

    # Return a placeholder ID; real ID assigned by worker
    return f"queued:{event.session_id}:{event.turn_index}"


# ── /v1/ingest ─────────────────────────────────────────────────────────────────

@app.post("/v1/ingest", dependencies=[Depends(require_key)])
async def ingest_event(event: UniversalEventIn, background_tasks: BackgroundTasks):
    """Ingest a single UniversalEvent. Latency-optimized — queues async processing."""
    master_session_id, _ = await get_or_create_master_session(
        event.human_id, event.agent_id
    )
    chunk_ref = await ingest_event_internal(event, master_session_id)
    return {"chunk_id": chunk_ref, "queued": True}


@app.post("/v1/ingest/batch", dependencies=[Depends(require_key)])
async def ingest_batch(batch: BatchIngestIn):
    """Batch ingest up to 100 events."""
    if len(batch.events) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 events per batch")

    results = []
    sessions: dict[str, UUID] = {}

    for event in batch.events:
        key = f"{event.human_id}:{event.agent_id}"
        if key not in sessions:
            mid, _ = await get_or_create_master_session(event.human_id, event.agent_id)
            sessions[key] = mid
        chunk_ref = await ingest_event_internal(event, sessions[key])
        results.append(chunk_ref)

    return {"chunk_ids": results, "count": len(results)}


# ── /v1/session ────────────────────────────────────────────────────────────────

@app.post("/v1/session/start", dependencies=[Depends(require_key)])
async def session_start(req: SessionStartIn):
    """
    Notify session start. Returns orient injection, open loops, Augur briefing.
    """
    master_session_id, gap_hours = await get_or_create_master_session(
        req.human_id, req.agent_id, req.project_id
    )

    # Load Psyche orient injection
    from sidecars.psyche.psyche import Psyche
    psyche = Psyche(cfg.get("psyche", {}))
    orient = await psyche.session_start_orient(
        master_session_id=master_session_id,
        last_session_id=None,
        session_gap_hours=gap_hours,
    )

    # Update loneliness signal in SSS
    from rip.engine import RIPEngine
    rip = RIPEngine(cfg.get("rip", {}))
    sss = await rip.load_latest_sss(master_session_id)
    sss.update_loneliness(gap_hours)
    await rip.snapshot_sss(sss, master_session_id, req.session_id, 0)

    # Get open loops
    open_loops_rows = await db.fetchall(
        "SELECT description, opened_at FROM open_loops "
        "WHERE master_session_id=$1 AND resolved=FALSE "
        "ORDER BY last_seen DESC LIMIT 5",
        str(master_session_id),
    )

    # Augur session-start briefing
    from sidecars.augur.augur import Augur
    augur = Augur(cfg.get("augur", {}))
    augur_briefing = await augur.session_start_briefing(master_session_id)

    return {
        "master_session_id": str(master_session_id),
        "session_gap_hours": round(gap_hours, 1),
        "orient_injection": orient,
        "open_loops": [dict(r) for r in open_loops_rows],
        "augur_briefing": augur_briefing,
    }


@app.post("/v1/session/end", dependencies=[Depends(require_key)])
async def session_end(req: SessionEndIn, background_tasks: BackgroundTasks):
    """
    Notify session end. Triggers full reflective layer asynchronously.
    Returns immediately — reflective processing happens in background.
    """
    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        req.human_id,
    )
    if not row:
        return {"status": "no_session"}

    master_session_id = UUID(str(row["id"]))

    # Update turn count
    await db.execute(
        "UPDATE master_sessions SET total_turns=total_turns+$1 WHERE id=$2",
        req.turn_count, str(master_session_id),
    )

    # Queue reflective layer via Redis (non-blocking)
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
        await r.lpush("mc:reflective_queue", json.dumps({
            "trigger": "session_end",
            "master_session_id": str(master_session_id),
            "session_id": req.session_id,
            "human_id": req.human_id,
        }))
        await r.aclose()
    except Exception as e:
        logger.warning(f"Reflective queue push failed: {e}")

    return {"status": "reflective_layer_queued", "master_session_id": str(master_session_id)}


# ── /v1/inject ─────────────────────────────────────────────────────────────────

@app.get("/v1/inject", dependencies=[Depends(require_key)])
async def get_injection(
    session_id: str,
    hook_type: str = "PreToolUse",
    tool_name: str = "",
    turn_index: int = 0,
    human_id: str = Header(..., alias="X-MC-Human-ID"),
    agent_id: str = Header(default="default-agent", alias="X-MC-Agent-ID"),
):
    """
    Core injection endpoint. Called at every hook point.
    Returns memory blocks, relational context, orchestration hints.
    Latency target: < 450ms.
    """
    import asyncio

    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        human_id,
    )
    if not row:
        return {"inject": False}

    master_session_id = UUID(str(row["id"]))

    # Run Anamnesis + RIP in parallel
    from sidecars.anamnesis.anamnesis import Anamnesis, SessionState
    from rip.engine import RIPEngine

    session = SessionState(
        session_id=session_id,
        master_session_id=master_session_id,
        turn_index=turn_index,
    )

    rip = RIPEngine(cfg.get("rip", {}))
    sss = await rip.load_latest_sss(master_session_id)
    relational_ctx = rip.format_relational_context(sss)

    anamnesis = Anamnesis(cfg.get("anamnesis", {}))
    payload = {
        "hook_type": hook_type,
        "session_id": session_id,
        "tool_name": tool_name,
        "turn_index": turn_index,
    }

    try:
        async with asyncio.timeout(0.40):
            memory_injection = await anamnesis.run(
                payload, session,
                psyche_steering=relational_ctx if relational_ctx else None,
            )
    except asyncio.TimeoutError:
        memory_injection = ""

    # Augur orchestration hints
    from sidecars.augur.augur import Augur
    augur = Augur(cfg.get("augur", {}))
    hints = await augur.get_sequence_hints(master_session_id, [])

    hint_injections = [augur.format_orchestration_hint(h) for h in hints[:2]]

    all_parts = [p for p in [memory_injection] + hint_injections if p]
    system_message = "\n\n".join(all_parts) if all_parts else None

    return {
        "inject": bool(system_message),
        "system_message": system_message,
        "confusion_tier": session.confusion_tier(),
        "psyche_steering": relational_ctx if relational_ctx else None,
        "orchestration_hints": [
            {
                "skill_name": h.skill_name,
                "probability": h.probability,
                "basis_sessions": h.session_count,
                "injection_xml": augur.format_orchestration_hint(h),
            }
            for h in hints[:2]
        ],
    }


# ── /v1/recall ─────────────────────────────────────────────────────────────────

@app.post("/v1/recall", dependencies=[Depends(require_key)])
async def recall(req: RecallIn):
    """Semantic recall. Returns ranked chunks matching the query."""
    from sidecars.engram.engram import EmbeddingClient
    embedder = EmbeddingClient(
        endpoint=cfg.get("embedding", {}).get("endpoint", "http://127.0.0.1:11434"),
        model=cfg.get("embedding", {}).get("model", "nomic-embed-text"),
    )

    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        req.human_id,
    )
    if not row:
        return {"results": [], "count": 0}

    embedding = await embedder.embed(req.query)
    rows = await db.anamnesis_search(
        embedding=embedding,
        master_session_id=UUID(str(row["id"])),
        current_session_id="__recall__",
        confidence_floor=req.confidence_min,
        recency_days=req.recency_days,
        similarity_floor=0.55,
        limit=req.limit,
    )

    results = []
    for r in rows:
        d = dict(r)
        d["chunk_id"] = str(d["chunk_id"])
        d["similarity"] = float(d["similarity"])
        d["topic_labels"] = list(d.get("topic_labels") or [])
        results.append(d)

    return {"results": results, "count": len(results)}


# ── /v1/soul ────────────────────────────────────────────────────────────────────

@app.get("/v1/soul", dependencies=[Depends(require_key)])
async def get_soul(human_id: str = Header(..., alias="X-MC-Human-ID")):
    """Read soul.md for this human."""
    from pathlib import Path
    soul_path = Path(cfg.get("psyche", {}).get("soul_md_path", "/data/soul/soul.md"))
    if soul_path.exists():
        return {"soul": soul_path.read_text(encoding="utf-8"), "path": str(soul_path)}
    return {"soul": None}


@app.put("/v1/soul", dependencies=[Depends(require_key)])
async def update_soul(
    human_id: str = Header(..., alias="X-MC-Human-ID"),
    content: str = "",
):
    """Manually update soul.md (human edits)."""
    from pathlib import Path
    soul_path = Path(cfg.get("psyche", {}).get("soul_md_path", "/data/soul/soul.md"))
    soul_path.write_text(content, encoding="utf-8")
    return {"status": "updated", "chars": len(content)}


# ── /v1/open_loops ─────────────────────────────────────────────────────────────

@app.get("/v1/open_loops", dependencies=[Depends(require_key)])
async def get_open_loops(human_id: str = Header(..., alias="X-MC-Human-ID")):
    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        human_id,
    )
    if not row:
        return {"open_loops": []}
    rows = await db.fetchall(
        "SELECT loop_id, description, opened_at, last_seen FROM open_loops "
        "WHERE master_session_id=$1 AND resolved=FALSE ORDER BY last_seen DESC LIMIT 10",
        str(row["id"]),
    )
    return {"open_loops": [dict(r) for r in rows]}


# ── /v1/sss ────────────────────────────────────────────────────────────────────

@app.get("/v1/sss", dependencies=[Depends(require_key)])
async def get_sss(human_id: str = Header(..., alias="X-MC-Human-ID")):
    """Get current Synthetic Somatic State."""
    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        human_id,
    )
    if not row:
        return {"sss": None}

    from rip.engine import RIPEngine
    rip = RIPEngine(cfg.get("rip", {}))
    sss = await rip.load_latest_sss(UUID(str(row["id"])))
    return {"sss": sss.to_dict()}


# ── /v1/export ─────────────────────────────────────────────────────────────────

@app.get("/v1/export/{human_id}", dependencies=[Depends(require_admin)])
async def export_memory(human_id: str):
    """Export complete memory state for a human as a portable JSON archive."""
    from datetime import datetime, timezone

    row = await db.fetchone(
        "SELECT * FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        human_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"No session found for human_id={human_id}")

    master_session_id = str(row["id"])

    # Fetch all data
    chunks = await db.fetchall(
        "SELECT chunk_id, content, chunk_type, confidence, provisional, validated, "
        "created_at, session_id, somatic_register, somatic_valence, turn_index "
        "FROM chunks WHERE master_session_id=$1 AND NOT archived ORDER BY created_at",
        master_session_id,
    )

    topics = await db.fetchall(
        "SELECT node_id, label, keywords, topic_type, chunk_count, session_count, "
        "confidence, first_seen, last_active FROM topic_nodes WHERE master_session_id=$1",
        master_session_id,
    )

    topic_summaries = await db.fetchall(
        """
        SELECT ts.node_id, ts.depth, ts.summary_text, ts.updated_at
        FROM topic_summaries ts
        JOIN topic_nodes tn ON ts.node_id = tn.node_id
        WHERE tn.master_session_id=$1
        """,
        master_session_id,
    )

    open_loops = await db.fetchall(
        "SELECT description, opened_at, last_seen FROM open_loops "
        "WHERE master_session_id=$1 AND resolved=FALSE",
        master_session_id,
    )

    procedural_notes = await db.fetchall(
        "SELECT skill_name, note_text, confidence FROM procedural_notes "
        "WHERE master_session_id=$1 AND active=TRUE",
        master_session_id,
    )

    # Soul.md
    from pathlib import Path
    soul_path = Path(cfg.get("psyche", {}).get("soul_md_path", "/data/soul/soul.md"))
    soul_md = soul_path.read_text() if soul_path.exists() else ""

    def serialize(rows):
        result = []
        for r in rows:
            d = {}
            for k, v in dict(r).items():
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
                elif isinstance(v, UUID):
                    d[k] = str(v)
                else:
                    d[k] = v
            result.append(d)
        return result

    archive = {
        "export_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "human_id": human_id,
        "master_session": {k: str(v) if isinstance(v, UUID) else
                           v.isoformat() if hasattr(v, 'isoformat') else v
                           for k, v in dict(row).items()},
        "chunks": serialize(chunks),
        "topic_nodes": serialize(topics),
        "topic_summaries": serialize(topic_summaries),
        "open_loops": serialize(open_loops),
        "procedural_notes": serialize(procedural_notes),
        "soul_md": soul_md,
        "export_stats": {
            "total_chunks": len(chunks),
            "total_topics": len(topics),
        },
    }

    return JSONResponse(content=archive)


@app.post("/v1/import", dependencies=[Depends(require_admin)])
async def import_memory(req: ImportIn):
    """Import a previously exported memory archive."""
    archive = req.archive
    human_id = archive.get("human_id")
    mode = req.mode  # "merge" or "replace"

    if not human_id:
        raise HTTPException(status_code=400, detail="Archive missing human_id")

    if mode == "replace":
        # Delete existing data for this human
        await db.execute(
            "DELETE FROM master_sessions WHERE human_id=$1", human_id
        )
        logger.info(f"Replaced memory for human_id={human_id}")

    # Restore master session
    ms = archive.get("master_session", {})
    existing = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1", human_id
    )

    if not existing:
        new_ms = await db.fetchone(
            "INSERT INTO master_sessions (agent_id, human_id) VALUES ($1,$2) RETURNING id",
            ms.get("agent_id", "imported-agent"), human_id,
        )
        master_session_id = str(new_ms["id"])
    else:
        master_session_id = str(existing["id"])

    # Restore chunks (without embeddings — will be re-embedded by worker)
    chunks_imported = 0
    for chunk in archive.get("chunks", []):
        try:
            await db.execute(
                """
                INSERT INTO chunks
                    (master_session_id, session_id, turn_index, source_framework,
                     chunk_type, content, confidence, provisional, validated)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT DO NOTHING
                """,
                master_session_id,
                chunk.get("session_id", "imported"),
                chunk.get("turn_index", 0),
                chunk.get("source_framework", "imported"),
                chunk.get("chunk_type", "MODEL"),
                chunk.get("content", ""),
                float(chunk.get("confidence", 0.5)),
                bool(chunk.get("provisional", False)),
                bool(chunk.get("validated", False)),
            )
            chunks_imported += 1
        except Exception as e:
            logger.warning(f"Chunk import skipped: {e}")

    # Restore soul.md
    soul_md = archive.get("soul_md", "")
    if soul_md:
        from pathlib import Path
        soul_path = Path(cfg.get("psyche", {}).get("soul_md_path", "/data/soul/soul.md"))
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(soul_md, encoding="utf-8")

    # Queue re-embedding for imported chunks
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
        await r.lpush("mc:reembed_queue", json.dumps({
            "master_session_id": master_session_id,
            "human_id": human_id,
        }))
        await r.aclose()
    except Exception:
        pass

    return {
        "status": "imported",
        "human_id": human_id,
        "mode": mode,
        "chunks_imported": chunks_imported,
        "reembedding_queued": True,
    }


# ── /v1/admin/reflective ───────────────────────────────────────────────────────

@app.post("/v1/admin/reflective/oneiros", dependencies=[Depends(require_admin)])
async def trigger_oneiros(
    human_id: str = Header(..., alias="X-MC-Human-ID"),
    min_chunks: int = 10,
    background_tasks: BackgroundTasks = None,
):
    """Trigger Oneiros belief consolidation for all mature topics."""
    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        human_id,
    )
    if not row:
        return {"status": "no_session"}

    from sidecars.oneiros.oneiros import Oneiros
    oneiros = Oneiros(cfg.get("oneiros", {}))
    results = await oneiros.run_session_end(UUID(str(row["id"])))
    consolidated = [r for r in results if not r.skipped]

    return {
        "status": "complete",
        "topics_consolidated": len(consolidated),
        "topics_checked": len(results),
        "detail": [
            {"topic": r.topic_label, "beliefs": r.beliefs_written,
             "archived": r.chunks_archived, "ratio": r.compression_ratio}
            for r in consolidated
        ],
    }


@app.post("/v1/admin/reflective/psyche", dependencies=[Depends(require_admin)])
async def trigger_psyche(
    human_id: str = Header(..., alias="X-MC-Human-ID"),
    turns: int = 50,
):
    """Trigger Psyche self-reflection and soul.md update."""
    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        human_id,
    )
    if not row:
        return {"status": "no_session"}

    master_session_id = UUID(str(row["id"]))
    from sidecars.psyche.psyche import Psyche
    from rip.engine import RIPEngine

    rip = RIPEngine(cfg.get("rip", {}))
    sss = await rip.load_latest_sss(master_session_id)
    sss_summary = "\n".join(f"{k}: {v}" for k, v in sss.to_dict().items())

    psyche = Psyche(cfg.get("psyche", {}))
    # Use the most recent session ID
    recent_session = await db.fetchone(
        "SELECT session_id FROM chunks WHERE master_session_id=$1 "
        "ORDER BY created_at DESC LIMIT 1",
        str(master_session_id),
    )
    session_id = recent_session["session_id"] if recent_session else "unknown"

    steering = await psyche.reflect(
        master_session_id=master_session_id,
        session_id=session_id,
        sss_summary=sss_summary,
    )

    return {
        "status": "complete",
        "soul_updated": True,
        "steering_ready": bool(steering),
    }


@app.post("/v1/admin/reflective/augur", dependencies=[Depends(require_admin)])
async def trigger_augur(
    human_id: str = Header(..., alias="X-MC-Human-ID"),
    sessions: int = 20,
):
    """Trigger Augur behavioral pattern mining."""
    row = await db.fetchone(
        "SELECT id FROM master_sessions WHERE human_id=$1 ORDER BY last_active DESC LIMIT 1",
        human_id,
    )
    if not row:
        return {"status": "no_session"}

    from sidecars.augur.augur import Augur
    augur = Augur(cfg.get("augur", {}))
    recent_session = await db.fetchone(
        "SELECT session_id FROM chunks WHERE master_session_id=$1 "
        "ORDER BY created_at DESC LIMIT 1",
        str(row["id"]),
    )
    if recent_session:
        await augur.mine_session_patterns(
            UUID(str(row["id"])), recent_session["session_id"]
        )

    return {"status": "complete"}


# ── /v1/tenants ────────────────────────────────────────────────────────────────

@app.get("/v1/tenants", dependencies=[Depends(require_admin)])
async def list_tenants():
    rows = await db.fetchall(
        """
        SELECT ms.human_id, ms.agent_id, ms.total_sessions, ms.total_turns,
               ms.last_active, ms.created_at,
               COUNT(c.chunk_id) as chunk_count
        FROM master_sessions ms
        LEFT JOIN chunks c ON c.master_session_id = ms.id AND NOT c.archived
        GROUP BY ms.id
        ORDER BY ms.last_active DESC
        """
    )
    return {
        "tenants": [
            {k: str(v) if isinstance(v, UUID) else
             v.isoformat() if hasattr(v, 'isoformat') else v
             for k, v in dict(r).items()}
            for r in rows
        ],
        "count": len(rows),
    }


@app.delete("/v1/forget/{human_id}", dependencies=[Depends(require_admin)])
async def forget_human(human_id: str, confirm: str = ""):
    """GDPR right-to-be-forgotten. Irreversible."""
    if confirm != "YES_DELETE_ALL":
        raise HTTPException(
            status_code=400,
            detail="Pass ?confirm=YES_DELETE_ALL to confirm. This is permanent."
        )
    await db.execute("DELETE FROM master_sessions WHERE human_id=$1", human_id)
    logger.warning(f"FORGET: all data deleted for human_id={human_id}")
    return {"status": "deleted", "human_id": human_id}


# ── /health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Container health check. No auth required."""
    checks = {}

    # Database
    try:
        await db.fetchone("SELECT 1 as ok")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Ollama
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://127.0.0.1:11434/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
    except Exception:
        checks["ollama"] = "unreachable"

    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://127.0.0.1:6379")
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unreachable"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "version": "1.0.0",
        "services": checks,
    }
