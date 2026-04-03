# 05 — Oneiros: Consolidation and Pruning

> *Oneiros — Greek god of dreams, son of Hypnos, shaper of meaningful*
> *visions from waking residue.*

---

## 1  Identity Card

| Field                | Value                                                                 |
|----------------------|-----------------------------------------------------------------------|
| **Name**             | Oneiros                                                               |
| **Tier**             | Reflective                                                            |
| **Role**             | Lossy consolidation, productive forgetting, corpus pruning            |
| **Trigger**          | Topic corpus exceeds threshold; weekly schedule; manual invocation    |
| **Latency**          | Unbounded (may run minutes to hours)                                  |
| **Model**            | Largest context window available (128k+ preferred for full topic read)|
| **Human-in-the-loop**| Recommended for first runs; autonomous with confidence threshold      |

---

## 2  Purpose

Oneiros performs the machine equivalent of REM consolidation: reading
accumulated episodic fragments, extracting generalized meaning, and
rewriting the representation in a more useful and less voluminous form.

### 2.1  The Key Distinction — Generalization, Not Summarization

Oneiros does **NOT** summarize. Summarization preserves event structure
with reduced detail. Oneiros **generalizes** — extracting patterns,
beliefs, and directional knowledge while discarding temporal scaffolding.

| Mode                        | Example output                                                                                       |
|-----------------------------|------------------------------------------------------------------------------------------------------|
| **Summarization (Kairos)**  | "On March 14th, three sessions explored JWT implementation..."                                       |
| **Generalization (Oneiros)**| "For this system: JWT validation failures are almost always clock skew, not algorithmic. RS256 with 30-second tolerance is the established pattern." |

Oneiros output is a **generalized belief statement** — durable,
directional, actionable. It captures what was *learned*, not what
*happened*.

---

## 3  Inputs

| Input                        | Source                          | Required |
|------------------------------|---------------------------------|----------|
| Full episodic corpus         | `chunks` table, chronological   | Yes      |
| Topic node metadata          | `topic_nodes` table             | Yes      |
| Corpus size signal           | Kairos (trigger notification)   | No       |
| Retention policy overrides   | Configuration / human operator  | No       |

All chunks for the target topic are retrieved in chronological order so
that the consolidation model can observe how understanding evolved over
time — even though the output will discard that temporal structure.

---

## 4  Processing — The Consolidation Run

### 4.1  Step-by-Step

1. **Retrieve** — Fetch ALL chunks for the target topic, sorted by
   `created_at` ascending.
2. **Assemble** — Build the full corpus text. This is where the large
   context window matters; the model must hold the entire episodic
   history simultaneously to detect cross-session patterns.
