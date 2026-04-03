# Praxis — Procedural Memory Optimizer

## Identity Card

| Field | Value |
|---|---|
| **Name** | Praxis (Greek: *praxis* — practice, action; knowledge realized through doing) |
| **Tier** | Reflective |
| **Role** | Skill and procedure optimizer |
| **Trigger** | Session end (primary), or after N invocations of a monitored skill |
| **Latency** | Unbounded — explicitly the slowest sidecar in the constellation |
| **Model** | Largest available local generative LLM |
| **Stateful** | Maintains skill invocation history and procedural notes store |
| **Human-in-the-loop** | Required for ALL skill file modifications |

---

## 1. Purpose

Every other sidecar in the Atlas constellation handles **what** the agent knows — episodic fragments, semantic structure, narrative self-model, predictive patterns. Praxis handles something orthogonal: **how** the agent performs tasks. It is the procedural memory layer.

Skills are the agent's muscle memory. They encode sequences of tool calls, reasoning patterns, and decision heuristics into reusable procedures. But skills, once written, tend to calcify. The environment evolves — infrastructure changes, new tools become available, patterns that were once adaptive become vestigial — while the skill files remain frozen. The agent compensates by adapting on the fly, paying reasoning cost every invocation for adjustments that should have been committed to the procedure itself.

Praxis watches how skills are actually used and compares that reality against how they are written. The gap between specification and practice is the optimization surface.

---

## 2. The Procedural Memory Gap

A skill can be individually correct — every step well-reasoned, every tool call appropriate — and still produce poor aggregate outcomes. The failure modes are structural, not logical:

**Incorrect sequencing.** The right skill fires at the wrong time. A deployment verification skill runs before the deployment skill has finished propagating. The skill itself is fine; its position in the invocation sequence is wrong.

**Redundant steps.** A skill includes setup steps that were necessary when it was written but are now handled by infrastructure. The agent faithfully executes them, paying latency and token cost for operations that resolve to no-ops.

**De facto universal modifications.** The agent adapts a skill identically on every invocation — always skipping step 3, always adding an extra validation check. The modification has become universal practice but hasn't been committed to the procedure. Every invocation pays the reasoning cost of re-deriving what should be encoded.

**Manual steps that are always identical.** A skill produces output that the human always processes the same way — copy to a specific file, run a specific command, verify against a specific endpoint. These are candidates for script extraction.

**Inefficient decomposition.** Three skills fire in sequence where one refactored skill would suffice. The inter-skill overhead — context re-establishment, redundant preamble, repeated tool authentication — exceeds the complexity cost of consolidation.

Praxis exists to detect these patterns and surface corrections through a graduated confidence pipeline.

---

## 3. Input Signal: Skill Invocation Records

Praxis operates on a structured log of every skill invocation across all sessions. This is its primary — and only — signal source. It does not read conversation content directly; it reads the metadata exhaust of skill execution.

```python
@dataclass
class SkillInvocationRecord:
    invocation_id: str
    session_id: str
    master_session_id: str
    timestamp: datetime
    turn_index: int

    # Skill identification
    skill_name: str
    skill_path: str
    skill_version_hash: str

    # Context before invocation
    preceding_turns: int
    preceding_tool_calls: List[str]
    human_prompt_before: Optional[str]

    # Execution trace
    turns_to_complete: int
    tool_calls_during: List[ToolCallRecord]
    model_corrections: int          # Times the model revised its own output
    human_corrections: int          # Times the human intervened to correct

    # Outcome
    task_complete_message: Optional[str]
    task_complete_was_null: bool     # Skill ended without explicit completion

    # Sequence context
    subsequent_skill: Optional[str]  # What skill fired next, if any

    # Deviation tracking
    steps_skipped: List[str]         # Skill steps the agent skipped
    steps_added: List[str]           # Steps the agent added beyond the spec
    modifications_made: str          # Free-text summary of adaptations
```

### 3.1 ToolCallRecord

```python
@dataclass
class ToolCallRecord:
    tool_name: str
    arguments_hash: str             # Deterministic hash of arguments
    arguments_summary: str          # Human-readable summary
    result_status: str              # success | error | timeout
    duration_ms: int
    sequence_index: int             # Position in the invocation's tool call list
```

