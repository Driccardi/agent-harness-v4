# 08 — Augur: The Predictive Engine

> *Augur — from the Roman practice of divination through observation of
> natural patterns. The augur read the flight of birds not as magic but
> as signal: structured inference from observed regularity.*

---

## 1  Identity Card

| Field                | Value                                                                     |
|----------------------|---------------------------------------------------------------------------|
| **Name**             | Augur                                                                     |
| **Tier**             | Reflective (primary) with Real-Time prefetch component                    |
| **Role**             | Behavioral pattern learning, prediction generation, anticipatory pre-fetching |
| **Trigger**          | Session end (pattern mining), inter-turn (prefetch update), session start (briefing) |
| **Latency**          | Pattern mining: unbounded. Prefetch: <2 s. Session-start brief: <5 s.    |
| **Model**            | Small-fast model for prefetch; capable model for intent inference and arc analysis. ML models (TensorFlow) for trained behavioral prediction. |
| **Stateful**         | Yes — maintains behavioral sequence index, intent model, prefetch cache   |
| **Human-in-the-loop**| Not required — predictions are suggestions, not actions                   |
| **Cognitive analogy**| Predictive coding — the brain's continuous generation of expectations against which incoming signals are compared |

---

## 2  Purpose

Augur extends the memory substrate from "recall relevant past" to
"anticipate likely next." It treats prediction as infrastructure — like
CPU cache prefetching — not personality. The prediction is not "what do
people generally ask next." It is "what does THIS person typically do
next, in THIS context, based on EVERYTHING observed about them."

Most memory systems are reactive: a request arrives, retrieval fires,
results return. Augur makes the memory system proactive. By the time a
request arrives, the most likely relevant memories are already ranked
and staged for injection. The agent responds faster and with richer
context because the retrieval pipeline was primed before the question
was asked.

### 2.1  The Core Insight

Human behavior is predictable text. Given a sequence of interactions —
requests, tasks, tools, problems — the next interaction follows from
the preceding sequence with learnable probabilistic structure. These
are not universal human tendencies. They are **personal behavioral
signatures** specific to a particular person's working style, habits,
rhythms, and cognitive patterns.

A developer who always runs tests after implementing a feature. A
writer who always re-reads the last paragraph before continuing. A
manager who always asks for a status summary before diving into detail.
These are not guesses — they are observed regularities in the
behavioral record.

### 2.2  Prediction Is a Cache, Not a Controller

This is the critical invariant. Augur's outputs are performance
optimizations and contextual hints. They never gate correctness. The
system must function correctly with Augur offline. Cache misses are
normal. Wrong predictions must be low-impact. Prediction is a cache,
not a controller.

---

## 3  Three Prediction Horizons

### 3.1  Immediate (Next 1–2 Interactions)

| Aspect     | Detail                                                        |
|------------|---------------------------------------------------------------|
| Data       | Fast index (current session) + behavioral n-gram index        |
| Use        | Pre-fetch relevant memories, prepare tool contexts            |
| Confidence | Highest — short extrapolation, rich context                   |

Output format:

```xml
<prediction horizon="immediate" confidence="0.82">
  <next_likely_request>
    Based on completing JWT implementation, this human typically
    reviews test coverage next (observed in 7/9 similar sessions).
  </next_likely_request>
  <pre_fetched_context>
    Test file location, last test run results, relevant memory chunks
  </pre_fetched_context>
</prediction>
```

### 3.2  Session (Next 3–10 Interactions)

| Aspect     | Detail                                                        |
|------------|---------------------------------------------------------------|
| Data       | Topic graph transitions + semantic sequence matching          |
| Use        | Anticipatory skill preparation, session planning              |
| Confidence | Moderate — longer horizon, more branching possibilities       |

Session-horizon predictions are less precise but structurally useful.
They describe the likely *arc* of a session rather than specific next
steps. "This session is following an implement-test-debug-commit
pattern" is actionable even when the specific next request is unknown.

### 3.3  Cross-Session (Next Session)

