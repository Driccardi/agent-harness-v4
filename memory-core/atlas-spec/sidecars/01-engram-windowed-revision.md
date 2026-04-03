
# 01 — Engram: Stream Embedder

> **Named for**: the engram, the hypothetical means by which memory traces are
> stored as physical changes in the brain.

---

## 1. Identity Card

| Field             | Value                                                                 |
|-------------------|-----------------------------------------------------------------------|
| Name              | Engram                                                                |
| Tier              | Real-Time                                                             |
| Role              | Hippocampal encoder — durably record raw events, emit recall-worthy chunks |
| Trigger           | Continuous; reads JSONL stream as events are emitted                  |
| Latency target    | < 100 ms per emitted chunk (p95, including DB write)                  |
| Model requirement | Embedding model only (`nomic-embed-text`, 768 dimensions)             |
| Stateless         | Yes — no in-memory state survives process restart                     |
| Owns (write)      | `raw_events`, `chunks`, `skill_invocations`                           |
| Depends on (read) | JSONL event stream from agent runtime                                 |

---

## 2. Purpose

Engram is the fast-lane encoder of the Atlas Cognitive Substrate. It reads the
agent's JSONL event stream continuously, durably records the raw event log, and
emits semantically useful chunks into PostgreSQL within milliseconds. It is the
hippocampal analog: capture first, understand later, stay fast.

Engram is deliberately simple. It does not classify topics, does not build
graph structure, does not consolidate beliefs, and does not prune. But it is no
longer required to treat every individual JSONL row as an independent memory
chunk. The stream contains conversational content, tool actions, tool results,
and runtime exhaust. Engram's job is to preserve all raw signal while emitting
chunks that are actually worth recall.

Its guarantees are therefore twofold:

1. **If something appeared in the stream, it is durably preserved in the raw event log.**
2. **If something is memory-worthy, it becomes retrievable by vector similarity within seconds.**

Other sidecars depend on Engram's output:

- **Eidos** enriches chunks with somatic tags and signal classification.
- **Kairos** clusters chunks into topic nodes.
- **Oneiros** consolidates and prunes aged chunks.
- **Anamnesis** retrieves chunks for injection into context.

Engram's relationship to these consumers is fire-and-forget. It writes and
moves on. It never waits for downstream processing.

---

## 3. Inputs

### 3.1 JSONL Event Stream

Engram consumes a newline-delimited JSON stream emitted by the agent runtime.
Each line is a self-contained event object. The stream is the sole ingestion
input; Engram performs no semantic database reads during normal operation.

Events in the stream include:

