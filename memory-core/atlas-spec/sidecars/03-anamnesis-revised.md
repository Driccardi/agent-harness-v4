# 03 — Anamnesis

## Sidecar Specification: Injection Agent

---

## 1. Identity Card

| Field              | Value                                                                                  |
| ------------------ | -------------------------------------------------------------------------------------- |
| **Name**           | Anamnesis                                                                              |
| **Etymology**      | Greek: *anamnesis* — recollection. Plato's theory that learning is remembering what the soul already knows. |
| **Tier**           | Real-Time                                                                              |
| **Role**           | Associative recall interface — making the model remember                               |
| **Trigger**        | Hook events: `PostToolUse`, `UserPromptSubmit`, `PreCompact`, `SessionStart`           |
| **Latency budget** | < 500 ms per hook event                                                                |
| **Model**          | Embedding model + optional reranker                                                    |
| **Stateful**       | Yes — maintains session injection state, confusion signal, turn index, and hook-scoped ready queues |

---

## 2. Purpose

Anamnesis is the injection agent — the interface between stored memory and the
agent's active context window. It is the only sidecar that writes into the
model's prompt at inference time.

Its goal is **not** information delivery. That is RAG. RAG retrieves documents
from a corpus and hands them to the model as external evidence. Anamnesis does
something categorically different: it makes the model *experience recall*. The
distinction matters because externally-supplied evidence and internally-surfaced
memory produce different epistemic postures. Evidence invites evaluation.
Memory invites integration.

The target phenomenology is what humans describe as "things surfacing from
within current processing" — the moment a relevant fact floats up mid-sentence,
unbidden but apt. Anamnesis manufactures that moment by injecting memory
fragments at precisely the point where they become contextually inevitable.

Anamnesis does **not** rely exclusively on hook-time retrieval. It prepares
candidate injections continuously in the background so that memories are already
"warm" when a hook exposes an opportunity. Hook time is reserved for live
gating, freshness checks, final ranking, and payload delivery — not expensive,
from-scratch retrieval whenever that work can be amortized earlier.

### 2.1 Design Principles

1. **Bias toward silence.** Injection requires a positive case. The absence of
   a reason *not* to inject is never a reason to inject. Every injection
   carries a cost: context-window budget, attentional interference, and the
   risk of anchoring the model on stale information.

2. **Phenomenological framing.** Injected memories are formatted as recalled
   context, never as external retrieval results. The model should treat them
   the way it treats its own prior reasoning — with integration, not citation.

3. **Non-blocking execution.** On any failure — query timeout, database
   unavailability, embedding error — Anamnesis skips injection and returns
   control. The agent must always function without memory injection.

4. **Injection is advisory.** The model is free to ignore injected memories.
   Anamnesis influences but does not compel.

5. **Preparation before opportunity.** Retrieval should happen before the hook
   opportunity when possible. Gating should happen at the hook opportunity.
   This keeps injection conservative while minimizing runtime latency.

---

## 3. Inputs

Anamnesis reads from multiple sources, each providing a different axis of
recall.

| Source                     | Purpose                                        | Access pattern          |
| -------------------------- | ---------------------------------------------- | ----------------------- |
| Hook events                | Trigger signal from agent runtime               | Push (event listener)   |
| `chunks` table (Postgres)  | Semantic similarity queries against stored text | Pull (vector query)     |
| Knowledge graph            | Topic-based retrieval via `topic_nodes`, `topic_summaries` | Pull (graph traversal) |
| `procedural_notes` store   | Praxis-authored skill/procedure injection       | Pull (keyed lookup)     |
| SSS snapshots              | Somatic state for affective weighting           | Pull (latest snapshot)  |
| Augur prefetch cache       | Pre-computed injection candidates               | Pull (cache read)       |
| Psyche self-narrative queue | Gate-bypass channel for identity-critical memories | Push (direct channel) |
| Hook-scoped ready queue    | Pre-built, short-lived injection candidates     | Pull (cache / table read) |
| Precompute event stream    | Signals that a candidate set should be refreshed | Push (event listener) |

### 3.1 Hook Event Payloads

Each hook event carries a context envelope:

```typescript
interface HookPayload {
  event_type: "PostToolUse" | "UserPromptSubmit" | "PreCompact" | "SessionStart";
  session_id: string;
  turn_index: number;
  timestamp: string;             // ISO 8601
  tool_name?: string;            // PostToolUse only
  tool_result_summary?: string;  // PostToolUse only — truncated to 512 tokens
  user_prompt?: string;          // UserPromptSubmit only
  compaction_reason?: string;    // PreCompact only
  context_window_usage: number;  // 0.0 to 1.0
  active_branch_id?: string;
  session_metadata: Record<string, unknown>;
}
```

### 3.2 Prepared Injection Candidates

Anamnesis maintains a short-lived pool of precomputed injection candidates.
These are created asynchronously before a hook fires and are scoped to a
session, branch, and intended hook type.

