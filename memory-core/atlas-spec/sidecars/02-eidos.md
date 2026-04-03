# Eidos — Signal Classifier

> Greek: *eidos* (εἶδος) — form, essence; the intelligible structure behind appearances.

---

## 1. Identity Card

| Field | Value |
|---|---|
| **Name** | Eidos |
| **Tier** | Real-Time sidecar (async, local, near-real-time) |
| **Role** | Metadata enrichment — classifying what each chunk IS |
| **Trigger** | Asynchronous wakeup from database-backed queue populated immediately after Engram chunk writes |
| **Execution model** | Headless single-turn enrichment worker |
| **Latency** | Target <200ms per chunk exclusive of queue wait; never blocks Engram commit path |
| **Runtime locality** | Local-only process on the same host / trusted private network segment as Postgres and Engram |
| **Model** | Fast classification model (3B) or rule-based heuristic |
| **Optional** | Yes. System functions without Eidos; retrieval quality improves with it. |
| **Cognitive analogy** | Amygdala — rapid appraisal of incoming signals |
---

### 2. Purpose

Eidos is the local near-real-time enrichment sidecar that classifies newly stored
chunks after Engram commits them to the database.

Where Engram captures content and embeddings, Eidos adds *structured meaning*:
what kind of signal is this? what affective register does it carry? is this a
correction event? does it validate or abandon a provisional reasoning chunk?

Eidos is intentionally **not** in the synchronous ingestion path. Engram writes
first. That durable write then causes Eidos work to be enqueued through a
database-mediated trigger path. Eidos wakes asynchronously, reads the target
chunk plus bounded temporal context, computes enrichment fields, and updates the
existing row in place.

Eidos answers three questions about every chunk:

1. **What category of knowledge is this?** (signal classification)
2. **What does this moment feel like?** (somatic affective tagging)
3. **Does this chunk carry a special lifecycle signal?** (correction, validation,
   abandonment, high-priority human utterance)

Eidos is optional — the system degrades gracefully without it. When Eidos is
disabled or unavailable, chunks retain their raw content and embeddings but lack
structured metadata. Anamnesis still retrieves by vector similarity, but cannot
filter or weight by signal class or somatic register.

With Eidos active, retrieval quality improves because Anamnesis can:
- Filter candidates by signal class before ranking
- Weight somatic-aligned memories during affectively loaded sessions
- Prefer correction events when confusion scoring is elevated

The architectural boundary is strict: Eidos enriches existing chunk records in
near-real-time, but does not own topic clustering or topic graph construction.
Those reflective semantic-structure responsibilities belong downstream.

---

## 3. Inputs

### 3.1 Database-Triggered Enrichment Queue

Engram writes the chunk record first. Immediately after a successful chunk
insert, a database-mediated trigger path enqueues the chunk for Eidos
classification.

The preferred pattern is:

1. Engram inserts the chunk row into `chunks`
2. An `AFTER INSERT` database trigger enqueues `chunk_id` into an Eidos work
   queue table
3. The trigger may also emit a lightweight local wakeup signal (for example,
   `NOTIFY`) to reduce polling latency
4. Eidos consumes pending queue rows asynchronously and enriches the associated
   chunk record

This design preserves three important properties:

- **Durability first** — the chunk exists before enrichment begins
- **Engram isolation** — classification never blocks the write path
- **Replayability** — missed or failed enrichments can be re-run from durable
  queue state

Each queue entry contains:

| Field | Type | Description |
|---|---|---|
| `chunk_id` | UUID | Reference to the stored chunk |
| `session_id` | UUID | Current session identifier |
| `turn_index` | int | Turn index of the target chunk |
| `enqueued_at` | timestamp | Time the entry was placed on the queue |
| `attempts` | int | Retry count |
| `status` | enum | pending, processing, done, failed, dropped |

Eidos then retrieves the canonical chunk content and surrounding turns from the
database rather than trusting a transient in-memory payload as the source of
truth.

### 3.1.1 Local Near-Real-Time Operating Posture

Eidos is designed for **local near-real-time enrichment**, not hard real-time
execution.

This means:

- Eidos runs as a headless worker on the same machine, or on a tightly coupled
  private runtime adjacent to Postgres and Engram
- Wakeup latency should typically be sub-second
- Per-chunk enrichment should usually complete within a few hundred milliseconds
- Temporary backlog is acceptable; missing metadata is not fatal
- The system remains correct when enrichment is delayed, retried, or skipped