| Event kind            | Source                  | Typical content                               |
|-----------------------|-------------------------|-----------------------------------------------|
| Human utterance       | `UserPromptSubmit` hook | User's natural-language message               |
| Model response        | `ModelResponse` hook    | Assistant's generated text                    |
| Reasoning block       | `ModelResponse` hook    | Extended thinking / chain-of-thought content  |
| Tool input            | `PreToolUse` hook       | Tool name + input parameters (JSON)           |
| Tool output           | `PostToolUse` hook      | Tool execution result (JSON, truncated)       |
| System message        | Various                 | System prompts, configuration directives      |
| Progress / telemetry  | Various                 | Hook progress, queue progress, timing, etc.   |
| Snapshot / bookkeeping| Various                 | File-history snapshot, queue operation, etc.  |

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
  "user_message":       "...",
  "model_content":      "...",
  "reasoning_content":  "...",
  "tool_name":          "Read",
  "tool_input":         { ... },
  "tool_output":        { ... },
  "system_content":     "...",
  "event_type":         "progress"
}
```

### 3.3 Windowed Episode Chunking

Engram is **row-driven for durability** but **windowed for chunk formation**.

A single JSONL row may be:
- emitted as a standalone chunk,
- merged with nearby rows into a composite episodic chunk, or
- preserved only in `raw_events` and suppressed from semantic chunking.

To do this, Engram maintains a small rolling tail buffer of recent rows
(default: 10). The buffer is used only for local chunking heuristics.

Typical uses of the tail buffer:

- Pair an assistant tool call with the corresponding tool result
- Merge repeated `Read` / `Glob` / `Bash` bursts into one discovery episode
- Identify assistant conclusions that should flush an open buffered episode
- Dismiss operational exhaust (`progress`, `queue-operation`, snapshots)
- Prevent trivial rows (`ok`, `done`, empty thinking) from becoming first-class memories

### 3.4 Chunk Emission Modes

Every raw event is written to `raw_events`. Chunk emission then chooses one of
four modes:

| Mode | Description | Example |
|------|-------------|---------|
| `STANDALONE` | Emit this row as its own chunk | User request, assistant conclusion |
| `TOOL_EPISODE` | Merge tool call + tool result (+ optional interpretation) | `Read` + file contents + conclusion |
| `DISCOVERY_BURST` | Merge short search/read bursts into one episode | `Glob`/`Read` burst ending in a finding |
| `SUPPRESSED` | Preserve raw row only; do not emit semantic chunk | Progress update, queue operation, empty thinking |

---

## 4. Signal Taxonomy and Priority Weights

Engram classifies each emitted chunk into exactly one `ChunkType` and assigns an
initial confidence weight. This weight represents the a priori informational
value of the signal class — not a judgment about any specific chunk's content.

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

When a candidate chunk contains multiple signal types (for example, a merged
tool episode), classification precedence is:

```
HUMAN > REASONING > MODEL > SYSTEM > TOOL_OUT > TOOL_IN
```

This preserves the existing rule that human intent dominates and that reasoning
blocks retain provisional semantics when present.

### 4.2 Reasoning Chunks: Provisional Semantics

Chunks with `chunk_type = REASONING` are always written with `provisional = true`
and `confidence = 0.40`. This reflects the epistemological status of
chain-of-thought output: it is exploratory, may contain dead ends, and may be
abandoned before the model settles on a final response.

However, Engram should not emit reasoning chunks mechanically. Empty thinking,
procedural throat-clearing, or extremely low-information reasoning should be
suppressed. Only reasoning with substantive semantic content is emitted.

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
  [3] Write raw event to `raw_events` (durable append-only log)
       |
       v
  [4] Update rolling tail buffer (default: last 10 rows)
       |
       v
  [5] Apply chunking heuristics:
       - suppress noise
       - emit standalone chunk
       - merge into tool episode / discovery burst
       |
       v
  [6] Classify ChunkType + assign confidence
       |
       v
  [7] Extract content string, apply truncation limits
       |
       v
  [8] Compute content_hash (SHA-256) for deduplication
       |
       v
  [9] Check dedup: content_hash + session_id already exists? --> skip
       |
       v
  [10] Generate embedding via local model (<100ms target)
       |
       v
  [11] Write NormalizedChunk to PostgreSQL (INSERT only)
       |
       v
  [12] Database trigger enqueues chunk_id for Eidos enrichment
       |
       v
  [13] Record skill invocation if tool episode matches known skill
```

### 5.2 Chunking Heuristics

Engram uses cheap local heuristics only. It does not do semantic interpretation
beyond what is necessary to form a better chunk.

#### Suppress by default
The following are preserved in `raw_events` but usually not emitted as chunks:

- `progress`
- `queue-operation`
- `file-history-snapshot`
- `last-prompt`
- system timing / bookkeeping rows
- empty or trivial `thinking`
- trivial tool results (`done`, `ok`, empty-success markers)

#### Standalone by default
Emit as standalone chunks:

- human natural-language turns
- human corrections and preferences
- assistant conclusions / synthesized findings
- rich self-contained tool outputs with durable factual value

#### Composite by default
Merge into one emitted chunk when local context indicates a single episode:

- assistant tool use + corresponding tool result
- repeated search/read bursts in the same local objective
- tool-use / result / assistant-interpretation triplets

#### Flush rules
Buffered composite chunks are flushed when:

- an assistant conclusion appears,
- a new distinct human request begins,
- the buffer reaches the configured tail limit,
- a timeout or turn boundary indicates the episode has ended

### 5.3 Pseudocode