A prepared candidate includes:

```typescript
interface PreparedInjectionCandidate {
  candidate_id: string;
  session_id: string;
  master_session_id: string;
  hook_type: "PostToolUse" | "UserPromptSubmit" | "PreCompact" | "SessionStart";
  source_kind: "chunk" | "topic_summary" | "procedural_note" | "self_narrative" | "prediction" | "branch_synthesis";
  source_id: string;
  payload_xml: string;                 // pre-rendered or partially rendered memory block
  similarity_score?: number;           // precomputed if retrieval-based
  novelty_score?: number;
  somatic_alignment?: number;
  topic_id?: string;
  branch_id?: string;
  predicted_by_augur: boolean;
  created_at: string;
  expires_at: string;
}
```

Prepared candidates are **not** automatically injected. They remain subject to
live gate evaluation at hook time unless their type is explicitly configured as
a bypass type.

### 3.3 Hook-Scoped Ready Queues

Prepared candidates are staged into small, per-session ready queues keyed by
hook type:

- `SessionStart`
- `UserPromptSubmit`
- `PostToolUse`
- `PreCompact`

These queues are intended to keep the most likely relevant candidates already
available when the corresponding hook fires. They are aggressively expired and
refreshed; they are a prefetch layer, not a second long-term memory store.

### 3.4 Candidate Preparation Sources

The ready queues are refreshed from several upstream events:

- new chunk writes and chunk updates
- Eidos enrichment completion
- Kairos topic summary or graph updates
- Praxis procedural note creation
- Psyche self-narrative output
- Augur predictions and session briefs
- compaction-survival markings
- branch synthesis completion
- confusion-tier transitions that require candidate invalidation or restriction

---

## 4. The Conjunctive Injection Gate

The gate is the heart of Anamnesis. It enforces the bias toward silence through
a conjunction of eight independent checks. **All eight must pass** for a
standard memory candidate to be injected. Failure of any single check vetoes
the candidate.

This design is intentional. A disjunctive gate (any check passes) would be
biased toward injection. A weighted-score gate would hide the individual
failure reasons and make debugging difficult. The conjunction makes the system
conservative and transparent.

The existence of prepared candidates does not weaken the gate. Preparation only
moves expensive retrieval and formatting work earlier in time. Final
injectability is always decided against live session state at the moment the
hook fires.

### 4.1 Gate Checks

#### Check 1 — Similarity Floor

```
candidate.similarity >= config.similarity_threshold
```

The candidate's embedding similarity to the current context must meet a minimum
threshold. This is **necessary but never sufficient alone**. High similarity
does not imply injection value — the candidate might be redundant, stale, or
contextually inappropriate.

Default threshold: `0.72`

#### Check 2 — Not In Context

```
NOT recoverable_from_context(candidate, current_window)
```

The candidate's information must not already be present or trivially derivable
from the current context window. This check prevents the most common failure
mode: injecting something the model already knows from its immediate context.

Implementation: lightweight token-overlap heuristic against the last N turns,
supplemented by embedding comparison against the rolling context summary.

#### Check 3 — Temporal Confidence

```
candidate.similarity - (age_in_days * config.age_penalty_per_day) >= config.similarity_threshold
```

Older memories require higher raw similarity to pass. This models the
intuition that distant memories should surface only when strongly relevant.
A memory from yesterday at 0.73 similarity passes. The same memory from six
months ago at 0.73 does not — it would need to score higher to overcome the
age penalty.

Default penalty: `0.002` per day. A memory 100 days old faces a 0.20
penalty, requiring raw similarity of 0.92 to clear a 0.72 threshold.

#### Check 4 — Topic Frequency

```
topic_injection_count(candidate.topic, window=last_10_turns) < config.topic_frequency_cap
```

Suppress candidates whose topic has already been injected recently. This
prevents topical drift, where a single strong topic dominates injection and
pulls the conversation away from its natural trajectory.

Default cap: 2 injections of the same topic within a 10-turn window.

#### Check 5 — Net New Information

```
net_new_score(candidate, recent_turns) >= config.net_new_threshold
```

The candidate must contribute information not already present in the most
recent turns. This overlaps with Check 2 but operates at a finer granularity:
Check 2 asks "is it in the window?" while Check 5 asks "does it add anything
the model hasn't already been working with?"

Implementation: compare candidate content against the union of recent turn
embeddings. Score represents the fraction of candidate information that is
novel.

Default threshold: `0.85` (at least 85% of the candidate must be new).

#### Check 6 — Branch Contamination Guard

```
IF candidate.branch_id != active_branch_id
   AND branch_age(active_branch_id) < config.branch_maturity_turns
THEN REJECT
```

Young branches (those within their first few turns of divergence) must be
protected from cross-branch injection to preserve epistemic independence.
Injecting memories from another branch into a young branch undermines the
purpose of branching — exploring an alternative line of reasoning without
contamination.