### 3.2 Why Metadata, Not Content

Praxis deliberately operates on structural metadata rather than raw conversation content. This is a design choice, not a limitation:

- **Privacy boundary.** Skill optimization should not require reading the human's conversational intent. The invocation pattern is sufficient.
- **Signal density.** Raw conversation is noisy. The structured record distills what actually happened — which tools fired, in what order, with what outcome — without the agent's reasoning narrative.
- **Scale.** Metadata records are small. Praxis can hold hundreds of invocation records in context simultaneously, enabling cross-session pattern detection that would be impossible with raw transcripts.

---

## 4. Three Output Modes

Praxis operates through a graduated pipeline. Confidence determines which mode activates. Lower confidence produces lighter-touch interventions; higher confidence produces structural recommendations. This gradient exists because the cost of a wrong intervention scales with how deeply it modifies the agent's procedural memory.

### 4.1 Mode 1: Procedural Notes Injection

**Confidence threshold:** 0.50
**Automation level:** Fully autonomous
**Persistence:** Procedural notes store (key-value by skill name)

The lightest intervention. Praxis writes a short note to the skill-specific notes store. On the next invocation of that skill, Anamnesis injects the note into context before the skill loads. The agent receives the note as advisory context — it can follow or ignore it.

```xml
<procedural_note skill="deploy-verify" confidence="0.72" based_on="last_4_invocations">
  The agent has skipped the DNS propagation check (step 4) on the last 4
  invocations, proceeding directly to HTTP verification. Consider starting
  with HTTP verification and only falling back to DNS check on failure.
</procedural_note>
```

```xml
<procedural_note skill="db-migration" confidence="0.58" based_on="last_3_invocations">
  Human has corrected the schema diff output format on 3 of the last 5
  invocations, requesting markdown table format instead of raw SQL. Consider
  defaulting to markdown table output.
</procedural_note>
```

**Self-validation.** Notes are not static. Each note carries a confidence score that is updated after every subsequent invocation of the associated skill:

- If the note was injected and the skill completed with fewer corrections, fewer added steps, or lower turn count: **confidence increases** (+0.05 per positive signal).
- If the note was injected and outcomes did not improve or worsened: **confidence decays** (-0.08 per negative signal, asymmetric to bias toward removal).
- Notes below confidence 0.30 are automatically archived (soft-deleted, never hard-deleted — negative knowledge is preserved).
- Notes above confidence 0.85 that persist across 10+ invocations become candidates for Mode 2 graduation.

### 4.2 Mode 2: Refactoring Recommendation

**Confidence threshold:** 0.75
**Automation level:** Human review REQUIRED
**Delivery:** Notification channel (not injected into agent context)

When the pattern signal is strong enough to warrant structural change to a skill file, Praxis generates a formal recommendation. This is never applied automatically. It is surfaced to the human through the notification channel with full evidence.

A Mode 2 recommendation includes:

```yaml
recommendation:
  id: praxis-rec-2026-03-15-001
  skill: deploy-verify
  type: refactoring
  confidence: 0.82
  generated_at: "2026-03-15T22:41:00Z"

  evidence:
    invocations_analyzed: 12
    pattern_first_seen: "2026-02-28"
    pattern_description: |
      Steps 3-5 (DNS propagation check, TTL wait, DNS re-verify) have been
      skipped on 11 of 12 invocations. The agent proceeds directly to HTTP
      endpoint verification. On the one invocation where DNS steps were
      executed, they were triggered by an HTTP failure — suggesting DNS
      verification is a fallback path, not a primary path.
    supporting_data:
      - invocation_ids: [inv-041, inv-042, ..., inv-052]
      - skip_rate: 0.917
      - human_corrections_during_skip: 0
      - avg_turns_with_skip: 3.2
      - avg_turns_without_skip: 5.0

  proposed_change:
    type: step_reorder
    description: |
      Move DNS verification to a conditional fallback block that triggers
      only on HTTP verification failure. Remove the mandatory TTL wait.
    diff: |
      --- a/skills/deploy-verify/SKILL.md
      +++ b/skills/deploy-verify/SKILL.md
      @@ -12,9 +12,7 @@
      -3. Check DNS propagation for the target domain
      -4. Wait for TTL expiration (default: 60s)
      -5. Re-verify DNS resolution
      -6. Perform HTTP GET against the deployment endpoint
      +3. Perform HTTP GET against the deployment endpoint
      +4. On HTTP failure: check DNS propagation and retry after TTL

  eval_harness_result: null  # Or populated if eval ran (see Section 6)
  status: pending_review
```