```python
async def ingest(raw_line: str) -> Optional[UUID]:
    t0 = monotonic()

    # Step 1: Parse + normalize
    event = StreamEvent.from_raw(json.loads(raw_line))
    normalized = adapter.normalize(event.raw)
    if normalized is None:
        await db.insert_raw_event(event.raw)   # preserve raw event even if suppressed
        return None

    # Step 2: Always preserve raw event first
    await db.insert_raw_event(event.raw)

    # Step 3: Update tail buffer and decide chunking action
    tail_buffer.append(normalized)
    action = chunker.evaluate(tail_buffer)

    if action.kind == "SUPPRESSED":
        return None

    candidate = chunker.materialize(action, tail_buffer)
    chunk_type = classify_chunk(candidate)
    content = extract_content(candidate, chunk_type)

    if not content.strip():
        return None

    # Step 4: Dedup
    content_hash = sha256(content.encode()).hexdigest()
    if await dedup_exists(content_hash, candidate.session_id):
        return None

    provisional = (chunk_type == ChunkType.REASONING)
    confidence = PRIORITY_WEIGHTS[chunk_type]

    context_pressure = (
        candidate.context_tokens / MAX_CONTEXT_TOKENS
        if candidate.context_tokens else None
    )

    # Step 5: Embed
    try:
        embedding = await embedder.embed(content)
    except EmbeddingError:
        embedding = None

    # Step 6: Persist chunk
    try:
        chunk_id = await db.insert_chunk(
            master_session_id = candidate.master_session_id,
            session_id        = candidate.session_id,
            turn_index        = candidate.turn_index,
            source_framework  = candidate.source_framework,
            chunk_type        = chunk_type.value,
            content           = content,
            content_hash      = content_hash,
            raw_event_refs    = candidate.raw_event_refs,
            confidence        = confidence,
            provisional       = provisional,
            embedding         = embedding,
            input_modality    = candidate.input_modality,
            context_pressure  = context_pressure,
            chunk_mode        = action.kind,
        )
    except TransientDBError as e:
        await wal.append(event)
        log.error(f"DB write failed, buffered to WAL: {e}")
        return None

    # Step 7: Record skill invocation if applicable
    if action.kind in ("TOOL_EPISODE", "DISCOVERY_BURST"):
        await maybe_record_skill_invocation(candidate, chunk_id)

    elapsed_ms = (monotonic() - t0) * 1000
    metrics.observe("engram.ingest_latency_ms", elapsed_ms)
    return chunk_id
```

### 5.4 Content Extraction and Truncation

Different chunk types require different extraction strategies:

```python
def extract_content(candidate: ChunkCandidate, chunk_type: ChunkType) -> str:
    match candidate.mode:
        case "STANDALONE":
            return candidate.primary_content
        case "TOOL_EPISODE":
            return render_tool_episode(candidate)
        case "DISCOVERY_BURST":
            return render_discovery_burst(candidate)

    match chunk_type:
        case ChunkType.HUMAN:
            return candidate.human_content or ""
        case ChunkType.REASONING:
            return candidate.reasoning_content or ""
        case ChunkType.MODEL:
            return candidate.model_content or ""
        case ChunkType.SYSTEM:
            return candidate.system_content or ""
        case ChunkType.TOOL_OUT:
            return json.dumps(candidate.tool_output)[:4000]
        case ChunkType.TOOL_IN:
            payload = {"tool": candidate.tool_name, "input": candidate.tool_input}
            return json.dumps(payload)[:2000]
```

Truncation limits are applied to the embedding input only. The complete raw
event payloads are always preserved in `raw_events`, and chunk source references
point back to those raw rows.

### 5.5 Input Modality Metadata

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

### 6.1 `raw_events` Table (Authoritative Raw Log)

Every successfully parsed stream row is written to `raw_events`, even if it is
later suppressed from semantic chunking.

Suggested columns:

| Column              | Notes |
|---------------------|-------|
| `raw_event_id`      | DB default `gen_random_uuid()` |
| `master_session_id` | From stream event |
| `session_id`        | From stream event |
| `turn_index`        | From stream event |
| `source_framework`  | Adapter-provided |
| `event_type`        | Raw / framework-specific event kind |
| `payload`           | Full original JSON payload |
| `created_at`        | Insert timestamp |

This table is the forensic and replay substrate. It is not the primary retrieval
surface for associative memory.

### 6.2 `chunks` Table (Primary Semantic Output)

Every successfully emitted chunk produces exactly one row in the `chunks` table.
Engram performs **INSERT only** against this table.

Key columns written by Engram:

