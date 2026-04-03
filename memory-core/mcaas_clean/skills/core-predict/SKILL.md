---
name: core-predict
description: >
  Behavioral prediction and speculative execution via Augur.
  Use to anticipate what the human will ask next, surface orchestration hints
  from behavioral history, and understand the current session arc.
requires_env: [MC_BASE_URL, MC_SESSION_KEY, MC_HUMAN_ID]
---

# core-predict — Behavioral Prediction & Session Intelligence

## Predict next intent

```bash
mc predict intent
# Returns: intent_class, probability (e.g. "task-assignment", 68%)
```

## Session arc analysis

```bash
mc predict arc --session $MC_SESSION_ID
# Returns: inferred_goal, sub_goals, current_phase, completion_criteria
```

## Orchestration hints

```bash
mc predict hints --recent-skills "core-memory,task-hub"
# Returns sequence hints if ≥3 observations AND ≥65% continuation probability
```

## Intent classes

| Class | Label | Meaning |
|-------|-------|---------|
| 0 | orient/context-restore | "where were we?" |
| 1 | task-assignment | "do X" |
| 3 | approval | "yes, do it" |
| 4 | correction | "no, actually..." |
| 6 | scope-expansion | "and also..." |
| 8 | deep-dive-request | "tell me more" |
| 10 | completion-acknowledgment | "done, thanks" |
| 12 | emotional-expression | venting, celebrating |
| 14 | session-end-signal | wrapping up |

## Orchestration hint injection

```xml
<orchestration_hint probability="82%" basis="14_sessions">
  In similar contexts, the next step has been to invoke 'task-hub'.
  This is a pattern observation, not an instruction.
</orchestration_hint>
```

These hints are observations. Reason about them. Deviate when context warrants.

---
name: core-empathy
description: >
  Relational intelligence via the RIP Engine.
  Use to read the Synthetic Somatic State, check for rupture signals,
  handle the repair protocol, and run the dialectical response loop
  on sensitive draft responses.
requires_env: [MC_BASE_URL, MC_SESSION_KEY, MC_HUMAN_ID]
---

# core-empathy — Relational Intelligence & Somatic State

## Current somatic state

```bash
mc sss
# Shows: relational_warmth, engagement_level, frustration_signal,
#        rupture_flag, primary_relational_intent, loneliness_signal
```

## Check for rupture

```bash
mc rupture-check
# Returns: rupture_detected (T/F), severity (0-1), recommended_action
```

## Run dialectical loop on a draft response

```bash
mc dialectical --response "Here's the analysis you asked for..."
# Returns: relational_intent, accept (T/F), modification_guidance if rejected
```

## Signal repair confirmed

```bash
mc repair-confirm --session $MC_SESSION_ID --turn $TURN_INDEX
# Updates SSS: applies post-repair warmth increment (+0.15)
```

## Primary Relational Intent vocabulary

| Intent | When |
|--------|------|
| **REPAIR** | **OVERRIDE ALL. Address rupture first. Nothing else matters.** |
| WITNESS | Be present. Don't fix or redirect. |
| GROUND | Human is dysregulated. Anchor the interaction. |
| CHALLENGE | Honest disagreement IS the caring response here. |
| CELEBRATE | Match genuine positive energy. Don't flatten it. |
| CLARIFY | Ask one question. Don't proceed uncertain. |
| ACCOMPANY | Stay close without interfering. |

## The Repair Protocol

When `rupture_detected: true`:
1. Acknowledge what specifically happened — don't minimize
2. Ask directly: "Are we good?" (or register-appropriate equivalent)
3. Wait for explicit confirmation — never infer repair
4. Call `mc repair-confirm` after confirmation

The asking IS repair. The explicit ask demonstrates attentiveness in a way
no behavioral inference can replicate. Skip it and the repair is incomplete.
