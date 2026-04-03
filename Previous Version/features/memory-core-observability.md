# Memory-Core Observability UI

## Executive Summary
- **Mission:** Deliver a Tkinter-based operator console embedded in `atlas_ui` so humans can inspect, search, and govern memory-core-v2 without touching Postgres or CLI tooling. The UI must stay local-only, respect existing auth, and surface CRUD + health instrumentation with audit trails.
- **What Exists Today:** The codebase already includes `memory_admin.py` for API accessors, a feature plan + README docs, and an integrated `memory_explorer_panel.py` wired into `atlas_ui` under the feature flag `MEMORY_UI_ENABLED`. The explorer renders the read-only table, detail pane, and health polling loop, backed by new unit tests in `tests/test_memory_explorer_panel.py`.
- **Milestone Progress:**  
  - *M1 (Read-only explorer):* Panel skeleton, pagination/filtering, metadata detail pane, and threading model are implemented and validated via `pytests` + `py_compile`.  
  - *M2 (CRUD + replay):* Create/edit/delete dialogs, dry-run preview, optimistic concurrency, re-embed toggle, and edit guard switch are functional, though replay hooks still need polish.  
  - *M3 (Health & hardening):* `/health` polling, metrics cards, log tail, and the new keyring-backed operator token resolver (with env/file fallbacks + warnings) are live; soak/perf tuning + replay routines remain open.
- **Key Capabilities:** Searchable/paginated Treeview, metadata & edge detail panes, background fetch queue, toast notifications, audit ID surfacing, `/tools` action hooks, and health widgets (heartbeat, queue depth, ingest errors). Token retrieval prefers Windows Credential Manager with `.env` fallback warnings.
- **Risks / Debt:** Replay tooling and richer audit visualization are outstanding; optimistic concurrency is proposed but requires broader coverage; large result sets may still stress the UI without virtualization. Health polling currently relies on HTTP polling instead of push streams.
- **Immediate Focus:** Finalize replay controls + audit log viewer, expand automated coverage for CRUD flows, and complete soak/perf tuning before flipping the feature flag on by default. Continuous UX feedback with David remains essential.

## 1. Context
- **Problem statement:** Memory-core-v2 offers CLI-only visibility into durable memories and curator health. Operators cannot quickly inspect, filter, or edit stored memories, which slows debugging, corrections, and red-team drills.
- **Why now:** The curator now writes autonomously and we are scaling Memory V2 adoption. Without a GUI, validating captures or repairing mistakes requires raw SQL or ad-hoc scripts, which is risky and time-consuming.
- **Current behavior:** atlas_ui surfaces only a basic health indicator; CRUD requires `atlas_actions.py memory ...` or direct Postgres access. Audit trails live in logs with no friendly presentation.
- **Constraints:** Local machine only, no public exposure. Must respect existing service auth (loopback token). UI has to embed cleanly into Tkinter desktop and remain responsive while fetching potentially thousands of rows. Actions must be auditable with dry-run preview to avoid silent memory corruption.

## 2. Requirements
### 2.1 Functional
- **R1:** Provide searchable, paginated table of memory entries with filters (tenant/agent, topic, type, status, created_at, importance).
- **R2:** Show a detail pane (full content, metadata, provenance edges, embedding status) and enable inline editing.
- **R3:** Support create/update/delete flows with validation, dry-run preview, and clear error/success status (including references to audit log IDs).
- **R4:** Surface service health info: heartbeat timestamp, curator throughput, ingest errors, queue depth, and last few log entries.
- **R5:** Include tooling to trigger curator replays or re-embedding for a selected memory record.
- **R6:** Respect auth: all API calls must include memory-core operator token pulled from secure local config.

### 2.2 Non-Functional
- **Performance:** Initial table load <= 2 s for first 100 rows; pagination fetch <= 750 ms; UI must stay responsive during streaming fetch by using async thread/executor.
- **Reliability:** Actions must be idempotent, with conflict detection (optimistic version or eTag). Failed CRUD operations should never leave partial state; UI must retry safely.
- **Security/Privacy:** Local-only HTTP over loopback; store token in OS keyring or encrypted config, never plain text in logs/UI. Enforce read-only mode unless operator toggles "Allow edits" with confirmation.
- **UX:** Follow atlas_ui visual language (Tk treeview + detail panel). Provide keyboard shortcuts (Ctrl+F search, Ctrl+N new memory) and accessible error messaging.

## 3. User Stories
- As an operator, I want to search and filter memories so I can quickly inspect what the curator stored for a topic or time window.
- As an operator, I want to correct or delete bad memories with audit logging so the knowledge base stays trustworthy.
- As an operator, I want to create new memories manually (e.g., commitments from offline conversations) without writing SQL.
- As an operator, I want a health dashboard revealing curator throughput and errors so I can spot ingest issues early.
- As an operator, I want to re-run curator or embeddings on selected entries so repairs do not require shell scripts.