| Column              | Set by Engram?  | Notes                                     |
|---------------------|-----------------|-------------------------------------------|
| `chunk_id`          | DB default      | `gen_random_uuid()`                       |
| `master_session_id` | Yes             | From candidate                            |
| `session_id`        | Yes             | From candidate                            |
| `turn_index`        | Yes             | From candidate                            |
| `source_framework`  | Yes             | Adapter-provided                          |
| `chunk_type`        | Yes             | Classified by Engram                      |
| `content`           | Yes             | Extracted and possibly truncated          |
| `raw_event_refs`    | Yes             | References to one or more `raw_events` rows |
| `confidence`        | Yes             | Initial weight from priority table        |
| `provisional`       | Yes             | `true` for REASONING, `false` otherwise   |
| `embedding`         | Yes             | 768-dim vector, or NULL on embed failure  |
| `input_modality`    | Yes (HUMAN)     | Only populated for HUMAN chunks           |
| `context_pressure`  | Yes             | Computed from `context_tokens`            |
| `chunk_mode`        | Yes             | `STANDALONE`, `TOOL_EPISODE`, `DISCOVERY_BURST` |

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

### 6.3 Eidos Wakeup Path

After Engram inserts a chunk row, a database-mediated trigger path enqueues the
chunk for Eidos enrichment.

Preferred pattern:

1. Engram inserts into `chunks`
2. An `AFTER INSERT` trigger inserts a durable row into `eidos_queue`
3. The trigger may also emit a lightweight wakeup signal (for example, `NOTIFY`)
4. Eidos consumes pending queue rows asynchronously

This keeps Engram out of direct queue-management logic and preserves the rule
that chunk durability comes first.

### 6.4 `skill_invocations` Table

When a tool episode or discovery burst matches a known skill pattern, Engram
writes a record to `skill_invocations`. This table feeds the Praxis procedural
memory optimizer.

---

## 7. Critical Invariants

### 7.1 NO PRUNING

Engram **never** prunes, expires, archives, or deletes chunks. The moment of
ingestion is the worst possible time for retention decisions. Pruning is owned
entirely by Oneiros.

### 7.2 NO BLOCKING

Engram never blocks on slow downstream operations.

- If the embedding server is slow: log a warning but still complete the write.
- If embedding fails entirely: write the chunk without an embedding and let the
  re-embed worker backfill later.
- If the database write fails transiently: buffer the event to a local
  Write-Ahead Log (WAL) file and replay on recovery. Never drop a raw event.

### 7.3 NO TOPIC CLASSIFICATION

Topic assignment is Kairos's responsibility. Engram does not cluster, label, or
assign topic nodes.

### 7.4 RAW-EVENT FIRST

Every stream row is preserved in `raw_events` before any chunking decision is
finalized. Suppression from semantic chunking is allowed; suppression from raw
durability is not.

### 7.5 INSERT-ONLY CHUNK WRITES

Engram issues only `INSERT` statements against the `chunks` table. It never
issues `UPDATE` or `DELETE`. Other sidecars own mutable columns.

### 7.6 WINDOWED HEURISTICS ONLY

Engram may use a small rolling tail buffer and cheap deterministic heuristics to
form better chunks, but it must not drift into slow semantic reasoning,
retrospective clustering, or LLM-mediated interpretation. That belongs to later
sidecars.

---

## 8. Model-Agnostic Ingestion

Engram uses framework adapters to normalize diverse event stream formats into
internal event candidates. This abstraction allows the same Engram core to
ingest events from different agent frameworks without modification.

### 8.1 Adapter Protocol

```python
class FrameworkAdapter(Protocol):
    """
    Converts a framework-specific raw event dict into zero or more
    normalized event candidates. Returns None if the event should be
    skipped for semantic chunking, though the raw event is still preserved.
    """

    def normalize(self, raw_event: dict) -> Optional[NormalizedEvent]:
        ...

    @property
    def framework_name(self) -> str:
        ...
```

### 8.2 Provided Adapters

| Adapter                | Framework             | Notes                                       |
|------------------------|-----------------------|---------------------------------------------|
| `ClaudeCodeAdapter`    | Claude Code (JSONL)   | Primary adapter; maps hook payloads directly |
| `LangGraphAdapter`     | LangGraph             | Maps node/edge events to event candidates    |
| `OpenAICompatAdapter`  | OpenAI-compatible API | Handles streaming SSE and batch responses    |