After a branch matures (exceeds the configured turn threshold), cross-branch
injection is permitted.

Default maturity: `4` turns.

#### Check 7 — Confusion Headroom

```
confusion_tier(session) NOT IN [CRITICAL, FULL_STOP]
```

When the session confusion score reaches CRITICAL or FULL_STOP, standard
injection is suspended entirely. At these tiers, the model is already
struggling with its existing context; adding more information would
compound the problem.

Note: this check applies only to standard injection. Certain bypass types
(see Section 7) may override it.

#### Check 8 — Recency Flood Suppression

```
NOT is_recent_output(candidate, window=config.recency_flood_window)
```

Suppress candidates that closely match the model's own recent output. Without
this check, the system can enter a feedback loop: the model produces output,
that output gets chunked and embedded, and Anamnesis immediately re-injects
it as a "memory." The model sees its own words reflected back and treats them
as confirmation.

Default window: `5` turns.

### 4.2 Gate Evaluation Order

The checks are ordered by computational cost (cheapest first) to enable
early exit:

1. Recency flood (bit-flag check against recent output hashes)
2. Not in context (token overlap heuristic — fast path)
3. Confusion headroom (single score comparison)
4. Topic frequency (counter lookup)
5. Branch contamination (branch metadata check)
6. Similarity floor (pre-computed during retrieval or preparation)
7. Temporal confidence (arithmetic on similarity + age)
8. Net new information (embedding comparison — most expensive)

---

## 5. Prepared Injection Architecture

Anamnesis uses a two-phase architecture:

1. **Preparation phase** — background workers precompute candidate injections
   before a hook opportunity appears.
2. **Opportunity phase** — when a hook fires, Anamnesis applies live gating,
   freshness checks, final ranking, and payload delivery.

This design preserves conservative injection behavior while removing most of
the avoidable retrieval and formatting latency from the hook path.

### 5.1 Preparation Phase

Background preparers create candidates from fresh or newly relevant memory
artifacts and stage them into hook-scoped ready queues.

Four preparation modes are expected:

#### 5.1.1 Recency Preparation

Freshly written or updated artifacts are immediately evaluated for near-term
injectability. Typical examples include:

- newly stored chunks from the current session
- newly enriched correction events
- fresh procedural notes
- fresh self-narrative outputs
- newly marked compaction-survival items

#### 5.1.2 Predictive Preparation

Augur predicts likely next requests, session arcs, and next-session openings.
Anamnesis (or a colocated prefetch worker) uses those predictions to retrieve,
rank, and prebuild likely injection candidates ahead of time.

#### 5.1.3 Hook-Semantic Preparation

Each hook type has characteristic informational needs:

- `SessionStart` → open loops, last working state, session brief, likely next focus
- `UserPromptSubmit` → local continuity, recent correction, user preference, relevant topic context
- `PostToolUse` → prior similar outcomes, validated constraints, procedural notes, likely next step
- `PreCompact` → compaction-vulnerable chunks, active objective, unresolved loops

Prepared queues should reflect those different opportunity profiles.

#### 5.1.4 Invalidation and Refresh

Prepared candidates are invalidated or refreshed when new information makes
prior preparation stale, including:

- new corrections
- topic merges or summary updates
- branch divergence or maturation
- confusion-tier changes
- new Psyche or Praxis outputs
- candidate expiry

### 5.2 Opportunity Phase

At hook time, Anamnesis should prefer already prepared candidates and fall back
to direct retrieval only when needed.

The hook-time objective is to remain lightweight:

- consume ready candidates for the current session, hook type, and branch
- discard expired or stale entries
- merge any bypass-channel injections
- apply the live gate
- rank the survivors
- inject zero or more memories

---

## 6. Processing Pipeline

The full pipeline executes on each hook event. Steps are numbered for
reference; the implementation may fuse or reorder steps as an optimization
as long as the observable behavior is preserved.

```
 1. CHECK cooldown state → if cooldown active, RETURN empty (fastest exit)
 2. EMBED current hook context (tool result, user prompt, or compaction summary)
 3. UPDATE confusion score with latest signal components
 4. CHECK confusion tier:
      - HIGH or CRITICAL → restrict to priority injections only
      - FULL_STOP → suspend all injection, RETURN empty
 5. READ hook-scoped ready queue:
      - Session + hook + branch filtered candidates
      - Drop expired / stale entries
      - Limit: top-K by preparation score
 6. CHECK Augur prefetch cache:
      - If cache contains candidates for current context, merge with ready queue
      - Prefetch candidates skip retrieval work already done
      - Apply prefetch_hit_threshold for cache acceptance
 7. FALL BACK to direct retrieval only if prepared coverage is insufficient:
      - QUERY fast index for in-session memories
      - QUERY slow index for cross-session/topic memories (suspended at ELEVATED and above)
 8. APPLY conjunctive gate to each candidate:
      - Run all 8 checks in cost order
      - Record rejection reason for each failed candidate (diagnostics)
 9. RANK passing candidates by composite score:
      - similarity * 0.40 + recency * 0.25 + topic_relevance * 0.20
        + somatic_alignment * 0.15
      - Respect per-turn injection limit
10. BUILD injection payload:
      - Format each selected memory as XML (see Section 9)
      - Attach metadata: relevance, source, age, topic, somatic register
11. RECORD injection event:
      - Write to injection_log: session_id, turn_index, candidate_id,
        similarity, gate_pass (bool), rejection_reason (if any), timestamp
12. RETURN injection payload to hook dispatcher
```

