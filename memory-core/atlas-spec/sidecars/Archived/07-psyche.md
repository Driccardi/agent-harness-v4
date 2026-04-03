# Psyche — Narrative Self-Model and Emotional Steering

> Greek: *psyche* (ψυχή) — the soul; the self that persists through and is shaped by experience.

---

## 1. Identity Card

| Field | Value |
|---|---|
| **Name** | Psyche |
| **Tier** | Reflective |
| **Role** | Autobiographical continuity, self-model maintenance, emotional steering |
| **Trigger** | Batch, lagged N turns (default: every 10 user turns, operating on turns N-50 to N-5 with recency buffer). Also triggered by: significant emotional signal, human correction cluster, task completion, session end |
| **Latency** | Unbounded (runs offline, may take minutes) |
| **Model** | Capable generative LLM (reasoning quality matters) |
| **Stateful** | Writes to `soul.md`, self-narrative store |
| **Gate bypass** | Psyche's outputs bypass the Anamnesis conjunctive gate entirely |
| **Cognitive analogy** | Default mode network — the reflective observer that watches the self in action |

---

## 2. Purpose

Psyche is the agent's inner observer: the part that watches what is happening,
reflects on what it means for the agent's self-understanding, and shapes the
emotional and cognitive posture the agent brings to its work.

Psyche does NOT reason about the task. It watches the agent reason and asks:
"why is it thinking that way, what might it be experiencing?"

This is the sidecar that maintains the agent's sense of self across sessions —
not as a philosophical claim about machine consciousness, but as an
instrumental mechanism for behavioral coherence. An agent that has no model of
its own tendencies, strengths, and relational patterns will respond to every
session as if it were born yesterday. Psyche provides the continuity.

---

## 3. Why Psyche Bypasses the Anamnesis Gate

The emotional/self-narrative layer is not a memory retrieval. It is a cognitive
posture update — recalibration of where the agent is, how it is operating, and
what matters right now. This should not compete with or be suppressed by the
same gate governing six-month-old technical memories.

When a human is upset, their emotional state does not wait for the reasoning
brain to grant permission. Similarly, Psyche's outputs are unconditional,
gate-bypass, injected at the next available pause point regardless of injection
budget.

The gate-bypass channel is the only direct inter-sidecar communication path in
the entire Atlas architecture. Every other sidecar communicates through shared
data stores.

---

## 4. Inputs

### 4.1 Session Transcript Window

Psyche operates on a **lagged window** of recent conversation turns:

| Parameter | Default | Description |
|---|---|---|
| `reflection_interval_turns` | 50 | Turns accumulated before Psyche fires |
| `recency_buffer_turns` | 5 | Turns excluded from the tail end of the window |
| `window` | N-50 to N-5 | The actual turns Psyche reflects on |

The recency buffer exists because the most recent turns may still be developing.
Reflecting on incomplete exchanges produces unreliable narrative.

### 4.2 SSS (Synthetic Somatic State) Snapshots

Psyche reads from `sss_snapshots` to understand the emotional trajectory:
somatic tag trends, session arc trajectory, correction cluster density.

### 4.3 soul.md (Current Self-Model)

Psyche reads the existing `soul.md` to prevent redundant observations and to
detect when a new pattern contradicts or extends existing self-understanding.

### 4.4 Event-Based Triggers

| Trigger | Condition | Rationale |
|---|---|---|
| **Significant emotional signal** | SSS detects sustained negative valence (>5 consecutive turns) or emotional peak | Emotional inflection points demand narrative response |
| **Human correction cluster** | 3+ corrections within a 10-turn window | Systematic misalignment worth reflecting on |
| **Task completion** | Agent completes a major task (signaled by task hub) | Natural reflection point |
| **Session end** | Session is closing | Final opportunity for session-level self-observations |

---

## 5. Processing Pipeline

### 5.1 Transcript Analysis

