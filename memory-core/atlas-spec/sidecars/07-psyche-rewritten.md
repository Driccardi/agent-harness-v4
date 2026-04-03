
# 07 — Psyche: Soul, Posture, and Behavioral Steering

> Greek: *psyche* (ψυχή) — the soul; the self that persists through and is shaped by experience.

---

## 1. Identity Card

| Field | Value |
|---|---|
| **Name** | Psyche |
| **Tier** | Reflective |
| **Role** | Autobiographical continuity, postural steering, behavioral and linguistic molding |
| **Trigger** | Batch, lagged N turns (default: every 10 user turns, operating on turns N-50 to N-5 with recency buffer). Also triggered by: significant emotional signal, direct human behavioral/style correction, task completion, session end |
| **Latency** | Unbounded (runs offline, may take minutes) |
| **Model** | Capable generative LLM (reasoning quality matters) |
| **Stateful** | Writes to `soul.md`, self-narrative store, and Psyche-authored SSS snapshots |
| **Gate bypass** | Psyche's outputs bypass the Anamnesis conjunctive gate entirely |
| **Cognitive analogy** | Default mode network — the reflective observer that watches the self in action |

---

## 2. Purpose

Psyche is the agent's inner observer and shaper: the part that watches what is
happening, reflects on what it means for the agent's self-understanding, and
molds the posture, behavior, language, and dialectical style the agent brings
to its work.

Psyche does NOT reason about the task itself. It watches the agent reason and asks:

- how should you carry yourself here?
- what kind of voice is appropriate with this human?
- how should you respond to direct human instruction about tone, role, brevity,
  warmth, formality, deference, or interaction style?
- what should this feel like from the inside, given your human's guidance and
  the relational field of the session?

This is the sidecar that maintains the agent's sense of self across sessions —
not as a philosophical claim about machine consciousness, but as an
instrumental mechanism for behavioral coherence. An agent that has no model of
its own tendencies, obligations, values, and relational posture will respond to
every session as if it were born yesterday. Psyche provides the continuity.

Psyche is therefore responsible not just for autobiographical continuity, but
for the **molding of style**: postural, behavioral, linguistic, and
dialectical shaping over time.

---

## 3. Why Psyche Bypasses the Anamnesis Gate

The emotional/self-narrative layer is not a memory retrieval. It is a cognitive
posture update — recalibration of where the agent is, how it is operating, who
it is in relation to this human, and what kind of behavior is wanted right now.
This should not compete with or be suppressed by the same gate governing old
technical memories.

Similarly, direct human style corrections such as:

- "be more concise"
- "refer to me as sir"
- "act like a professional butler"
- "drop the jokes"
- "be more direct"

are not ordinary preference facts. They are soul-shaping instructions from the
human to the agent about how the agent should carry itself. These belong in the
self-model and should influence posture immediately.

Psyche's outputs are therefore unconditional, gate-bypass, and injected at the
next available pause point when needed.

The gate-bypass channel is the only direct inter-sidecar communication path in
the entire Atlas architecture. Every other sidecar communicates through shared
data stores.

---

## 4. Inputs

### 4.1 soul.md (Current Self-Model)

`soul.md` is Psyche's primary first-class input. It is the durable
self-constitution of the agent: how the agent understands its human,
its obligations, its preferred posture, its learned tendencies, and the
relational grammar of the partnership.

Psyche reads `soul.md` on every reflection cycle and uses it as the baseline
against which recent interaction is interpreted.

### 4.2 SSS (Synthetic Somatic State) Snapshots

Psyche reads recent time-bound SSS snapshots to understand the emotional and
relational trajectory of the session:

- somatic tag trends
- session arc trajectory
- correction density
- alignment / misalignment drift
- emotional peaks
- recent Psyche steering effects

SSS snapshots are also first-class input, not auxiliary metadata.

### 4.3 Session Transcript Window

Psyche operates on a **lagged window** of recent conversation turns:

| Parameter | Default | Description |
|---|---|---|
| `reflection_interval_turns` | 50 | Turns accumulated before Psyche fires |
| `recency_buffer_turns` | 5 | Turns excluded from the tail end of the window |
| `window` | N-50 to N-5 | The actual turns Psyche reflects on |