3. **Consolidate** — Run the consolidation prompt against the largest
   available model. The system prompt instructs the model to:
   - Preserve **meaning** and **direction**; discard **specifics** and
     **temporal anchors**.
   - Write in present tense as standing beliefs.
   - Capture constraints and negative knowledge explicitly ("X does NOT
     work because Y").
   - Flag uncertainty honestly — do not inflate confidence.
   - Identify open questions that require future investigation.
4. **Parse** — Structure the raw model output into `ConsolidatedBelief`
   records, each with a confidence score and belief type.
5. **Write** — Insert consolidated belief chunks into the
   `consolidated_beliefs` table.
6. **Archive** — Mark the original episodic chunks as archived
   (`archived = true`). They are NOT deleted.
7. **Report** — Return a consolidation report. Optionally notify a human
   reviewer.

### 4.2  Atomicity Guarantee

Steps 5 and 6 execute within a single transaction. If any part fails,
no chunks are archived and no beliefs are written. The topic is left
unchanged and will re-trigger on the next cycle.

### 4.3  Consolidation Prompt Guidelines

The system prompt for the consolidation model must enforce:

- **Present tense only.** "The API requires Bearer tokens" not "We
  discovered that the API required Bearer tokens."
- **No dates, no session references.** Temporal context is scaffolding;
  strip it.
- **Explicit negatives.** "HMAC-SHA256 is NOT suitable here because..."
  is more valuable than omitting the failed approach.
- **Confidence calibration.** Each belief carries an honest confidence
  score. "Probably true based on two observations" is better than
  false certainty.
- **Open questions preserved.** If the episodic record shows unresolved
  investigation, the consolidated output must flag it.

---

## 5  ConsolidatedBelief Schema

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BeliefType(Enum):
    FACTUAL       = "factual"        # verified or strongly evidenced fact
    CONSTRAINT    = "constraint"     # limitation, boundary, "do not" rule
    PREFERENCE    = "preference"     # chosen approach among alternatives
    PATTERN       = "pattern"        # recurring observation across sessions
    OPEN_QUESTION = "open_question"  # unresolved item requiring future work


@dataclass
class ConsolidatedBelief:
    belief_id: str                   # unique identifier (UUID)
    topic_node_id: str               # foreign key to topic_nodes
    content: str                     # present-tense declarative statement
    confidence: float                # 0.0 to 1.0
    belief_type: BeliefType          # see enum above
    basis: str                       # episodic evidence summary (brief)
    freshness_sensitivity: str       # "stable" | "moderate" | "volatile"
    replaces_chunk_count: int        # how many episodic chunks this replaces
    created_at: datetime             # timestamp of consolidation run
```

### 5.1  Field Semantics

| Field                   | Notes                                                                 |
|-------------------------|-----------------------------------------------------------------------|
| `content`               | Self-contained declarative statement. Must be interpretable without any other context. |
| `confidence`            | Model-assigned. 0.5 = weak signal, 0.7 = reasonable, 0.9+ = well-established. |
| `basis`                 | One or two sentences summarizing the episodic evidence. Not a full citation — just enough for audit. |
| `freshness_sensitivity` | `stable`: unlikely to change (e.g., language semantics). `moderate`: may shift with new evidence. `volatile`: likely outdated within weeks. |
| `replaces_chunk_count`  | Tracks compression ratio per belief for operational metrics.          |

---

## 6  Retention Policy

### 6.1  Per-Topic Thresholds

| Topic Class       | Max Raw Chunks | Consolidation Trigger | Post-Consolidation Archive Limit |
|-------------------|----------------|-----------------------|----------------------------------|
| Active project    | 500            | 200 chunks            | 100 archived chunks retained     |
| Recurring domain  | 200            | 100 chunks            | 50 archived chunks retained      |
| One-off session   | 50             | 30 chunks             | 15 archived chunks retained      |
| Completed task    | 20             | 10 chunks             | 5 archived chunks retained       |

### 6.2  Archive Lifecycle

1. **Live** — Chunk is active, searchable, used in retrieval.
2. **Archived** — Chunk is marked `archived = true` after consolidation.
   No longer returned in standard retrieval queries. Retained for audit.
3. **Eligible for deletion** — Archived chunks exceeding the
   post-consolidation archive limit (oldest first) become eligible for
   permanent deletion.
4. **Deleted** — Permanently removed. The consolidated beliefs are the
   sole durable record.

Deletion of archived chunks is a separate garbage-collection pass, not
part of the consolidation transaction itself.

### 6.3  This Is Productive Forgetting by Design

Not random decay. Not information loss through neglect. Oneiros
implements **deliberate replacement** of episodic specificity with
semantic generalization.

The agent remembers **what it learned**, not **everything that happened**.

This mirrors biological memory consolidation: the hippocampus replays
and compresses daily experience into cortical long-term storage during
sleep. Oneiros is the cortical rewrite step.

---

## 7  Outputs

| Output                   | Destination               | Operation          |
|--------------------------|---------------------------|--------------------|
| Consolidated beliefs     | `consolidated_beliefs`    | INSERT             |
| Archived chunk flags     | `chunks`                  | UPDATE (`archived = true`) |
| Consolidation report     | Human notification (optional) | Informational  |

### 7.1  Consolidation Report Contents

Each run produces a report containing:

- Topic name and node ID
- Number of episodic chunks processed
- Number of consolidated beliefs produced
- Compression ratio achieved
- List of belief statements with confidence scores
- Open questions identified
- Recommended human review items (if any belief confidence < threshold)

---

## 8  Contracts

### 8.1  Read Access

| Table / Resource     | Access Pattern                                  |
|----------------------|-------------------------------------------------|
| `chunks`             | SELECT all chunks for target topic, ordered by `created_at` |
| `chunk_topics`       | SELECT to resolve topic-to-chunk membership     |
| `topic_nodes`        | SELECT metadata for classification and policy   |

### 8.2  Write Access

| Table / Resource         | Access Pattern                              | Constraint                          |
|--------------------------|---------------------------------------------|-------------------------------------|
| `chunks`                 | UPDATE `archived = true`                    | Archive authority is exclusive to Oneiros |
| `consolidated_beliefs`   | INSERT new belief records                   | —                                   |
| Human notification       | Consolidation reports (optional)            | —                                   |

### 8.3  Exclusive Authority

Oneiros is the **only** sidecar with archive authority on the `chunks`
table. No other sidecar may set `archived = true`. This constraint is
enforced at the application layer and should be validated in integration
tests.

---

## 9  Operational Semantics

### 9.1  Failure Handling

- **Mid-consolidation failure:** Transaction rollback. No chunks
  archived, no beliefs written. The topic remains in its pre-run state
  and will re-trigger on the next cycle.
- **Model timeout:** Treat as failure. Log the timeout duration for
  capacity planning.
- **Partial model output:** Do not attempt to salvage partial results.
  Full re-run on next trigger.

### 9.2  Idempotency

Running Oneiros twice on the same topic (before new chunks arrive)
should be a no-op: there are no un-archived chunks to process, so the
run exits early with an empty report.

### 9.3  Concurrency

Only one Oneiros run may operate on a given topic at a time. A
distributed lock (or equivalent) must be held for the duration of the
consolidation transaction. Concurrent runs on *different* topics are
permitted and encouraged.

### 9.4  Human-in-the-Loop Calibration

- For the first N runs (configurable, default 3), consolidation reports
  are sent for human review **before** archiving proceeds.
- The human may approve, reject, or edit individual beliefs.
- Rejected beliefs are discarded; their source chunks remain live.
- After calibration, Oneiros operates autonomously for beliefs above the
  confidence threshold. Beliefs below threshold are still flagged for
  human review.

---

## 10  Governance Role

Oneiros is the primary governance mechanism for long-term data
retention within the memory system. It enforces:

1. **Per-topic retention limits** — No topic accumulates unbounded
   episodic fragments.
2. **Productive forgetting schedule** — Regular consolidation prevents
   memory bloat while preserving semantic value.
3. **Archive vs. hard-delete distinction** — Archived chunks are
   retained for audit before eventual deletion.
4. **Audit trail preservation** — Consolidation reports and the `basis`
   field on each belief maintain provenance.
5. **Compression accountability** — Every belief records how many chunks
   it replaced, enabling monitoring of information loss risk.

---

## 11  Evaluation Metrics

| Metric                    | Target    | Measurement Method                              |
|---------------------------|-----------|-------------------------------------------------|
| Belief coverage           | > 90%     | Human review: do beliefs capture episodic meaning? |
| Compression ratio         | > 5:1     | `replaces_chunk_count` averaged across beliefs  |
| Belief accuracy           | > 90%     | Human-judged correctness of belief statements   |
| Open question detection   | > 80%     | Human review: were unresolved items flagged?    |
| Consolidation latency     | < 10 min  | Wall-clock time per topic consolidation run     |
| Archive integrity         | 100%      | No chunks archived outside a successful transaction |

Metrics should be tracked per-run and trended over time. Degradation in
belief accuracy or coverage signals prompt drift and should trigger
human review re-enablement.

---

## 12  Configuration

```yaml
oneiros:
  enabled: true

  # Trigger thresholds
  consolidation_threshold_chunks: 200
  min_chunks_for_consolidation: 10

  # Scheduling
  schedule: weekly            # cron-compatible or "weekly" / "daily"
  manual_trigger: true        # allow on-demand invocation

  # Model selection
  model: largest_available    # resolved at runtime to largest context window
  min_context_window: 128000  # refuse to run if model context < this

  # Human review
  human_review_first_n_runs: 3
  autonomy_confidence_threshold: 0.85
  flag_beliefs_below_confidence: 0.70

  # Retention (defaults, overridable per topic class)
  retention:
    active_project:
      max_raw_chunks: 500
      consolidation_trigger: 200
      archive_retention: 100
    recurring_domain:
      max_raw_chunks: 200
      consolidation_trigger: 100
      archive_retention: 50
    one_off_session:
      max_raw_chunks: 50
      consolidation_trigger: 30
      archive_retention: 15
    completed_task:
      max_raw_chunks: 20
      consolidation_trigger: 10
      archive_retention: 5

  # Operational
  concurrency_lock_timeout_seconds: 600
  max_consolidation_duration_seconds: 3600
  retry_on_failure: true
  retry_delay_seconds: 300
```

---

## 13  Interaction with Other Sidecars

| Sidecar     | Interaction                                                        |
|-------------|--------------------------------------------------------------------|
| **Kairos**  | Kairos emits corpus-size signals that trigger Oneiros runs. Kairos summarizes; Oneiros generalizes. They are complementary, not redundant. |
| **Engram**  | Engram writes the episodic chunks that Oneiros later consolidates. Engram never archives; Oneiros never writes raw episodes. |
| **Mnemon**  | Mnemon retrieves chunks for query answering. After consolidation, Mnemon retrieves consolidated beliefs instead of archived episodes. |
| **Ariadne** | Ariadne maintains the topic graph. Oneiros reads topic metadata but does not modify the graph structure. |

---

## 14  Design Rationale

### 14.1  Why Not Just Summarize?

Summaries preserve narrative structure: "first X happened, then Y, then
Z." This is useful for recent history (Kairos handles this) but becomes
noise at scale. A year of weekly summaries is still a year of reading.

Generalized beliefs are **O(concepts)** not **O(sessions)**. They scale
with the complexity of the domain, not the volume of interaction.

### 14.2  Why Archive Before Delete?

The two-phase lifecycle (archive, then delete) provides a safety net
during early operation. If consolidation quality is poor, archived
chunks can be restored. Once confidence in the consolidation pipeline is
established, the archive-to-delete pipeline can be tightened.

### 14.3  Why Largest Model?

Consolidation quality depends on the model's ability to hold the full
episodic history in context simultaneously. Chunked or sliding-window
approaches risk missing cross-session patterns — the exact patterns
Oneiros exists to detect. The cost of using the largest model is
justified by the infrequency of consolidation runs (weekly or less).

---

## 15  Future Considerations

- **Incremental consolidation:** For topics that grow continuously,
  explore consolidating only new chunks against existing beliefs rather
  than re-processing the full corpus each time.
- **Belief versioning:** Track how beliefs evolve across consolidation
  runs to detect knowledge drift.
- **Cross-topic consolidation:** Identify beliefs that span multiple
  topics and promote them to a higher-level knowledge tier.
- **Confidence decay:** Beliefs with `freshness_sensitivity: volatile`
  could have their confidence automatically reduced over time, forcing
  re-evaluation.