### 6.1 Cooldown

After an injection, Anamnesis enters a brief cooldown for that specific topic.
This prevents rapid-fire injection of related memories across consecutive hook
events within the same turn.

Cooldown duration: `1 turn` (not wall-clock time).

### 6.2 Embedding Strategy

The embedding step (step 2) produces a single vector representing the current
context. For `PostToolUse` events, this is the tool result summary. For
`UserPromptSubmit`, the user prompt. For `PreCompact`, the compaction summary.
For `SessionStart`, the session brief (if Augur provides one) or the initial
user prompt.

The embedding model must match the model used to embed stored chunks. Model
version mismatches will degrade similarity scores silently and are treated as
a configuration error.

### 6.3 Ready Queue Refresh Worker

Anamnesis includes, or is paired with, a background refresh worker that keeps
hook-scoped ready queues current.

Its responsibilities are:

- consume precompute-trigger events
- generate or refresh prepared candidates
- pre-render XML payloads when possible
- expire stale entries
- maintain a bounded queue size per session and hook type
- preserve branch isolation in candidate staging

This worker is not allowed to inject. It only prepares.

### 6.4 Fallback Policy

Prepared queues are an optimization, not a correctness dependency.

If the ready queue is empty, stale, or unavailable, Anamnesis falls back to
live retrieval and proceeds normally. The system must remain functionally
correct without any prepared candidates.

---

## 7. Injection Types and Gate Bypass Rules

Not all injections pass through the full conjunctive gate. Certain injection
types carry enough intrinsic justification to bypass some or all gate checks.
Bypass is not "skipping safety" — it reflects the fact that the injection
source has already performed equivalent validation.

| Type                    | Gate applied | Bypass condition                        |
| ----------------------- | ------------ | --------------------------------------- |
| Standard memory         | Full gate    | Never bypassed                          |
| Branch synthesis        | Bypassed     | All tiers except CRITICAL and FULL_STOP |
| Compaction survival     | Bypassed     | All tiers except CRITICAL and FULL_STOP |
| Psyche self-narrative   | Bypassed     | Always — unconditional                  |
| Augur session brief     | Bypassed     | `SessionStart` event only               |
| Praxis procedural note  | Full gate    | Never bypassed                          |
| Memory steering prompt  | N/A          | Triggered by confusion signal rise      |

### 7.1 Type Descriptions

**Standard memory.** A chunk retrieved from the `chunks` table via semantic
similarity or staged in the ready queue from prior retrieval. Must pass all 8
gate checks. This is the default and most common injection type.

**Branch synthesis.** A synthesized summary produced when branches merge or
when a branch conclusion is reached. The synthesis sidecar (Themis or
equivalent) has already validated relevance; Anamnesis injects it directly.
Suppressed only at CRITICAL or FULL_STOP confusion.

**Compaction survival.** During `PreCompact`, certain memories are flagged as
"must survive compaction." These may be prepared in advance and are injected
into the post-compaction context to preserve continuity. The compaction process
itself decides what survives; Anamnesis is the delivery mechanism.

**Psyche self-narrative.** Psyche may push identity-critical memories through
a direct channel that bypasses all gates unconditionally. This is the only
fully unconditional bypass. It exists because identity coherence is a
prerequisite for all other reasoning — without it, the gate checks themselves
become unreliable.

**Augur session brief.** At `SessionStart`, Augur may provide a pre-computed
session brief containing predicted-relevant memories. This brief is injected
once, at session start only, and never repeated.

**Praxis procedural note.** Skill-related notes authored by Praxis (e.g.,
"when using the X API, always set header Y"). These pass the full gate because
procedural relevance is context-dependent and cannot be pre-validated.

**Memory steering prompt.** Not a memory injection per se, but a meta-prompt
injected when the confusion signal rises. It gently reminds the model of its
current objective and recent progress. See Section 8.3.

---

## 8. Confusion Scoring

The confusion score is an advisory signal that modulates injection behavior.
It is **not** a control system — it does not autonomously suppress injection.
It provides Anamnesis with a signal about the model's current epistemic state,
which Anamnesis uses as one input (gate check 7) among many.

### 8.1 Signal Components

