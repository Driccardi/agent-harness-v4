---
name: core-memory
description: >
  Memory search, inspection, and management via the memory-core container.
  Use before asking the human to repeat information, when reasoning feels
  circular, or to validate/abandon provisional chunks.
requires_env: [MC_BASE_URL, MC_SESSION_KEY, MC_HUMAN_ID]
---

# core-memory — Memory Search & Management

## Search your memory

```bash
mc search "JWT authentication issue"
mc search "deployment process" --limit 5 --confidence 0.75
mc search "what did we decide about the database schema" --days 30
```

## Inspect the knowledge graph

```bash
mc topics                          # list all topic nodes
mc topics --sort chunks            # sort by chunk count
```

## Validate or abandon chunks

```bash
mc chunk validate <chunk_id>       # promote provisional chunk (confidence → 0.85)
mc chunk abandon <chunk_id>        # mark as negative knowledge (confidence → 0.10)
```

## Invalidate stale topics

```bash
mc invalidate --topic "old-api-name"    # clears stale chunks after a system change
```

## Injection log (what surfaced and why)

```bash
mc injection-log --last 20
mc injection-log --filter rejected   # see what was blocked and why
```

## Interpreting confidence

| Confidence | Meaning |
|-----------|---------|
| ≥ 0.85    | Validated belief — treat as established |
| 0.55–0.84 | Moderate confidence — use with uncertainty |
| 0.40–0.54 | Provisional hypothesis — needs validation |
| ≤ 0.10    | Abandoned / negative knowledge — do not re-explore |
| CONSOLIDATED_BELIEF | Oneiros-generalized — most durable |

## Key principle

Memory is ambient. Anamnesis injects relevant chunks automatically at tool boundaries.
Use `core-memory` for deliberate inspection and correction, not for routine recall.
