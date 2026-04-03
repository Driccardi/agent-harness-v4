
# 08 — Augur: The Predictive Engine and Speculative Prefetch Runner

> *Augur — from the Roman practice of divination through observation of
> natural patterns. The augur read the flight of birds not as magic but
> as signal: structured inference from observed regularity.*

---

## 1  Identity Card

| Field                | Value                                                                     |
|----------------------|---------------------------------------------------------------------------|
| **Name**             | Augur                                                                     |
| **Tier**             | Reflective (primary) with Real-Time speculative prefetch component        |
| **Role**             | Behavioral pattern learning, next-turn prediction, contextual steering priors, anticipatory prefetching |
| **Trigger**          | Post-agent-turn async launch, session end pattern mining, session start cold-boot steering, retrain schedule |
| **Latency**          | Pattern mining: unbounded. Speculative runner: target <2 s. Cold-start steering brief: <5 s. |
| **Model**            | Small-fast model for online prediction and prefetch scoring; capable model for intent inference and difficult priors; optional ML models for trained behavioral prediction |
| **Stateful**         | Yes — maintains behavioral sequence index, predictive models, prefetch buffers, observability traces |
| **Human-in-the-loop**| Not required for routine predictions; predictions are suggestions and staged context, not actions |
| **Cognitive analogy**| Predictive coding — continuous generation of expectations against which new signals are compared |

---

## 2  Purpose

Augur extends the memory substrate from "recall relevant past" to
"anticipate likely next." It treats prediction as infrastructure — like
CPU cache prefetching — not personality. The prediction is not "what do
people generally ask next." It is "what does THIS person typically do
next, in THIS context, based on EVERYTHING observed about them."

Most memory systems are reactive: a request arrives, retrieval fires,
results return. Augur makes the memory system proactive. By the time a
request arrives, the most likely relevant memories, skills, and read-only
data artifacts may already be ranked and staged. The agent responds
faster and with richer context because the retrieval and preparation
pipeline was primed before the question was asked.

### 2.1  The Core Insight

Human behavior is predictable text. Given a sequence of interactions —
requests, tasks, tools, problems, corrections, and outcomes — the next
interaction follows from the preceding sequence with learnable
probabilistic structure. These are not universal human tendencies. They
are **personal behavioral signatures** specific to a particular person's
working style, habits, rhythms, and cognitive patterns.

### 2.2  Prediction Is a Cache, Not a Controller

This is the critical invariant. Augur's outputs are performance
optimizations and contextual hints. They never gate correctness. The
system must function correctly with Augur offline. Cache misses are
normal. Wrong predictions must be low-impact. Prediction is a cache,
not a controller.

### 2.3  Preparation, Not Premature Action

Augur may prepare the stage. It may not start the play.

This means Augur may:

- prefetch memories
- prefetch skill metadata and prerequisites
- perform bounded read-only MCP/data prefetch
- stage cold-start steering suggestions
- surface orchestration hints

It may not silently perform consequential actions, mutate external state,
or advance the user's work without being asked.

---

## 3  Prediction Scope

Augur is centered on two output families, not three grand horizons.

### 3.1  Next-Turn Prediction (Primary)

The core predictive question is:

> What is the human likely to ask for, need, or do next?

This is the primary prediction product. Everything else exists to support
it.

Next-turn prediction drives:
- memory prefetch
- skill prefetch
- MCP/data prefetch
- lightweight steering priors
- cold-start opening suggestions

### 3.2  Contextual Priors (Secondary)

Longer-horizon patterning is still useful, but only as **contextual priors**
that shape next-turn prediction and cold-start posture. These include:

- time-of-day priors
- day-of-week habits
- session-gap priors
- cold-boot priors
- open-loop priors
- arc-phase priors
- common skill-sequence continuations

These are not treated as independent prediction products. They are
supporting priors that improve the quality of next-turn prediction and
steering.

### 3.3  Cold-Start Steering

What the previous draft called "cross-session prediction" is narrowed here
to **cold-start steering**: when a session begins, Augur may use open loops,
temporal habits, and likely recurring work patterns to prepare a useful
opening stance.

Example:

- Tuesday morning + recurring reporting pattern
- open loops from last session
- local time and session gap
- likely first useful question or offer

This is a special case of next-turn prediction at session start.

---

## 4  Architecture Overview

Augur consists of four cooperating subsystems:

1. **Prediction Engine** — predicts next-turn needs and contextual priors
2. **Speculative Prefetch Runner** — async worker/sub-agent controlled by Augur
3. **Prefetch Buffer** — per-session staging area for memory, skill, and data artifacts
4. **Learning & Evaluation Pipeline** — stores observations, outcomes, model versions, and retraining artifacts

### 4.1  Ownership Model

Augur owns:
- behavioral prediction logic
- next-turn candidate generation
- contextual prior generation
- orchestration hints
- speculative prefetch decisions
- prefetch observability traces
- prediction training/evaluation records

Anamnesis remains the live gate and injector. Augur prepares; Anamnesis decides at hook time.

---

## 5  Async Speculative Runner

### 5.1  Why Augur Owns It

The "just do it" speculative prefetch runner is owned by Augur, not the
main thread. Prediction and prefetch are one system. The same component
that scores likely next needs should decide what is worth staging.

### 5.2  Trigger Timing

The speculative runner is launched on **post-agent-turn**.

Flow:

```text
assistant turn completes
  -> post-agent-turn hook fires
  -> Augur async runner starts
  -> predicts likely next-turn needs
  -> stages memory/skill/data prefetch into Augur buffer
  -> writes observability events

next UserPromptSubmit
  -> Anamnesis reads Augur buffer
  -> applies live gate
  -> injects or stays silent
```

The runner should usually complete before the next `UserPromptSubmit`
opportunity. If it misses the window, its output may still be retained
briefly if not stale; otherwise it expires.

### 5.3  Output Buffer

The speculative runner writes to a **per-session output buffer**:

- memory candidates
- skill prefetch artifacts
- MCP/data prefetch artifacts
- steering priors
- orchestration hints
- observability events

This buffer is separate from the agent context. It is a staging area,
not an injection channel.

### 5.4  Deadlines and Expiry

Each staged artifact has:
- `created_at`
- `expires_at`
- `predicted_for_hook`
- `prediction_confidence`
- `cost_score`
- `used` flag

Stale staged outputs should be discarded automatically.

---

## 6  Input Signals

Prediction quality depends on the richness of signals. The following are
divided into **must-have** and **nice-to-have** groups.

### 6.1  Must-Have Signals

| Signal | Description |
|--------|-------------|
| Recent human turns | Last several human requests / responses |
| Recent assistant turns | Recent completions, offers, summaries, pivots |
| Canonicalized interaction sequence | Reduced action labels for recent steps |
| Active topic / recent topic path | Current topic cluster and recent transitions |
| Session gap | Time since prior human turn / prior session |
| Local time / day-of-week | Temporal habit priors |
| Skill invocation sequence | Last 1–5 relevant skills and outcomes |
| Open loops | Unresolved work items, recent gaps |
| Success / failure outcomes | What usually follows success, partial success, or failure |
| Current session phase / arc hint | orientation, execution, verification, wrap-up, etc. |

### 6.2  Nice-to-Have Signals

| Signal | Description |
|--------|-------------|
| Somatic state | Eidos / SSS affective register |
| Context pressure | current context window utilization |
| Runtime capability surface | tools, modules, skills currently available |
| Tool latency / quota pressure | whether speculation should be conservative |
| User modality / route | desktop, mobile, voice, etc. |
| Recent correction density | useful for confidence and caution |
| Concurrent priority load | many open loops / many pending tasks |

### 6.3  Signal Sources

| Source | Use |
|--------|-----|
| `chunks` | recent interaction sequence and context |
| `skill_invocations` | skill-sequence prediction and workflow continuation |
| `topic_edges` / `topic_nodes` | topic transition priors |
| `sss_snapshots` | affective correlation and pacing |
| `semantic_learnings` | stable context for understanding likely next needs |
| `open_loops` / task state | unresolved work and likely continuations |
| runtime capability registry | tool / module / MCP availability |
| operator / calendar priors | recurring temporal patterns when available |

---

## 7  Prediction Engine

### 7.1  Next-Turn Candidate Generation

Augur generates a ranked list of next-turn candidates. Each candidate may
represent:

- likely request
- likely intent class
- likely skill need
- likely read-only data need
- likely opening suggestion at cold start

```python
@dataclass
class NextTurnCandidate:
    candidate_id: str
    candidate_type: str          # memory | skill | data | steering | orchestration
    description: str
    confidence: float
    predicted_intent: str
    supporting_signals: list[str]
    estimated_usefulness: float
    estimated_cost: float
    expires_after_turns: int
```