| Component                   | Weight | Description                                              |
| --------------------------- | ------ | -------------------------------------------------------- |
| Self-contradiction rate     | 0.30   | Frequency of statements that contradict prior turns      |
| Reasoning inflation ratio   | 0.25   | Ratio of reasoning tokens to conclusion tokens           |
| Tool call repetition        | 0.20   | Repeated identical or near-identical tool invocations     |
| Epistemic hedge frequency   | 0.15   | Density of hedging language ("perhaps", "might", "maybe") |
| Human correction rate       | 0.10   | Frequency of user corrections or redirections            |

The composite score is a weighted sum, normalized to `[0.0, 1.0]`.

### 8.2 Confusion Tiers

| Tier       | Score range  | Injection behavior                                          |
| ---------- | ------------ | ----------------------------------------------------------- |
| NOMINAL    | 0.00 — 0.20 | Normal operation. Up to `max_injections_per_turn` allowed.  |
| GUARDED    | 0.20 — 0.40 | Reduced injection budget (default: 1 per turn).             |
| ELEVATED   | 0.40 — 0.60 | Cross-session (slow index) queries suspended.               |
| HIGH       | 0.60 — 0.80 | Only priority injections (bypass types). Inject `<memory_steering>` prompt. |
| CRITICAL   | 0.80 — 0.95 | Only Psyche self-narrative. All other injection suspended.  |
| FULL_STOP  | 0.95 — 1.00 | All injection suspended. Anamnesis returns empty on every hook. |

### 8.3 Memory Steering Prompt

When confusion transitions upward into HIGH tier, Anamnesis injects a
`<memory_steering>` block:

```xml
<memory_steering>
  You have been working on: [current objective summary].
  Your most recent progress: [last successful tool result or conclusion].
  Consider pausing to verify your current approach before continuing.
</memory_steering>
```

This is a gentle nudge, not a command. The model may ignore it. The steering
prompt is injected at most once per tier transition (not on every turn at HIGH).

### 8.4 Score Decay

Confusion scores decay toward zero when contradicting signals arrive:
successful tool calls, user affirmations, coherent multi-step reasoning. The
decay rate is `0.05` per turn of positive signal. This prevents a single
confusing exchange from permanently elevating the score.

### 8.5 Prepared Candidate Restrictions Under Confusion

Confusion-tier transitions may invalidate previously prepared candidates.
For example:

- entering `ELEVATED` invalidates prepared cross-session candidates that depend
  on slow-index retrieval
- entering `HIGH` restricts ready queues to priority or bypass candidates only
- entering `CRITICAL` clears all standard prepared candidates from active use

Preparedness never overrides current confusion posture.

---

## 9. Injection Format

All injected memories use a consistent XML format. The format is designed to
be parseable by both the model (for integration) and by downstream logging
(for evaluation).

### 9.1 Standard Memory Block

```xml
<memory relevance="0.87" source="prior_session" age="4d"
        topic="jwt_auth" somatic_register="collaborative"
        chunk_id="a1b2c3d4" turn_origin="42">
  When implementing JWT refresh tokens last week, we settled on a dual-token
  approach: short-lived access tokens (15 min) paired with longer-lived
  refresh tokens (7 days) stored in HttpOnly cookies. The rationale was to
  balance security against UX friction for the dashboard app.
</memory>
```

### 9.2 Attribute Definitions

| Attribute          | Type    | Description                                                    |
| ------------------ | ------- | -------------------------------------------------------------- |
| `relevance`        | float   | Composite relevance score (0.0 to 1.0)                        |
| `source`           | enum    | `current_session`, `prior_session`, `branch_synthesis`, `compaction`, `procedural`, `psyche` |
| `age`              | string  | Human-readable age: `2h`, `4d`, `3w`, `6mo`                   |
| `topic`            | string  | Primary topic label from knowledge graph                       |
| `somatic_register` | string  | Affective register from SSS: `collaborative`, `frustrated`, `exploratory`, `focused`, etc. |
| `chunk_id`         | string  | Reference to source chunk (for traceability)                   |
| `turn_origin`      | integer | Turn index where the memory was originally created             |

### 9.3 Compaction Survival Block

```xml
<memory_survival priority="high" reason="active_objective">
  The user's stated goal for this session is to refactor the authentication
  module to support OAuth2 PKCE flow. Three files have been modified so far:
  auth/provider.ts, auth/pkce.ts, and auth/callback.ts.
</memory_survival>
```

### 9.4 Memory Steering Block

```xml
<memory_steering confusion_tier="HIGH" turn="47">
  You have been working on: refactoring auth module for OAuth2 PKCE.
  Your most recent progress: successfully implemented the code verifier
  generation in auth/pkce.ts.
  Consider pausing to verify your current approach before continuing.
</memory_steering>
```

### 9.5 Psyche Self-Narrative Block