### 4.3 Mode 3: Deterministic Script Extraction

**Confidence threshold:** 0.85
**Automation level:** Human review REQUIRED
**Additional requirement:** Determinism threshold met across 10+ invocations

The most aggressive optimization. When a skill invocation produces nearly identical tool call sequences across many invocations — same tools, same argument patterns, same ordering — the LLM is paying full reasoning cost for a deterministic outcome. The reasoning tokens are wasted. The sequence should be a script.

**Determinism detection:**

```python
def compute_sequence_similarity(seq_a: List[ToolCallRecord],
                                 seq_b: List[ToolCallRecord]) -> float:
    """
    Normalized edit distance over tool call sequences.
    Compares: tool_name, arguments_hash, sequence_index.
    Returns: 1.0 = identical, 0.0 = completely different.
    """
    ...

def check_determinism(skill_name: str,
                       invocations: List[SkillInvocationRecord]) -> Optional[float]:
    """
    Pairwise similarity across all invocation tool call sequences.
    Returns mean similarity if >= determinism_min_invocations exist,
    else None.
    """
    if len(invocations) < config.determinism_min_invocations:
        return None
    pairs = itertools.combinations(invocations, 2)
    similarities = [compute_sequence_similarity(a.tool_calls_during,
                                                 b.tool_calls_during)
                    for a, b in pairs]
    return statistics.mean(similarities)
```

**Determinism threshold:** 0.85 mean pairwise similarity across 10+ invocations.

When met, Praxis generates a script extraction proposal:

```yaml
recommendation:
  id: praxis-rec-2026-03-15-002
  skill: format-changelog
  type: deterministic_extraction
  confidence: 0.91
  determinism_score: 0.93

  evidence:
    invocations_analyzed: 14
    tool_call_sequence_template:
      - { tool: Read, target: "CHANGELOG.md" }
      - { tool: Bash, command: "git log --oneline {since}..HEAD" }
      - { tool: Edit, target: "CHANGELOG.md", pattern: "prepend_section" }
      - { tool: Bash, command: "git add CHANGELOG.md" }
    variation_points:
      - "git log --oneline: '{since}' parameter varies (always last tag)"
    identical_across_all: ["Read target", "Edit pattern", "git add target"]

  proposed_script:
    language: bash
    path: scripts/update-changelog.sh
    content: |
      #!/usr/bin/env bash
      set -euo pipefail
      LAST_TAG=$(git describe --tags --abbrev=0)
      ENTRIES=$(git log --oneline "${LAST_TAG}..HEAD")
      # ... rest of deterministic script
    replaces_skill: false  # Skill still exists; script is offered as alternative
    estimated_savings: "~800 reasoning tokens per invocation"
```

---

## 5. Procedural Notes Store

The notes store is the persistence layer for Mode 1 outputs and the evidence base for Mode 2/3 graduation decisions.

### 5.1 Schema

```sql
CREATE TABLE procedural_notes (
    note_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name      TEXT NOT NULL,
    note_content    TEXT NOT NULL,
    confidence      FLOAT NOT NULL DEFAULT 0.50,
    based_on_count  INT NOT NULL DEFAULT 1,
    first_generated TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_injected   TIMESTAMPTZ,
    injection_count INT NOT NULL DEFAULT 0,
    positive_signals INT NOT NULL DEFAULT 0,
    negative_signals INT NOT NULL DEFAULT 0,
    archived        BOOLEAN NOT NULL DEFAULT FALSE,
    archive_reason  TEXT,
    source_invocations UUID[] NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_procedural_notes_skill ON procedural_notes(skill_name)
    WHERE NOT archived;
```

### 5.2 Lifecycle

