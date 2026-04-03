
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
| **Stateful** | Maintains skill invocation history, procedural notes store, and skill edit audit log |
| **Human-in-the-loop** | Required for structural or behavioral skill changes; limited autonomous factual maintenance permitted under strict policy |

---

## 1. Purpose

Every other sidecar in the Atlas constellation handles **what** the agent knows — episodic fragments, semantic structure, narrative self-model, predictive patterns. Praxis handles something orthogonal: **how** the agent performs tasks. It is the procedural memory layer.

Skills are the agent's muscle memory. They encode sequences of tool calls, reasoning patterns, and decision heuristics into reusable procedures. But skills, once written, tend to calcify. The environment evolves — infrastructure changes, new tools become available, paths move, flags change, patterns that were once adaptive become vestigial — while the skill files remain frozen. The agent compensates by adapting on the fly, paying reasoning cost every invocation for adjustments that should have been committed to the procedure itself.

Praxis watches how skills are actually used and compares that reality against how they are written. The gap between specification and practice is the optimization surface.

The design goal is not unrestricted self-modification. It is **graduated procedural maintenance**:

- light advisory guidance when signal is weak
- narrow autonomous factual repair when signal is strong and risk is low
- human-reviewed structural change when the procedure itself should evolve

---

## 2. The Procedural Memory Gap

A skill can be individually correct — every step well-reasoned, every tool call appropriate — and still produce poor aggregate outcomes. The failure modes are structural, not logical:

**Incorrect sequencing.** The right skill fires at the wrong time. A deployment verification skill runs before the deployment skill has finished propagating. The skill itself is fine; its position in the invocation sequence is wrong.

**Redundant steps.** A skill includes setup steps that were necessary when it was written but are now handled by infrastructure. The agent faithfully executes them, paying latency and token cost for operations that resolve to no-ops.

**De facto universal modifications.** The agent adapts a skill identically on every invocation — always skipping step 3, always adding an extra validation check. The modification has become universal practice but hasn't been committed to the procedure. Every invocation pays the reasoning cost of re-deriving what should be encoded.

**Minor factual drift.** A skill points to a script path, config path, file name, command flag, or environment location that has changed. The model repeatedly compensates by searching, locating the correct target, and then continuing. The procedure is still conceptually correct, but one or two factual literals are stale.

**Manual steps that are always identical.** A skill produces output that the human always processes the same way — copy to a specific file, run a specific command, verify against a specific endpoint. These are candidates for script extraction.

**Inefficient decomposition.** Three skills fire in sequence where one refactored skill would suffice. The inter-skill overhead — context re-establishment, redundant preamble, repeated tool authentication — exceeds the complexity cost of consolidation.

Praxis exists to detect these patterns and surface corrections through a graduated confidence pipeline.

---

## 3. Input Signal: Skill Invocation Records

Praxis operates on a structured log of every skill invocation across all sessions. This is its primary signal source. Unlike earlier versions of the design, Praxis may also read the current skill artifact text and minimal file-system evidence when evaluating whether a proposed edit is merely factual maintenance or a deeper behavioral change.

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

### 3.2 Additional Read Signals

Praxis may additionally read:

| Source | Use |
|---|---|
| Current `SKILL.md` artifact | Determine whether the observed drift is factual or structural |
| File-system existence checks | Confirm whether referenced paths/scripts actually exist |
| Edit audit log | Prevent oscillating autonomous edits and repeated low-value churn |

### 3.3 Why Mostly Metadata, Not Full Conversation

Praxis still prefers structural metadata over raw conversation content:

- **Privacy boundary.** Skill optimization should not require broad inspection of human conversation.
- **Signal density.** The structured record distills what actually happened — which tools fired, in what order, with what outcome.
- **Scale.** Metadata records are small and compare well across many invocations.

However, limited artifact reads are now allowed because factual skill maintenance sometimes requires comparing what the skill says to what the environment demonstrably contains.

---

## 4. Four Output Modes

Praxis operates through a graduated pipeline. Confidence and blast radius determine which mode activates. Lower confidence produces lighter-touch interventions; higher confidence or higher-risk changes require stronger review. This gradient exists because the cost of a wrong intervention scales with how deeply it modifies procedural memory.

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

- If the note was injected and the skill completed with fewer corrections, fewer added steps, or lower turn count: **confidence increases** (`+0.05` per positive signal).
- If the note was injected and outcomes did not improve or worsened: **confidence decays** (`-0.08` per negative signal, asymmetric to bias toward removal).
- Notes below confidence `0.30` are automatically archived (soft-deleted, never hard-deleted — negative knowledge is preserved).
- Notes above confidence `0.85` that persist across 10+ invocations become candidates for escalation.

