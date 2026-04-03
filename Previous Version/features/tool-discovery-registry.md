# Tool Discovery Registry (Postgres + Embeddings)

## Context and background
Atlas now has many endpoints, scripts, and skills spread across modules. Runtime agents need a consistent way to discover available capabilities without hardcoding every tool in prompts or relying on static lists.

This feature introduces a semantic tool registry in memory-core using Postgres + pgvector so agents can:
- register/update tool metadata,
- semantically search for relevant tools by intent,
- preload common tools and lazily discover infrequent tools at runtime,
- track usage to improve ranking.

## Feature requirements
### Functional requirements
- Store a canonical tool registry table with namespace, tool key, summary, tags, source type, invocation schema, and load policy.
- Maintain embeddings for tool records in pgvector-backed storage.
- Provide APIs to register/update tool records and embeddings.
- Provide semantic search API with filters (namespace, tags, source type, load policy, active/inactive).
- Provide preload list API for tools marked `preload` or `always`.
- Provide usage-mark API to increment tool use_count and last_used_at.
- Expose CLI commands for register/list/search/preload/used operations.

### Non-functional requirements
- Keep compatibility with sqlite test mode and Postgres production mode.
- Reuse existing embedding provider abstraction (OpenAI/local).
- Keep endpoint latencies practical for local desktop usage.
- Preserve backward compatibility with existing memory endpoints.

## User stories / acceptance criteria
- As an agent, I can search tools by plain-language intent and get ranked tool candidates.
  - Acceptance: `/tools/search` returns relevant results with score and metadata.
- As an operator, I can register tools and mark frequent tools for preload.
  - Acceptance: `/tools/register` upserts records and `/tools/preload` lists preload candidates.
- As orchestration logic, I can track usage to bias future retrieval.
  - Acceptance: `/tools/used` increments use_count and updates last_used_at.
- As a CLI user, I can perform the full flow without custom scripts.
  - Acceptance: `atlas_actions.py memory tool-*` commands work end-to-end.

## Execution plan
### Phase 1: Schema + API
- Add `tool_registry_items` and `tool_registry_embeddings` models.
- Add API schemas for register/search/list/preload/used.
- Add service endpoints with embedding + search ranking.

### Phase 2: CLI + admin integration
- Add `MemoryAdmin` methods for the new endpoints.
- Add `atlas_actions.py memory` subcommands.

### Phase 3: validation + docs
- Add integration tests for register/search/used/preload.
- Update migration script with registry indexes.
- Document operational usage in README.

## Technical architecture
- `Agreed`: Store tool metadata in `tool_registry_items` scoped by `tenant_id` + `agent_id`.
- `Agreed`: Store vectors in `tool_registry_embeddings` with unique `(tool_id, embedding_model)`.
- `Agreed`: Reuse existing embedding provider (`memory_core.embeddings`) for tool text.
- `Agreed`: Ranking combines semantic similarity plus small boosts from `load_policy=preload` and `use_count`.
- `Proposed`: Add scheduled re-embedding / stale-record refresh if registry size grows significantly.
- `Proposed`: Add lexical + vector hybrid retrieval for tools similar to memory RRF mode.

## Test cases
- Register a new tool and verify created+embedded flags.
- Search semantically with tag filters and confirm relevant tool returned.
- Mark tool as used and verify use_count increments.
- Fetch preload list and verify preload tool appears.
- Verify CLI JSON parsing for `--schema-json` and `--metadata-json`.

## Test methodology
- Automated:
  - FastAPI integration test in sqlite mode with stub embedding provider.
  - Existing memory tests remain regression coverage for unrelated endpoints.
- Manual:
  - Run memory service against Postgres with pgvector.
  - Register a few tools and verify search ordering + preload output via CLI.

## Risks, dependencies, rollout, rollback
- Risks:
  - Embedding dimension mismatch if environment settings drift.
  - Registry quality depends on summary/description/tag quality.
- Dependencies:
  - Existing memory-core service, OpenAI/local embedding provider, pgvector in Postgres.
- Rollout:
  - Deploy updated service and run `scripts/memory_v2_migrate.py`.
  - Seed frequently used tools with `load_policy=preload`.
- Rollback:
  - Disable runtime usage of `/tools/*` endpoints while keeping existing memory endpoints active.
  - Drop/ignore registry tables if needed (non-breaking to core memory flow).