```
Generated (confidence 0.50)
    │
    ├── Injected → Outcome measured
    │       ├── Positive signal → confidence += 0.05
    │       └── Negative signal → confidence -= 0.08
    │
    ├── confidence < 0.30 → Archived
    │       └── archive_reason = "decay"
    │
    └── confidence > 0.85 AND injection_count > 10
            └── Graduate to Mode 2 recommendation candidate
```

### 5.3 Injection Protocol

When Anamnesis prepares to inject context before a skill invocation, it queries the procedural notes store:

```sql
SELECT note_content, confidence
FROM procedural_notes
WHERE skill_name = $1
  AND NOT archived
  AND confidence >= 0.50
ORDER BY confidence DESC
LIMIT 3;
```

Maximum three notes per skill invocation. Notes are injected in descending confidence order. This cap prevents note accumulation from polluting the agent's context — the same principle that governs the Anamnesis injection gate applies here.

---

## 6. Eval Harness Integration

Before Mode 2 recommendations surface to the human, Praxis can optionally validate the proposed change through an automated eval harness. This transforms recommendations from "pattern-based intuition" into "measured evidence."

### 6.1 Mechanism

1. Praxis generates the proposed skill modification as a diff.
2. A git worktree is created from the current branch (isolated filesystem).
3. The diff is applied in the worktree.
4. A synthetic invocation scenario is constructed from historical invocation records.
5. The modified skill is exercised against the scenario in the worktree.
6. Outcome metrics (turn count, tool calls, corrections, completion) are compared against the historical baseline.

### 6.2 Eval Result Structure

```python
@dataclass
class EvalHarnessResult:
    recommendation_id: str
    worktree_path: str
    eval_timestamp: datetime

    # Comparison metrics
    baseline_avg_turns: float
    modified_avg_turns: float
    baseline_avg_corrections: float
    modified_avg_corrections: float
    baseline_avg_tool_calls: int
    modified_avg_tool_calls: int

    # Outcome
    improvement_detected: bool
    regression_detected: bool
    confidence_adjustment: float       # Applied to recommendation confidence
    notes: str
```

### 6.3 Constraints

- The eval harness is **optional** (`eval_harness_enabled` in config). Recommendations can surface without it.
- Eval runs are expensive (full LLM invocations in an isolated worktree). Praxis runs them only when recommendation confidence exceeds 0.80.
- The worktree is destroyed after eval completes. No persistent side effects.
- Eval results are attached to the recommendation but do not auto-approve it. Human review remains required.

---

## 7. Analysis Pipeline

When Praxis fires (session end or invocation threshold), it executes the following pipeline:

### 7.1 Collect

Gather all skill invocation records since the last Praxis run. Group by skill name.

### 7.2 Filter

Discard skills with fewer than `min_invocations_for_analysis` (default: 5) total invocations. Insufficient data produces unreliable patterns.

### 7.3 Detect Patterns

For each qualifying skill, run the following detectors:

**Skip detector.** Identify steps that are consistently skipped. If `steps_skipped` contains the same step across >60% of invocations, flag as redundant step candidate.

**Addition detector.** Identify steps that are consistently added. If `steps_added` contains the same step across >60% of invocations, flag as missing step candidate.

**Correction detector.** Track `human_corrections` rate. If corrections cluster around specific tool calls or sequence positions, flag as error-prone region.

**Sequence detector.** Compare `tool_calls_during` across invocations using normalized edit distance. If mean pairwise similarity exceeds `determinism_threshold`, flag as deterministic extraction candidate.

**Efficiency detector.** Track `turns_to_complete` trend over time. If turn count is increasing or consistently high relative to tool call count, flag as efficiency degradation.

**Chaining detector.** Analyze `subsequent_skill` patterns. If the same skill always follows, consider consolidation.

### 7.4 Score and Classify

Each detected pattern receives a confidence score based on:
- Sample size (more invocations = higher confidence)
- Consistency (pattern present in what fraction of invocations)
- Recency (recent invocations weighted higher via exponential decay)
- Human signal (corrections are weighted 3x model corrections)

Classification into output mode:
- Confidence 0.50–0.74: Mode 1 (procedural note)
- Confidence 0.75–0.84: Mode 2 (refactoring recommendation)
- Confidence 0.85+ with determinism threshold met: Mode 3 (script extraction)
- Confidence 0.85+ without determinism: Mode 2 (strong refactoring recommendation)