### 7.2  Intent Classes

Augur classifies each human turn into intent classes such as:

- `orient`
- `task_assignment`
- `clarification`
- `approval`
- `correction`
- `status_check`
- `scope_expansion`
- `scope_reduction`
- `deep_dive`
- `pivot`
- `completion`
- `content_provision`
- `emotional_expression`
- `meta_conversation`
- `session_end`

These remain useful as compact labels for learning and evaluation.

### 7.3  Arc-Phase Priors

Augur may maintain a coarse phase estimate:

- orientation
- planning
- execution
- verification
- wrap-up

This is not a separate prediction horizon. It is a contextual prior used
to bias next-turn prediction and cold-start behavior.

### 7.4  Orchestration Hints

When behavioral history shows consistent skill or task continuations,
Augur may surface soft orchestration hints. These remain **pattern
observations, not instructions**.

---

## 8  Speculative Prefetch Classes

Augur supports four progressively stronger classes of speculative work.

### 8.1  Tier 0 — Prediction Only

No prefetch. Just ranked candidates and steering priors.

### 8.2  Tier 1 — Memory Prefetch

Precompute:
- likely memory retrieval queries
- topic summaries
- procedural notes
- semantic learnings
- open-loop context

This is the cheapest and safest class.

### 8.3  Tier 2 — Skill Prefetch

Stage likely skill artifacts:
- parse `SKILL.md`
- load tool prerequisites
- resolve likely next required inputs
- stage dependent references

This does **not** invoke the skill. It only prepares it.

### 8.4  Tier 3 — Read-Only MCP / Data Prefetch

Perform bounded, read-only fetching of likely next-needed data:
- MCP reads
- local file reads
- metadata listing
- schema fetches
- reference doc fetches
- cached record pulls

These artifacts are staged in a temp cache or temp directory.

### 8.5  Tier 4 — Speculative Execution

Rare and tightly constrained. Only for:
- deterministic
- read-only
- bounded
- cheap
- discardable

Example: reading a likely next-needed local file or fetching a small
read-only record set. Never mutate, send, delete, or commit work.

### 8.6  Governing Rule

Prefetch may stage context. It may not silently advance work.

---

## 9  Prefetch Scoring, K-Ranking, and Safety

### 9.1  Scoring

Augur should rank prefetch actions by **expected value**, not probability alone.

```text
prefetch_score =
  probability_of_need
  * usefulness_if_ready
  * freshness_value
  * read_safety
  * cheapness
  * discardability
```

Penalty terms should reduce score for:
- latency
- monetary/API cost
- quota pressure
- payload size
- staleness risk
- sensitivity

### 9.2  K-Ranked Options

Augur should stage top-K candidates per prefetch class.

Recommended defaults:
- memory K = 5
- skill K = 2
- data K = 2
- speculative execution K = 0 or 1

### 9.3  Safe Speculation Policy

#### Allowed by default
- memory retrieval staging
- skill parsing / loading
- read-only file reads
- read-only MCP/API fetches
- metadata listing
- schema / reference lookup

#### Threshold-gated
- expensive searches
- larger dataset pulls
- multi-file sweeps
- higher-latency external fetches

#### Forbidden by default
- writes
- deletes
- sends
- updates
- commands with side effects
- irreversible operations

---

## 10  Prefetch Buffer and Artifact Store

### 10.1  Buffer Structure

Augur writes staged artifacts into a per-session buffer.

Suggested conceptual structure:

```python
@dataclass
class PrefetchArtifact:
    artifact_id: str
    session_id: str
    candidate_type: str         # memory | skill | data | steering | orchestration
    source_kind: str            # chunks | semantic_learnings | skill | mcp | file
    payload_ref: str            # cache key / temp path / in-memory ref
    confidence: float
    cost_score: float
    predicted_for_hook: str     # UserPromptSubmit | SessionStart | PostToolUse
    created_at_turn: int
    expires_at_turn: int
    used: bool
```

### 10.2  Storage Options

Artifacts may be staged in:
- in-memory per-session cache
- structured DB-backed cache rows
- temp directory, e.g. `/tmp/atlas/augur/<session_id>/...`

### 10.3  Cache Semantics