| Aspect     | Detail                                                        |
|------------|---------------------------------------------------------------|
| Data       | Master session graph + session transition patterns + temporal/calendar signals |
| Use        | Pre-warm agent at session start, contextual brief, surface open loops |
| Confidence | Lowest — but even 40–50% accuracy is valuable                |

Cross-session prediction is the highest-risk, highest-reward horizon.
A wrong prediction costs only a brief mismatch at session start. A
correct prediction means the agent greets the human with precisely the
context they need, before they ask.

Temporal and calendar signals matter here. Tuesday mornings may
consistently involve planning. Friday afternoons may involve
documentation. Post-holiday sessions may involve re-orientation.

---

## 4  Behavioral Sequence Mining

### 4.1  N-gram Sequence Patterns

Build probability distributions over next interactions given last N
interactions. Simple but positional — pattern-matches on recency and
sequence order.

```python
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class BehavioralNgramIndex:
    """
    Maps interaction n-grams to probability distributions over
    next interactions. An interaction is represented as a canonical
    action label (e.g., "implement_feature", "run_tests",
    "review_diff", "ask_clarification").
    """
    max_n: int                                          # maximum n-gram length (default 5)
    ngrams: Dict[Tuple[str, ...], Dict[str, float]]     # sequence -> {next_action: probability}
    observation_counts: Dict[Tuple[str, ...], int]       # sequence -> times observed
    recency_weights: Dict[Tuple[str, ...], float]        # decay-weighted by last observation time

    def predict(self, recent_actions: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
        """
        Given recent action history, return top-k predicted next
        actions with probabilities. Tries longest matching n-gram
        first, backs off to shorter sequences.
        """
        for n in range(min(len(recent_actions), self.max_n), 0, -1):
            key = tuple(recent_actions[-n:])
            if key in self.ngrams:
                dist = self.ngrams[key]
                ranked = sorted(dist.items(), key=lambda x: -x[1])
                return ranked[:top_k]
        return []
```

### 4.2  Semantic Sequence Patterns

Embed interaction sequences as vectors and find patterns in semantic
space. Two sessions following different literal paths but semantically
similar arcs produce generalizable predictions.

For example: "implement OAuth → write tests → fix token expiry" and
"implement WebSocket auth → write tests → fix reconnection logic" are
literally different but semantically similar arcs. Augur should
recognize the shared pattern (implement-auth → test → fix-edge-case)
and predict the third step when observing the first two in a new
authentication context.

```python
@dataclass
class EmbeddedSessionArc:
    """
    A session's interaction sequence embedded as a single vector,
    along with the original action labels for interpretation.
    """
    session_id: str
    arc_embedding: List[float]         # 768-dim vector representing full arc
    action_sequence: List[str]         # original action labels
    outcome: str                       # how the session ended
    topic_cluster: str                 # primary topic area
```

### 4.3  Sequence Canonicalization

Raw interactions must be reduced to canonical action labels before
n-gram indexing. This is a classification step performed at session end
during the pattern-mining pass.

| Raw Interaction                              | Canonical Label        |
|----------------------------------------------|------------------------|
| "Can you implement the login endpoint?"      | `implement_feature`    |
| "Run the test suite"                         | `run_tests`            |
| "What's the status of the auth module?"      | `status_check`         |
| "Actually, let's use RS256 instead"          | `correction`           |
| "Looks good, let's commit"                   | `approval`             |
| "Let me think about this differently..."     | `pivot`                |

The canonicalization model maps free-text interactions to a controlled
vocabulary of approximately 30–50 action labels. This vocabulary is
extensible as new interaction patterns emerge.

---

## 5  Anticipatory Pre-fetching

The most immediately practical output of Augur. Pre-compute embedding
queries and pre-rank injection candidates BEFORE the agent needs them.
When Anamnesis fires, the injection decision is instant because results
are already cached.