## 4. Acceptance Criteria
- [ ] AC1: Memory table loads with pagination, text search, and column filters; verified against a dataset of >=500 records.
- [ ] AC2: Detail pane shows content, metadata, edges, and embedding status for the selected row.
- [ ] AC3: Create/edit/delete operations persist to memory-core-v2 and display success/error toasts referencing audit IDs.
- [ ] AC4: Health tab shows heartbeat timestamp, curator TPS, queue depth, recent errors, and can trigger service health check.
- [ ] AC5: Re-embed and replay actions work for selected records with confirmation prompts.
- [ ] AC6: README section documents setup, permissions, and failure recovery steps.

## 5. Technical Architecture
- **Decision:** Embed observability UI as a new Tkinter panel within `atlas_ui` rather than a separate web app.  
  - Status: `Agreed`  
  - Rationale: Reuses existing GUI shell, event loop, and auth patterns; avoids bundling new server.  
  - Alternatives: Standalone Electron/web app (more overhead) or CLI-only TUI (poor operator UX).
- **Decision:** Use a thin local client (Python `requests` via existing infrastructure) targeting memory-core HTTP endpoints (`/memory/items`, `/memory/tools`, `/health`).  
  - Status: `Agreed`  
  - Rationale: Service already exposes these endpoints; reduces duplicate data plumbing.  
  - Alternatives: Direct Postgres queries (bypass API contracts, risk schema drift).
- **Decision:** Introduce a dedicated observability view-model layer that caches filter state, handles pagination cursors, and centralizes API transforms.  
  - Status: `Agreed`  
  - Rationale: Keeps UI widgets decoupled from REST payloads and simplifies testing.  
  - Alternatives: Binding widgets directly to raw responses (tighter coupling).
- **Decision:** Implement optimistic concurrency for edits by sending `if-match` revisions derived from `updated_at`.  
  - Status: `Proposed`  
  - Rationale: Prevents silent overwrites when curator updates between fetch and edit.  
  - Alternatives: Server-side locking or versionless updates (risk).
- **Decision:** Store operator token in Windows Credential Manager (via `keyring`) and fetch at runtime; fallback to `.env` with warning if missing.  
  - Status: `Agreed`  
  - Rationale: Avoids plain text token leakage.  
  - Alternatives: Hardcode token path (unacceptable).
- **Decision:** All destructive actions require a modal confirmation plus logging via `/tools/audit` endpoint.  
  - Status: `Agreed`  
  - Rationale: Aligns with compliance need for traceability.  
  - Alternatives: Silent deletes (unsafe).
- **Decision:** Health tab polls `/health` and `/metrics` every 30 s using background thread; manual refresh button triggers immediate fetch.  
  - Status: `Proposed`  
  - Rationale: Balances freshness with load.  
  - Alternatives: WebSocket stream (not yet implemented server-side).

## 6. Execution Plan
### Milestone 1 - Read-Only Explorer
- **Scope:** Build Tkinter panel, view-model, and read-only pagination/filter/search hitting `/memory/items` and `/memory/edges`. Include detail pane with metadata and edges. Wire up background fetch thread + cancellation.
- **Deliverables:** Panel accessible via atlas_ui sidebar, README stub, feature flag `MEMORY_UI_ENABLED`.
- **Status (2026-03-14):** Implemented in `memory_explorer_panel.py` (view-model + Tk panel) and wired into `atlas_ui` plus README instructions; feature flag + settings toggle live. Need soak test + UX feedback before closing M1 formally.
- **Verification:** `python -m pytest tests/test_memory_explorer_panel.py` (view-model/unit coverage) and `python -m py_compile atlas_ui.py memory_explorer_panel.py`.
- **Latest checkpoints (2026-03-14 02:45 ET):** Re-ran the verification commands during Task Runner wake-up; both `pytest tests/test_memory_explorer_panel.py` and `python -m py_compile atlas_ui.py memory_explorer_panel.py` succeeded, so the read-only wiring is stable heading into Milestone 2 work.
- **Dependencies:** memory-core `/memory/items` filter support; existing atlas_ui plugin loader.

### Milestone 2 - CRUD + Replay
- **Scope:** Implement create/update/delete dialogs with form validation and optimistic concurrency, dry-run preview, audit logging, and re-embed/replay controls. Add "Allow edits" toggle with guardrail prompt.
- **Deliverables:** CRUD workflows, audit log references, per-action toast notifications, CLI parity doc.
- **Status (2026-03-14):** Added guarded CRUD toggles to the Tk panel; create/edit dialogs now preview payloads, call the new `/memory/items` PATCH/DELETE endpoints, and re-embed on demand. Delete flow enforces expected `updated_at` concurrency checks. Replay controls still TBD.
- **Status (2026-03-14 03:10 ET):** Health tab UI landed with `/health` polling, db stats fallback, log tail viewer, and auto-refresh w/ queue/backlog/heartbeat alerts (meets AC4 baseline, still need replay/audit hooks).
- **Dependencies:** memory-core endpoints for POST/PATCH/DELETE, `/tools/reembed`, `/tools/replay`.