| Property          | Value                                                        |
|-------------------|--------------------------------------------------------------|
| Storage           | In-memory and/or temp-cache backed                           |
| TTL               | Configurable, default 3 turns                                |
| Eviction          | Time-based + LRU within capacity                             |
| Hit threshold     | Configurable, based on similarity or exact predicted use     |
| Miss cost         | Anamnesis falls through to normal retrieval                  |
| Hit benefit       | Eliminates or reduces retrieval / preparation latency        |

---

## 11  Cold-Start Steering

### 11.1  Purpose

At session start, Augur may produce a small **cold-start steering brief**:
- likely first useful question
- likely recurring work pattern
- likely open-loop reminder
- temporal prior (e.g. Tuesday-morning reporting habit)

This is not broad prophecy. It is a modest opening prior.

### 11.2  Examples

- "The human usually begins by re-orienting after an overnight gap."
- "Tuesday mornings often involve reporting tasks."
- "The most useful opening may be to offer the pending report run."

### 11.3  Cold Start Threshold

Before sufficient data accumulates, Augur remains mostly observational.
However, weak temporal priors may still be used in **low-authority** form
if they are grounded in repeated patterns, not fantasy.

---

## 12  Observability

Augur should expose what it is doing while the user and main agent
continue their work. This is especially useful because prediction is
otherwise invisible.

### 12.1  Observable Events

Augur should stream or log:
- ranked next-turn candidates
- candidate confidence scores
- contextual priors in effect
- staged memory artifacts
- staged skill artifacts
- staged MCP/data artifacts
- speculative reads launched
- cache hits / misses
- expired unused artifacts
- suppressed speculative actions and why
- model version used
- time spent per prefetch class

### 12.2  Operator View

The operator UI should be able to show:
- "what Augur thinks is next"
- "what it has already staged"
- "what was used"
- "what was wasted"
- "why it did or did not speculate"

### 12.3  Why This Matters

Observability supports:
- debugging
- evaluation
- trust
- drift detection
- cost control
- pattern-lock-in monitoring

---

## 13  Predictive Modeling

### 13.1  Scope

The predictive modeling layer should explicitly support:

1. next-turn intent classification
2. next-turn request embedding prediction
3. likely skill continuation prediction
4. likely data dependency prediction
5. cold-start steering prior generation

### 13.2  Model Families

#### Model A — Intent Classifier
Predicts next human intent class from:
- recent context embeddings
- active topic embedding
- temporal scalars
- recent skill sequence
- open-loop features

#### Model B — Next-Request Embedding Predictor
Predicts the embedding of the likely next request. This supports
memory prefetch directly.

#### Model C — Skill Continuation Predictor
Predicts likely next skill(s) from:
- recent skill sequence
- topic path
- outcome history
- time-of-day / session-gap priors

#### Model D — Data Dependency Predictor
Predicts likely next read-only data needs:
- likely files
- MCP endpoints
- schemas
- reference docs
- records / datasets

These may begin as heuristics and graduate to trained models later.

### 13.3  Training Strategy

Augur should support:
- heuristic baseline
- rules + light models hybrid
- offline supervised training on historical session data
- ablation tests by feature family
- model versioning and rollback

TensorFlow is acceptable, but it should be one implementation option, not
the entire modeling story.

### 13.4  Training Data Requirements

All training signals must remain observable in database structures.

Required training data includes:
- session_id
- turn_index
- prior action sequence
- prior skill sequence
- active topic / recent topic path
- session gap
- local time / day-of-week
- candidate prediction made
- actual next event / skill / data need
- whether prefetched artifact was used
- cost of incorrect prediction
- human correction within N turns

---

## 14  Database Structures

### 14.1  Behavioral Sequences