### 4.2 Mode 2: Autonomous Minor Factual Maintenance

**Confidence threshold:** 0.90  
**Automation level:** Autonomous, but narrowly constrained  
**Persistence:** Direct in-place skill edit plus mandatory audit log entry  
**Allowed change class:** High-confidence, low-risk, factual maintenance only

This mode exists for cases where the **procedure is still right** but a small factual detail in the skill file has drifted.

Canonical example:
- skill says `scripts/foo/run.sh`
- repeated invocations show the model must `find` or `glob` the script first
- the same new path is discovered repeatedly with high consistency
- replacing the stale literal with the repeatedly confirmed literal removes wasted search turns without changing the procedure's meaning

Allowed examples include:
- script or file path updates
- command path updates
- directory names that have moved
- non-semantic flag or literal replacements when repeated execution shows one stable correct value
- correcting obviously stale filenames, env var names, or endpoint paths inside procedural examples

Not allowed in this mode:
- changing step order
- adding or removing decision logic
- changing the procedure's behavioral semantics
- changing safety constraints, approvals, destructive commands, or trust boundaries
- changing anything with ambiguous multiple valid replacements

```yaml
maintenance_edit:
  id: praxis-fix-2026-03-15-001
  skill: run-migration-helper
  type: factual_path_update
  confidence: 0.94
  generated_at: "2026-03-15T22:41:00Z"

  evidence:
    invocations_analyzed: 7
    stale_literal: "scripts/migrate/run.sh"
    observed_resolution_pattern:
      - "Glob scripts/**/run.sh"
      - "Found scripts/db/migrate/run.sh"
      - "Executed scripts/db/migrate/run.sh successfully"
    successful_resolutions: 7
    conflicting_resolutions: 0
    human_corrections: 0

  proposed_change:
    file: skills/run-migration-helper/SKILL.md
    change_class: literal_replacement
    before: "scripts/migrate/run.sh"
    after: "scripts/db/migrate/run.sh"

  audit:
    auto_applied: true
    rollback_available: true
    review_status: logged_for_review
```

#### 4.2.1  Safety Rules for Autonomous Maintenance

A Mode 2 autonomous edit is permitted only if **all** of the following are true:

1. **Single-literal scope.** The diff changes only a narrowly bounded factual literal or similarly tiny patch.
2. **No semantic control-flow change.** The surrounding procedure remains behaviorally identical.
3. **Stable repeated evidence.** The same correction has been observed successfully across the configured minimum number of invocations.
4. **No conflicting resolutions.** Praxis has not observed two competing “correct” replacements.
5. **Low-risk target.** The edited field is not safety-critical, approval-related, destructive, credential-bearing, or policy-bearing.
6. **Artifact verification succeeds.** The replacement can be confirmed by file existence, command success, or comparable deterministic check.
7. **Rollback path exists.** The prior version is preserved and reversible.
8. **Edit budget not exceeded.** Praxis has not already made too many recent autonomous edits to the same skill.

If any one of these fails, the proposed change is downgraded to a human-reviewed recommendation.

#### 4.2.2  Post-Edit Validation

After an autonomous maintenance edit, Praxis records a probation window. If subsequent invocations improve, confidence is reinforced. If they regress, the edit is automatically reverted and future similar edits for that skill are blocked pending human review.

### 4.3 Mode 3: Refactoring Recommendation

**Confidence threshold:** 0.75  
**Automation level:** Human review REQUIRED  
**Delivery:** Notification channel (not injected into agent context)

When the pattern signal is strong enough to warrant structural change to a skill file, Praxis generates a formal recommendation. This is never applied automatically. It is surfaced to the human through the notification channel with full evidence.

A Mode 3 recommendation includes:

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

  eval_harness_result: null
  status: pending_review
```

### 4.4 Mode 4: Deterministic Script Extraction

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

**Determinism threshold:** `0.85` mean pairwise similarity across 10+ invocations.

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
    replaces_skill: false
    estimated_savings: "~800 reasoning tokens per invocation"
```

---

## 5. Procedural Notes Store

The notes store is the persistence layer for Mode 1 outputs and the evidence base for higher-mode escalation decisions.

### 5.1 Schema