```python
from typing import Optional


class AnticipatoryPrefetcher:
    """
    Maintains an in-memory cache of pre-ranked retrieval candidates
    based on Augur's predictions. Sits between Augur (producer) and
    Anamnesis (consumer).
    """

    def __init__(self, ttl_turns: int = 3, hit_threshold: float = 0.80):
        self.prefetch_cache: Dict[str, PrefetchEntry] = {}
        self.ttl_turns = ttl_turns
        self.hit_threshold = hit_threshold
        self.stats = PrefetchStats()

    def on_prediction_available(self, prediction, session_state):
        """
        Called by Augur when a new prediction is generated.
        Pre-computes retrieval results for the top predicted requests.
        """
        for likely_request in prediction.next_likely_requests[:3]:
            anticipated_embedding = embed(likely_request.description)
            candidates = db.query(
                similarity_search,
                anticipated_embedding,
                limit=20,
            )
            self.prefetch_cache[likely_request.id] = PrefetchEntry(
                embedding=anticipated_embedding,
                candidates=candidates,
                created_at_turn=session_state.turn_index,
                prediction_confidence=likely_request.confidence,
            )

    def check_prefetch(self, query_embedding) -> Optional[List]:
        """
        Called by Anamnesis before running a full retrieval query.
        Returns cached candidates if a sufficiently similar query
        was pre-fetched, otherwise returns None (cache miss).
        """
        best_match = None
        best_similarity = 0.0

        for entry_id, entry in self.prefetch_cache.items():
            if entry.is_expired(self.ttl_turns):
                continue
            sim = cosine_similarity(query_embedding, entry.embedding)
            if sim > best_similarity:
                best_similarity = sim
                best_match = entry

        if best_match and best_similarity > self.hit_threshold:
            self.stats.record_hit(best_similarity)
            return best_match.candidates

        self.stats.record_miss()
        return None

    def evict_expired(self, current_turn: int):
        """Remove entries older than TTL."""
        expired = [
            k for k, v in self.prefetch_cache.items()
            if v.is_expired(current_turn, self.ttl_turns)
        ]
        for k in expired:
            del self.prefetch_cache[k]
```

### 5.1  Prefetch Cache Semantics

| Property          | Value                                                        |
|-------------------|--------------------------------------------------------------|
| Storage           | In-memory only — never persisted to disk                     |
| TTL               | Configurable, default 3 turns                                |
| Eviction          | Time-based (TTL) + LRU within capacity                       |
| Max entries       | 10 (3 per prediction horizon, plus overflow)                 |
| Hit threshold     | Cosine similarity > 0.80 between actual and predicted query  |
| Miss cost         | Zero — Anamnesis falls through to normal retrieval           |
| Hit benefit       | Eliminates retrieval latency for that query                  |

Prefetch cache hit rate is the primary metric for prediction quality.
A cache that never hits is a cache that wastes compute. A cache that
always hits means predictions are perfectly aligned with actual usage.

---

## 6  Intent Modeling

### 6.1  Request Prediction vs Intent Modeling

| Level              | Example                                               |
|--------------------|-------------------------------------------------------|
| Request prediction | "Human will probably ask to run tests"                |
| Intent modeling    | "Human is trying to ship auth module by EOD"          |

Request prediction is shallow — it forecasts the next literal action.
Intent modeling is deeper — it infers the goal that drives a sequence
of actions. The gap between stated and actual intent is often the most
valuable prediction Augur can surface.

### 6.2  Intent Inference from Session Arc Shape

Intent is inferred from the *shape* of the session arc, not from any
single interaction's content. A session that starts with broad
exploration, narrows to a specific implementation, and enters a
test-fix loop has a recognizable shape: "ship a specific feature."

```python
@dataclass
class InferredIntent:
    """
    Augur's current best guess at the human's driving intent
    for this session.
    """
    intent_id: str
    description: str                # natural language description
    confidence: float               # 0.0 to 1.0
    inferred_from: str              # "arc_shape" | "explicit_statement" | "pattern_match"
    arc_phase: str                  # "exploration" | "narrowing" | "execution" | "verification" | "wrap-up"
    estimated_completion: float     # 0.0 to 1.0 — how far through the arc
    open_subgoals: List[str]        # inferred remaining steps
```

