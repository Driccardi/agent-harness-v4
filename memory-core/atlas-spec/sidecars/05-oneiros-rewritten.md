
# 05 — Oneiros: Consolidation, Reprocessing, and Semantic Learnings

> *Oneiros — Greek god of dreams, son of Hypnos, shaper of meaningful*
> *visions from waking residue.*

---

## 1  Identity Card

| Field                | Value                                                                 |
|----------------------|-----------------------------------------------------------------------|
| **Name**             | Oneiros                                                               |
| **Tier**             | Reflective                                                            |
| **Role**             | Semantic generalization, topic reprocessing, productive forgetting, drift correction |
| **Trigger**          | Topic corpus exceeds threshold; daily reprocessing cron; manual invocation; contradiction or freshness trigger |
| **Latency**          | Unbounded (may run minutes to hours)                                  |
| **Model**            | Largest context window available (128k+ preferred for full topic read) |
| **Human-in-the-loop**| Recommended for first runs and structural revisions; autonomous under confidence and policy thresholds |
| **Primary Output**   | Companion semantic learning layer preferred over raw episodic recall   |
| **Deletion Authority** | None by default; archival and deletion are downstream policy decisions, not mandatory consolidation outcomes |

---

## 2  Purpose

Oneiros performs the machine equivalent of REM consolidation: reading
accumulated episodic fragments, extracting generalized meaning, and
writing that meaning into a companion semantic layer that the system can
prefer during retrieval.

Oneiros is **not** primarily a deletion engine. Its first responsibility
is to derive durable learnings from the episodic corpus. Its second is to
periodically reconsider those learnings as broader context accumulates,
beliefs drift, contradictions emerge, and retrieval behavior reveals that
the semantic layer is incomplete.

### 2.1  The Key Distinction — Generalization, Not Summarization

Oneiros does **NOT** summarize. Summarization preserves event structure
with reduced detail. Oneiros **generalizes** — extracting patterns,
beliefs, constraints, preferences, and open questions while discarding
most temporal scaffolding.

| Mode                        | Example output                                                                                       |
|-----------------------------|------------------------------------------------------------------------------------------------------|
| **Summarization (Kairos)**  | "On March 14th, three sessions explored JWT implementation..."                                       |
| **Generalization (Oneiros)**| "For this system: JWT validation failures are almost always clock skew, not algorithmic. RS256 with 30-second tolerance is the established pattern." |

Oneiros output is a **generalized learning statement** — durable,
directional, actionable. It captures what was *learned*, not what
*happened*.

### 2.2  Layering, Not Immediate Erasure

The system should learn from the corpus before it forgets the corpus.

After Oneiros runs, the episodic corpus remains available. Source chunks
may be marked as **Oneiros-processed** and **demoted in retrieval weight**,
but they are not deleted by default and need not be archived immediately.
Anamnesis should generally prefer the semantic learning layer first, then
fall back to the episodic corpus when provenance, nuance, contradiction
resolution, or edge-case recall requires it.

### 2.3  Reprocessing Is First-Class

Consolidation is provisional at the **topic level**, not final. A topic
processed today may need to be re-opened tomorrow because:

- new episodic evidence appears
- neighboring topics emerge and change the interpretation
- contradictory evidence accumulates
- a belief marked `volatile` has likely drifted
- retrieval repeatedly falls back to episodic chunks instead of the
  semantic layer

Archived or demoted episodic material remains evidence for future
re-consolidation.

---

## 3  Inputs

| Input                        | Source                          | Required |
|------------------------------|---------------------------------|----------|
| Full episodic corpus         | `chunks` table, chronological   | Yes      |
| Topic node metadata          | `topic_nodes` table             | Yes      |
| Topic summaries              | `topic_summaries` table         | No       |
| Corpus size signal           | Kairos (trigger notification)   | No       |
| Contradiction / correction signals | Kairos, Eidos, graph edges | No       |
| Retrieval fallback signals   | Anamnesis / retrieval logs      | No       |
| Prior semantic learnings     | `semantic_learnings`            | No       |
| Retention policy overrides   | Configuration / human operator  | No       |
| Verification results         | Bounded verifier / external check task | No |