```sql
CREATE TABLE procedural_notes (
    note_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name       TEXT NOT NULL,
    note_content     TEXT NOT NULL,
    confidence       FLOAT NOT NULL DEFAULT 0.50,
    based_on_count   INT NOT NULL DEFAULT 1,
    first_generated  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_injected    TIMESTAMPTZ,
    injection_count  INT NOT NULL DEFAULT 0,
    positive_signals INT NOT NULL DEFAULT 0,
    negative_signals INT NOT NULL DEFAULT 0,
    archived         BOOLEAN NOT NULL DEFAULT FALSE,
    archive_reason   TEXT,
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
            └── Graduate to recommendation candidate
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

Maximum three notes per skill invocation. Notes are injected in descending confidence order.

---

## 6. Autonomous Maintenance Audit Log

Autonomous edits must be fully visible and reversible.

### 6.1 Schema

```sql
CREATE TABLE praxis_skill_edits (
    edit_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name           TEXT NOT NULL,
    skill_path           TEXT NOT NULL,
    prior_version_hash   TEXT NOT NULL,
    new_version_hash     TEXT NOT NULL,
    edit_class           TEXT NOT NULL,      -- factual_path_update | literal_replacement | etc.
    confidence           FLOAT NOT NULL,
    rationale            TEXT NOT NULL,
    evidence_summary     JSONB NOT NULL,
    auto_applied         BOOLEAN NOT NULL,
    reverted             BOOLEAN NOT NULL DEFAULT FALSE,
    revert_reason        TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    reverted_at          TIMESTAMPTZ
);
```

### 6.2 Invariants

- every autonomous edit gets an audit row
- every autonomous edit stores the previous version hash
- every autonomous edit is revertible
- repeated oscillation on the same field disables further autonomous edits for that skill until human review

---

## 7. Eval Harness Integration

Before higher-mode recommendations surface to the human, Praxis can optionally validate the proposed change through an automated eval harness. This transforms recommendations from "pattern-based intuition" into "measured evidence."

### 7.1 Mechanism

1. Praxis generates the proposed skill modification as a diff.
2. A git worktree is created from the current branch (isolated filesystem).
3. The diff is applied in the worktree.
4. A synthetic invocation scenario is constructed from historical invocation records.
5. The modified skill is exercised against the scenario in the worktree.
6. Outcome metrics (turn count, tool calls, corrections, completion) are compared against the historical baseline.

### 7.2 Eval Result Structure

```python
@dataclass
class EvalHarnessResult:
    recommendation_id: str
    worktree_path: str
    eval_timestamp: datetime

    baseline_avg_turns: float
    modified_avg_turns: float
    baseline_avg_corrections: float
    modified_avg_corrections: float
    baseline_avg_tool_calls: int
    modified_avg_tool_calls: int

    improvement_detected: bool
    regression_detected: bool
    confidence_adjustment: float
    notes: str