### 6.3  Intent Classes

Augur classifies each human turn into one of 15 intent classes:

| Class                  | Description                                          |
|------------------------|------------------------------------------------------|
| `orient`               | Getting bearings — "where were we?"                  |
| `task_assignment`      | Assigning a concrete task                            |
| `clarification`        | Asking for or providing clarification                |
| `approval`             | Confirming, accepting, approving                     |
| `correction`           | Correcting a mistake or redirecting                  |
| `status_check`         | Asking about progress or state                       |
| `scope_expansion`      | Adding requirements or broadening focus              |
| `scope_reduction`      | Narrowing focus, deferring, cutting scope            |
| `deep_dive`            | Requesting detailed exploration of a topic           |
| `pivot`                | Changing direction entirely                          |
| `completion`           | Marking something as done                            |
| `content_provision`    | Providing raw content (paste, upload, reference)     |
| `emotional_expression` | Expressing frustration, satisfaction, urgency        |
| `meta_conversation`    | Talking about the conversation itself                |
| `session_end`          | Wrapping up, saying goodbye                          |

---

## 7  Emergent Orchestration

When behavioral history shows consistent skill sequences — for
example, a human who reliably follows memory-core work with curiosity
exploration and then task-hub updates — Augur surfaces these as soft
orchestration hints.

```xml
<orchestration_hint probability="0.875" basis="7_sessions">
  Pattern: After completing implementation work, this human typically
  reviews related documentation, then updates task tracking.

  This is a pattern observation, not an instruction.
  Follow if it serves the current goal. Disregard otherwise.
</orchestration_hint>
```

Orchestration hints are explicitly non-binding. They inform but never
constrain. An orchestration hint that becomes a requirement has crossed
the line from prediction to control — violating the core invariant
established in section 2.2.

---

## 8  ML Training Pipeline

### 8.1  Model A: Behavioral Intent Classifier (~500K Parameters)

Predicts intent class of the next human turn from a feature vector
composed of:

- Context embedding (current session state)
- Topic embedding (active topic cluster)
- Scalar features (time of day, day of week, session phase, session
  duration so far, turn count)
- Recent skill invocation sequence (last 5 skills used)

Architecture:

```
context_embedding (768) ─┐
                         ├─→ Concat (868) → Dense(512) → ReLU
topic_embedding (768) ───┘                      │
                                                ↓
scalar_features (32) ────→ Dense(64) → ReLU ──→ Concat (576)
                                                ↓
skill_sequence (50) ─────→ Dense(64) → ReLU ──→ Dense(256) → ReLU
                                                ↓
                                          Dense(15) → Softmax
```

- 15 intent classes (see section 6.3)
- Output: probability distribution over intent classes
- Training loss: categorical cross-entropy
- Inference latency target: <10 ms

### 8.2  Model B: Next-Request Embedding Predictor (~2M Parameters)

Predicts the embedding vector of the next human request. The predicted
embedding is used directly as a prefetch query — no decoding to text
required.

Architecture:

```
session_context (768) ─┐
                       ├─→ Concat → Dense(1024) → ReLU → Dropout(0.2)
topic_context (768) ───┘                    │
                                            ↓
recent_turns (768×5) → LSTM(256) ─────→ Concat → Dense(1024) → ReLU
                                            ↓
                                    Dense(768) → L2-Normalize
```

- L2-normalized output for cosine similarity compatibility
- Training loss: 1 - cosine_similarity(predicted, actual)
- Inference latency target: <50 ms

### 8.3  Training Pipeline