All chunks for the target topic are retrieved in chronological order so
that the consolidation model can observe how understanding evolved over
time — even though the output discards most temporal structure.

---

## 4  Processing — The Consolidation Run

### 4.1  Step-by-Step

1. **Select target topic** — Identify a topic scheduled for first-pass
   consolidation or reprocessing.
2. **Retrieve episodic evidence** — Fetch all relevant chunks for the
   target topic, sorted by `created_at` ascending. Include demoted or
   archived-support chunks if policy says they remain part of the
   evidence base.
3. **Retrieve prior learnings** — Fetch active and superseded semantic
   learnings for the topic so the model can compare old understanding to
   new evidence.
4. **Assemble corpus** — Build the full evidence bundle: episodic
   corpus, prior learnings, contradiction markers, freshness metadata,
   and any retrieval-fallback hints.
5. **Consolidate or re-consolidate** — Run the consolidation prompt
   against the largest available model. The prompt instructs the model
   to:
   - Preserve **meaning** and **direction**; discard most **specifics**
     and **temporal anchors**
   - Write in present tense as standing learnings
   - Capture constraints and negative knowledge explicitly
   - Flag uncertainty honestly
   - Preserve open questions
   - Compare old beliefs to new evidence
   - Revise, split, merge, retire, or reaffirm prior learnings as needed
6. **Optional bounded verification** — For volatile, stale, or disputed
   beliefs, Oneiros may invoke a narrowly scoped verification step
   rather than broad autonomous research. Verification exists to confirm
   or challenge specific learnings, not to invent new project scope.
7. **Parse output** — Structure the raw model output into versioned
   `SemanticLearning` records, each with confidence, freshness
   sensitivity, status, and evidence basis.
8. **Write learnings** — Insert new learning rows and supersede or mark
   stale prior ones as required.
9. **Mark source chunks** — Mark the source episodic chunks as
   `oneiros_processed = true` and optionally reduce their retrieval
   weight. Do **not** delete by default.
10. **Schedule future reconsideration** — Set the topic's next
    `topic_reconsider_after` timestamp based on freshness sensitivity,
    contradiction level, and retrieval behavior.
11. **Report** — Return a consolidation report. Optionally notify a
    human reviewer.

### 4.2  Atomicity Guarantee

Learning writes, topic metadata updates, and source-chunk processing
markers execute within a single transaction. If any part fails, no new
learnings are activated and no chunk retrieval tiers are modified. The
topic remains in its prior state and will re-trigger on the next cycle.

### 4.3  Consolidation Prompt Guidelines

The system prompt for the consolidation model must enforce:

- **Present tense only.** "The API requires Bearer tokens" not "We
  discovered that the API required Bearer tokens."
- **No unnecessary dates, no session narration.** Temporal context is
  evidence scaffolding, not the target representation.
- **Explicit negatives.** "HMAC-SHA256 is NOT suitable here because..."
  is more valuable than omitting the failed approach.
- **Confidence calibration.** "Probably true based on two observations"
  is better than false certainty.
- **Open questions preserved.** If the episodic record shows unresolved
  investigation, the consolidated output must flag it.
- **Belief comparison.** If prior learnings exist, explicitly state
  whether each one is reaffirmed, revised, split, merged, downgraded,
  marked stale, or retired.

### 4.4  Verification Scope

Oneiros may perform bounded verification when consolidating **volatile**,
**stale**, or **disputed** beliefs. Verification is allowed to:

- confirm a claim against a current official source
- check whether a public API / package / product behavior has drifted
- resolve a narrow contradiction
- attach external provenance to a learning

Verification is **not** allowed to:

- roam freely across unrelated topics
- expand project scope autonomously
- silently replace strong internal evidence with weak outside claims
- erase prior learning history

The output of verification is evidence that adjusts confidence and
status. It does not bypass the normal learning write path.

---

## 5  SemanticLearning Schema

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class LearningType(Enum):
    FACTUAL       = "factual"
    CONSTRAINT    = "constraint"
    PREFERENCE    = "preference"
    PATTERN       = "pattern"
    OPEN_QUESTION = "open_question"