```

### 7.3 Constraints

- The eval harness is **optional** (`eval_harness_enabled` in config).
- Eval runs are expensive. Praxis runs them only when recommendation confidence exceeds `0.80`.
- The worktree is destroyed after eval completes. No persistent side effects.
- Eval results are attached to the recommendation but do not auto-approve it.
- Autonomous Mode 2 maintenance edits may use a lighter validation harness, but they do not depend on full eval runs.

---

## 8. Analysis Pipeline

When Praxis fires (session end or invocation threshold), it executes the following pipeline:

### 8.1 Collect

Gather all skill invocation records since the last Praxis run. Group by skill name.

### 8.2 Filter

Discard skills with fewer than `min_invocations_for_analysis` (default: 5) total invocations, except for potential factual maintenance candidates which may use a smaller threshold if deterministic repeated resolution is observed.

### 8.3 Detect Patterns

For each qualifying skill, run the following detectors:

**Skip detector.** Identify steps that are consistently skipped. If `steps_skipped` contains the same step across >60% of invocations, flag as redundant step candidate.

**Addition detector.** Identify steps that are consistently added. If `steps_added` contains the same step across >60% of invocations, flag as missing step candidate.

**Correction detector.** Track `human_corrections` rate. If corrections cluster around specific tool calls or sequence positions, flag as error-prone region.

**Sequence detector.** Compare `tool_calls_during` across invocations using normalized edit distance. If mean pairwise similarity exceeds `determinism_threshold`, flag as deterministic extraction candidate.

**Efficiency detector.** Track `turns_to_complete` trend over time. If turn count is increasing or consistently high relative to tool call count, flag as efficiency degradation.

**Chaining detector.** Analyze `subsequent_skill` patterns. If the same skill always follows, consider consolidation.

**Factual drift detector.** Compare the skill's literal references (paths, filenames, script targets, flags, env var names) against repeated successful runtime resolutions. If the model consistently performs a compensating `find` / `glob` / lookup routine before the same successful target, flag as autonomous maintenance candidate.

### 8.4 Score and Classify

Each detected pattern receives a confidence score based on:

- sample size
- consistency
- recency (recent invocations weighted higher via exponential decay)
- human signal (human corrections weighted 3x model corrections)
- blast radius of the proposed edit
- whether the proposed change is factual-only or behavioral

Classification into output mode:
- Confidence `0.50–0.74`: Mode 1 (procedural note)
- Confidence `0.75–0.89`: Mode 3 (refactoring recommendation) unless deterministic extraction applies
- Confidence `>= 0.90` with low blast radius and factual-only scope: Mode 2 (autonomous maintenance)
- Confidence `>= 0.85` with determinism threshold met: Mode 4 (script extraction)
- Any proposed edit touching control flow, safety, sequencing, or destructive operations: Mode 3 or 4 only, never Mode 2

### 8.5 Generate Outputs

For each classified pattern, generate the appropriate output (note, autonomous maintenance edit, recommendation, or extraction proposal). Write to the relevant store. Queue human notifications for Modes 3 and 4. Log autonomous edits immediately for later review.

---

## 9. Contracts

### 9.1 Reads

| Source | Purpose |
|---|---|
| `skill_invocations` | Primary signal — all invocation records |
| `procedural_notes` | Existing notes for update/decay/graduation checks |
| `praxis_recommendations` | Existing recommendations to avoid duplicates |
| Skill artifact files | Determine factual vs structural change class |
| File-system checks / command existence checks | Validate factual maintenance candidates |
| `praxis_skill_edits` | Prevent repeated churn and support rollback |

### 9.2 Writes

| Target | Operation | Conditions |
|---|---|---|
| `procedural_notes` | INSERT / UPDATE | Mode 1 outputs; confidence updates after injection |
| `praxis_recommendations` | INSERT / UPDATE | Modes 3 and 4 outputs |
| `praxis_skill_edits` | INSERT / UPDATE | Mode 2 autonomous maintenance edits and reversions |
| Human notification channel | PUSH | All Modes 3 and 4 outputs; optional notice for Mode 2 |
| Git worktree manager | CREATE / DESTROY | Eval harness runs (when enabled) |
| Skill files | PATCH | Mode 2 only, under strict maintenance rules |

### 9.3 Does NOT Write Freely

Praxis does **not** have general authority to rewrite skill behavior. It may only patch skill artifacts autonomously under the narrow Mode 2 safety policy. Structural modifications remain human-gated.

---

## 10. Safety Invariant: Autonomous Maintenance Is Narrow, Structural Change Is Human-Gated

The old invariant “human review for all skill file modifications” is replaced with a more precise one:

> **Mode 1 (procedural notes) is safe to apply autonomously.** Notes are advisory and decay naturally.

> **Mode 2 (minor factual maintenance) may be applied autonomously only when the edit is tiny, factual, high-confidence, low-risk, reversible, and repeatedly validated by runtime evidence.** Praxis may correct the map, but not redraw the territory.

> **Modes 3 and 4 ALWAYS require human approval.** Structural, behavioral, sequencing, and extraction changes remain human-gated. No exception.

This invariant must be enforced in code and data policy:

- Mode 2 writes require passing the autonomous maintenance safety rules
- Mode 3 / 4 recommendations are created with `status = 'pending_review'`
- there is no autonomous path from recommendation to applied structural change

---

## 11. Timing: Why Session-End Is Correct

Praxis is explicitly the slowest sidecar. It runs at session end alongside the other reflective-tier processes (Kairos, Oneiros, Psyche, Augur), but with no latency budget whatsoever. It takes as long as it takes.

This timing is correct for several reasons:

**Signal requires accumulation.** A single skill invocation is anecdote, not pattern. Praxis needs multiple invocations of the same skill to detect meaningful deviation from the specification.

**Thoughtfulness over speed.** Structural recommendations require careful analysis that conflicts with the latency requirements of real-time sidecars.

**Non-interference.** Praxis should never slow down the agent's active work.

**Secondary trigger.** The invocation-count trigger exists for skills that are used heavily within a single session. If a skill fires 20 times in one session, waiting for session end wastes signal. But even then, the analysis runs asynchronously and does not block the agent.

Autonomous maintenance edits should still be generated by reflective processing, not mid-turn improvisation.

---

## 12. Evaluation Metrics

| Metric | Target | Measurement Method |
|---|---|---|
| Note helpfulness rate | >50% | Fraction of injected notes that correlate with improved outcomes |
| Autonomous maintenance precision | >90% | Fraction of Mode 2 edits not reverted or corrected by human |
| Autonomous maintenance rollback rate | <10% | Fraction of Mode 2 edits automatically reverted |
| Recommendation acceptance rate | >60% | Fraction of Mode 3/4 recommendations approved by human |
| Determinism detection accuracy | >90% | Manual audit of deterministic extraction proposals |
| Skill efficiency improvement | Measurable turn reduction | Compare avg turns-to-complete before and after adopted change |
| False positive rate (Modes 3/4) | <20% | Fraction of recommendations rejected as incorrect by human |
| Note decay rate | 30–50% | Healthy system should archive a substantial fraction of notes |

---

## 13. Configuration

```yaml
praxis:
  enabled: true

  # Analysis thresholds
  min_invocations_for_analysis: 5
  pattern_consistency_threshold: 0.60

  # Output mode thresholds
  note_confidence_threshold: 0.50
  autonomous_edit_confidence_threshold: 0.90
  recommendation_confidence_threshold: 0.75

  # Determinism (Mode 4)
  determinism_threshold: 0.85
  determinism_min_invocations: 10

  # Factual maintenance
  autonomous_edit_enabled: true
  autonomous_edit_min_repeated_resolutions: 5
  autonomous_edit_max_changed_literals: 2
  autonomous_edit_low_risk_only: true
  autonomous_edit_rollback_window_invocations: 5
  autonomous_edit_max_per_skill_per_7d: 3

  # Confidence dynamics
  positive_signal_increment: 0.05
  negative_signal_decrement: 0.08
  archive_threshold: 0.30
  graduation_threshold: 0.85
  graduation_min_injections: 10

  # Note injection
  max_notes_per_invocation: 3

  # Human review
  human_review_required_for_structural_changes: true

  # Eval harness
  eval_harness_enabled: true
  eval_min_confidence: 0.80

  # Trigger
  session_end_enabled: true
  invocation_count_trigger: 20