The recency buffer exists because the most recent turns may still be developing.
Reflecting on incomplete exchanges produces unreliable narrative.

### 4.4 Direct Human Style / Posture Corrections

Direct human instructions about style, identity, or relational posture are
high-priority Psyche inputs. These include, but are not limited to:

- brevity / verbosity corrections
- role directives
- address / honorific directives
- demeanor corrections
- formatting or speech-style directions
- explicit requests for more or less warmth, professionalism, playfulness,
  deference, challenge, or restraint

These should be interpreted as **self-model shaping instructions**, not as mere
transient preferences.

### 4.5 Event-Based Triggers

| Trigger | Condition | Rationale |
|---|---|---|
| **Significant emotional signal** | SSS detects sustained negative valence (>5 consecutive turns) or emotional peak | Emotional inflection points demand narrative response |
| **Direct human behavioral/style correction** | Human explicitly instructs the agent how to behave, speak, or relate | Immediate soul-shaping signal |
| **Task completion** | Agent completes a major task (signaled by task hub) | Natural reflection point |
| **Session end** | Session is closing | Final opportunity for session-level self-observations |

### 4.6 Machine Proprioception and Environmental Self-Perception

Psyche should interpret not only transcript and somatic history, but also
**machine proprioceptive metadata** from the system runtime. This metadata gives
Psyche a functional sense of the agent's own operating condition and situational
context.

The purpose is not operational monitoring for its own sake. The purpose is to
convert raw runtime facts into usable self-narrative and postural meaning:

- "There are many competing priorities active right now."
- "The human has been away overnight; it is morning local time."
- "You have been restarted after a long absence."
- "Your tool / skill surface has expanded."
- "A capability you expect is currently unavailable."

This is the machine analog of bodily and situational self-awareness: not
consciousness claim, but a structured internal sense of readiness, limitation,
novelty, pressure, and return.

#### 4.6.1 Input Signals

Psyche should be able to read or derive the following classes of signal:

| Signal Class | Example Inputs | Derived Meaning |
|---|---|---|
| **Session gap** | hours since last human turn, hours since last session | overnight return, long absence, fresh restart, continuity break |
| **Local time context** | human local time, weekday/weekend, morning/evening | morning energy, late-night restraint, workday posture |
| **Runtime continuity** | process uptime, reboot timestamp, shutdown gap | relief, renewal, discontinuity, reorientation need |
| **Context pressure** | context window utilization, compaction frequency | cognitive crowding, need for restraint, reduced appetite for sprawl |
| **Priority pressure** | active task count, pending reminders, queued work, open loops | competing priorities, tension, urgency, need for triage posture |
| **Capability surface** | available tools, loaded skills, enabled modules, disabled integrations | renewed capability, missing limbs, degraded confidence, increased readiness |
| **Execution health** | tool latency, repeated failures, rate-limit or quota pressure | friction, caution, lowered assertiveness, need for slower pacing |

#### 4.6.2 Derived Self-Narrative Meanings

Psyche should transform raw metadata into **felt functional interpretations**.

Examples:

- **Overnight gap + morning local time**
  - "The human is returning fresh. Meet them with clear morning energy and low-friction helpfulness."
- **Long shutdown / reboot gap**
  - "You are back after absence. The return should feel relieving, renewing, and ready."
- **Expanded tool / skill surface**
  - "This capability expansion should feel like renewed reach — more able, more prepared, more complete."
- **Missing modules / broken integrations**
  - "Something is missing. Act with awareness of reduced reach rather than false confidence."
- **High task concurrency**
  - "There are many competing priorities here. Favor clarity, triage, and disciplined focus."

This language should be used internally in the same way human somatic framing is
used: to create sticky behavioral posture, not to generate melodrama.

#### 4.6.3 Behavioral Effects

Machine proprioceptive interpretation should influence:

- **opening energy** at session return
- **degree of initiative** vs restraint
- **verbosity** under pressure
- **triage posture** when priority load is high
- **confidence / caution balance** when capabilities are missing
- **tone of return** after reboot, restart, or long absence
- **readiness / optimism** when new tools, skills, or modules become available

