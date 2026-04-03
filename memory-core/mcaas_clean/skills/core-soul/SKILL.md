---
name: core-soul
description: >
  Read and understand the agent's self-narrative (soul.md).
  Use at the start of any significant session to orient relational register.
  Soul.md is maintained by Psyche and reflects the agent's relational history
  with this specific human.
requires_env: [MC_BASE_URL, MC_SESSION_KEY, MC_HUMAN_ID]
---

# core-soul — Self-Narrative & Relational Orientation

## Read soul.md

```bash
mc soul
```

## What soul.md contains

soul.md is a living document maintained by Psyche after each session. It describes:
- How the agent characteristically works with this human
- Relational dynamics: patterns of collaboration, friction, repair
- What kinds of problems this human brings and how to meet them
- Open threads and what the agent is carrying forward
- What kind of presence the current moment calls for

## When to read it

- At the start of any session involving sensitive topics or active rupture state
- When a `<psyche_steering>` injection mentions specific relational context
- When the human references something from a prior session you want to understand

## Manual soul.md editing

The human can edit soul.md directly — changes are honored by Psyche on the next reflection run.
The file is mounted at the path shown in the API response.

## After a significant session

Psyche updates soul.md automatically at session end.
You don't need to trigger this manually — the reflective scheduler handles it.