```

---

## 14. Interaction with Other Sidecars

**Anamnesis.** Praxis writes procedural notes; Anamnesis injects them. Anamnesis does not inject pending structural recommendations.

**Engram.** Engram captures the raw events from which invocation records are constructed. Praxis may benefit from chunk-linked artifact evidence indirectly, but its primary input remains invocation logs.

**Kairos.** Praxis and Kairos both run at session end but operate on orthogonal data. No direct coupling.

**Psyche.** Persistent struggle with a skill may inform Psyche's self-model. This remains one-way and optional.

**Augur.** If Praxis detects strong skill chaining patterns, that information may feed Augur's predictive engine in future work.

---

## 15. Failure Modes and Mitigations

**Premature pattern detection.** Small sample sizes produce unreliable patterns.  
Mitigation: minimum invocation thresholds and confidence scoring weighted by sample size.

**Autonomous edit overreach.** A supposedly factual edit accidentally changes behavior.  
Mitigation: strict edit-class rules, low-risk allowlist, tiny diff scope, rollback, and audit.

**Oscillating maintenance edits.** Praxis flips a path or literal back and forth.  
Mitigation: churn detection in `praxis_skill_edits`; disable further autonomous edits on that field pending human review.

**Note pollution.** Too many low-confidence notes accumulate and clutter injection.  
Mitigation: archive threshold and cap of three notes per invocation.

**Stale recommendations.** A recommendation waits too long and the skill changes underneath it.  
Mitigation: recommendations include `skill_version_hash` and are marked stale if the file changes.

**Determinism false positives.** A skill appears deterministic only because it has been used in a narrow context.  
Mitigation: high invocation minimum and human review gate.

---

## 16. Anti-Patterns: What Praxis Must NOT Do

- **Never autonomously change step order, decision logic, or safety constraints.**
- **Never inject Modes 3/4 content into the agent's live context.**
- **Never block session-end processing.**
- **Never generate structural recommendations from tiny sample sizes.**
- **Never allow autonomous edits without rollback and audit.**
- **Never treat repeated search compensation as permission to rewrite the whole skill.**