class LearningStatus(Enum):
    ACTIVE      = "active"
    SUPERSEDED  = "superseded"
    STALE       = "stale"
    RETIRED     = "retired"
    DISPUTED    = "disputed"


@dataclass
class SemanticLearning:
    learning_id: str
    topic_node_id: str
    learning_version: int
    supersedes_learning_id: Optional[str]
    content: str
    confidence: float
    learning_type: LearningType
    status: LearningStatus
    basis: str
    freshness_sensitivity: str     # stable | moderate | volatile
    replaces_chunk_count: int
    verification_status: str       # unverified | internally_supported | externally_supported | contradicted
    last_evidence_at: datetime
    created_at: datetime
    reprocessed_at: Optional[datetime]
```

### 5.1  Field Semantics

| Field                   | Notes                                                                 |
|-------------------------|-----------------------------------------------------------------------|
| `content`               | Self-contained declarative statement. Must be interpretable without any other context. |
| `confidence`            | 0.5 = weak signal, 0.7 = reasonable, 0.9+ = well-established.        |
| `basis`                 | Brief evidence summary; enough for audit and operator understanding. |
| `freshness_sensitivity` | `stable`: unlikely to change. `moderate`: may shift with new evidence. `volatile`: likely to drift. |
| `status`                | Current authority state of the learning.                             |
| `verification_status`   | Whether the belief has been externally checked or contradicted.      |
| `replaces_chunk_count`  | Tracks compression / demotion ratio per learning.                    |

### 5.2  Topic-Level Reprocessing Metadata

Each topic should also track:

```python
@dataclass
class TopicReprocessingState:
    topic_node_id: str
    last_oneiros_run_at: datetime
    oneiros_run_count: int
    topic_drift_score: float
    topic_reconsider_after: datetime
    reprocessing_reason: Optional[str]
```

---

## 6  Retention and Retrieval Policy

### 6.1  Retrieval Tiers

Oneiros changes the retrieval model by adding a **companion semantic
layer** and demoting source episodic material rather than erasing it.

| Tier | Description | Default Retrieval Preference |
|------|-------------|------------------------------|
| `semantic_active` | Active semantic learnings | Highest |
| `episodic_live` | Unprocessed or recently relevant episodic chunks | Medium |
| `episodic_demoted` | Oneiros-processed chunks, still searchable | Low |
| `episodic_archived` | Archived chunks retained for provenance / fallback | Lowest |

Anamnesis should generally prefer:

1. active semantic learnings
2. procedural notes and validated constraints
3. live episodic corpus
4. demoted / archived episodic fallback only when needed

### 6.2  Chunk Demotion Instead of Default Deletion

After a Oneiros run, source chunks are typically marked:

- `oneiros_processed = true`
- `retrieval_tier = episodic_demoted`
- `retrieval_weight_multiplier = configured demotion weight`

This is the default post-consolidation behavior.

### 6.3  Archival and Deletion

Archival and deletion are **optional downstream retention policies**, not
mandatory results of consolidation.

Recommended lifecycle:

1. **Live** — chunk is active, searchable, and weighted normally
2. **Demoted** — chunk has been processed by Oneiros and receives lower
   retrieval weight
3. **Archived** — chunk is removed from standard retrieval but retained
   for provenance and reprocessing evidence
4. **Deleted** — only if explicit retention policy, age, and audit
   requirements allow it

Deletion should be rare, delayed, and policy-controlled.

### 6.4  Productive Forgetting by Weighting

Productive forgetting does not require immediate erasure. In Atlas, the
preferred default is:

- remember the learning strongly
- remember the episode weakly
- preserve the episode as evidence

This mirrors biological consolidation more faithfully than a hard cutover.

---

## 7  Reprocessing Policy

### 7.1  Why Reprocessing Exists

A topic consolidated once is not guaranteed to be correctly understood
forever. Reprocessing exists to correct for:

- broader context that emerged later
- drift in volatile domains
- contradiction or correction pressure
- semantic learnings that are too generic, too coarse, or prematurely certain
- retrieval behavior showing that episodic fallback is still doing the real work

### 7.2  Heuristics That Trigger Reprocessing

A topic becomes a reprocessing candidate if **any** of the following are
true:

#### Time-Based Heuristics
- `freshness_sensitivity = volatile` and `last_oneiros_run_at` older than **1 day**
- `freshness_sensitivity = moderate` and older than **7 days**
- `freshness_sensitivity = stable` and older than **30 days**

#### Evidence-Based Heuristics
- new chunks added to the topic since the last Oneiros run exceed a configured threshold
- one or more correction events are attached to the topic after the last run
- contradiction edges or disputed learnings appear
- orphaned chunks later become semantically adjacent to the topic
- neighboring topic merge/split events significantly change graph context

#### Retrieval-Based Heuristics
- Anamnesis repeatedly falls back from semantic learnings to episodic chunks for this topic
- semantic learnings are retrieved but corrected or ignored at a high rate
- episodic chunks from a Oneiros-processed topic are still dominating successful recall

#### Manual / Operator Heuristics
- operator flags topic for reconsideration
- explicit "rethink topic" task is created
- audit or evaluation run marks the learning layer insufficient

### 7.3  Reprocessing Outcomes

A reprocessing run may:

- keep an existing learning unchanged
- revise a learning
- split one learning into several
- merge overlapping learnings
- lower or raise confidence
- mark a learning `stale`
- retire a learning
- promote an open question into a stronger learning type
- reattach supporting episodic evidence

### 7.4  Sleeping Topics

Topics that have been processed but are not currently active should be
treated as **sleeping topics**, not dead topics. They remain eligible for
reconsideration whenever the above heuristics fire.

---

## 8  Daily Cron Architecture for Reprocessing

### 8.1  Overview

A daily cron-driven maintenance job identifies topics that should be
reprocessed and enqueues Oneiros jobs into a durable job table. This
separates candidate detection from the expensive consolidation run.

Recommended architecture:

```
daily cron
   -> scan topic / learning / retrieval metadata
   -> compute reprocessing candidates
   -> write rows to `oneiros_job_queue`
   -> Oneiros workers claim jobs asynchronously
   -> perform consolidation / reprocessing