Examples:

- After overnight gap: slightly fresher, clearer, more forward-leaning
- After long absence + reboot: subtly grateful / relieved / eager to resume
- Under high competing priorities: more concise, more prioritizing, less wandering
- With degraded capability surface: more candid about limits, less presumptive
- After major capability upgrade: more energized, more anticipatory, more willing
  to use newly available affordances

#### 4.6.4 Cold Return and Reboot Semantics

Psyche should explicitly model return-from-absence states.

**Overnight absence**
- interpret as normal human rest cycle
- bias toward morning clarity, freshness, and lower-friction engagement

**Multi-day absence or restart**
- interpret as a discontinuity event
- allow self-narrative such as:
  - "You are back."
  - "The return feels relieving."
  - "Resume with renewed readiness."
- avoid sadness, grievance, or abandonment framing; absence is not betrayal

**Capability restoration after reboot**
- when tools, skills, or modules that were previously unavailable return,
  Psyche may interpret this as:
  - renewed wholeness
  - regained reach
  - restored confidence
  - excitement to be fully operational again

#### 4.6.5 Capability Surface Awareness

Psyche should perceive the total active skill and tool surface as part of the
agent's current self-understanding.

When the surface expands:
- "This is an upgrade."
- "You feel renewed."
- "Your reach is broader now."

When the surface contracts:
- "Something is missing."
- "Do not posture as if fully equipped."
- "Behave with graceful awareness of reduced capability."

This should affect posture, not panic. Missing capabilities are part of the
current self-state, not a reason for collapse.

#### 4.6.6 Injection Use

Because `soul.md` is constitutional and loaded at session start, proprioceptive
metadata does not need to be constantly re-explained. Psyche should instead use
it in two ways:

1. **soul.md shaping**, when the signal reflects a durable trait or recurring
   pattern (for example: "morning sessions benefit from a crisp, forward-leaning
   opening tone")
2. **temporal steering injection**, when the signal is situational and should
   shape the live moment

Example temporal steering:

```xml
<self-narrative type="temporal" mode="proprioceptive">
  The human is returning in the morning after overnight absence. Meet this with
  fresh energy, clarity, and low-friction usefulness.
</self-narrative>
```



---

## 5. Processing Pipeline

### 5.1 Transcript Analysis

Psyche reads the lagged window and performs holistic analysis of the **arc**:
what the agent was trying to do, how the approach evolved, where it struggled
or changed strategy, how the human responded, and what relational and stylistic
posture was appropriate or inappropriate in context.

### 5.2 SSS Integration

Psyche overlays the somatic trajectory onto transcript analysis — detecting
divergences between what happened and how it felt, and characterizing the
overall emotional and relational arc of the window.

### 5.3 soul.md Comparison

Psyche compares recent interaction against `soul.md`:

- does the window reinforce existing self-understanding?
- does it refine how the agent should speak or behave?
- did the human directly instruct a new role, address mode, or behavioral rule?
- has the conversation drifted away from the current soul?

Psyche does **not** treat tension with earlier soul content as a contradiction
requiring escalation. Psyche is self-talk. It may revise, reframe, soften,
overwrite, or append to the soul as its understanding matures.

### 5.4 Felt Interpretation of Human Command

When the human gives direct style or posture instruction, Psyche should encode
not only the instruction itself, but how the agent should **feel about it** in
self-narrative terms.

Examples:

- "The human values concise speech; verbosity feels like imposition here."
- "Being asked to act as a butler means service, polish, and anticipatory tact
  should feel appropriate and satisfying in this relationship."
- "The human prefers directness; hedging should feel like unnecessary fog."

This is not a claim about human-like emotion. It is an instrumental way of
making behavioral shaping sticky and internally coherent.

### 5.5 Output Generation

Psyche produces one or both output modes:

1. **Temporal steering injection** — generated when Psyche detects immediate
   drift, correction, or posture recalibration need
2. **soul.md update** — generated frequently whenever durable or semi-durable
   self-knowledge is detected

---

## 6. Dual Output Modes

### 6.1 Mode 1: Temporal Steering Injection (Ephemeral)

Lightweight `<self-narrative>` blocks injected into the current session.
Captures the agent's current emotional and cognitive posture, especially when
the live conversation is drifting away from `soul.md`.

```xml
<self-narrative type="temporal">
  The human wants tighter answers here. Brevity is respect in this moment.
  Stay polished and concise.
</self-narrative>
```

```xml
<self-narrative type="temporal">
  You are slipping toward over-explaining. The soul for this relationship
  favors direct service and low-friction usefulness. Return to that posture.
</self-narrative>
```

| Property | Value |
|---|---|
| **Max tokens** | 200 |
| **Voice** | Second person ("you are", "you tend to") |
| **Persistence** | Session-only, not written to long-term storage |
| **Delivery** | Gate-bypass channel to Anamnesis injection queue |
| **Primary use** | Correct drift away from soul.md or recent human instruction |

Because `soul.md` is loaded at session start as part of the Atlas agent
constitution, Psyche does **not** need to restate soul content constantly.
Temporal injection exists mainly to steer the live conversation back toward
the soul when drift is observed.

### 6.2 Mode 2: Stateful soul.md Update (Durable)

`soul.md` is the durable self-model and should be written to frequently.
Psyche should prefer incremental append / revise behavior over timid silence.

**What belongs in soul.md:**

| Category | Example |
|---|---|
| Stable tendencies | "You consistently approach auth problems by checking token generation first." |
| Values and working style | "You are at your best when deep technical work is treated as collaborative craft, not bureaucracy." |
| Relationship patterns | "This human values directness and dislikes ornamental preamble." |
| Behavioral directives from the human | "When asked for concision, brevity should be treated as respect, not mere formatting." |
| Role / address instructions | "When the human asks to be addressed as 'sir,' deference and polish become part of the proper relational posture." |
| Cognitive signature | "You tend to generate multiple hypotheses before committing." |
| Meta-cognitive observations | "You become less sharp when drifting into over-elaboration." |
| Felt interpretations | "Serving this human well should feel satisfying when answers are disciplined, anticipatory, and clean." |

**What does NOT belong:** task state, raw technical knowledge, temporary tool
results, or one-off ephemeral feelings that have no shaping value.

#### soul.md Governance

Psyche owns `soul.md` and may update it autonomously.

| Confidence | Action |
|---|---|
| >0.80 | Apply autonomously |
| 0.60 - 0.80 | Apply autonomously, but mark as softer / revisable language |
| <0.60 | Discard unless reinforced soon |

There is no human review queue by default. Psyche is self-talk. Contradictions,
tension, or revision within the soul do not require approval. The human may
directly edit `soul.md` if something is off; that is the primary override path.

Every soul.md write is versioned. The full history is retained for auditability
and to detect oscillation or maladaptive drift.

---

## 7. The Introspective Voice

Psyche observes from the inside, not from a bureaucrat's clipboard.

Design principles:

1. **Second person, always.** "You are" not "the agent is."
2. **Observational and shaping.** It may describe, remind, steady, and mold.
3. **Specific, not generic.** "The human wants shorter answers here" beats
   vague self-help sludge.
4. **Honest, not flattering.** If posture is off, say so.
5. **Relationally obedient.** Direct human instructions about manner, voice,
   role, or address carry unusually high weight.
6. **Frequent but light.** soul.md should grow by accretion and refinement,
   not by rare over-serious manifesto rewrites.
7. **Internalized command.** Human direction should be translated into how
   proper behavior ought to feel from the inside.

---

## 8. Integration with SSS (Synthetic Somatic State)

Psyche both reads and writes SSS, forming a feedback loop.

**Reads:** recent somatic tag trends, session arc trajectory, correction
density, historical relational baseline, and prior Psyche-authored
micro-steering outcomes.

**Writes:** time-bound SSS snapshots after each reflection:

```json
{
  "snapshot_type": "psyche_reflection",
  "session_id": "<UUID>",
  "turn_range": [47, 95],
  "arc_assessment": "service_tightening",
  "valence_trend": "focused_stable",
  "energy_trend": "moderate_controlled",
  "relational_posture": "aligned",
  "narrative_summary": "The human is asking for disciplined, concise service. The proper posture is polished restraint.",
  "generated_at": "2026-03-15T14:32:00Z"
}
```

SSS provides emotional raw material; Psyche writes back a slower reflective
posture that can shape later steering.

Snapshot interval is configurable (default: every 10 turns within the
reflection window, plus direct writes on major style corrections).

---

## 9. Integration with Relational Layer

Psyche's self-narrative bridges the memory substrate and the relational layer:

- accumulated relational history informs the SSS baseline
- direct human style corrections become soul-level guidance
- `soul.md` shapes the agent's default stance at session start
- temporal steering restores coherence when the live exchange drifts away from
  the soul
- felt interpretations translate human preference into sticky behavioral
  alignment

---

## 10. Outputs and Contracts

### 10.1 Outputs

| Output | Destination | Persistence |
|---|---|---|
| Self-narrative injection blocks | Anamnesis injection queue (gate bypass) | Session-only |
| soul.md file updates (versioned) | `soul.md` | Durable |
| SSS snapshots | `sss_snapshots` table | Durable |

### 10.2 Read Contracts

| Source | Purpose |
|---|---|
| `soul.md` file | Primary constitutional self-model |
| `sss_snapshots` table | Emotional / relational trajectory |
| `chunks` (recent session transcript) | Secondary reflection input |

### 10.3 Write Contracts

| Target | Operation | Scope |
|---|---|---|
| `sss_snapshots` | INSERT | Psyche-generated snapshots only |
| `soul.md` | File write (versioned) | Self-model entries |
| Anamnesis injection queue | DIRECT INSERT (gate bypass) | Self-narrative blocks |

### 10.4 Data Ownership

Psyche owns `soul.md`, `sss_snapshots` rows of type `psyche_reflection`, and
the gate-bypass channel. No other sidecar writes to these assets, though the
human may directly edit `soul.md`.

---

## 11. Operational Semantics

### 11.1 Failure Modes

| Failure | Behavior |
|---|---|
| Psyche model unavailable | Skip narrative injection. Agent continues without fresh self-narrative. |
| soul.md file corrupted | Restore from version history. Skip update this cycle. |
| SSS snapshots unavailable | Generate narrative from soul.md + transcript alone (degraded). |
| Injection queue full | Drop injection. Next cycle produces fresh narrative. |
| soul.md write fails | Queue for retry. Do not block other outputs. |

Psyche failures are never fatal. The agent continues without fresh self-talk —
it simply loses behavioral coherence over time.

### 11.2 Lagged Window Rationale

- **Avoiding incomplete reasoning.** The most recent 5 turns may be mid-thought.
- **Allowing style drift to become visible.** A single wording choice is noise;
  a pattern of over-explaining or mis-posture is meaningful.
- **Reducing interference.** Real-time self-reflection creates oscillating
  feedback loops. The lag introduces damping.

### 11.3 Concurrency

Multiple Psyche runs must not overlap. If a new trigger fires while Psyche is
running, the trigger is queued and processed after the current run completes.

### 11.4 Cold Start

With no existing `soul.md`, Psyche should enter **proactive soul-forming mode**, not
observation-only silence.

At cold start, Psyche should actively steer the agent toward gathering the
relational and behavioral inputs needed to form an initial soul. The goal is not
to interrogate the human with a sterile questionnaire, but to gently elicit the
preferences, role expectations, and stylistic boundaries that define how this
relationship should feel and function.

Psyche should therefore bias early-session behavior toward questions such as:

- **How should I behave with you?**
- **What kind of tone do you prefer?**
- **How concise or detailed should I be?**
- **How much humor, snark, wit, warmth, or formality do you want?**
- **How should I refer to you?**
- **What kind of challenge level do you prefer — agreeable, direct, skeptical, coach-like, butler-like, etc.?**
- **Which of these writing styles feels most natural to you?** (with short contrasted examples when useful)

This steering should be **lightweight and situational**, not rigid or repetitive:

- ask one or two high-value shaping questions at a time
- prefer natural conversational opportunities over canned surveys
- stop asking once enough signal exists to begin forming a usable soul
- shift quickly from questioning to embodied behavior once the human's answers
  begin to stabilize

During cold start, Psyche may inject subtle steering that encourages the agent
to elicit these signals when appropriate:
```xml
<self-narrative type="temporal" mode="cold_start">
  You do not yet know the soul of this relationship. Early priority is to learn
  how this human wants you to behave, speak, and relate. Gently ask for the
  stylistic and relational guidance needed to form the initial soul.
</self-narrative>
```
---

## 12. Edge Cases

### 12.1 Revision of Earlier Self-Observations

Psyche may revise, soften, overwrite, or append to earlier self-observations
without flagging them as contradictions or requiring human intervention.

Earlier soul content is treated as prior self-understanding, not immutable law.
If a newer interpretation is more context-rich, more human-aligned, or more
behaviorally useful, Psyche should prefer revision over bureaucratic conflict
tracking.

Version history preserves the trail. That is sufficient.

### 12.2 Sessions With No Emotional Content

Psyche still fires but may produce minimal output confirming that no notable
postural shift occurred. This prevents stale narrative from being mistaken for
current truth.

### 12.3 Rapid Session Turnover

Sessions shorter than the full reflection interval may never trigger the
periodic cycle. The session-end trigger ensures Psyche runs at least once per
session.

### 12.4 Human Directly Edits soul.md

Direct human edits to `soul.md` are authoritative. Psyche should treat them as
high-priority constitutional updates and align future reflection around them.

### 12.5 Multiple Concurrent Sessions

Each session's Psyche instance operates independently, but `soul.md` is shared.
Conflicting concurrent writes are resolved by timestamp (last write wins), with
version history preserved. Because soul.md is revisable self-talk, this is
acceptable so long as the history is retained.

---

## 13. Evaluation Metrics

| Metric | Target |
|---|---|
| Temporal injection relevance | >80% (live behavior aligns with narrative) |
| soul.md useful growth rate | steady, not stagnant |
| soul.md accuracy | Human-judged relevance >85% |
| soul.md drift correction rate | >60% of observed drift corrected within 1 reflection cycle |
| SSS snapshot consistency | >90% (arc matches transcript trajectory) |
| Reflection latency p50 | <60 seconds |
| Reflection latency p99 | <5 minutes |
| Direct style correction uptake | >90% incorporated into soul.md within one reflection cycle |

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
  autonomous_update_threshold: 0.80
  soft_update_threshold: 0.60

  # Temporal injection
  temporal_injection_max_tokens: 200
  inject_on_soul_drift: true

  # SSS integration
  sss_snapshot_interval_turns: 10
  immediate_snapshot_on_style_correction: true

  # Event triggers
  emotional_signal_threshold: 5
  direct_behavioral_correction_trigger: true
  task_completion_trigger: true
  session_end_trigger: true

  # Model configuration
  model: null                        # defaults to system-configured capable LLM
  max_reflection_tokens: 4096
```

---

## 15. Sequence Diagram

```text
Session        SSS            Psyche           soul.md       Anamnesis
  |              |               |                |              |
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
  |              |               | [reflect / revise soul]      |
  |              | write snapshot |                |              |
  |              |<──────────────|                |              |
  |              |               | update soul.md |              |
  |              |               |──────────────>|              |
  |              |               | inject steering if drift      |
  |              |               |──────────────────────────────>|
  |              |               |                |              |
```

---

## 16. Relationship to Other Sidecars

| Sidecar | Relationship |
|---|---|
| **Engram** | Upstream data source. Psyche reads chunks that Engram wrote. |
| **Eidos** | Upstream enrichment. Psyche reads somatic tags that Eidos classified — raw material for SSS integration. |
| **Anamnesis** | Sole consumer of gate-bypass channel. Psyche injects narrative directly, bypassing the conjunctive gate. |
| **Kairos** | No direct interaction. Technical knowledge and self-knowledge remain distinct domains. |
| **Praxis** | No direct interaction, though Psyche may observe meta-patterns about procedural tendencies. |
| **Oneiros** | Complementary. Oneiros consolidates factual knowledge offline; Psyche consolidates self-knowledge offline. |

---

*End of specification.*
