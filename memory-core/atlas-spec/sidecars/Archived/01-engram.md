# 01 — Engram: Stream Embedder

> **Named for**: the engram, the hypothetical means by which memory traces are
> stored as physical changes in the brain.

---

## 1. Identity Card

| Field             | Value                                                     |
|-------------------|-----------------------------------------------------------|
| Name              | Engram                                                    |
| Tier              | Real-Time                                                 |
| Role              | Hippocampal encoder -- capture everything, prune nothing  |
| Trigger           | Continuous; reads JSONL stream as events are emitted       |
| Latency target    | < 100 ms per chunk (p95, including DB write)              |
| Model requirement | Embedding model only (`nomic-embed-text`, 768 dimensions) |
| Stateless         | Yes -- no in-memory state survives process restart         |
| Owns (write)      | `chunks`, `skill_invocations`                             |
| Depends on (read) | JSONL event stream from agent runtime                     |

---

## 2. Purpose

Engram is the fast-lane encoder of the Atlas Cognitive Substrate. It reads
the agent's JSONL event stream continuously and embeds every meaningful event
into the PostgreSQL vector store within milliseconds. It is the hippocampal
analog: capture everything, understand nothing, be fast.

Engram is deliberately simple. It does not classify topics, does not build
graph structure, does not consolidate beliefs, does not prune. Its only
guarantee is this: **if something appeared in the stream, it will be
retrievable by vector similarity within seconds.**

Other sidecars depend on Engram's output:

- **Eidos** enriches chunks with somatic tags and signal classification.
- **Kairos** clusters chunks into topic nodes.
- **Oneiros** consolidates and prunes aged chunks.
- **Anamnesis** retrieves chunks for injection into context.

Engram's relationship to these consumers is fire-and-forget. It writes chunks
and moves on. It never waits for downstream processing.

---

## 3. Inputs

### 3.1 JSONL Event Stream

Engram consumes a newline-delimited JSON stream emitted by the agent runtime.
Each line is a self-contained event object. The stream is the sole input;
Engram performs no database reads during normal operation.

Events in the stream include:

| Event kind        | Source                  | Typical content                              |
|-------------------|-------------------------|----------------------------------------------|
| Human utterance   | `UserPromptSubmit` hook | User's natural-language message               |
| Model response    | `ModelResponse` hook    | Assistant's generated text                    |
| Reasoning block   | `ModelResponse` hook    | Extended thinking / chain-of-thought content  |
| Tool input        | `PreToolUse` hook       | Tool name + input parameters (JSON)           |
| Tool output       | `PostToolUse` hook      | Tool execution result (JSON, truncated)       |
| System message    | Various                 | System prompts, configuration directives      |

### 3.2 Event Schema (Minimum Required Fields)

```jsonc
{
  "hook_type":          "UserPromptSubmit",   // string, required
  "session_id":         "sess_abc123",        // string, required
  "master_session_id":  "uuid-...",           // UUID, required
  "turn_index":         7,                    // integer, required
  "timestamp":          "2026-03-15T...",     // ISO 8601, required
  "model":              "claude-sonnet-4-6",  // string, optional
  "context_tokens":     48000,                // integer, optional

  // Content fields -- at most one populated per event:
  "user_message":       "...",                // human utterance
  "model_content":      "...",                // model response
  "reasoning_content":  "...",                // thinking block
  "tool_name":          "Read",               // tool invocation
  "tool_input":         { ... },              // tool parameters
  "tool_output":        { ... },              // tool result
  "system_content":     "..."                 // system directive
}
```

---

## 4. Signal Taxonomy and Priority Weights

Engram classifies each event into exactly one `ChunkType` and assigns an
initial confidence weight. This weight represents the a priori informational
value of the signal class -- not a judgment about any specific chunk's content.

```
ChunkType       Confidence   Provisional   Rationale
─────────────   ──────────   ───────────   ─────────────────────────────────────
HUMAN           1.00         false         User intent is ground truth.
MODEL           0.85         false         Agent output, high but deferential.
TOOL_OUT        0.80         false         Observed external state.
TOOL_IN         0.65         false         Agent action, meaningful but verbose.
REASONING       0.40         true          Speculative; may be abandoned mid-chain.
SYSTEM          0.30         false         Configuration noise, rarely recalled.
```