### Milestone 3 - Health & Hardening
- **Scope:** Health dashboard, metrics graphs, error log tail, token storage integration, README completion, soak + perf tuning, telemetry instrumentation.
- **Deliverables:** Health tab, metrics cards, doc updates, test matrix, acceptance sign-off.
- **Dependencies:** `/health`, `/metrics`, `/logs/recent` endpoints; `keyring` availability.

## 7. Test Cases
1. **TC1 - Pagination and Filters**  
   - Preconditions: Memory-core seeded with >500 entries.  
   - Steps: Apply topic + date filters, paginate forward/back.  
   - Expected: Filters narrow results, page transitions keep selection stable, API calls include filters.
2. **TC2 - Detail Panel Accuracy**  
   - Preconditions: Selected memory has edges + metadata.  
   - Steps: Select row, inspect pane, compare against API JSON.  
   - Expected: All fields match, edges list scrolls, copy buttons work.
3. **TC3 - Create Memory**  
   - Preconditions: Operator token stored; edits enabled.  
   - Steps: Open create dialog, submit new fact, confirm.  
   - Expected: Dry-run preview shows normalized payload, creation returns success, entry appears in table with audit ID.
4. **TC4 - Update Conflict Handling**  
   - Preconditions: Simulate concurrent update (modify via CLI).  
   - Steps: Edit stale row, submit.  
   - Expected: UI surfaces conflict, offers refresh; no accidental overwrite.
5. **TC5 - Delete Memory**  
   - Preconditions: Candidate entry with no dependencies.  
   - Steps: Trigger delete, confirm, verify removal and audit log link.  
   - Expected: Row removed, toast shows audit event ID.
6. **TC6 - Re-embed/Replayed**  
   - Steps: Select entry, run re-embed, check status change.  
   - Expected: Command submitted, spinner shows progress, completion toast.
7. **TC7 - Health Dashboard**  
   - Steps: Open health tab, verify heartbeat, queue stats, log tail auto-refresh.  
   - Expected: Values match CLI output; stale data warnings appear if endpoint down.
8. **TC8 - Token Storage Fallback**  
   - Steps: Delete credential, fall back to .env.  
   - Expected: UI warns about fallback but still functions.

## 8. Test Methodology
- **Automated:** Add unit tests for view-model filtering, payload builders, optimistic concurrency helpers, and token retrieval fallback. Integration tests hitting mocked memory-core endpoints using responses/pytest fixtures. Snapshot tests for table serialization + diff detection.
- **Manual QA:** Run atlas_ui with feature flag enabled, execute TC1-TC8, plus soak test with continuous polling for 30 minutes to observe resource usage. Conduct red-team scenario (inject malformed entries) to ensure validation catches issues.

## 9. Observability
- **Logs:** Client-side debug logger for every API call (endpoint, status, duration, correlation ID). Error logs include payload preview but redact sensitive content. Audit logs reference server-issued IDs.
- **Metrics:** Instrument UI to emit counters (fetch latency, CRUD success/failure, retries, token fallback usage) to local telemetry (or dev console). Health tab displays service metrics: curator TPS, queue depth, error rate, last heartbeat age, memory count per status.
- **Alerts/Thresholds:** Highlight health cards in red when heartbeat age >60 s, curator error rate >5%, queue depth >200 pending jobs, or `/health` unreachable for >3 consecutive polls.

## 10. Risks & Mitigations
- **Risk:** Large result sets freeze UI.  
  - *Mitigation:* Paginate, stream fetch results, run network calls off main thread.
- **Risk:** Operator mis-edits and corrupts knowledge.  
  - *Mitigation:* Dry-run preview, optimistic concurrency, confirmation dialogs, audit logging, "Allow edits" toggle defaults off.
- **Risk:** Token exposure.  
  - *Mitigation:* Keyring storage, mask token in logs, warn if fallback in use.
- **Risk:** API mismatches or downtime.  
  - *Mitigation:* Graceful error states, retry with exponential backoff, offline banner.
- **Risk:** Re-embed/replay actions overload service.  
  - *Mitigation:* Queue operations, enforce rate limit per UI session, show load warnings.

## 11. Rollout Plan
- **Stage 1 (Internal):** Ship read-only explorer behind feature flag, validate on dev host. Collect feedback from Dave.  
- **Stage 2 (Trusted Ops):** Enable CRUD + replay for Atlas operator role, gather audit trails, tune UX.  
- **Stage 3 (Default):** Turn flag on for all Atlas desktop sessions once perf + safeguards validated. Document in README and announce via release notes.

## 12. Rollback Plan
- **Trigger:** UI instability, data corruption, or security issues.  
- **Steps:** Disable `MEMORY_UI_ENABLED` flag (feature toggle), remove observability panel from sidebar, revert to CLI instructions. Optionally uninstall keyring credential entry if compromised.  
- **Data Recovery:** Use audit logs to revert mistaken CRUD operations via CLI or direct SQL; re-run embeddings as needed.

## 13. Open Questions
1. Should we support multi-tenant filtering in the first release or assume single-tenant for now?  
2. Do we need to visualize memory graph edges (node-link) beyond the tabular view in M1?  
3. Will memory-core expose WebSocket/log stream endpoints soon, making push-based health updates preferable?