"Near-real-time" here means that classification happens quickly enough to
benefit same-session retrieval and downstream sidecars, while still remaining
fully asynchronous and non-blocking.


### 3.2 Context Window

Eidos receives a sliding window of **2 turns before and 2 turns after** the
target chunk. This context is critical for:

- Disambiguation: "Yes" means nothing without the question it answers
- Correction detection: a human correction only makes sense relative to the
  agent utterance it corrects
- Affective register: tone shifts are relational, not absolute

When fewer than 2 turns exist in either direction (e.g., session start, or the
chunk is the most recent turn), Eidos operates on whatever context is available.
Missing context is never fabricated.

---

## 4. Processing Pipeline

Eidos processes each queued chunk as a **headless single-turn enrichment task**.
For each target chunk, it loads the stored row plus a bounded temporal context
window, computes structured enrichment, and writes only its owned columns back
to the database.

Each stage is independent — failure in one stage does not prevent execution of
subsequent stages. All writes are idempotent.

### 4.1 Signal Classification

Classify the chunk into exactly one primary signal class:

| Signal Class | Description | Examples |
|---|---|---|
| `EPISODIC` | Event-specific, temporally anchored | "We deployed the auth fix on Tuesday" |
| `SEMANTIC` | Factual, declarative knowledge | "The API uses JWT with RS256" |
| `EMOTIONAL` | Affective expression or relational signal | "This is really frustrating" |
| `ENVIRONMENTAL` | Context about the working environment | "I'm using Node 18 on Ubuntu" |
| `PROCEDURAL` | How-to, workflow, or process knowledge | "To deploy, run make release then tag" |

Classification rules (in priority order):

1. If the chunk contains explicit emotional language or relational markers →
   `EMOTIONAL`
2. If the chunk describes a step-by-step process, command sequence, or workflow →
   `PROCEDURAL`
3. If the chunk describes the user's environment, tooling, or system config →
   `ENVIRONMENTAL`
4. If the chunk is anchored to a specific event, time, or session occurrence →
   `EPISODIC`
5. Default → `SEMANTIC`

A chunk may exhibit traits of multiple classes. Eidos assigns the **single best
fit** based on the priority above. The signal class is a retrieval filter, not a
taxonomy — precision matters more than nuance.

### 4.2 Somatic Affective Tagging

Somatic tags capture the affective register of a moment as perceived by a
**neutral third-party observer**. This framing is critical: Eidos does not
interpret the user's internal state or the agent's "feelings." It describes what
an outside observer reading the transcript would perceive.

#### System Prompt for Somatic Tagging

```
You are a neutral third-party observer reading a transcript excerpt.
Characterize the affective register of this moment using ONLY the provided
dimensions. Do not interpret intent. Do not infer hidden emotions. Describe
what an outside observer would perceive from the text alone.
```

#### Somatic Dimensions

| Dimension | Values | Description |
|---|---|---|
| **Valence** | `positive` · `neutral` · `negative` | Overall hedonic tone |
| **Energy** | `high` · `moderate` · `low` | Activation level / intensity |
| **Register** | `engaging` · `tedious` · `tense` · `playful` · `frustrated` · `collaborative` · `uncertain` · `resolved` | Qualitative character of the interaction |
| **Relational** | `aligned` · `misaligned` · `correcting` · `exploring` | Relational posture between participants |

#### Tagging Rules

- Each dimension is tagged independently.
- A chunk receives exactly one value per dimension.
- When the signal is ambiguous, prefer `neutral` / `moderate` / `uncertain` /
  `exploring` — the conservative defaults.
- TOOL_OUTPUT chunks with no conversational content receive:
  `neutral` / `low` / `engaging` / `aligned` (the "background operation"
  default profile).
- REASONING chunks (from extended thinking blocks) use the same pipeline but
  are expected to skew toward `uncertain` / `exploring` due to their
  provisional nature.

### 4.3 Correction Event Detection

A correction event occurs when a participant revises, contradicts, or overrides
a prior statement. Eidos detects two subtypes:

| Subtype | Signal | Example |
|---|---|---|
| **Human correction** | Human explicitly corrects agent output | "No, the endpoint is /v2/users, not /v1/users" |
| **Self-correction** | Agent revises its own prior statement | "Actually, I was wrong about the encoding — it uses UTF-16" |

Detection heuristics:

- Negation + reference to prior content ("no", "not", "actually", "wait",
  "correction")
- Contradiction between current chunk and a chunk within the context window
- Explicit correction markers ("let me correct", "I misspoke", "that's wrong")