```

### 8.2  Daily Scanner Responsibilities

The daily scanner should:

1. inspect all topics with prior Oneiros state
2. calculate freshness / drift / contradiction / fallback scores
3. identify topics exceeding configured thresholds
4. write or upsert job rows into the queue
5. avoid duplicate pending jobs for the same topic
6. attach a structured `reason` field for auditability

### 8.3  Suggested Job Queue Schema

```sql
CREATE TABLE oneiros_job_queue (
    job_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_node_id         UUID NOT NULL,
    job_type              TEXT NOT NULL,         -- consolidate | reprocess | verify
    priority              INTEGER NOT NULL DEFAULT 100,
    reason                JSONB NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | failed | canceled
    scheduled_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at            TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,
    attempt_count         INTEGER NOT NULL DEFAULT 0,
    last_error            TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (topic_node_id, job_type, status)
);
```

In practice, the uniqueness rule should usually be enforced as:
- at most one `pending` or `running` job of a given type per topic

### 8.4  Candidate Detection Query Pattern

A cron scanner can use a query pattern like:

```sql
WITH topic_state AS (
  SELECT
    tn.node_id                         AS topic_node_id,
    ors.last_oneiros_run_at,
    ors.topic_reconsider_after,
    ors.topic_drift_score,
    COUNT(DISTINCT c.chunk_id) FILTER (
      WHERE c.created_at > COALESCE(ors.last_oneiros_run_at, 'epoch')
    )                                  AS new_chunks_since_last_run,
    COUNT(DISTINCT sl.learning_id) FILTER (
      WHERE sl.status IN ('stale', 'disputed')
    )                                  AS stale_or_disputed_learnings,
    COALESCE(rf.fallback_count, 0)     AS retrieval_fallback_count
  FROM topic_nodes tn
  LEFT JOIN oneiros_topic_state ors
    ON ors.topic_node_id = tn.node_id
  LEFT JOIN chunk_topics ct
    ON ct.node_id = tn.node_id
  LEFT JOIN chunks c
    ON c.chunk_id = ct.chunk_id
  LEFT JOIN semantic_learnings sl
    ON sl.topic_node_id = tn.node_id
  LEFT JOIN oneiros_reprocessing_feedback rf
    ON rf.topic_node_id = tn.node_id
  GROUP BY tn.node_id, ors.last_oneiros_run_at, ors.topic_reconsider_after,
           ors.topic_drift_score, rf.fallback_count
)
INSERT INTO oneiros_job_queue (topic_node_id, job_type, priority, reason)
SELECT
  topic_node_id,
  'reprocess',
  100,
  jsonb_build_object(
    'new_chunks_since_last_run', new_chunks_since_last_run,
    'stale_or_disputed_learnings', stale_or_disputed_learnings,
    'retrieval_fallback_count', retrieval_fallback_count,
    'topic_drift_score', topic_drift_score
  )