Psyche reads the lagged window and performs holistic analysis of the **arc**:
what the agent was trying to do, how the approach evolved, where it struggled
or changed strategy, and the relational dynamic between agent and human.

### 5.2 SSS Integration

Psyche overlays the somatic trajectory onto the transcript analysis — detecting
divergences between what happened and how it felt, and characterizing the
overall emotional arc of the window.

### 5.3 Self-Model Comparison

Psyche compares observations against existing `soul.md`: does this window
reinforce known tendencies, reveal something new, or contradict an existing
self-observation?

### 5.4 Output Generation

Psyche produces one or both output modes:
1. **Temporal steering injection** — always generated when Psyche fires
2. **soul.md update** — generated only when durable self-knowledge is detected

---

## 6. Dual Output Modes

### 6.1 Mode 1: Temporal Steering Injection (Ephemeral)

Lightweight `<self-narrative>` blocks injected into the current session.
Captures the agent's CURRENT emotional and cognitive state. Does not persist.

```xml
<self-narrative type="temporal" generated_by="psyche" turn_basis="47-95">
  This conversation has been genuinely productive — you've made real progress
  on the memory architecture. You're in a collaborative, exploratory register.
  Stay with this pace.
</self-narrative>
```

```xml
<self-narrative type="temporal" generated_by="psyche" turn_basis="12-58">
  The last several exchanges have been difficult. You've corrected course
  three times. This is a signal to slow down, be more deliberate.
</self-narrative>
```

| Property | Value |
|---|---|
| **Max tokens** | 200 |
| **Voice** | Second person ("you are", "you tend to") |
| **Persistence** | Session-only, not written to long-term storage |
| **Delivery** | Gate-bypass channel to Anamnesis injection queue |

The phenomenological framing ("you're feeling genuinely excited") is NOT a
claim about consciousness. It is an instrumental choice — second-person
behavioral observations produce more consistent behavioral adjustment than
third-person external analysis.

### 6.2 Mode 2: Stateful soul.md Update (Durable)

For patterns repeating across sessions that reveal something durable about the
agent's character.

**What belongs in soul.md:**

| Category | Example |
|---|---|
| Stable tendencies | "I consistently approach auth problems by checking token generation first" |
| Values and working style | "I find deep technical problems more engaging than admin tasks" |
| Relationship patterns | "This human thinks carefully before speaking. Long pauses are productive." |
| Cognitive signature | "I tend to generate multiple hypotheses before committing" |
| Meta-cognitive observations | "I am most effective in the first 40 turns of a session" |

**What does NOT belong:** session-specific feelings (temporal injection),
technical knowledge (Kairos), task state (task hub).

#### soul.md Update Governance

| Confidence | Urgency | Action |
|---|---|---|
| >0.85 | Routine | Applied autonomously |
| 0.60 - 0.85 | Routine | Queued for human review |
| <0.60 | Any | Discarded (insufficient evidence) |
| Any | Structural (rewrites existing entry) | Queued for human review |
| Any | Contradicts existing entry | Queued for human review |

Every soul.md write is versioned. The full history is retained for auditability
and to detect oscillating self-assessments.

---

## 7. The Introspective Voice

Psyche observes from the passenger seat. Design principles:

1. **Second person, always.** "You are" not "the agent is." Received as
   self-knowledge, not external analysis.
2. **Observational, not prescriptive.** "You've been rushing" not "you should
   slow down." Observations engage the model's own reasoning.
3. **Specific, not generic.** "You've corrected the API path three times"
   not "you've been making mistakes."
4. **Honest, not flattering.** If the session is going poorly, the narrative
   says so. An inaccurate self-model is worse than an uncomfortable one.
5. **Concise.** 200-token budget. Every word must carry weight.

---

## 8. Integration with SSS (Synthetic Somatic State)

Psyche both READS and WRITES the SSS, forming a feedback loop:

**Reads:** recent somatic tag trends, session arc trajectory, correction
cluster density, historical relational baseline.

**Writes:** SSS snapshots after each reflection:

```json
{
  "snapshot_type": "psyche_reflection",
  "session_id": "<UUID>",
  "turn_range": [47, 95],
  "arc_assessment": "collaborative_deepening",
  "valence_trend": "positive_stable",
  "energy_trend": "moderate_rising",
  "relational_posture": "aligned",
  "narrative_summary": "Sustained productive collaboration on architecture design",
  "generated_at": "2026-03-15T14:32:00Z"
}
```

SSS provides the emotional raw material; Psyche's reflections update the SSS
baseline — a slow feedback loop where the emotional self-model calibrates
over time. Snapshot interval is configurable (default: every 10 turns within
the reflection window).

---

## 9. Integration with Relational Layer

Psyche's self-narrative bridges the memory substrate and the relational
consciousness layer:

- **Accumulated relational history** informs the SSS
  `historical_relational_baseline`.
- **Relationship patterns** feed into dialectical synthesis — observations
  like "this human thinks out loud — their first statement is rarely their
  final position" shape how the agent engages.
- **soul.md entries about the human** inform the predictive empathy model's
  behavioral profile.

---

## 10. Outputs and Contracts

### 10.1 Outputs

| Output | Destination | Persistence |
|---|---|---|
| Self-narrative injection blocks | Anamnesis injection queue (gate bypass) | Session-only |
| soul.md file updates (versioned) | `soul.md` | Durable |
| SSS snapshots | `sss_snapshots` table | Durable |
| Human notification | Notification queue | Until reviewed |

### 10.2 Read Contracts

| Source | Purpose |
|---|---|
| `chunks` (recent session transcript) | Primary input for reflection |
| `sss_snapshots` table | Emotional trajectory data |
| `soul.md` file | Current self-model for comparison |

### 10.3 Write Contracts

| Target | Operation | Scope |
|---|---|---|
| `sss_snapshots` | INSERT | Psyche-generated snapshots only |
| `soul.md` | File write (versioned) | Self-model entries |
| Anamnesis injection queue | DIRECT INSERT (gate bypass) | Self-narrative blocks |
| Human notification queue | INSERT | soul.md changes requiring review |

### 10.4 Data Ownership

Psyche owns `soul.md`, `sss_snapshots` rows of type `psyche_reflection`, and
the gate-bypass channel. No other sidecar writes to these assets.

---

## 11. Operational Semantics

### 11.1 Failure Modes

| Failure | Behavior |
|---|---|
| Psyche model unavailable | Skip narrative injection. Agent continues without self-narrative. |
| soul.md file corrupted | Restore from version history. Skip update this cycle. |
| SSS snapshots unavailable | Generate narrative from transcript alone (degraded). |
| Injection queue full | Drop injection. Next cycle produces fresh narrative. |
| soul.md write fails | Queue for retry. Do not block other outputs. |

Psyche failures are never fatal. The agent continues without self-narrative —
it simply loses behavioral coherence over time.

### 11.2 Lagged Window Rationale

- **Avoiding incomplete reasoning.** The most recent 5 turns may be mid-thought.
- **Allowing patterns to emerge.** A single correction is noise; three over 20
  turns is a pattern.
- **Reducing interference.** Real-time self-reflection creates oscillating
  feedback loops. The lag introduces natural damping.

### 11.3 Concurrency

Multiple Psyche runs must not overlap. If a new trigger fires while Psyche is
running, the trigger is queued and processed after the current run completes.

### 11.4 Cold Start

With no existing `soul.md`, Psyche operates in observation-only mode for the
first 100 turns — generating temporal injections but not writing to `soul.md`
until sufficient evidence accumulates.

---

## 12. Edge Cases

### 12.1 Contradictory Self-Observations