| Phase                   | Detail                                                   |
|-------------------------|----------------------------------------------------------|
| Data collection         | Continuous — every session adds labeled examples          |
| Initial training        | After 30 sessions (~2000+ interaction examples)          |
| Retraining              | Every 10 sessions (full retrain from accumulated data)   |
| Fine-tuning             | Every 3 sessions (incremental update)                    |
| Compute window          | Post-session idle time (same window as Oneiros/Psyche)   |
| Hardware                | Local GPU if available; CPU fallback acceptable for Model A |
| Train/validation split  | Chronological — never leak future into past              |

### 8.4  Calibration

Confidence scores must be empirically accurate. A model that reports
0.82 confidence should be correct 82% of the time across all
predictions at that confidence level.

Calibration method: temperature scaling applied post-training.

| Calibration Metric        | Target    |
|---------------------------|-----------|
| Expected Calibration Error (ECE) | < 0.05   |
| Maximum Calibration Error (MCE)  | < 0.15   |
| Reliability diagram       | Monotonic, close to diagonal |

Calibration is checked at every retrain cycle. If ECE exceeds the
target, temperature is re-tuned before the model is deployed.

---

## 9  Data Model

### 9.1  BehavioralProfile

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class BehavioralProfile:
    """
    The complete behavioral model for one human, persisted across
    sessions. This is the primary stateful artifact Augur maintains.
    """
    master_session_id: str
    ngram_index: BehavioralNgramIndex
    semantic_arc_library: List[EmbeddedSessionArc]
    skill_sequence_index: SkillSequenceIndex
    topic_transition_matrix: Dict[str, Dict[str, float]]
    session_start_patterns: Dict[str, float]
    post_task_patterns: Dict[str, List[str]]
    current_inferred_intent: Optional[InferredIntent]
    session_arc_phase: Optional[str]
    prediction_accuracy_history: List[PredictionOutcome]
    calibration_score: float
    last_updated: datetime = field(default_factory=datetime.utcnow)
    total_sessions_observed: int = 0
    total_interactions_observed: int = 0
```

### 9.2  PredictionOutcome

```python
@dataclass
class PredictionOutcome:
    """
    Records a single prediction and its actual outcome, used for
    accuracy tracking and calibration.
    """
    prediction_id: str
    horizon: str                    # "immediate" | "session" | "cross_session"
    predicted_intent: str           # predicted intent class
    predicted_confidence: float     # confidence at prediction time
    actual_intent: str              # what actually happened
    correct: bool                   # top-1 match
    correct_top3: bool              # top-3 match
    embedding_cosine_similarity: Optional[float]   # for Model B predictions
    prefetch_hit: bool              # did the prefetch cache serve this query
    timestamp: datetime
```

### 9.3  SkillSequenceIndex

```python
@dataclass
class SkillSequenceIndex:
    """
    Tracks ordered sequences of skill invocations to detect
    habitual workflows.
    """
    sequences: Dict[Tuple[str, ...], int]       # skill sequence -> observation count
    transition_matrix: Dict[str, Dict[str, float]]  # skill -> {next_skill: probability}
    common_workflows: List[Tuple[List[str], float]]  # (workflow, frequency)
```

---

## 10  Session-Start Brief

The most immediately valuable output Augur produces. Delivered before
the first human message of a new session, it primes the agent with
predicted context.

```xml
<augur_session_brief
    confidence="0.71"
    based_on_sessions="23"
    generated_at="session_start"
    generation_latency_ms="3200">

  <likely_focus>
    Previous session ended mid-task on auth module implementation.
    High probability (0.78) this session continues that work.
  </likely_focus>

  <anticipated_arc>
    implement → test → debug → commit
  </anticipated_arc>

  <pre_fetched_memories count="13">
    7 auth implementation chunks, 3 test coverage gap chunks,
    2 token refresh open-loop chunks, 1 deployment config chunk
  </pre_fetched_memories>

  <behavioral_notes>
    This human typically starts sessions with an orientation question.
    Tuesday mornings trend focused and moderate-energy.
    Last session ended abruptly (possible interruption) — may need
    brief re-orientation.
  </behavioral_notes>

  <open_loops count="2">
    1. Token refresh endpoint not yet tested (from session 22)
    2. CORS configuration deferred for later (from session 20)
  </open_loops>