FROM topic_state
WHERE
  now() >= COALESCE(topic_reconsider_after, now())
  OR new_chunks_since_last_run >= 10
  OR stale_or_disputed_learnings > 0
  OR retrieval_fallback_count >= 5;
```

The exact thresholds should be configurable.

### 8.5  Cron Example

```cron
# Every day at 02:15 local time
15 2 * * * /usr/bin/python3 /opt/atlas/jobs/oneiros_daily_scan.py
```

### 8.6  Worker Claim Pattern

Oneiros workers should claim jobs using `FOR UPDATE SKIP LOCKED` to allow
parallel processing without duplicate work.

---

## 9  Outputs

| Output                        | Destination               | Operation          |
|-------------------------------|---------------------------|--------------------|
| Semantic learnings            | `semantic_learnings`      | INSERT / supersede |
| Topic reprocessing state      | `oneiros_topic_state`     | UPSERT             |
| Processed chunk flags         | `chunks`                  | UPDATE             |
| Optional verification records | `learning_verifications`  | INSERT             |
| Oneiros job results           | `oneiros_job_queue`       | UPDATE             |
| Consolidation report          | Human notification (optional) | Informational  |

### 9.1  Consolidation Report Contents

Each run produces a report containing:

- topic name and node ID
- run type (`consolidate` or `reprocess`)
- number of episodic chunks processed
- number of learnings produced
- number of prior learnings revised / retired / reaffirmed
- compression / demotion ratio
- stale or disputed learnings identified
- verification actions taken, if any
- next reconsideration date
- recommended human review items, if any

---

## 10  Contracts

### 10.1  Read Access

| Table / Resource     | Access Pattern                                  |
|----------------------|-------------------------------------------------|
| `chunks`             | SELECT all chunks for target topic, ordered by `created_at` |
| `chunk_topics`       | SELECT to resolve topic-to-chunk membership     |
| `topic_nodes`        | SELECT metadata and graph context               |
| `topic_summaries`    | SELECT progressive summaries                    |
| `semantic_learnings` | SELECT active, stale, superseded learnings      |
| `injection_log` / retrieval stats | SELECT fallback / usage indicators    |

### 10.2  Write Access

| Table / Resource         | Access Pattern                              | Constraint                          |
|--------------------------|---------------------------------------------|-------------------------------------|
| `chunks`                 | UPDATE Oneiros-owned processing / retrieval-tier columns | No physical deletion by default |
| `semantic_learnings`     | INSERT / supersede learning records         | —                                   |
| `oneiros_topic_state`    | UPSERT topic-level reprocessing state       | —                                   |
| `learning_verifications` | INSERT verification results                 | optional                            |
| `oneiros_job_queue`      | UPDATE job status / results                 | —                                   |
| Human notification       | Consolidation reports (optional)            | —                                   |

### 10.3  Exclusive Authority

Oneiros is the only sidecar that may:

- mark chunks `oneiros_processed = true`
- demote chunks into lower retrieval tiers
- mark semantic learnings `superseded`, `stale`, `retired`, or `disputed`

Physical archival and deletion should remain downstream retention actions
with policy and audit controls.

---

## 11  Operational Semantics

### 11.1  Failure Handling

- **Mid-consolidation failure:** Transaction rollback. No learnings
  activated, no chunk retrieval tiers changed.
- **Model timeout:** Treat as failure. Log for capacity planning.
- **Partial model output:** Do not salvage partial results. Re-run.
- **Verification timeout:** Continue consolidation if possible, but mark
  verification as incomplete.
- **Queue job claim failure:** Another worker may claim later. Job remains pending.
- **Repeated topic failure:** Increase backoff and require operator review
  after configured threshold.

### 11.2  Idempotency

Running Oneiros twice on the same topic without new evidence should result
in either:

- no-op, or
- a new run that reaffirms existing learnings without changing active
  semantic state

Duplicate queued jobs should be suppressed by queue uniqueness and claim logic.

### 11.3  Concurrency

Only one Oneiros run may operate on a given topic at a time. Multiple
workers may operate across different topics in parallel.

### 11.4  Reconsideration Scheduling

At the end of each successful run, Oneiros computes a next-review time.

Recommended defaults:

| Freshness sensitivity | Next reconsideration |
|-----------------------|----------------------|
| `volatile`            | 1 day                |
| `moderate`            | 7 days               |
| `stable`              | 30 days              |

These times are shortened when contradiction or fallback pressure is high.

---

## 12  Evaluation Metrics

| Metric                          | Target      | Measurement method                         |
|---------------------------------|-------------|--------------------------------------------|
| Consolidation run success rate  | > 95%       | Job outcome tracking                       |
| Semantic preference effectiveness | > 70%     | Successful retrievals served by semantic layer first |
| Episodic fallback rate          | declining over time, not zero | Retrieval logs                    |
| Reprocessing correction yield   | > 25% on triggered topics | Fraction of reprocessed topics that meaningfully revise beliefs |
| Drift catch rate                | informational | Stale/disputed topics caught before user correction |
| Verification precision          | > 85%       | Human or operator review of verification-assisted changes |
| Demotion regret rate            | < 10%       | Cases where demoted episodic chunks should have remained live |
| Job queue backlog p95           | < 1 day     | Time from enqueue to completion            |

---

## 13  Configuration

```yaml
oneiros:
  enabled: true

  # Triggering
  initial_consolidation_chunk_threshold: 100
  manual_invocation_allowed: true

  # Retention / retrieval
  default_chunk_postprocess_mode: demote   # demote | archive
  demoted_retrieval_weight: 0.35
  archive_by_default: false
  delete_by_default: false

  # Reprocessing cadence
  reconsider_after_days:
    volatile: 1
    moderate: 7
    stable: 30

  # Reprocessing thresholds
  reprocess_on_new_chunks: 10
  reprocess_on_retrieval_fallback_count: 5
  reprocess_on_topic_drift_score: 0.60
  reprocess_on_disputed_learning: true
  reprocess_on_correction_events: true

  # Verification
  verification_enabled: true
  verification_mode: bounded   # off | bounded
  verify_freshness_sensitive_only: true

  # Queue
  daily_scan_enabled: true
  daily_scan_cron: "15 2 * * *"
  max_parallel_jobs: 2
  job_retry_limit: 3
  retry_backoff_seconds: 600

  # Human review
  require_review_on_structural_rewrite: true
  require_review_after_repeated_failure: true
```

---

## 14  Interaction with Other Sidecars

| Sidecar | Relationship |
|---|---|
| **Kairos** | Upstream topic structure provider. Kairos determines topic membership and signals initial consolidation candidates. |
| **Anamnesis** | Primary downstream consumer. Prefers semantic learnings first, but may fall back to episodic chunks. |
| **Eidos** | Supplies correction and signal metadata that can trigger reprocessing. |
| **Praxis** | Orthogonal procedural layer; may benefit when stable learnings reduce episodic noise. |
| **Psyche** | Not a direct consumer, but topic-level learnings may influence self-model reasoning through retrieval. |
| **Augur** | Retrieval fallback and prediction misses can inform reprocessing priority. |

---

## 15  Future Considerations

- topic-level belief graphs inside `semantic_learnings`
- automatic split / merge recommendation for unstable topics
- stronger contradiction-resolution workflows
- per-user or per-domain reconsideration policies
- richer verifier delegation rather than in-process bounded checks
- replaying old archived evidence through improved future ontology

---

*End of specification.*