### 8.3 Adapter Selection

The adapter is selected at startup based on the `source_framework` field in
the configuration or the first event's structure. Once selected, the adapter
is fixed for the lifetime of the Engram process.

---

## 9. Operational Semantics

### 9.1 Idempotency

The deduplication key for emitted chunks is `(content_hash, session_id)`.
Replaying the same stream segment produces identical semantic chunk state.

Raw-event durability may instead use a framework event ID when available, or a
hash of the full raw line if necessary.

### 9.2 Ordering

Engram processes events in stream emission order. The `turn_index` field
reflects this order and is written as-is from the stream event. Engram does
not reorder the stream globally, but it may temporarily buffer nearby rows in
order to form a composite chunk.

Within a single turn, multiple rows may contribute to one emitted chunk.

### 9.3 Failure Handling

```
Failure scenario          Response
──────────────────────    ──────────────────────────────────────────────
Embedding server down     Write chunk with embedding = NULL.
                          Re-embed worker backfills asynchronously.

Embedding server slow     Log warning if > 100ms. Continue normally.

Database write fails      Append serialized raw event to local WAL file.
(transient)               Replay WAL on recovery. NEVER drop raw event.

Database write fails      Log critical error. Continue WAL buffering.
(persistent)              Alert operator via health check endpoint.

Malformed event JSON      Log warning with raw line content.
                          Skip semantic processing. Preserve line if possible.

Unknown hook_type         Pass to adapter. If adapter returns None,
                          preserve raw event and skip semantic chunking.
```

### 9.4 Write-Ahead Log (WAL)

The WAL is a simple append-only JSONL file at a configurable path. Each line is
a serialized raw event that failed to persist.

WAL replay is triggered:
- On Engram process startup
- Periodically if the WAL file is non-empty
- On successful database reconnection after a transient failure

---

## 10. Contracts

### 10.1 Tables Written

| Table                | Operation   | Condition                               |
|----------------------|-------------|-----------------------------------------|
| `raw_events`         | INSERT only | Every parsed stream row                 |
| `chunks`             | INSERT only | Every non-empty, non-duplicate emitted chunk |
| `skill_invocations`  | INSERT only | Tool episodes matching known skills     |

### 10.2 Queue / Trigger Boundary

| Mechanism           | Owner      | Purpose                                 |
|--------------------|------------|-----------------------------------------|
| `AFTER INSERT` trigger on `chunks` | Database | Enqueue durable Eidos work           |
| `eidos_queue`      | Database/Eidos | Pending chunk enrichment work       |
| optional `NOTIFY`  | Database   | Low-latency wakeup for Eidos            |

### 10.3 Tables Read

Engram reads no semantic tables during normal ingestion. The sole primary input
is the JSONL event stream. Deduplication may query `chunks` or use a
session-scoped in-memory set.

### 10.4 Cross-References

- **02-eidos**: Eidos queue consumption contract
- **04-kairos**: Provisional lifecycle and clustering
- **05-oneiros**: Pruning and archival ownership

---

## 11. Embedding Details

### 11.1 Model Selection

The default embedding model is `nomic-embed-text`, served locally via Ollama.

| Property          | Value                                  |
|-------------------|----------------------------------------|
| Model             | `nomic-embed-text`                     |
| Dimensions        | 768                                    |
| Max input tokens  | 8192                                   |
| Similarity metric | Cosine similarity                      |
| Index type        | HNSW (`m=16, ef_construction=64`)      |
| Served via        | Ollama (`/api/embeddings` endpoint)    |

### 11.2 Embedding Failure Recovery

If the embedding server is unavailable or returns an error, Engram writes the
chunk with `embedding = NULL`. A background re-embed worker periodically scans
for chunks missing embeddings and backfills them.

---

## 12. Evaluation Metrics

| Metric                       | Target      | Measurement method                           |
|------------------------------|-------------|----------------------------------------------|
| Chunk emit latency p50       | < 50 ms     | Per emitted chunk                            |
| Chunk emit latency p95       | < 100 ms    | Including DB write                           |
| Raw event write success rate | > 99.99%    | Raw durability is the highest-priority path  |
| Stream lag                   | < 1 second  | Time from event emission to chunk visibility |
| Suppression precision        | > 80%       | Sampled review of suppressed vs useful rows  |
| Composite chunk usefulness   | > 70%       | Human-evaluated retrieval usefulness         |
| Dedup accuracy               | 100%        | No duplicate `(content_hash, session_id)` pairs |
| WAL replay success rate      | > 99.9%     | All WAL entries eventually persisted         |
| Embedding backfill latency   | < 5 minutes | Time for NULL embeddings to be backfilled    |