### 4.1 Classification Priority

When an event contains multiple content fields (which should not happen but
must be handled defensively), the classification precedence is:

```
HUMAN > REASONING > MODEL > SYSTEM > TOOL_OUT > TOOL_IN
```

This order ensures that human utterances always take priority, and that
reasoning blocks (which may coexist with model responses in some frameworks)
are captured with their provisional flag intact.

### 4.2 Reasoning Chunks: Provisional Semantics

Chunks with `chunk_type = REASONING` are always written with `provisional = true`
and `confidence = 0.40`. This reflects the epistemological status of
chain-of-thought output: it is exploratory, may contain dead ends, and may be
abandoned before the model settles on a final response.

Provisional chunks are:
- Excluded from Anamnesis injection queries by default.
- Subject to validation or abandonment by Kairos within K turns (configurable,
  default K=5).
- Never pruned by Engram (pruning is Oneiros's responsibility).

---

## 5. Processing Pipeline

### 5.1 High-Level Flow

```
  JSONL Stream
       |
       v
  [1] Parse line as JSON
       |
       v
  [2] Normalize via FrameworkAdapter
       |
       v
  [3] Classify ChunkType + assign confidence
       |
       v
  [4] Extract content string, apply truncation limits
       |
       v
  [5] Compute content_hash (SHA-256) for deduplication
       |
       v
  [6] Check dedup: content_hash + session_id already exists? --> skip
       |
       v
  [7] Generate embedding via local model (<100ms target)
       |
       v
  [8] Write NormalizedChunk to PostgreSQL (INSERT only)
       |
       v
  [9] Enqueue chunk_id for Eidos enrichment (async, fire-and-forget)
       |
       v
  [10] Record skill invocation if tool event matches known skill
```

### 5.2 Pseudocode

```python
async def ingest(event: StreamEvent) -> Optional[UUID]:
    """
    Embed and persist a single stream event.
    Returns chunk_id on success, None if content is empty or duplicate.
    """
    t0 = monotonic()

    # ── Step 1: Classify ──
    chunk_type = classify_event(event)
    content    = extract_content(event, chunk_type)

    if not content.strip():
        return None

    # ── Step 2: Dedup ──
    content_hash = sha256(content.encode()).hexdigest()
    if await dedup_exists(content_hash, event.session_id):
        return None  # idempotent on replay

    # ── Step 3: Assign metadata ──
    provisional = (chunk_type == ChunkType.REASONING)
    confidence  = PRIORITY_WEIGHTS[chunk_type]

    context_pressure = (
        event.context_tokens / MAX_CONTEXT_TOKENS
        if event.context_tokens else None
    )

    # ── Step 4: Embed ──
    try:
        embedding = await embedder.embed(content)
    except EmbeddingError:
        # Store without embedding; re-embed worker will backfill.
        embedding = None

    # ── Step 5: Persist ──
    try:
        chunk_id = await db.insert_chunk(
            master_session_id = event.master_session_id,
            session_id        = event.session_id,
            turn_index        = event.turn_index,
            source_framework  = event.source_framework,
            chunk_type        = chunk_type.value,
            content           = content,
            content_hash      = content_hash,
            raw_event         = event.raw,
            confidence        = confidence,
            provisional       = provisional,
            embedding         = embedding,
            input_modality    = event.input_modality,
            context_pressure  = context_pressure,
        )
    except TransientDBError as e:
        await wal.append(event)   # buffer to local WAL, replay on recovery
        log.error(f"DB write failed, buffered to WAL: {e}")
        return None

    # ── Step 6: Notify downstream (non-blocking) ──
    if provisional or chunk_type == ChunkType.HUMAN:
        await eidos_queue.put_nowait(chunk_id, content)

    # ── Step 7: Record skill invocation if applicable ──
    if chunk_type in (ChunkType.TOOL_IN, ChunkType.TOOL_OUT):
        await maybe_record_skill_invocation(event, chunk_id)

    elapsed_ms = (monotonic() - t0) * 1000
    metrics.observe("engram.ingest_latency_ms", elapsed_ms)

    return chunk_id
```

### 5.3 Content Extraction and Truncation

Different chunk types require different extraction strategies:

```python
def extract_content(event: StreamEvent, chunk_type: ChunkType) -> str:
    match chunk_type:
        case ChunkType.HUMAN:
            return event.human_content or ""
        case ChunkType.REASONING:
            return event.reasoning_content or ""
        case ChunkType.MODEL:
            return event.model_content or ""
        case ChunkType.SYSTEM:
            return event.system_content or ""
        case ChunkType.TOOL_OUT:
            # Truncate large tool outputs to 4000 chars.
            # Full output is preserved in raw_event JSONB.
            return json.dumps(event.tool_output)[:4000]
        case ChunkType.TOOL_IN:
            # Include tool name for retrieval context.
            payload = {"tool": event.tool_name, "input": event.tool_input}
            return json.dumps(payload)[:2000]
```

Truncation limits are applied to the embedding input only. The complete
event payload is always preserved in the `raw_event` JSONB column.

### 5.4 Input Modality Metadata

For `HUMAN` chunks, Engram records additional proprioceptive metadata:

| Field              | Description                                           |
|--------------------|-------------------------------------------------------|
| `input_modality`   | TEXT, VOICE, CLIPBOARD, FILE_UPLOAD, API              |
| `input_route`      | DIRECT, CONTINUATION, SLASH_COMMAND                   |
| `context_pressure` | Ratio of current context tokens to max context window |

This metadata enables downstream sidecars (particularly Augur and Psyche) to
reason about the human's interaction patterns without re-parsing raw events.

---

## 6. Outputs

### 6.1 `chunks` Table (Primary Output)

Every successfully processed event produces exactly one row in the `chunks`
table. Engram performs **INSERT only** -- it never issues UPDATE or DELETE
against this table.

Key columns written by Engram:

| Column              | Set by Engram?  | Notes                                     |
|---------------------|-----------------|-------------------------------------------|
| `chunk_id`          | DB default      | `gen_random_uuid()`                       |
| `master_session_id` | Yes             | From stream event                         |
| `session_id`        | Yes             | From stream event                         |
| `turn_index`        | Yes             | From stream event                         |
| `source_framework`  | Yes             | Adapter-provided (e.g. `claude_code`)     |
| `chunk_type`        | Yes             | Classified by Engram                      |
| `content`           | Yes             | Extracted and possibly truncated          |
| `raw_event`         | Yes             | Complete original JSON payload            |
| `confidence`        | Yes             | Initial weight from priority table        |
| `provisional`       | Yes             | `true` for REASONING, `false` otherwise   |
| `embedding`         | Yes             | 768-dim vector, or NULL on embed failure  |
| `input_modality`    | Yes (HUMAN)     | Only populated for HUMAN chunks           |
| `context_pressure`  | Yes             | Computed from `context_tokens`            |

Columns **not** written by Engram (owned by other sidecars):

| Column              | Owner    |
|---------------------|----------|
| `signal_tags`       | Eidos    |
| `somatic_register`  | Eidos    |
| `somatic_valence`   | Eidos    |
| `somatic_energy`    | Eidos    |
| `validated`         | Kairos   |
| `archived`          | Oneiros  |
| `archived_at`       | Oneiros  |

### 6.2 `skill_invocations` Table

When a tool event matches a known skill pattern, Engram writes a record to
`skill_invocations`. This table feeds the Praxis procedural memory optimizer.

### 6.3 Eidos Classification Queue

After persisting a chunk, Engram pushes a lightweight notification to an
async queue (Redis list `mc:eidos_queue` or in-process `asyncio.Queue`). The
notification contains `chunk_id`, truncated `content`, and `chunk_type`.

This notification is fire-and-forget. If the queue is full, the notification
is dropped. Eidos will eventually process the chunk through its own polling
cycle regardless.

---

## 7. Critical Invariants

These invariants are non-negotiable. Any code change that violates them is a
correctness bug, not a design trade-off.

### 7.1 NO PRUNING

Engram **never** prunes, expires, archives, or deletes chunks. The moment of
ingestion is the worst possible time for retention decisions -- the system has
no topic context, no usage history, no consolidation graph. Pruning is owned
entirely by Oneiros, which operates with full retrospective context.

### 7.2 NO BLOCKING

Engram never blocks on slow downstream operations.

- If the Eidos queue is full: drop the queue entry silently. Eidos enrichment
  is optional and eventually consistent.
- If the embedding server is slow: log a warning but still complete the write.
  If embedding fails entirely, write the chunk without an embedding and let
  the re-embed worker backfill later.
- If the database write fails transiently: buffer the event to a local
  Write-Ahead Log (WAL) file and replay on recovery. Never drop a chunk.

### 7.3 NO TOPIC CLASSIFICATION

Topic assignment is Kairos's responsibility. Engram does not cluster, label,
or assign topic nodes. It does not read the `topic_nodes` or `chunk_topics`
tables. Attempting to classify topics at ingestion time would both slow down
the pipeline and produce inferior results compared to Kairos's retrospective
clustering.

### 7.4 CONTENT HASH DEDUPLICATION

The tuple `(content_hash, session_id)` is the deduplication key. If the same
content appears in the same session (e.g., due to stream replay or retry),
Engram writes it exactly once. This makes stream replay idempotent.

### 7.5 INSERT-ONLY WRITES

Engram issues only `INSERT` statements against the `chunks` table. It never
issues `UPDATE` or `DELETE`. Other sidecars own the mutable columns
(`validated`, `archived`, `somatic_register`, etc.) and are solely responsible
for mutating them.

The sole exception is the `validate_chunk` and `abandon_chunk` helper
methods, which update `provisional` and `confidence` on reasoning chunks.
These are called by Kairos through Engram's API, not by Engram's own
ingestion pipeline.

---

## 8. Model-Agnostic Ingestion

Engram uses framework adapters to normalize diverse event stream formats into
`NormalizedChunk` objects. This abstraction allows the same Engram core to
ingest events from different agent frameworks without modification.

### 8.1 Adapter Protocol

```python
class FrameworkAdapter(Protocol):
    """
    Converts a framework-specific raw event dict into zero or more
    NormalizedChunks. Returns None if the event should be skipped
    (e.g., keepalive pings, progress bars, framework-internal noise).
    """

    def normalize(self, raw_event: dict) -> Optional[NormalizedChunk]:
        ...

    @property
    def framework_name(self) -> str:
        """Identifier written to chunks.source_framework."""
        ...
```

### 8.2 Provided Adapters

| Adapter                | Framework             | Notes                                       |
|------------------------|-----------------------|---------------------------------------------|
| `ClaudeCodeAdapter`    | Claude Code (JSONL)   | Primary adapter; maps hook payloads directly |
| `LangGraphAdapter`     | LangGraph             | Maps node/edge events to chunk types         |
| `OpenAICompatAdapter`  | OpenAI-compatible API | Handles streaming SSE and batch responses    |

### 8.3 Adapter Selection

The adapter is selected at startup based on the `source_framework` field in
the configuration or the first event's structure. Once selected, the adapter
is fixed for the lifetime of the Engram process.

```python
def select_adapter(config: dict, sample_event: Optional[dict] = None) -> FrameworkAdapter:
    framework = config.get("source_framework", "auto")
    if framework == "auto" and sample_event:
        if "hook_type" in sample_event:
            return ClaudeCodeAdapter()
        if "langgraph_node" in sample_event:
            return LangGraphAdapter()
        return OpenAICompatAdapter()
    return ADAPTER_REGISTRY[framework]()
```

---

## 9. Operational Semantics

### 9.1 Idempotency

The deduplication key is `(content_hash, session_id)`. Replaying the same
stream segment produces identical database state. This property is essential
for crash recovery: the WAL replay mechanism depends on idempotent writes.

Note: `content_hash` is a SHA-256 digest of the extracted content string
(post-truncation), not the raw event JSON. Two events with different metadata
but identical content are considered duplicates within the same session.

### 9.2 Ordering

Engram processes events in stream emission order. The `turn_index` field
reflects this order and is written as-is from the stream event. Engram does
not reorder, batch, or coalesce events.

Within a single turn, multiple chunks may be emitted (e.g., a TOOL_IN
followed by a TOOL_OUT). These are written as separate rows with the same
`turn_index`, distinguished by `chunk_type` and `created_at`.

### 9.3 Failure Handling

```
Failure scenario          Response
──────────────────────    ──────────────────────────────────────────────
Embedding server down     Write chunk with embedding = NULL.
                          Re-embed worker backfills asynchronously.

Embedding server slow     Log warning if > 100ms. Continue normally.
(>100ms)                  Do not retry; accept the latency hit.

Database write fails      Append serialized event to local WAL file.
(transient)               Replay WAL on next successful DB connection.
                          NEVER drop a chunk.

Database write fails      Log critical error. Continue WAL buffering.
(persistent)              Alert operator via health check endpoint.

Eidos queue full          Drop the queue entry silently.
                          Log at DEBUG level. Eidos will catch up.

Malformed event JSON      Log warning with raw line content.
                          Skip event. Do not crash the process.

Unknown hook_type         Pass to adapter. If adapter returns None,
                          skip silently. Otherwise ingest normally.
```

### 9.4 Write-Ahead Log (WAL)

The WAL is a simple append-only JSONL file at a configurable path (default:
`/data/engram_wal/`). Each line is a serialized `StreamEvent` that failed to
persist.

WAL replay is triggered:
- On Engram process startup (replay any events from previous crash).
- Periodically (every 30 seconds) if the WAL file is non-empty.
- On successful database reconnection after a transient failure.

WAL replay is idempotent by construction: the content hash dedup mechanism
ensures that events already persisted are not duplicated.

```python
class WriteAheadLog:
    def __init__(self, wal_dir: str):
        self.wal_path = Path(wal_dir) / "engram.wal"

    async def append(self, event: StreamEvent) -> None:
        """Append a failed event to the WAL. Non-blocking, best-effort."""
        async with aiofiles.open(self.wal_path, "a") as f:
            await f.write(json.dumps(event.raw) + "\n")

    async def replay(self, ingest_fn: Callable) -> int:
        """Replay all WAL entries. Returns count of successfully replayed events."""
        if not self.wal_path.exists():
            return 0

        replayed = 0
        temp_path = self.wal_path.with_suffix(".replaying")
        self.wal_path.rename(temp_path)  # atomic rename prevents double-replay

        async with aiofiles.open(temp_path, "r") as f:
            async for line in f:
                try:
                    event = StreamEvent.from_raw(json.loads(line))
                    await ingest_fn(event)
                    replayed += 1
                except Exception as e:
                    log.error(f"WAL replay failed for line: {e}")

        temp_path.unlink()
        return replayed
```

---

## 10. Contracts

### 10.1 Tables Written

| Table                | Operation   | Condition                               |
|----------------------|-------------|-----------------------------------------|
| `chunks`             | INSERT only | Every non-empty, non-duplicate event    |
| `skill_invocations`  | INSERT only | Tool events matching known skill names  |

### 10.2 Queues Written

| Queue              | Transport          | Payload                                 |
|--------------------|--------------------|-----------------------------------------|
| `mc:eidos_queue`   | Redis LPUSH        | `{chunk_id, content[:800], chunk_type}` |

### 10.3 Tables Read

Engram reads no tables during normal ingestion. The sole input is the JSONL
event stream.

Deduplication may optionally query the `chunks` table for existing
`content_hash` values, or maintain a session-scoped in-memory set (preferred
for performance).

### 10.4 Cross-References

- **09-contracts Section 2.1**: `NormalizedChunk` schema definition.
- **09-contracts Section 2.2**: `ChunkType` enumeration and semantics.
- **02-eidos**: Eidos queue consumption contract.
- **05-oneiros**: Pruning and archival ownership.
- **04-kairos**: Provisional chunk validation/abandonment lifecycle.

---

## 11. Embedding Details

### 11.1 Model Selection

The default embedding model is `nomic-embed-text`, served locally via Ollama.
This model produces 768-dimensional vectors with strong performance on
retrieval benchmarks while maintaining sub-100ms inference on modest hardware.

| Property          | Value                                  |
|-------------------|----------------------------------------|
| Model             | `nomic-embed-text`                     |
| Dimensions        | 768                                    |
| Max input tokens  | 8192                                   |
| Similarity metric | Cosine similarity                      |
| Index type        | HNSW (`m=16, ef_construction=64`)      |
| Served via        | Ollama (`/api/embeddings` endpoint)    |

### 11.2 Embedding Client

```python
class EmbeddingClient:
    """Wraps Ollama (or any compatible) embedding API."""

    def __init__(self, endpoint: str, model: str, timeout_s: float = 5.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=timeout_s)

    async def embed(self, text: str) -> list[float]:
        t0 = monotonic()
        response = await self._client.post(
            f"{self.endpoint}/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        response.raise_for_status()
        embedding = response.json()["embedding"]

        latency_ms = (monotonic() - t0) * 1000
        if latency_ms > 100:
            log.warning(f"Embedding latency exceeded target: {latency_ms:.1f}ms")

        return embedding

    async def close(self):
        await self._client.aclose()
```

### 11.3 Embedding Failure Recovery

If the embedding server is unavailable or returns an error, Engram writes the
chunk with `embedding = NULL`. A background re-embed worker periodically
scans for chunks missing embeddings and backfills them:

```sql
SELECT chunk_id, content FROM chunks
WHERE master_session_id = $1
  AND embedding IS NULL
  AND NOT archived
ORDER BY created_at
LIMIT 100;
```

This ensures that temporary embedding server outages do not cause data loss.

---

## 12. Evaluation Metrics

| Metric                       | Target      | Measurement method                           |
|------------------------------|-------------|----------------------------------------------|
| Embedding latency p50        | < 50 ms     | Per-chunk, measured at `ingest()` boundary   |
| Embedding latency p95        | < 100 ms    | Including DB write                            |
| Stream lag                   | < 1 second  | Time from event emission to store visibility  |
| Chunk write success rate     | > 99.9%     | Including WAL replay within 60 seconds        |
| Dedup accuracy               | 100%        | No duplicate `(content_hash, session_id)` pairs |
| WAL replay success rate      | > 99.9%     | All WAL entries eventually persisted           |
| Embedding backfill latency   | < 5 minutes | Time for NULL embeddings to be backfilled     |

### 12.1 Health Check Endpoint

Engram exposes a `/health` endpoint that reports:

```json
{
  "status": "healthy",
  "embedding_server": "connected",
  "db": "connected",
  "wal_pending": 0,
  "chunks_ingested_last_60s": 42,
  "avg_latency_ms_last_60s": 38.2,
  "eidos_queue_depth": 7
}
```

Unhealthy conditions:
- `wal_pending > 100`: Database connectivity issue, chunks buffered.
- `embedding_server: "disconnected"`: Chunks being written without embeddings.
- `avg_latency_ms > 200`: Embedding server under load; consider scaling.

---

## 13. Configuration Reference

```yaml
engram:
  enabled: true
  latency_target_ms: 100
  embedding_model: nomic-embed-text
  embedding_dimensions: 768
  batch_size: 1                        # single-chunk for real-time guarantee
  wal_path: /data/engram_wal/
  wal_replay_interval_s: 30
  eidos_queue_size: 1000
  content_hash_algorithm: sha256

  # Types to ingest (others are silently dropped)
  ingestion_types:
    - human
    - model
    - tool_in
    - tool_out
    - reasoning

  # Priority weights (initial confidence per chunk type)
  priority_weights:
    HUMAN: 1.00
    MODEL: 0.85
    TOOL_OUT: 0.80
    TOOL_IN: 0.65
    REASONING: 0.40
    SYSTEM: 0.30

  # Content truncation limits (chars)
  truncation:
    tool_output_max_chars: 4000
    tool_input_max_chars: 2000

  # Re-embed worker (backfills NULL embeddings)
  reembed:
    enabled: true
    batch_size: 100
    poll_interval_s: 60
```

---

## 14. Worker Architecture

Engram runs as two cooperating processes, both managed by the container
supervisor (e.g., Supervisor, systemd, or container orchestrator).

### 14.1 Stream Ingestion Worker

The primary worker. Reads from the JSONL event stream (via Redis queue
`mc:ingest_queue` in the current deployment) and processes events one at a
time in strict order.

```
Agent Runtime --> [hook payload] --> Redis mc:ingest_queue --> Engram Worker
                                                                  |
                                                           [embed + write]
                                                                  |
                                                           PostgreSQL chunks
```

Startup sequence:
1. Load configuration from `atlas.yaml`.
2. Initialize embedding client; health-check the embedding server (retry up
   to 30 times with 2-second backoff).
3. Initialize database connection pool.
4. Replay any pending WAL entries.
5. Begin consuming from the ingest queue.

Shutdown sequence:
1. Stop accepting new events from the queue.
2. Drain in-flight events (allow current `ingest()` call to complete).
3. Flush any buffered WAL entries.
4. Close embedding client and database connections.

### 14.2 Re-Embed Worker

A secondary worker that backfills embeddings for chunks stored with
`embedding = NULL` (due to embedding server outages). Polls periodically,
processes in batches of 100, and uses the same `EmbeddingClient`.

This worker is idempotent and safe to restart at any time.

---

## 15. Interaction with Other Sidecars

### 15.1 Engram -> Eidos

After writing a chunk, Engram pushes a notification to the Eidos queue. Eidos
uses this notification to prioritize somatic tagging of HUMAN and REASONING
chunks. The notification contains only the `chunk_id`, a truncated content
preview (800 chars), `chunk_type`, and `turn_index`.

If the Eidos queue is full (capacity: 1000 entries), the notification is
dropped silently. Eidos has its own polling mechanism as a fallback.

### 15.2 Engram -> Kairos (Indirect)

Engram does not communicate with Kairos directly. Kairos reads from the
`chunks` table on its own schedule. Engram's responsibility ends at writing
the chunk row.

### 15.3 Engram -> Anamnesis (Indirect)

Anamnesis queries the `chunks` table for similarity search. Engram's
responsibility is to ensure chunks are available and searchable (i.e., have
non-NULL embeddings) as quickly as possible.

### 15.4 Kairos -> Engram (Validation API)

Kairos calls Engram's `validate_chunk()` and `abandon_chunk()` methods to
update the status of provisional reasoning chunks. These are the only UPDATE
operations Engram performs, and they are initiated externally, not by the
ingestion pipeline.

```python
async def validate_chunk(chunk_id: UUID) -> None:
    """Promote a provisional chunk: provisional=False, validated=True, confidence=0.85."""
    await db.execute(
        "UPDATE chunks SET provisional=FALSE, validated=TRUE, confidence=0.85 "
        "WHERE chunk_id=$1",
        str(chunk_id),
    )

async def abandon_chunk(chunk_id: UUID) -> None:
    """Mark a provisional chunk as abandoned: confidence=0.10, validated=False."""
    await db.execute(
        "UPDATE chunks SET confidence=0.10, validated=FALSE WHERE chunk_id=$1",
        str(chunk_id),
    )
```

---

## 16. Security and Data Handling

- **No filtering of sensitive content**: Engram is a faithful recorder. It does
  not redact, mask, or filter content. Sensitive data handling is the
  responsibility of the agent runtime (pre-stream) and access control layers
  (post-store).
- **Raw event preservation**: The complete original event payload is stored in
  `raw_event` (JSONB). This enables forensic analysis and re-processing
  without stream replay.
- **No external network calls**: Engram communicates only with the local
  embedding server (Ollama) and the local PostgreSQL instance. It makes no
  calls to external APIs or services.

---

## 17. Future Considerations

These are documented non-goals for the current version that may be revisited:

- **Batch embedding**: Currently processes one chunk at a time for latency
  guarantees. If throughput becomes a bottleneck, micro-batching (2-4 chunks)
  with a 50ms collection window could be considered without violating the
  100ms p95 target.
- **Streaming embeddings**: Some embedding models support incremental
  embedding of streaming tokens. This could reduce perceived latency for long
  model responses but adds substantial complexity.
- **Content-aware dedup**: The current dedup mechanism is exact-match
  (SHA-256). Near-duplicate detection (e.g., for slightly reformulated
  retries) is a Kairos responsibility.
- **Adaptive priority weights**: The current weights are static. A feedback
  loop from Anamnesis retrieval hit rates could inform dynamic weight
  adjustment, but this crosses Engram's simplicity boundary.