When a correction event is detected, Eidos writes:

```json
{
  "correction_detected": true,
  "correction_type": "human" | "self",
  "corrected_chunk_id": "<UUID of the chunk being corrected, if identifiable>",
  "correction_confidence": 0.0-1.0
}
```

Correction events are high-value signals for Kairos (knowledge graph updates)
and Anamnesis (preferring corrected knowledge over stale chunks).

### 4.4 Provisional Validation / Abandonment Detection

Provisional chunks (sourced from REASONING blocks) enter the system at
confidence 0.4 and must be validated within K=5 turns. Eidos assists this
lifecycle by detecting explicit validation or abandonment signals:

| Signal | Trigger | Effect |
|---|---|---|
| **Validation** | Human confirms, uses, or builds upon provisional content | Chunk promoted: confidence → 0.85+ |
| **Abandonment** | Human rejects, ignores, or contradicts provisional content | Chunk marked abandoned (not deleted — negative knowledge preserved) |
| **Implicit validation** | Agent's provisional reasoning is reflected in successful tool output | Moderate confidence bump: +0.2 |

Eidos writes validation signals to the queue for Engram to apply to the
provisional chunk's confidence score. Eidos does not modify confidence directly.

These lifecycle signals are also asynchronous: Eidos proposes them from local
classification context, while the owning sidecar applies the authoritative
confidence change.

### 4.5 High-Priority Human Utterance Identification

Not all human turns carry equal weight. Eidos flags utterances that should
receive elevated retrieval priority:

| Flag | Criteria |
|---|---|
| `preference_statement` | Human states a preference, convention, or rule ("I always use...", "Never do X") |
| `identity_signal` | Human reveals something about themselves, their role, or their context |
| `emotional_peak` | High-energy emotional expression (frustration, delight, concern) |
| `explicit_memory_request` | Human asks the agent to remember something ("Remember that...", "Keep in mind...") |
| `correction` | (Inherited from 4.3 — correction events are always high-priority) |

A chunk may carry zero or more flags. Flags are stored as a text array on the
chunk record.

### 4.6 Skill Invocation Outcome Enrichment

When a chunk is associated with a skill invocation (via `skill_invocations`
foreign key), Eidos enriches the invocation record with:

- **outcome_class**: `success` | `partial` | `failure` | `abandoned`
- **outcome_signals**: free-text summary of what the observer perceives as the
  outcome (e.g., "user confirmed result was correct", "tool returned error,
  user tried alternative approach")
- **affective_outcome**: the somatic register of the turns immediately
  following the invocation

This data feeds Praxis, which uses outcome patterns to optimize procedural
memory and detect poorly matched skills.

---

## 5. Outputs

## 5. Outputs

All Eidos outputs are **asynchronous UPDATEs to existing records**. Eidos never
creates new rows in the `chunks` table and never participates in Engram's
synchronous commit path.

### 5.1 Chunk Metadata Update

```sql
UPDATE chunks SET
  signal_class       = :signal_class,
  somatic_valence    = :valence,
  somatic_energy     = :energy,
  somatic_register   = :register,
  somatic_relational = :relational,
  priority_flags     = :flags,
  correction_meta    = :correction_json,
  eidos_classified_at = NOW()
WHERE chunk_id = :chunk_id
  AND eidos_classified_at IS NULL;  -- idempotency guard
```

The `eidos_classified_at IS NULL` guard ensures that reprocessing a queue entry
(e.g., after a crash recovery) does not overwrite an existing classification.
To force reclassification, a separate reprocessing pathway must explicitly clear
the timestamp.

### 5.2 Skill Invocation Enrichment

```sql
UPDATE skill_invocations SET
  outcome_class     = :outcome_class,
  outcome_signals   = :outcome_signals,
  affective_outcome = :affective_outcome,
  eidos_enriched_at = NOW()
WHERE invocation_id = :invocation_id
  AND eidos_enriched_at IS NULL;
```

### 5.3 Provisional Lifecycle Signals

Validation and abandonment signals are written to a lightweight signal queue
that Engram consumes to update chunk confidence:

```json
{
  "signal": "validate" | "abandon" | "implicit_validate",
  "target_chunk_id": "<UUID>",
  "confidence_delta": 0.45 | -1.0 | 0.2,
  "evidence_chunk_id": "<UUID of the chunk that triggered this signal>"
}
```

---

## 6. Contracts

### 6.1 Data Ownership

Eidos owns the following columns on the `chunks` table. No other sidecar writes
to these columns:

| Column | Type | Description |
|---|---|---|
| `signal_class` | enum | EPISODIC, SEMANTIC, EMOTIONAL, ENVIRONMENTAL, PROCEDURAL |
| `somatic_valence` | enum | positive, neutral, negative |
| `somatic_energy` | enum | high, moderate, low |
| `somatic_register` | enum | engaging, tedious, tense, playful, frustrated, collaborative, uncertain, resolved |
| `somatic_relational` | enum | aligned, misaligned, correcting, exploring |
| `priority_flags` | text[] | Array of high-priority flags |
| `correction_meta` | jsonb | Correction event metadata |
| `eidos_classified_at` | timestamp | Classification timestamp (idempotency marker) |

Eidos also owns enrichment columns on `skill_invocations`:

| Column | Type | Description |
|---|---|---|
| `outcome_class` | enum | success, partial, failure, abandoned |
| `outcome_signals` | text | Observer summary of outcome |
| `affective_outcome` | text | Somatic register post-invocation |
| `eidos_enriched_at` | timestamp | Enrichment timestamp |

### 6.2 Read Contracts

| Source | Purpose |
|---|---|
| Eidos classification queue | Primary input |
| `chunks` table (read) | Context retrieval for surrounding turns |
| `skill_invocations` table (read) | Linking chunks to skill invocations |

### 6.3 Write Contracts

| Target | Operation | Scope |
|---|---|---|
| `chunks` | UPDATE | Owned columns only |
| `skill_invocations` | UPDATE | Owned columns only |
| Provisional signal queue | INSERT | Validation/abandonment signals |

### 6.4 Downstream Consumers

| Consumer | What it reads | Why |
|---|---|---|
| **Anamnesis** | signal_class, somatic_* | Filtering and weighting during retrieval |
| **Kairos** | signal_class, correction_meta | Knowledge graph updates, correction propagation |
| **Praxis** | skill invocation enrichment | Procedural memory optimization |
| **Psyche** | somatic_* aggregates | Self-model narrative construction |
| **Augur** | signal_class patterns | Behavioral sequence analysis |

---

## 7. Operational Semantics

### 7.1 Async Queue Processing

Eidos consumes from a durable queue populated immediately after Engram chunk
writes through a database-triggered enqueue path. Optional low-latency wakeup
signals may be emitted alongside the durable queue write, but the queue itself
is the authoritative source of pending work.

Processing characteristics:

- **Near-real-time, not synchronous**: Eidos usually classifies shortly after
  chunk insert, but never before the insert is durable
- **Out-of-order delivery**: Queue entries may arrive or be processed out of
  chronological order. Each classification is self-contained given its context
  window. Writes are idempotent.
- **At-least-once delivery**: Duplicate processing is safe due to the
  `eidos_classified_at IS NULL` guard.
- **Durable replay**: If Eidos is offline, queue rows accumulate and can be
  processed later without data loss in the source chunk table.
- **Backpressure**: If queue depth exceeds the configured threshold, Eidos may
  drop or defer the stalest unprocessed entries according to policy. Dropped
  chunks remain valid but unclassified.

  ### 7.1.1 Trigger Semantics

The database trigger does not perform classification itself.

Its job is limited to signaling that a newly durable chunk is ready for
enrichment. This usually means inserting into an `eidos_queue` table and
optionally emitting a local wakeup signal.

This separation is intentional:

- database transactions remain short
- classification latency does not contaminate the write path
- enrichment can be retried independently
- crash recovery is straightforward because the work queue is durable

### 7.2 Failure Modes

| Failure | Behavior |
|---|---|
| Classification model unavailable | Fall back to rule-based heuristics |
| Rule-based heuristic inconclusive | Leave `signal_class` as null |
| Somatic tagging fails | Leave all `somatic_*` columns null |
| Queue timeout exceeded | Drop entry, log warning |
| Database write fails | Retry once, then drop. Chunk remains unclassified. |
| Context turns unavailable | Classify with reduced context. Never fabricate. |
| Database trigger wakeup signal lost | Queue row remains durable; Eidos picks it up on next poll cycle. |
| Queue table unavailable at insert time | Chunk write remains authoritative; fallback recovery job can discover unclassified chunks later. |

Eidos failures are **never fatal**. The system continues without enrichment.
Unclassified chunks are valid — they simply lack metadata that would improve
retrieval precision.



### 7.3 Idempotency

All writes check `eidos_classified_at IS NULL` (or `eidos_enriched_at IS NULL`
for skill invocations). This means:

- Replaying the queue after a crash is safe.
- Reclassification requires an explicit `SET eidos_classified_at = NULL` first.
- No partial writes: if any column in a classification update fails, the entire
  UPDATE is rolled back and `eidos_classified_at` remains null.

---

## 8. Why Somatic Tags Matter

Semantic similarity search alone cannot distinguish between two chunks that
discuss the same topic but carry radically different affective registers. A
chunk about "the deployment process" could be a calm procedural explanation or a
frustrated recounting of a failed deployment. The embedding vectors may be
nearly identical. The somatic tags are not.

Somatic tags enable:

### 8.1 Contrastive Retrieval

Anamnesis can match or deliberately contrast affective states across sessions.
If the current session carries a `frustrated` / `high-energy` register,
Anamnesis can retrieve prior moments with similar affect — surfacing relevant
context that pure semantic similarity would miss.

### 8.2 Amplification Under Affective Load

During emotionally loaded sessions, Anamnesis can weight somatic-aligned
memories higher. This is not empathy simulation — it is retrieval optimization.
A frustrated user benefits more from recalling how a similar frustration was
previously resolved than from a semantically similar but affectively neutral
chunk.

### 8.3 Praxis Signal

Skills that consistently generate `tedious` / `misaligned` somatic tags in
their outcome enrichment may be poorly matched to the user's working style.
Praxis uses this signal to recommend procedural adjustments.

### 8.4 Psyche Narrative

Psyche aggregates somatic tags across sessions to construct the agent's
self-narrative. Persistent patterns (e.g., sessions with this user tend toward
`collaborative` / `high-energy`) inform the soul.md document and session
orientation.

---

## 9. Model Strategy

### 9.1 Rule-Based Heuristic (Default)

The default classification strategy uses pattern matching and keyword heuristics.
This is fast (<10ms), deterministic, and requires no external model:

- **Signal classification**: Keyword lists, regex patterns, source-type
  heuristics (e.g., TOOL_OUTPUT chunks default to PROCEDURAL or ENVIRONMENTAL)
- **Somatic tagging**: Sentiment lexicon, punctuation analysis, turn-length
  heuristics, negation detection
- **Correction detection**: Negation + prior-reference patterns
- **Provisional validation**: Confirmation language patterns

Rule-based heuristics achieve ~70% accuracy on signal classification and ~65%
on somatic tagging relative to human judgment. This is sufficient for
meaningful retrieval improvement.

### 9.2 LLM Classification (Optional)

When `somatic_model: llm_classify` is configured, Eidos sends a structured
prompt to a fast model (e.g., Claude Haiku, or a local 3B model). The prompt
requests JSON output matching the exact schema of Eidos dimensions.

LLM classification achieves ~85-90% accuracy but adds latency (50-150ms) and
cost. It is recommended for users who want higher-fidelity somatic tagging and
are willing to accept the tradeoff.

### 9.3 Hybrid Strategy

A practical middle ground: use rule-based heuristics for signal classification
(which is relatively easy) and LLM classification for somatic tagging (which
benefits more from language understanding). This keeps average latency under
100ms while improving somatic accuracy.

---

## 10. Evaluation Metrics

| Metric | Target | Measurement |
|---|---|---|
| Classification latency p50 | <100ms | Timer on full pipeline per chunk |
| Classification latency p99 | <200ms | Must not block or degrade Engram |
| Somatic tag coverage | >90% of episodic chunks | % of EPISODIC chunks with all 4 somatic dimensions populated |
| Signal class accuracy | >80% vs human judgment | Periodic sample review |
| Somatic tag accuracy | >75% vs human judgment | Periodic sample review |
| Correction detection precision | >85% | False positives are more harmful than false negatives |
| Correction detection recall | >70% | Missing some corrections is acceptable |
| Queue depth p99 | <50 entries | Sustained backlog indicates capacity issue |
| Queue drop rate | <1% | Acceptable loss rate for non-critical enrichment |

---

## 11. Configuration

```yaml
eidos:
  # Master enable/disable switch
  enabled: true

  # Classification strategy: rule_based | llm_classify | hybrid
  somatic_model: rule_based

  # Model for LLM classification (ignored if somatic_model is rule_based)
  # Accepts any Anthropic model identifier or local model endpoint
  classification_model: null  # uses heuristics by default

  # Queue processing
  queue_timeout_ms: 5000       # max age of a queue entry before it is dropped
  queue_batch_size: 10         # process up to N entries per cycle
  queue_poll_interval_ms: 100  # polling interval when queue is empty

  # Context window
  context_window_turns: 2      # turns before/after for classification context

  # Retry behavior
  max_retries: 1               # retries on transient DB failure
  retry_delay_ms: 200          # delay between retries

  # Correction detection
  correction_confidence_threshold: 0.6  # minimum confidence to flag a correction

  # Priority flags
  priority_flags_enabled: true  # enable high-priority utterance detection

  # Skill enrichment
  skill_enrichment_enabled: true  # enable skill invocation outcome tagging
```

---

## 12. Sequence Diagram

```
Engram                    Queue                   Eidos                    DB
  │                         │                       │                      │
  │  write chunk            │                       │                      │
  │────────────────────────────────────────────────────────────────────────>│
  │                         │                       │                      │
  │  enqueue(chunk_id,      │                       │                      │
  │    content, context)    │                       │                      │
  │────────────────────────>│                       │                      │
  │                         │                       │                      │
  │                         │  poll / consume        │                      │
  │                         │<──────────────────────│                      │
  │                         │                       │                      │
  │                         │  entry                │                      │
  │                         │──────────────────────>│                      │
  │                         │                       │                      │
  │                         │                       │  classify signal     │
  │                         │                       │  tag somatic         │
  │                         │                       │  detect corrections  │
  │                         │                       │  check provisional   │
  │                         │                       │  flag priority       │
  │                         │                       │  enrich skill        │
  │                         │                       │                      │
  │                         │                       │  UPDATE chunks       │
  │                         │                       │─────────────────────>│
  │                         │                       │                      │
  │                         │                       │  UPDATE skill_inv    │
  │                         │                       │─────────────────────>│
  │                         │                       │                      │
```

---

## 13. Edge Cases

### 13.1 Empty or Trivial Chunks

Chunks with minimal content (e.g., "ok", "yes", single-word tool outputs) are
still classified. They typically receive:
- Signal class: EPISODIC (if conversational) or ENVIRONMENTAL (if tool output)
- Somatic profile: neutral / low / engaging / aligned
- No correction or priority flags

### 13.2 Very Long Chunks

Chunks exceeding 2000 tokens are truncated to the first and last 500 tokens
for classification purposes. The middle section is replaced with
`[... truncated for classification ...]`. This preserves opening context and
concluding signals while keeping classification latency bounded.

### 13.3 Multi-Language Content

Eidos does not perform language detection. Classification heuristics are
English-optimized. LLM classification handles multilingual content naturally.
For non-English users, `llm_classify` or `hybrid` mode is recommended.

### 13.4 Rapid Correction Chains

When multiple corrections occur in sequence (e.g., human corrects agent, agent
self-corrects, human corrects again), each correction event is tagged
independently. Kairos is responsible for resolving the chain into a final
authoritative state.

### 13.5 Eidos Disabled Mid-Session

If Eidos is disabled during a session, previously classified chunks retain
their metadata. New chunks arrive without classification. Anamnesis handles
mixed classified/unclassified result sets gracefully — unclassified chunks are
treated as neutral-weight candidates.

---

## 14. Relationship to Other Sidecars

| Sidecar | Relationship |
|---|---|
| **Engram** | Upstream producer. Engram writes durable chunk rows first; a database-triggered enqueue path wakes Eidos asynchronously. Eidos never blocks Engram's commit path. |
| **Anamnesis** | Primary consumer. Uses signal_class and somatic tags to filter and weight retrieval candidates. |
| **Kairos** | Consumes signal_class for knowledge graph construction. Consumes correction_meta for graph updates. |
| **Praxis** | Consumes skill invocation enrichment for procedural optimization. |
| **Psyche** | Reads somatic tag aggregates for self-narrative construction. |
| **Oneiros** | Does not directly consume Eidos output, but benefits indirectly — consolidated beliefs inherit signal metadata. |
| **Augur** | Reads signal_class patterns for behavioral sequence analysis and prediction. |

## 15. Architectural Note

Eidos is best understood as a **local, headless, single-turn enrichment worker**
that operates off a **database-triggered durable queue**.

It does not own raw ingestion.
It does not own topic graph construction.
It does not block the live cognitive stream.

Its job is narrower and more disciplined: once a chunk is durably stored, Eidos
classifies that chunk in near-real-time using bounded local context and writes
structured enrichment back onto the existing record.