### 12.1 Health Check Endpoint

Engram exposes a `/health` endpoint that reports:

```json
{
  "status": "healthy",
  "embedding_server": "connected",
  "db": "connected",
  "wal_pending": 0,
  "raw_events_last_60s": 282,
  "chunks_emitted_last_60s": 104,
  "avg_latency_ms_last_60s": 38.2
}
```

---

## 13. Configuration Reference

```yaml
engram:
  enabled: true
  latency_target_ms: 100
  embedding_model: nomic-embed-text
  embedding_dimensions: 768
  wal_path: /data/engram_wal/
  wal_replay_interval_s: 30
  content_hash_algorithm: sha256

  # Tail-buffer chunking
  tail_buffer_rows: 10
  trivial_content_min_chars: 8
  suppress_event_types:
    - progress
    - queue-operation
    - file-history-snapshot
    - last-prompt

  # Emission behavior
  emit_reasoning_min_chars: 80
  merge_tool_episodes: true
  merge_discovery_bursts: true
  flush_on_new_human_turn: true

  # Priority weights
  priority_weights:
    HUMAN: 1.00
    MODEL: 0.85
    TOOL_OUT: 0.80
    TOOL_IN: 0.65
    REASONING: 0.40
    SYSTEM: 0.30

  # Truncation
  truncation:
    tool_output_max_chars: 4000
    tool_input_max_chars: 2000

  # Re-embed worker
  reembed:
    enabled: true
    batch_size: 100
    poll_interval_s: 60
```

---

## 14. Worker Architecture

Engram runs as two cooperating processes.

### 14.1 Stream Ingestion Worker

The primary worker reads from the JSONL event stream and processes rows one at a
time in strict order:

```
Agent Runtime --> JSONL stream --> Engram Worker
                                  |        |
                                  |   raw_events INSERT
                                  |        |
                                  |   tail buffer + heuristics
                                  |        |
                                  |   embed + chunks INSERT
                                  |        |
                                  --> PostgreSQL
```

Startup sequence:
1. Load configuration
2. Initialize embedding client
3. Initialize database connection pool
4. Replay any pending WAL entries
5. Begin consuming from the stream

### 14.2 Re-Embed Worker

A secondary worker backfills embeddings for chunks stored with `embedding = NULL`.

---

## 15. Interaction with Other Sidecars

### 15.1 Engram -> Eidos

After Engram inserts a chunk, the database trigger path enqueues Eidos work.
Engram itself does not push directly to an application queue.

### 15.2 Engram -> Kairos (Indirect)

Engram does not communicate with Kairos directly. Kairos reads from `chunks` on
its own schedule.

### 15.3 Engram -> Anamnesis (Indirect)

Anamnesis queries the `chunks` table for similarity search. Engram's
responsibility is to ensure chunks are available and searchable as quickly as
possible.

### 15.4 Kairos -> Engram (Validation API)

Kairos may call Engram-owned helper APIs to update provisional reasoning chunks.
These are external lifecycle actions, not part of the ingestion path.

---

## 16. Security and Data Handling

- **Raw event preservation**: The complete original event payload is stored in
  `raw_events`.
- **No external network calls**: Engram communicates only with the local
  embedding server and the local PostgreSQL instance.
- **Chunk suppression is not data loss**: suppressed rows remain available in
  `raw_events` for forensics, replay, or future re-chunking.

---

## 17. Future Considerations

- **Adaptive chunking heuristics**: learned suppression / merge policies based on
  retrieval usefulness data
- **Re-chunk from raw log**: rebuild `chunks` from `raw_events` if heuristics evolve
- **Micro-batching**: small batch embedding if throughput becomes the bottleneck
- **Near-duplicate detection**: better duplicate handling beyond exact hash match
- **Multi-modal episode rendering**: richer chunk rendering when image/audio
  events are present

---

*End of specification.*