```xml
<memory_psyche channel="self_narrative" priority="identity">
  Prior session pattern: when working on security-sensitive code, you tend
  toward over-engineering. The user has previously expressed preference for
  simpler solutions with clear documentation of trade-offs.
</memory_psyche>
```

---

## 10. Outputs

Anamnesis produces four categories of output.

### 10.1 Injection Payload

The primary output: zero or more XML memory blocks delivered to the hook
dispatcher for insertion into the model's context. The payload is attached
via `systemMessage` or `additionalContext` depending on the hook type:

- `SessionStart` → `systemMessage` (appears before first user turn)
- `UserPromptSubmit` → `additionalContext` (appended after user message)
- `PostToolUse` → `additionalContext` (appended after tool result)
- `PreCompact` → `systemMessage` (appears in post-compaction context)

### 10.2 Injection Event Records

Every injection attempt (successful or rejected) is logged to the
`injection_log` table:

```sql
CREATE TABLE injection_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions(id),
    turn_index      INTEGER NOT NULL,
    chunk_id        UUID REFERENCES chunks(id),
    candidate_id    UUID,
    injection_type  TEXT NOT NULL,
    similarity      FLOAT,
    gate_passed     BOOLEAN NOT NULL,
    rejection_reason TEXT,          -- NULL if gate_passed = true
    confusion_tier  TEXT NOT NULL,
    latency_ms      INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_injection_log_session ON injection_log(session_id, turn_index);
CREATE INDEX idx_injection_log_chunk   ON injection_log(chunk_id);
CREATE INDEX idx_injection_log_candidate ON injection_log(candidate_id);
```

### 10.3 Confusion Score Updates

After each hook event, Anamnesis writes the updated confusion score to
session metadata. This is consumed by other sidecars (notably Augur, which
adjusts its prefetch strategy based on confusion tier).

### 10.4 Prepared Candidate Records

Prepared candidates may be stored in memory or in a short-lived durable store.
If persisted, a structure like the following is recommended:

```sql
CREATE TABLE memory_injection_candidate (
    candidate_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID NOT NULL,
    master_session_id UUID NOT NULL,
    hook_type         TEXT NOT NULL,
    source_kind       TEXT NOT NULL,
    source_id         UUID NOT NULL,
    payload_xml       TEXT NOT NULL,
    similarity_score  FLOAT,
    novelty_score     FLOAT,
    somatic_alignment FLOAT,
    topic_id          UUID,
    branch_id         UUID,
    predicted_by_augur BOOLEAN NOT NULL DEFAULT false,
    consumed_at       TIMESTAMPTZ,
    expires_at        TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_memory_injection_candidate_live
    ON memory_injection_candidate(session_id, hook_type, expires_at)
    WHERE consumed_at IS NULL;
```

This table is a staging layer only. It is not part of the durable memory
corpus and should be aggressively expired.

---

## 11. Contracts

### 11.1 Reads

| Resource                  | Access type       | Frequency          |
| ------------------------- | ----------------- | ------------------ |
| `chunks`                  | Vector similarity | Hook fallback path / preparation path |
| `topic_nodes`             | Graph traversal   | Hook fallback path / preparation path |
| `topic_summaries`         | Keyed lookup      | Hook fallback path / preparation path |
| `procedural_notes`        | Keyed lookup      | `PostToolUse` / preparation path |
| `sss_snapshots`           | Latest snapshot    | Every hook event   |
| `behavioral_sequences`    | Pattern match      | Confusion scoring  |
| Augur prefetch cache      | Cache read         | Every hook event   |
| Hook-scoped ready queue   | Candidate staging  | Every hook event   |
| `memory_injection_candidate` | Candidate staging | Optional persistent ready queue |

### 11.2 Writes

| Resource         | Access type | Frequency        |
| ---------------- | ----------- | ---------------- |
| `injection_log`  | INSERT      | Every hook event |
| `memory_injection_candidate` | INSERT / UPDATE / DELETE | Background preparation and expiry |

### 11.3 Receives (Push Channels)

| Source | Channel             | Payload                     | Gate behavior     |
| ------ | ------------------- | --------------------------- | ----------------- |
| Psyche | `self_narrative`    | Identity-critical memories  | Unconditional bypass |
| Augur  | `prediction_ready`  | Predicted retrieval context | Preparation input |
| Kairos | `topic_update`      | Summary / topic refresh     | Preparation input |
| Praxis | `procedural_update` | Note refresh                 | Preparation input |
| Engram/Eidos | `memory_changed` | Fresh chunk or enrichment change | Preparation input |

### 11.4 Does NOT Write

Anamnesis never writes to `chunks`, `topic_nodes`, or any other durable memory
store. It is a consumer of stored memory and a manager of ephemeral prepared
candidate state. The write path belongs to memory-producing sidecars and the
knowledge graph builder.

---

## 12. Operational Semantics

### 12.1 Failure Modes

