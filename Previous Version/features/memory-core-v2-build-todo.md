# Memory Core V2 Build TODO

- [x] Review current V1 memory-core codepaths and V2 plan requirements.
- [x] Add V2 schema models (events, items, embeddings, edges, access, curator offsets) with tenant/agent integrity constraints.
- [x] Add V2 API schemas for write/search/recent/promote flows.
- [x] Implement V2 service endpoints:
  - `POST /memory/events`
  - `POST /memory/items`
  - `POST /memory/edges`
  - `POST /memory/search`
  - `GET /memory/recent`
  - `POST /memory/items/promote`
- [x] Record retrieval usage into `memory_access`.
- [x] Add filtered ANN safety defaults for Postgres vector retrieval.
- [x] Run compile checks and smoke test key endpoints.
- [x] Update this checklist with completed items and remaining follow-ups.

## Next Build Slice
- [x] Add curator worker (`memory_curator.py`) with JSONL tail + offset checkpoints.
- [x] Add strict curator prompt contract + schema validation layer.
- [x] Add async UI memory feed wiring from `GET /memory/recent`.
- [x] Add ops skill artifact for replay/prune/re-embed workflows.
- [x] Add V2 operator CLI commands (`recent/search/promote/curator-run-once`).
- [x] Add curator service endpoint (`POST /memory/curator/run-once`) for deterministic replay.
- [x] Add README V2 runtime flags and command docs.
- [x] Add schema/index migration helper (`scripts/memory_v2_migrate.py`).
- [x] Add baseline curator unit tests (`tests/test_memory_curator.py`).
- [x] Implement optional hybrid RRF retrieval path behind `MEMORY_HYBRID_SEARCH_ENABLED`.
- [x] Add broader integration tests for full event -> item -> embedding -> edge pipeline.