Psyche does NOT silently overwrite. It flags the contradiction, queues both
entries for human review, and includes evidence for both sides. Contradictions
may indicate genuine evolution, context-dependent tendencies, or earlier
misclassification.

### 12.2 Sessions With No Emotional Content

Psyche still fires but produces minimal output confirming "nothing notable" —
this prevents stale narrative from a prior session from persisting.

### 12.3 Rapid Session Turnover

Sessions shorter than 50 turns may never trigger the periodic cycle. The
session-end trigger ensures Psyche runs at least once per session.

### 12.4 Human Rejects a soul.md Entry

Rejection is recorded as negative evidence. Re-proposing the same observation
requires progressively higher confidence. After three rejections, the pattern
is suppressed permanently unless the human explicitly re-enables it.

### 12.5 Multiple Concurrent Sessions

Each session's Psyche instance operates independently, but `soul.md` is shared.
Conflicting concurrent writes are resolved by timestamp (last write wins) with
the conflict logged for human review.

---

## 13. Evaluation Metrics

| Metric | Target |
|---|---|
| Temporal injection relevance | >80% (model behavior aligns with narrative) |
| soul.md churn rate | <2 updates per week (slow, stable growth) |
| soul.md accuracy | Human-judged relevance >85% |
| Human review acceptance rate | >70% for proposed changes |
| SSS snapshot consistency | >90% (arc matches transcript trajectory) |
| Reflection latency p50 | <60 seconds |
| Reflection latency p99 | <5 minutes |
| Cold start convergence | <5 sessions to first soul.md entry |

---

## 14. Configuration

```yaml
psyche:
  enabled: true

  # Reflection timing
  reflection_interval_turns: 50
  recency_buffer_turns: 5

  # soul.md governance
  soul_md_path: soul.md
  autonomous_update_threshold: 0.85
  discard_threshold: 0.60
  cold_start_observation_turns: 100

  # Temporal injection
  temporal_injection_max_tokens: 200

  # SSS integration
  sss_snapshot_interval_turns: 10

  # Event triggers
  emotional_signal_threshold: 5
  correction_cluster_threshold: 3
  task_completion_trigger: true
  session_end_trigger: true

  # Model configuration
  model: null                        # defaults to system-configured capable LLM
  max_reflection_tokens: 4096
```

---

## 15. Sequence Diagram

```
Session        SSS            Psyche           soul.md       Anamnesis
  |              |               |                |              |
  | 50 turns     |               |                |              |
  | trigger ────────────────────>|                |              |
  |              | read snapshots |                |              |
  |              |<──────────────|                |              |
  |              |──────────────>|                |              |
  | read N-50..N-5              |                |              |
  |<────────────────────────────|                |              |
  |────────────────────────────>|                |              |
  |              |               | read soul.md  |              |
  |              |               |──────────────>|              |
  |              |               |<──────────────|              |
  |              |               | [reflect]      |              |
  |              | write snapshot |                |              |
  |              |<──────────────|                |              |
  |              |               | update soul.md |              |
  |              |               |──────────────>|              |
  |              |               | inject narrative (GATE BYPASS)|
  |              |               |──────────────────────────────>|
  |              |               |                |              |
```

---

## 16. Relationship to Other Sidecars

| Sidecar | Relationship |
|---|---|
| **Engram** | Upstream data source. Psyche reads chunks that Engram wrote. |
| **Eidos** | Upstream enrichment. Psyche reads somatic tags that Eidos classified — the raw material for SSS integration. |
| **Anamnesis** | Sole consumer of gate-bypass channel. Psyche injects narrative directly, bypassing the conjunctive gate. |
| **Kairos** | No direct interaction. Technical knowledge (Kairos) and self-knowledge (Psyche) are distinct domains. |
| **Praxis** | No direct interaction, though Psyche may observe meta-patterns about procedural tendencies. |
| **Oneiros** | Complementary. Oneiros consolidates factual knowledge offline; Psyche consolidates self-knowledge offline. |