| Failure                     | Behavior                                          |
| --------------------------- | ------------------------------------------------- |
| Embedding model unavailable | Skip injection. Log warning. Return empty.        |
| Database query timeout      | Skip injection. Log warning. Return empty.        |
| Augur cache miss            | Proceed with ready queue / direct queries. No degradation. |
| Ready queue unavailable     | Fall back to direct retrieval. Proceed normally.  |
| Prepared candidate stale    | Drop candidate. Continue with remaining candidates. |
| SSS snapshot unavailable    | Omit somatic register from ranking. Proceed.      |
| Psyche channel error        | Log error. Self-narrative injection deferred.      |
| Malformed hook payload      | Log error. Return empty.                          |

The overriding principle: **never block the agent runtime.** Anamnesis
operates on a best-effort basis. The agent must always be able to proceed
without injection.

### 12.2 Idempotency

Injection is idempotent within a turn. If the same hook event is delivered
twice (e.g., due to retry logic), Anamnesis produces the same injection
payload and deduplicates the injection_log entry.

Prepared candidates are also idempotent: regenerating a candidate for the same
session / hook / source should replace or supersede the old candidate rather
than multiply identical staged entries.

### 12.3 Ordering Guarantees

Within a single turn, hook events are processed in the order they arrive.
Anamnesis does not reorder events. If `PostToolUse` arrives before
`UserPromptSubmit` (which should not happen but might under race conditions),
Anamnesis processes them in arrival order and logs a warning.

Background preparation is eventually consistent. Ready queues may briefly lag
behind newly written memories. This is acceptable because the fallback path
remains available.

### 12.4 Context Window Awareness

Anamnesis monitors `context_window_usage` from the hook payload. When usage
exceeds 80%, injection budget is halved (rounded down, minimum 1). When usage
exceeds 95%, only compaction survival and Psyche self-narrative injections
are permitted.

### 12.5 Ready Queue Sizing

Ready queues must remain small and hot.

Recommended defaults:

- max 10 prepared candidates per session per hook type
- max TTL of 3 turns for inter-turn candidates
- max TTL of 1 session for `SessionStart` candidates
- immediate invalidation on explicit contradiction or source supersession

This prevents the prepared layer from turning into a shadow memory store.

---

## 13. Evaluation Metrics

| Metric                      | Target   | Measurement method                          |
| --------------------------- | -------- | ------------------------------------------- |
| Injection latency p50       | < 200 ms | Instrumented timing in pipeline             |
| Injection latency p95       | < 500 ms | Instrumented timing in pipeline             |
| Prepared-path hit rate      | > 50%    | Hook events satisfied primarily from ready queues |
| Prefetch cache hit rate     | > 40%    | Cache hits / total queries (when Augur active) |
| Injection helpfulness rate  | > 70%    | Human doesn't correct or override post-injection |
| Gate rejection rate         | 60 — 80% | `injection_log` where `gate_passed = false` |
| False positive rate         | < 15%    | Injections explicitly contradicted by user  |
| Confusion score accuracy    | > 65%    | Correlation with human-labeled confusion    |
| Context window overhead     | < 5%     | Injection tokens / total context tokens     |
| Stale candidate drop rate   | Informational | Prepared candidates expired or invalidated before use |

### 13.1 Metric Collection

Metrics are collected per-session and aggregated daily. The `injection_log`
table provides the raw data for most metrics. Helpfulness rate and false
positive rate require human annotation (sampled, not exhaustive). Prepared-path
metrics additionally require instrumentation on candidate creation, expiry,
consumption, and fallback usage.

### 13.2 Alerting Thresholds

| Condition                           | Alert level |
| ----------------------------------- | ----------- |
| p95 latency > 800 ms (sustained)   | WARNING     |
| Prepared-path hit rate < 25%        | WARNING     |
| Gate rejection rate < 50%           | WARNING     |
| Gate rejection rate > 90%           | WARNING     |
| Helpfulness rate < 50%              | ERROR       |
| Injection causing agent stall       | CRITICAL    |

---

## 14. Configuration

```yaml
anamnesis:
  # Master switch
  enabled: true

  # Gate thresholds
  similarity_threshold: 0.72
  net_new_threshold: 0.85
  prefetch_hit_threshold: 0.80

  # Injection budget
  max_injections_per_turn: 3
  max_injections_guarded: 1
  topic_frequency_cap: 2
  topic_frequency_window: 10    # turns

  # Temporal weighting
  age_penalty_per_day: 0.002

  # Recency flood
  recency_flood_window: 5       # turns

  # Branch protection
  branch_maturity_turns: 4

  # Confusion scoring
  confusion_check: true
  confusion_decay_rate: 0.05    # per turn of positive signal
  confusion_weights:
    self_contradiction: 0.30
    reasoning_inflation: 0.25
    tool_repetition: 0.20
    epistemic_hedging: 0.15
    human_correction: 0.10

  # Context window awareness
  context_budget_reduction_threshold: 0.80
  context_emergency_threshold: 0.95

  # Cooldown
  cooldown_turns: 1

  # Ranking weights
  ranking:
    similarity: 0.40
    recency: 0.25
    topic_relevance: 0.20
    somatic_alignment: 0.15

  # Prepared injection queues
  prepared_injection:
    enabled: true
    max_candidates_per_hook: 10
    inter_turn_ttl_turns: 3
    session_start_ttl_sessions: 1
    refresh_batch_size: 20
    allow_direct_fallback: true
    pre_render_xml: true

  # Logging
  log_rejections: true
  log_candidates: false         # Enable for debugging only — high volume
```

