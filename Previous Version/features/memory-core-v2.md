# Memory-Core V2 Feature Plan

## Context And Background
- V1 established Postgres + pgvector storage, `ingest/query/health` APIs, and a UI health widget.
- `plan/reference/memory-patterns.md` defines the target direction for agentic memory: append-only events, typed memories, edges/provenance, hybrid retrieval, and progressive discovery loops.
- Current gap: memory capture is mostly explicit/manual; we need automatic, asynchronous curation from conversation JSONL streams with strong filtering to avoid noisy memory pollution.

## Feature Requirements
### Functional
1. Add a V2 schema layer with:
- Append-only `memory_event`.
- Typed durable `memory_item` (`fact`, `episodic`, `semantic`, `procedural`, `state`).
- `memory_embedding` separated from item rows.
- `memory_edge` with provenance (`supports`, `contradicts`, `derived_from`, etc.).
 - Memory lifecycle states (`proposed`, `active`, `superseded`, `tombstoned`) with automatic promotion rules.
2. Add a local memory-curator worker that:
- Runs in its own thread/process abstraction.
- Tails/sniffs conversation JSONL in near-real-time.
- Uses a small local LLM to decide what should persist.
- Emits memory creation signals/logs without calling back into the main turn thread.
3. Add curated ingestion flow:
- Candidate extraction -> dedupe/chunking -> embedding enqueue -> persisted item/edge creation.
 - Direct writes land as `proposed`, then auto-promote to `active` after policy checks.
4. Add retrieval upgrades:
- Vector search + metadata filter baseline.
- Optional hybrid lexical + vector fusion (RRF) path for hard/global queries.
 - Track retrieval usage outcomes in a `memory_access` log to drive heat/decay and pruning.
5. Add memory-management skill artifact:
- A `SKILL.md` playbook for operator actions: inspect candidates, replay ingestion, prune, re-embed, rebuild indexes, and troubleshoot.
6. Extend Atlas UI memory pane:
- Show recent memory writes from curator signal stream.
- Show counts by memory type and recent edge creation.

### Non-Functional
- Keep main voice/UI responsiveness unaffected by curator workload.
- No blocking memory writes in UI turn path.
- Safe retry/idempotency for repeated JSONL scans.
- Tenant/agent integrity must be enforced across item/embedding/edge rows (composite constraints).
- Run reliably on this machine profile (32 GB RAM, 8 GB NVIDIA GPU, ~4 GB available CUDA memory budget for curator).
- Local-only operation (loopback), no remote dependency for curation decisions.

## User Stories And Acceptance Criteria
1. As the operator, I want relevant long-term facts automatically persisted so I do not manually copy important context.
- Acceptance: at least 90% of predefined “must-remember” test utterances are stored as correct memory types in evaluation set.
2. As the operator, I want chatter filtered out so memory stays compact and useful.
- Acceptance: at least 80% of predefined “small talk/noise” utterances are rejected during curation.
3. As the operator, I want to see when memory was added without polluting live chat flow.
- Acceptance: UI memory pane shows append-only curator log entries with timestamp/type/source, while no direct assistant-thread callback is required.
4. As the operator, I want graph edges for relationships so future retrieval can traverse related facts.
- Acceptance: new memory facts created from same context include at least one provenance edge when relationship confidence threshold is met.

## Technical Architecture
### Architecture Decisions
- `Agreed`: Keep Postgres + pgvector as primary memory store.
- `Agreed`: Add append-only `memory_event` and typed `memory_item` model.
- `Agreed`: Curator runs asynchronously in separate execution context from main UI turn loop.
- `Agreed`: Curator source is conversation JSONL tailing with persisted offsets.
- `Agreed`: Curator emits logging signals only; no direct reply path into main assistant thread.
- `Agreed`: Add skill documentation for memory ingestion/operations workflow.
- `Agreed`: Launch capture strictness set to medium (`5/10`) to balance recall and noise suppression.
- `Agreed`: Launch in direct-write mode from day one (no shadow-only gate), with fast rollback via feature flag.
- `Agreed`: Direct-write mode persists new curator memories as `proposed` first, with automated promotion to `active`.
- `Agreed`: Local curator LLM = `Qwen2.5-3B-Instruct` GGUF (`Q4_K_M`) via `llama.cpp` backend, GPU offload within ~4 GB VRAM budget.
- `Agreed`: Retrieval path logs per-memory access outcomes (`rank`, `score`, `used`) for feedback loops.
- `Agreed`: Filtered ANN retrieval defaults include pgvector iterative scans and tuned `ef_search`.
- `Proposed`: Hybrid retrieval (vector + FTS RRF) behind a feature flag after baseline vector path stabilizes.
- `Proposed`: RLS-style tenant isolation schema scaffolding now, enforcement enabled when multi-tenant mode lands.