```sql
CREATE TABLE behavioral_sequences (
    sequence_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id            UUID NOT NULL,
    turn_index            INTEGER NOT NULL,
    action_sequence       JSONB NOT NULL,
    skill_sequence        JSONB,
    topic_path            JSONB,
    session_gap_minutes   INTEGER,
    local_time_bucket     TEXT,
    dow_bucket            TEXT,
    observed_next_action  JSONB NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 14.2  Prediction Records

```sql
CREATE TABLE augur_predictions (
    prediction_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id            UUID NOT NULL,
    turn_index            INTEGER NOT NULL,
    trigger_type          TEXT NOT NULL,      -- post_agent_turn | session_start
    candidate_type        TEXT NOT NULL,      -- memory | skill | data | steering
    description           TEXT NOT NULL,
    confidence            FLOAT NOT NULL,
    model_version         TEXT,
    supporting_signals    JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 14.3  Prefetch Artifacts

```sql
CREATE TABLE augur_prefetch_artifacts (
    artifact_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id         UUID REFERENCES augur_predictions(prediction_id),
    session_id            UUID NOT NULL,
    artifact_type         TEXT NOT NULL,
    source_kind           TEXT NOT NULL,
    payload_ref           TEXT NOT NULL,
    confidence            FLOAT NOT NULL,
    cost_score            FLOAT,
    predicted_for_hook    TEXT NOT NULL,
    used                  BOOLEAN NOT NULL DEFAULT false,
    expired               BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at            TIMESTAMPTZ NOT NULL
);
```

### 14.4  Prediction Outcomes

```sql
CREATE TABLE prediction_outcomes (
    outcome_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id         UUID REFERENCES augur_predictions(prediction_id),
    session_id            UUID NOT NULL,
    actual_next_event     JSONB,
    matched               BOOLEAN NOT NULL,
    usefulness_score      FLOAT,
    false_positive_cost   FLOAT,
    consumed_artifact_ids JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 14.5  Model Registry

```sql
CREATE TABLE augur_model_versions (
    model_version         TEXT PRIMARY KEY,
    model_type            TEXT NOT NULL,
    training_window_start TIMESTAMPTZ,
    training_window_end   TIMESTAMPTZ,
    feature_schema        JSONB NOT NULL,
    metrics               JSONB NOT NULL,
    active                BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

These structures keep the predictive system fully inspectable and trainable.

---

## 15  Evaluation and Refinement

### 15.1  Metrics

| Metric                              | Target   | Measurement Method                           |
|-------------------------------------|----------|----------------------------------------------|
| Intent top-1 accuracy               | > 0.60   | Predicted vs actual intent class             |
| Intent top-3 accuracy               | > 0.80   | Predicted vs actual intent class             |
| Request-embedding similarity        | informative, improving | cosine similarity of predicted vs actual request |
| Prefetch artifact use rate          | > 0.30   | Used artifacts / staged artifacts            |
| Memory prefetch hit rate            | > 0.40   | Cache hits / candidate reads                 |
| Skill prefetch use rate             | informative | skill-prefetched artifacts later used       |
| Data prefetch use rate              | informative | MCP/file artifacts later used               |
| False-positive cost                 | < 0.5 turns/session average | correction and wasted-work correlation |
| Calibration error                   | < 0.05   | confidence calibration analysis              |
| Behavioral diversity index          | no significant decline | monitor pattern lock-in                     |

### 15.2  Testing

Augur should be tested via:
- offline replay against historical sessions
- held-out evaluation windows
- feature ablation tests
- model-to-model comparison
- heuristic baseline comparison
- cost/benefit analysis per prefetch class

### 15.3  Refinement Loop

Refinement should include:
- retraining on schedule or drift trigger
- feature ablation and selection
- threshold tuning
- rollback to prior model version
- operator review of wasted speculation
- periodic review of pattern lock-in risk

---

## 16  Contracts

### 16.1  Read Access

| Table / Resource        | Access Pattern                                       |
|-------------------------|------------------------------------------------------|
| `chunks`                | SELECT recent chunks for sequence extraction          |
| `skill_invocations`     | SELECT ordered skill history for continuation mining  |
| `topic_edges`           | SELECT topic transition graph for priors              |
| `sss_snapshots`         | SELECT somatic state for temporal correlation         |
| `semantic_learnings`    | SELECT stable learnings for context                   |
| capability registry     | SELECT available tools/modules/MCP surface            |
| `open_loops` / task state | SELECT unresolved work and likely continuations     |

### 16.2  Write Access

| Table / Resource           | Access Pattern                    | Constraint                 |
|----------------------------|-----------------------------------|----------------------------|
| `behavioral_sequences`     | INSERT/UPDATE behavioral records  | Augur exclusive            |
| `augur_predictions`        | INSERT prediction records         | Augur exclusive            |
| `augur_prefetch_artifacts` | INSERT/UPDATE staged artifacts    | Augur exclusive            |
| `prediction_outcomes`      | INSERT evaluation logs            | Augur exclusive            |
| `augur_model_versions`     | INSERT/UPDATE model registry      | Augur exclusive            |

### 16.3  Shared Boundary with Anamnesis

Augur stages. Anamnesis gates and injects.

Augur does not bypass the injection gate for standard memory candidates.
Cold-start steering and designated advisory hints may have explicit policy
exceptions, but speculative prep alone never authorizes injection.

---

## 17  Operational Semantics

### 17.1  Trigger Conditions

| Trigger            | When                                  | What Runs                          |
|--------------------|---------------------------------------|------------------------------------|
| Post-agent-turn    | After assistant finishes a turn       | Async speculative runner           |
| Session end        | Human ends session or timeout         | Full pattern mining pass           |
| Session start      | New session / cold boot detected      | Cold-start steering generation     |
| Retrain schedule   | Every N sessions or drift trigger     | Model retraining / recalibration   |

### 17.2  Failure Handling

- **Pattern mining failure:** Log error, skip this mining pass. Data remains for later reprocessing.
- **Speculative runner failure:** Silent degradation — Anamnesis falls through to normal retrieval.
- **Prefetch artifact fetch failure:** Drop that artifact, keep other candidates.
- **Cold-start brief failure:** Suppress the brief. Agent starts without predictive steering.
- **Model training failure:** Continue using the previous model version.
- **Observability write failure:** Do not block prediction; buffer if possible.

### 17.3  Idempotency

Running pattern mining twice on the same session data should produce
identical or deduplicated results. Prediction/outcome rows should dedupe on
`(session_id, turn_index, candidate_type, description_hash)` or similar.

### 17.4  Concurrency

The post-agent-turn speculative runner is asynchronous and bounded by a hard
timeout. It must not block the main agent runtime. Pattern mining and
retraining run off the hot path.

---

## 18  Failure Modes and Safeguards

### 18.1  Pattern Lock-In

If the system's own predictions begin to shape user behavior too strongly,
the prediction engine may become self-confirming. Augur must monitor:
- decreasing diversity of continuations
- near-perfect confirmation rates that look suspicious
- user behavior becoming path-dependent on what was staged

Safeguard:
- track behavioral diversity index
- decay stale priors
- occasionally widen top-K exploration under uncertainty

### 18.2  Stale Pattern Application

Historical patterns may stop being true. Recency weighting and drift
detection are required.

### 18.3  Over-Speculation

Too much speculative work wastes compute and creates spooky overreach.
Safeguard:
- cost-aware ranking
- read-only policy
- TTL expiry
- usage/outcome logging
- hard caps per prefetch class

---

## 19  Configuration

```yaml
augur:
  enabled: true

  # Core mode
  mode: hybrid                     # heuristic | ml | hybrid

  # Async speculative runner
  post_agent_turn_runner_enabled: true
  speculative_runner_timeout_ms: 2000

  # Prediction scope
  cold_start_enabled: true
  contextual_priors_enabled: true
  orchestration_hints_enabled: true

  # Prefetch K values
  prefetch_k:
    memory: 5
    skill: 2
    data: 2
    speculative_execution: 1

  # Safety
  speculative_execution_enabled: true
  read_only_prefetch_only: true
  expensive_prefetch_threshold: 0.80

  # Cache / buffer
  artifact_ttl_turns: 3
  max_artifacts_per_session: 20

  # Modeling
  intent_model_enabled: true
  embedding_predictor_enabled: true
  skill_predictor_enabled: true
  data_predictor_enabled: true

  # Retraining
  retrain_every_n_sessions: 25
  drift_trigger_enabled: true

  # Observability
  observability_enabled: true
  log_staged_artifacts: true
  log_unused_artifacts: true
```

---

## 20  Interaction with Other Sidecars

| Sidecar        | Interaction                                                     |
|----------------|-----------------------------------------------------------------|
| **Engram**     | Augur reads chunks and interaction traces written by Engram. Engram is unaware of Augur. |
| **Eidos**      | Augur reads somatic tags and affective signals when available. |
| **Kairos**     | Augur reads topic structure and transitions for contextual priors. |
| **Oneiros**    | Augur reads semantic learnings for stable understanding of likely next needs. |
| **Anamnesis**  | Primary consumer relationship. Augur stages artifacts; Anamnesis checks, gates, and injects when appropriate. |
| **Psyche**     | Psyche provides self/posture context; Augur provides prediction and preparation. They remain separate. |
| **Praxis**     | Praxis skill metadata and histories inform skill continuation prediction and prefetch. |

---

*End of specification.*