### 14.1 Configuration Precedence

Configuration values are resolved in the following order (highest priority
first):

1. Session-level overrides (set by Augur or operator)
2. User profile settings
3. YAML configuration file
4. Hardcoded defaults (values listed above)

### 14.2 Hot Reloading

Configuration changes are picked up on the next hook event. No restart
required. Changes to `enabled` take effect immediately. Changes to
thresholds take effect on the next gate evaluation.

Changes affecting prepared queues (TTL, max candidates, refresh batch size)
take effect on the next refresh cycle.

---

## 15. Interaction with Other Sidecars

### 15.1 Augur (Prefetch Provider)

Augur predicts what the user will ask next and pre-computes injection
candidates. Anamnesis checks the prefetch cache and/or accepts prediction-ready
signals during preparation.

The contract: Augur writes candidates or prediction contexts to a shared cache
or push channel. Anamnesis converts those into hook-scoped ready candidates and
applies its own gate checks at delivery time (prefetch does not bypass the gate
for standard memories).

### 15.2 Psyche (Self-Narrative Source)

Psyche maintains the agent's self-model and may push identity-critical
memories through a direct channel. These bypass all gates unconditionally.
Anamnesis is the delivery mechanism; Psyche decides what to push and when.

The contract: Psyche writes to a queue that Anamnesis drains on each hook
event. Messages in the queue are injected in FIFO order, subject only to
the `FULL_STOP` confusion tier (which suspends even Psyche injection in
one strict interpretation — but current design allows Psyche to override
that restriction if desired by policy).

### 15.3 Praxis (Procedural Source)

Praxis authors procedural notes that encode learned skills and tool-usage
patterns. These notes are stored in `procedural_notes` and retrieved by
Anamnesis via standard gate evaluation or staged into ready queues on
`PostToolUse` opportunities when applicable.

### 15.4 Memory Authors and Enrichment Sidecars

Memory-producing sidecars write chunks, enrich them, and build structure.
Anamnesis consumes those artifacts and prepares them for possible injection.
The database and shared caches are the contract boundaries.

### 15.5 SSS (Somatic State)

Anamnesis reads the latest SSS snapshot to obtain the current somatic
register. This register is used in two ways:

1. **Ranking**: somatic alignment between the candidate's origin register
   and the current register contributes to the composite ranking score.
2. **Formatting**: the `somatic_register` attribute in the injection XML
   gives the model a cue about the emotional context of the memory.

---

## 16. Security and Privacy Considerations

### 16.1 Injection Provenance

Every injected memory carries a `chunk_id` linking it back to its origin.
This enables full traceability: given an injection event, you can trace it
to the original chunk, the session that produced it, and the user interaction
that generated it.

### 16.2 Cross-User Isolation

Anamnesis queries are scoped to the current user's memory store. There is no
mechanism for cross-user injection. The database query layer enforces row-level
security on the `chunks` table.

### 16.3 Injection Tampering

The injection payload is constructed by Anamnesis and delivered to the hook
dispatcher via an internal channel. It is not exposed to external input. The
XML format is generated, not parsed from external sources, eliminating
injection attacks via malformed XML.

### 16.4 Prepared Candidate Isolation

Prepared candidate state must inherit the same isolation guarantees as the
underlying memory corpus. Session IDs, user scope, and branch IDs must be
respected in staging and delivery so that prefetching never becomes a side
channel for cross-user or cross-branch contamination.

---

## 17. Future Considerations

These items are out of scope for the initial implementation but are noted
for future design iterations.

- **Multi-modal injection**: injecting image or audio memory references when
  the model supports multi-modal input.
- **Collaborative memory**: cross-user injection for team contexts, with
  explicit consent and access control.
- **Injection feedback loop**: using model self-reports ("that was helpful" /
  "that was irrelevant") to tune gate thresholds per-user.
- **Adaptive thresholds**: ML-driven threshold adjustment based on injection
  outcome data, replacing static configuration.
- **Streaming injection**: injecting memories mid-generation rather than
  pre-generation, enabling true "mid-thought recall."
- **Prepared-path learning**: automatically learning which hook types and
  source kinds most benefit from precomputation.

---

*End of specification.*