### Components
1. Memory API service (`memory_core`)
- Add V2 tables and migration runner.
- New endpoints:
  - `POST /memory/events`
  - `POST /memory/items`
  - `POST /memory/edges`
  - `POST /memory/search` (v2 retrieval surface)
  - `GET /memory/recent` (for UI signal consumption)
2. Curator worker (`memory_curator.py`)
- JSONL file watcher/tailer with offset checkpointing.
- Candidate extraction envelope per turn.
- Local LLM inference call with strict output schema.
- Decision policy: persist / ignore / merge / update / edge-link.
3. Embedding pipeline
- Keep async embedding jobs table/queue.
- Separate curator decision model from embedding model.
4. UI integration
- Poll `GET /memory/recent` or local signal queue.
- Show last N curator memory creations + type badges.
5. Skill artifact
- New skill folder with operator SOP:
  - bootstrap, health checks, replay window ingestion, dedupe repair, prune policy run, index maintenance.

### Data Model V2 (Target)
- `memory_event(event_id, tenant_id, agent_id, run_id, event_type, payload, idempotency_key, created_at)`
- `memory_item(memory_id, tenant_id, agent_id, kind, scope, status, superseded_by_memory_id, fact_key, title, content, content_hash, occurred_at, importance, heat, source_event_id, derived_from_memory_id, metadata, created_at, updated_at)`
- `memory_embedding(memory_id, tenant_id, agent_id, embedding_model, dims, embedding, embedded_at)` with integrity checks against owning memory row
- `memory_edge(edge_id, tenant_id, src_memory_id, dst_memory_id, kind, weight, reason, source_event_id, created_at)`
- `memory_access(tenant_id, agent_id, run_id, memory_id, rank, score, used, created_at)` for retrieval feedback
- `curator_offset(source_file, offset_bytes, updated_at)` for idempotent tailing.

### Integrity And Retrieval Safety Defaults
- `memory_event.idempotency_key` treated as required for curator writes (no null idempotency for replayable events).
- Composite uniqueness/FKs enforce tenant/agent consistency between `memory_item`, `memory_embedding`, and `memory_edge`.
- Retrieval defaults:
  - `hnsw.iterative_scan = strict_order`
  - `hnsw.ef_search` elevated for filtered queries
  - only `status='active'` memories included by default.

## Local Curator LLM Design
- Model choice: `Qwen2.5-3B-Instruct` GGUF `Q4_K_M` (fits constrained GPU memory; acceptable CPU fallback).
- Runtime: `llama.cpp` server or in-process binding with bounded concurrency (`1`) and max token budget per decision.
- Launch policy: memory capture strictness target `5/10` (balanced); tune with precision/recall telemetry after canary.
- Promotion policy: in direct-write mode, curator writes are persisted immediately as `proposed`; auto-promotion job marks them `active` when confidence + conflict checks pass.
- Prompt contract:
  - Input: turn snippet, speaker roles, timestamps, prior candidate context.
  - Output JSON schema:
    - `action`: `ignore | create | update | merge`
    - `memory_kind`
    - `content`
    - `chunk_strategy`
    - `confidence`
    - `edge_suggestions[]`
    - `prune_reason` when ignored
- Hard rules in system prompt:
  - Preserve durable user preferences, commitments, recurring entities, unresolved tasks, and high-salience events.
  - Reject filler/small talk/transient acknowledgements.
  - Prefer concise atomic facts over long transcript fragments.
  - Emit provenance metadata for every persisted item.

## Execution Plan
### Phase 0: Discovery And Guardrails
1. Finalize memory taxonomy + confidence thresholds.
2. Define evaluation corpus (positive and negative memory examples from real JSONL).
3. Add feature flags:
- `MEMORY_V2_ENABLED`
- `MEMORY_CURATOR_ENABLED`
- `MEMORY_HYBRID_SEARCH_ENABLED`

### Phase 1: Schema + API Foundation
1. Add migration scripts for V2 tables/indexes.
2. Implement new V2 write/read endpoints with idempotency behavior.
3. Add `memory_event` write path alongside existing ingest endpoint (dual-write mode).
4. Add status lifecycle columns and promotion endpoints/jobs.
5. Add composite integrity constraints for tenant/agent consistency.