### 7.5 Generate Outputs

For each classified pattern, generate the appropriate output (note, recommendation, or extraction proposal). Write to the relevant store. Queue human notifications for Mode 2/3.

---

## 8. Contracts

### 8.1 Reads

| Source | Purpose |
|---|---|
| `skill_invocations` | Primary signal — all invocation records |
| `procedural_notes` | Existing notes for update/decay/graduation checks |
| `praxis_recommendations` | Existing recommendations to avoid duplicates |

### 8.2 Writes

| Target | Operation | Conditions |
|---|---|---|
| `procedural_notes` | INSERT / UPDATE | Mode 1 outputs; confidence updates after injection |
| `praxis_recommendations` | INSERT / UPDATE | Mode 2 and Mode 3 outputs |
| Human notification channel | PUSH | All Mode 2 and Mode 3 outputs |
| Git worktree manager | CREATE / DESTROY | Eval harness runs (when enabled) |

### 8.3 Does NOT Write

- Skill files (never; only humans modify skill files)
- Agent context (Anamnesis handles injection of procedural notes)
- Chunk store (Praxis is not an episodic memory system)

---

## 9. Critical Invariant: Human Review for Structural Changes

Skill files are procedural memory. They define how the agent behaves — what tools it reaches for, in what order, with what parameters, under what conditions. An agent that autonomously rewrites its own skill files is an agent that modifies its own behavioral specifications without oversight. This is a meaningful safety boundary, not a bureaucratic one.

The invariant is simple:

> **Mode 1 (procedural notes) is safe to apply autonomously.** Notes are advisory. They are injected as context, not as instructions. The agent can follow or ignore them. If a note causes harm, it decays naturally through the confidence mechanism.

> **Modes 2 and 3 ALWAYS require human approval.** No exception. No "high confidence auto-approve" path. No "trivial change" bypass. The human reviews the evidence, reads the proposed diff, and explicitly approves or rejects.

This invariant is enforced at the database level: `praxis_recommendations` rows are created with `status = 'pending_review'` and can only transition to `'approved'` or `'rejected'` through an authenticated human action. There is no code path that transitions status autonomously.

---

## 10. Timing: Why Session-End Is Correct

Praxis is explicitly the slowest sidecar. It runs at session end alongside the other reflective-tier processes (Kairos, Oneiros, Psyche, Augur), but with no latency budget whatsoever. It takes as long as it takes.

This timing is correct for several reasons:

**Signal requires accumulation.** A single skill invocation is anecdote, not pattern. Praxis needs multiple invocations of the same skill to detect meaningful deviation from the specification. Most sessions invoke a given skill at most once or twice — the cross-session view is where patterns emerge.

**Thoughtfulness over speed.** Refactoring recommendations require the kind of careful analysis that conflicts with the latency requirements of real-time sidecars. Praxis uses the largest available model and gives it unconstrained generation time. Rushed optimization is worse than no optimization.

**Non-interference.** Praxis should never slow down the agent's active work. Session end is the natural quiescent point where reflective processing can run without competing for resources.

**Secondary trigger.** The invocation-count trigger (`N` invocations of a monitored skill) exists for skills that are used heavily within a single session. If a skill fires 20 times in one session, waiting for session end wastes signal. But even then, the analysis runs asynchronously and does not block the agent.

---

## 11. Evaluation Metrics

| Metric | Target | Measurement Method |
|---|---|---|
| Note helpfulness rate | >50% | Fraction of injected notes that correlate with improved outcomes (fewer turns, fewer corrections) |
| Recommendation acceptance rate | >60% | Fraction of Mode 2/3 recommendations approved by human |
| Determinism detection accuracy | >90% | Manual audit of deterministic extraction proposals against ground truth |
| Skill efficiency improvement | Measurable turn reduction | Compare avg turns-to-complete before and after adopted recommendation |
| False positive rate (Mode 2/3) | <20% | Fraction of recommendations rejected as incorrect by human |
| Note decay rate | 30–50% | Healthy system should archive a substantial fraction of notes — aggressive generation with natural selection is the intended dynamic |

---

## 12. Configuration