</augur_session_brief>
```

### 10.1  Brief Generation Constraints

| Constraint              | Value                                                 |
|-------------------------|-------------------------------------------------------|
| Maximum latency         | 5 seconds (must complete before first human message)  |
| Maximum token length    | 500 tokens (must not crowd the context window)        |
| Minimum confidence      | 0.40 (below this, brief is suppressed)                |
| Minimum sessions        | 5 (too little data before this for meaningful prediction) |

### 10.2  Brief Accuracy Tracking

Every session-start brief is evaluated against the actual session that
unfolds. The `likely_focus` field is compared to the actual primary
topic. The `anticipated_arc` is compared to the actual interaction
sequence. These evaluations feed back into the prediction accuracy
history and calibration pipeline.

---

## 11  Signal Sources

Augur reads from multiple sidecar outputs to build its behavioral
model. It is a consumer of nearly every other sidecar's data.

| Signal Source                  | Sidecar Origin | What Augur Extracts                     |
|--------------------------------|----------------|-----------------------------------------|
| Topic transition probabilities | Kairos         | Which topics follow which topics        |
| Somatic transition patterns    | Eidos          | Affective state shifts during sessions  |
| Temporal/contextual metadata   | Engram         | Time of day, session duration, gaps     |
| Skill invocation sequences     | Engram (skill_invocations) | Tool and skill usage patterns |
| Session summaries              | Kairos         | High-level session arc descriptions     |
| Consolidated beliefs           | Oneiros        | Stable knowledge about the human's domain |
| Open loops                     | Kairos         | Unresolved threads to surface           |

---

## 12  Failure Modes and Safeguards

### 12.1  Pattern Lock-in

If the deviation rate (frequency of predictions being wrong) drops too
low, predictions may be *constraining* behavior rather than predicting
it. The agent may unconsciously steer interactions toward predicted
paths. Mitigation: if deviation rate falls below the configured
threshold (default 0.15), inject deliberate uncertainty into
predictions and log a warning.

### 12.2  Stale Patterns

Behavioral patterns change over time. A developer learning a new
framework will have different patterns than one working in a familiar
codebase. Mitigation: apply exponential recency weighting to all
pattern observations. Flag significant divergence from predicted
patterns as potential behavioral shift.

### 12.3  Overconfident Hints

Uncalibrated confidence is worse than no confidence. A prediction
reported at 0.90 that is actually correct 0.55 of the time will cause
the agent to over-commit to wrong expectations. Mitigation: strict
calibration pipeline (section 8.4), with automatic fallback to
uniform priors if ECE exceeds threshold.

### 12.4  Privacy Considerations

Behavioral profiles are intimate data. They encode working habits,
cognitive patterns, temporal rhythms, and emotional tendencies. They
require:

- Explicit retention limits (configurable maximum observation window)
- Full human visibility into the behavioral profile on request
- Deletion rights — human can clear their behavioral profile at any time
- No exfiltration — behavioral profiles never leave the local system

### 12.5  Cold Start

Before sufficient data accumulates (fewer than `initial_train_threshold`
sessions), Augur operates in observation-only mode. It collects
behavioral sequences but does not generate predictions or prefetch
queries. The session-start brief is suppressed. This avoids the
pathology of confident predictions from insufficient data.

---

## 13  Outputs

| Output                     | Destination                  | Operation      |
|----------------------------|------------------------------|----------------|
| Behavioral sequences       | `behavioral_sequences` table | INSERT/UPDATE  |
| Prefetch cache entries     | Anamnesis (in-memory, direct)| SET (volatile) |
| Session-start brief        | Agent context injection      | One-shot       |
| Orchestration hints        | Anamnesis injection pipeline | Advisory       |
| Prediction outcomes        | `prediction_outcomes` table  | INSERT         |

---

## 14  Contracts

### 14.1  Read Access

| Table / Resource        | Access Pattern                                       |
|-------------------------|------------------------------------------------------|
| `chunks`                | SELECT recent chunks for sequence extraction          |
| `skill_invocations`     | SELECT ordered skill history for workflow mining      |
| `topic_edges`           | SELECT topic transition graph for arc analysis        |
| `sss_snapshots`         | SELECT somatic state for temporal pattern correlation |
| `session_summaries`     | SELECT session arcs for cross-session prediction      |

### 14.2  Write Access

| Table / Resource           | Access Pattern                    | Constraint                 |
|----------------------------|-----------------------------------|----------------------------|
| `behavioral_sequences`     | INSERT/UPDATE behavioral n-grams  | Augur exclusive            |
| `prediction_outcomes`      | INSERT prediction evaluation logs | Augur exclusive            |
| Anamnesis prefetch cache   | SET (in-memory, volatile)         | Shared write with Anamnesis eviction |

### 14.3  Exclusive Authority

Augur is the **only** sidecar that writes to `behavioral_sequences`
and `prediction_outcomes`. No other sidecar generates predictions or
maintains behavioral models. This constraint prevents conflicting
prediction sources and ensures a single calibration pipeline.

---

## 15  Operational Semantics

### 15.1  Trigger Conditions

| Trigger            | When                           | What Runs                          |
|--------------------|--------------------------------|------------------------------------|
| Session end        | Human ends session or timeout  | Full pattern mining pass           |
| Inter-turn         | After each human turn          | Prefetch update (fast path only)   |
| Session start      | New session detected           | Session-start brief generation     |
| Retrain schedule   | Every N sessions (configurable)| ML model retraining                |

### 15.2  Failure Handling

- **Pattern mining failure:** Log error, skip this session's mining
  pass. Data is not lost — next session's mining pass will process
  accumulated interactions.
- **Prefetch failure:** Silent degradation — Anamnesis falls through
  to normal retrieval. No user-visible impact.
- **Brief generation failure:** Suppress the brief. Agent starts
  without predictions. Log the failure for diagnosis.
- **Model training failure:** Continue using the previous model
  version. Schedule retry at next idle window.

### 15.3  Idempotency

Running pattern mining twice on the same session data should produce
identical results. The behavioral sequence index is updated
idempotently — duplicate observations are deduplicated by session ID
and turn index.

### 15.4  Concurrency

Prefetch updates run on the hot path (inter-turn) and must not block
the agent. They execute asynchronously with a hard timeout of 2
seconds. Pattern mining runs post-session and has no concurrency
constraints with the active session.

---

## 16  Interaction with Other Sidecars

| Sidecar        | Interaction                                                     |
|----------------|-----------------------------------------------------------------|
| **Engram**     | Augur reads chunks and skill invocations written by Engram. Engram is unaware of Augur. |
| **Eidos**      | Augur reads somatic tags to correlate affective state with behavioral patterns. |
| **Kairos**     | Augur reads topic edges, session summaries, and open loops. Kairos provides the structural context Augur uses for arc analysis. |
| **Oneiros**    | Augur reads consolidated beliefs for stable domain knowledge. Both run in the post-session idle window but on independent data. |
| **Anamnesis**  | Primary consumer relationship. Augur writes to the prefetch cache; Anamnesis checks it before running full retrieval. |
| **Psyche**     | Both operate in the reflective tier. Psyche models relational dynamics; Augur models behavioral patterns. They share the post-session compute window. |

---

## 17  Evaluation Metrics

| Metric                              | Target   | Measurement Method                           |
|-------------------------------------|----------|----------------------------------------------|
| Intent top-1 accuracy               | > 0.60   | Predicted vs actual intent class             |
| Intent top-3 accuracy               | > 0.85   | Actual intent in top 3 predictions           |
| ECE (calibration)                   | < 0.05   | Temperature-scaled confidence vs empirical   |
| Prefetch cache hit rate             | > 0.40   | Cache hits / total Anamnesis queries         |
| Mean embedding cosine similarity    | > 0.65   | Predicted vs actual request embedding        |
| Session-start brief accuracy        | > 0.60   | Correct focus prediction (human-evaluated)   |
| Pattern lock-in monitoring          | > 0.15   | Deviation rate must stay above this floor    |
| Brief generation latency (p95)      | < 5 s    | Wall-clock time for session-start brief      |
| Prefetch update latency (p95)       | < 2 s    | Wall-clock time for inter-turn prefetch      |

Metrics are tracked per-session and trended over time. Degradation in
any metric triggers a diagnostic log entry. Sustained degradation in
calibration or hit rate triggers automatic model retraining.

---

## 18  Configuration

```yaml
augur:
  enabled: true

  # Cold start
  initial_train_threshold_sessions: 30
  min_sessions_for_brief: 5

  # Training schedule
  retrain_interval_sessions: 10
  fine_tune_interval_sessions: 3

  # Prediction thresholds
  prediction_confidence_floor: 0.40
  intent_classes: 15

  # Prefetch
  prefetch_ttl_turns: 3
  prefetch_hit_threshold: 0.80
  prefetch_max_entries: 10
  prefetch_candidates_per_prediction: 20

  # N-gram mining
  max_ngram: 5
  min_ngram_observations: 3
  semantic_match_threshold: 0.70
  recency_half_life_sessions: 20

  # Calibration
  calibration_ece_target: 0.05
  calibration_mce_limit: 0.15
  recalibrate_on_ece_exceed: true

  # Safety
  pattern_lock_in_threshold: 0.15
  max_behavioral_profile_age_days: 365
  allow_human_profile_deletion: true

  # Session-start brief
  brief_max_latency_ms: 5000
  brief_max_tokens: 500
  brief_suppress_below_confidence: 0.40

  # Operational
  prefetch_timeout_ms: 2000
  pattern_mining_timeout_ms: 300000
  model_training_timeout_ms: 3600000
  retry_on_training_failure: true
  retry_delay_seconds: 300