### Phase 2: Curator Worker
1. Implement JSONL tailer + offset checkpoints.
2. Integrate local LLM inference and strict JSON output validation.
3. Add candidate dedupe/chunking pipeline and persistence actions.
4. Emit memory-write logs/signals for UI panel.

### Phase 3: Retrieval + Edges
1. Implement edge creation from curator suggestions.
2. Add vector + filter retrieval baseline over typed memory items (`active` only).
3. Add optional RRF hybrid query path behind flag.
4. Add `memory_access` logging on retrieval/context assembly and feed heat/decay jobs.
5. Apply ANN filtered-query safety defaults (iterative scan + `ef_search` tuning).

### Phase 4: Skill + UI + Ops
1. Add `SKILL.md` + scripts for memory operations.
2. Extend UI memory pane with recent additions and per-kind counters.
3. Add runbooks for replay, prune, and reindex.

### Phase 5: Hardening
1. Stress test with long JSONL sessions and restart recovery.
2. Tune model latency/accuracy thresholds.
3. Final rollout with canary flags and fallback path to V1-only ingestion.

## Test Cases
| ID | Test | Type | Pass Criteria |
|---|---|---|---|
| V2-T1 | JSONL tail resume after restart | Integration | No duplicate writes; offset resumes correctly |
| V2-T2 | Curator classification quality | Eval/Integration | Precision/recall targets met on labeled set |
| V2-T3 | Ignore chatter policy | Eval | Noise rejection >= target threshold |
| V2-T4 | Durable fact persistence | Integration | Created `memory_item` + embedding + provenance |
| V2-T5 | Edge generation | Integration | Expected edge rows created for linked memories |
| V2-T6 | UI signal stream | UI manual/automated | Recent memory writes visible without turn-thread coupling |
| V2-T7 | Service under load | Soak | No UI lockup; backlog drains; no crash |
| V2-T8 | Rollback safety | Integration | Disable flags and system returns to V1 behavior |
| V2-T9 | Proposed-to-active promotion | Integration | `proposed` memories auto-promote only when policy checks pass |
| V2-T10 | Tenant/agent integrity constraints | Integration | Cross-tenant/agent skew inserts are rejected |
| V2-T11 | Filtered ANN recall guardrails | Integration/Perf | Retrieval remains stable under high-selectivity filters |
| V2-T12 | Retrieval feedback logging | Integration | `memory_access` rows are written and heat updates execute |

## Test Methodology
### Automated
- Unit tests for curator parsing, schema validation, dedupe rules, and action router.
- Integration tests against Postgres test DB for event->item->embedding->edge pipeline.
- Snapshot tests for prompt output schema validation (strict JSON contract).

### Manual
- Run Atlas UI with live conversation and verify:
  - memory pane updates asynchronously,
  - no chat-thread contamination,
  - expected memories persist and irrelevant chatter is skipped.
- Restart app/service and verify offset continuity.

## Risks, Dependencies, Rollout, Rollback
### Risks
- Over-capture noise due to weak prompt/policy.
- Under-capture critical context if thresholds too strict.
- Local model latency spikes impacting host CPU/GPU.
- Schema complexity introduces migration/operational burden.
- Direct-write pollution risk if promotion policy is too permissive.

### Dependencies
- Stable `memory_core` service process.
- `llama.cpp` runtime and model artifact distribution.
- JSONL session log consistency.

### Rollout
1. Ship schema and API behind flags.
2. Enable curator direct-write mode for canary sessions immediately (`proposed` writes + auto-promotion).
3. Enable UI memory-write feed.
4. Enable hybrid retrieval flag after baseline KPIs hold.

### Rollback
- Disable `MEMORY_CURATOR_ENABLED` and `MEMORY_V2_ENABLED`.
- Keep V1 ingest/query paths active.
- Retain V2 tables (read-only) for forensics; stop writes.
- Revert UI pane to health-only mode.

### Observability
- Metrics:
  - curator decisions/sec,
  - accept/reject ratio,
  - proposed->active promotion ratio,
  - promotion reject/conflict rate,
  - embedding queue depth,
  - per-kind memory creation counts,
  - duplicate suppression count,
  - retrieval hit quality indicators,
  - filtered query recall proxy + iterative-scan expansion count.
- Logs:
  - structured curator decision events,
  - promotion decisions (`proposed|active|superseded|tombstoned`) with reasons,
  - schema validation failures,
  - persistence failures with event IDs.