```yaml
praxis:
  enabled: true

  # Analysis thresholds
  min_invocations_for_analysis: 5     # Minimum invocations before analyzing a skill
  pattern_consistency_threshold: 0.60  # Fraction of invocations showing pattern

  # Mode confidence thresholds
  note_confidence_threshold: 0.50         # Mode 1 minimum confidence
  recommendation_confidence_threshold: 0.75  # Mode 2 minimum confidence

  # Determinism (Mode 3)
  determinism_threshold: 0.85             # Mean pairwise similarity required
  determinism_min_invocations: 10         # Minimum invocations for determinism check

  # Confidence dynamics
  positive_signal_increment: 0.05
  negative_signal_decrement: 0.08         # Asymmetric: bias toward removal
  archive_threshold: 0.30                 # Notes below this are archived
  graduation_threshold: 0.85              # Notes above this become Mode 2 candidates
  graduation_min_injections: 10           # Minimum injections before graduation

  # Note injection
  max_notes_per_invocation: 3             # Cap on concurrent procedural notes

  # Human review
  human_review_required: true             # Cannot be set to false (enforced)

  # Eval harness
  eval_harness_enabled: true
  eval_min_confidence: 0.80               # Only eval recommendations above this

  # Trigger
  session_end_enabled: true
  invocation_count_trigger: 20            # Mid-session trigger threshold
```

---

## 13. Interaction with Other Sidecars

**Anamnesis.** Praxis writes procedural notes; Anamnesis injects them. The two sidecars share the `procedural_notes` table but never run concurrently on the same record. Anamnesis reads at skill invocation time (real-time tier); Praxis writes at session end (reflective tier).

**Engram.** Praxis does not read from the chunk store. It reads from the skill invocation log, which is a separate signal stream. However, Engram is responsible for capturing the raw events from which invocation records are constructed.

**Kairos.** Praxis and Kairos both run at session end but operate on orthogonal data. Kairos consolidates episodic/semantic knowledge; Praxis optimizes procedural knowledge. No direct interaction.

**Psyche.** If Praxis detects that the agent consistently struggles with a particular skill (high correction rate, increasing turn count), this signal could inform Psyche's self-model. This interaction is currently one-way: Praxis writes to `praxis_recommendations`, and Psyche may read that table as an input signal. No direct coupling.

**Augur.** If Praxis detects strong skill chaining patterns (skill A always followed by skill B), this information could feed Augur's predictive engine. Future work — not currently implemented.

---

## 14. Failure Modes and Mitigations

**Premature pattern detection.** Small sample sizes produce unreliable patterns. Mitigation: `min_invocations_for_analysis` enforces minimum sample size. Confidence scoring weights sample size.

**Overfitting to recent behavior.** The human's workflow may have temporarily changed, not permanently shifted. Mitigation: exponential decay weighting means recent invocations dominate, but the graduation threshold (10+ injections) ensures notes must prove themselves over time before escalating.

**Note pollution.** Too many low-confidence notes accumulate and clutter injection. Mitigation: archive threshold (0.30) aggressively prunes unhelpful notes. Max three notes per invocation caps injection volume.

**Stale recommendations.** A Mode 2 recommendation is generated but the human doesn't review it for weeks, during which the skill has already been manually modified. Mitigation: recommendations include `skill_version_hash`. On review, the system checks whether the skill file has changed since the recommendation was generated and flags stale recommendations.

**Determinism false positives.** A skill appears deterministic because it has only been used in one narrow context. Mitigation: the 10-invocation minimum and 0.85 similarity threshold together require strong, sustained evidence. The human review gate catches remaining false positives.

---

## 15. Anti-Patterns: What Praxis Must NOT Do

- **Never modify skill files autonomously.** This is the core safety invariant. No exceptions.
- **Never inject Mode 2/3 content into the agent's context.** Recommendations go to the human, not the agent. The agent should not be aware of pending structural changes to its own procedures.
- **Never block session-end processing.** If Praxis encounters an error, it logs and exits. Other reflective sidecars must not be delayed.
- **Never analyze invocations from the current session only.** Cross-session patterns are the signal. Single-session analysis is anecdote.
- **Never generate recommendations for skills with fewer than `min_invocations_for_analysis` invocations.** Insufficient evidence produces noise, not signal.