```

---

## 19  Design Rationale

### 19.1  Why Prediction as Infrastructure?

Prediction framed as personality ("I think you want...") is creepy and
fragile. Prediction framed as infrastructure (cache prefetching) is
invisible when correct and harmless when wrong. Users never see
predictions directly — they experience faster, more relevant responses.

### 19.2  Why Local ML Models?

Behavioral profiles are too intimate to send to external APIs.
Training locally ensures the profile never leaves the user's machine.
Small models (500K–2M parameters) are sufficient for the prediction
task and train in minutes on consumer hardware.

### 19.3  Why Three Horizons?

Different prediction horizons serve different consumers. Immediate
predictions serve the prefetch cache (latency optimization). Session
predictions serve skill preparation (capability readiness). Cross-
session predictions serve the session-start brief (context priming).
Collapsing these into a single horizon would sacrifice either
precision or range.

### 19.4  Why Calibration Over Accuracy?

A model that is 70% accurate but perfectly calibrated is more useful
than a model that is 80% accurate but poorly calibrated. Calibration
means the system knows when it does not know. The agent can modulate
its reliance on predictions based on reported confidence — but only
if that confidence is trustworthy.

---

## 20  Future Considerations

- **Multi-human behavioral modeling:** When the system serves multiple
  humans, maintain separate behavioral profiles and detect when
  behavioral patterns transfer across humans (shared team habits).
- **Behavioral drift detection:** Explicitly detect and flag when a
  human's behavioral patterns shift significantly, distinguishing
  temporary deviation from permanent change.
- **Prediction explanation:** Surface human-readable explanations for
  predictions ("I pre-loaded test context because you usually test
  after implementing") when the human asks why certain context was
  available.
- **Federated pattern learning:** With explicit consent, learn from
  anonymized behavioral patterns across users to bootstrap cold-start
  predictions while preserving privacy.
- **Active prediction:** Move beyond passive prefetching to proactive
  suggestions — "Based on your usual workflow, would you like to run
  tests now?" Requires careful UX design to avoid being intrusive.
