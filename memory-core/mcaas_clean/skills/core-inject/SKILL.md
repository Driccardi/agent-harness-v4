---
name: core-inject
description: >
  Manually trigger a memory injection for a specific context.
  Use when you want to surface relevant memories for a topic before a complex task,
  or to understand what memory-core would inject at the current hook point.
requires_env: [MC_BASE_URL, MC_SESSION_KEY, MC_HUMAN_ID, MC_SESSION_ID]
---

# core-inject — Manual Memory Injection

## Get injection for current context

```bash
mc inject --hook PreToolUse --session $MC_SESSION_ID
mc inject --hook UserPromptSubmit --session $MC_SESSION_ID
mc inject --hook PreToolUse --tool bash --session $MC_SESSION_ID
```

## Semantic recall (explicit, unbounded by gate)

```bash
mc search "JWT auth debugging"          # returns ranked chunks, bypasses gate
mc search "deployment issues" --limit 5 --confidence 0.70
```

## Understanding injection format

Injections arrive as XML blocks:

```xml
<memory type="episodic" relevance="0.89" age_days="3" topic="JWT-auth">
  Recalled experience. Trust within context — check age_days for staleness.
</memory>

<psyche_steering session_arc="implementation" emotional_register="ENGAGED">
  Relational context. High priority — read before responding.
</psyche_steering>

<orchestration_hint probability="82%" basis="14_sessions">
  Pattern observation. Not an instruction. Follow if it serves the goal.
</orchestration_hint>
```

## Confusion check

If your reasoning feels circular or repetitive:

```bash
mc confusion-score --session $MC_SESSION_ID
```

Tiers: 0=nominal, 1=elevated, 2=warning, 3=high, 4=critical (injection suspended), 5=full stop
