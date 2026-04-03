# Shared Task Orchestration & Observability PRD

## 0. Summary
- **Goal**: replace the unstructured `todo.md` with a structured, observable task hub that ingests spoken/written requests, orchestrates reminders/delegations, and surfaces state to both David and Atlas (plus worker agents).
- **Why now**: the current markdown file can't track ownership, due/follow times, notifications, or worker hand-offs; it also provides no audit trail.
- **Deliverables**: new task service (DB + API), ingestion upgrades in `voice_loop.py`/`atlas_ui.py`, Tkinter dashboard for browsing/managing tasks, worker-session binding, and logging/notification infrastructure.

## 1. Background & Problem
- David issues rapid-fire errands verbally/textually; Atlas also stages prep tasks for David.
- Markdown list cannot encode structured metadata, makes delegation opaque, and offers zero observability when work moves to sub-agents.
- Scheduling ("remind me at 2 PM") and automation requests ("open DoorDash at 5 PM") are currently handled ad hoc; misses are costly.
- Workers spawned via `spawn-subagent` lack persistent instructions/IDs tied to originating tasks.

## 2. Objectives
1. **Dual visibility**: David and Atlas see the same canonical queue with filters for "Mine," "Yours," "Workers," and "All."
2. **Structured ingest**: Any spoken/typed instruction becomes a structured task with optional due/follow timestamps within two seconds of transcription.
3. **Delegation-ready**: Tasks can target a worker session; Atlas can push briefings + receive updates in that channel.
4. **Observability**: Every state change is logged with timestamp, actor, and context; both CLI/UI can show a timeline.
5. **Actionability**: Scheduler surfaces reminders/automation triggers precisely when needed (voice, toast, or worker action).

## 3. Non-Goals
- Building a cloud service or syncing with third-party task apps (local only).
- Advanced NLP beyond lightweight parsing/templates.
- Complex RBAC or multi-user beyond David/Atlas/worker sessions.
- Recurring task automation (create new tasks manually when needed).

## 4. Users & Scenarios
- **David**: reviews queues, drags tasks between Today/Later, checks audit log, deletes or reassigns items.
- **Atlas**: ingests commands, schedules work, notifies David, and monitors worker progress.
- **Worker agents**: receive structured instructions referencing a `session_id`; report status back into the task log.

Representative flows:
1. "Remind me at 2 PM to call my mom." -> ingestion creates task (`owner=dave`, `due_at=2026-02-29T14:00`, `status=scheduled`). Scheduler alerts both at 1:59 PM, provides snooze options.
2. "Open DoorDash session on Playwright at 5 PM so we can shop." -> scheduler triggers Atlas automation at 17:00 using the correct Playwright profile and marks task `in_progress`.
3. "We need to work on the ESP32 app this week." -> task lands in `week` view with follow-up date; Atlas spawns worker session with prep checklist, capturing all exchanges.

## 5. Functional Requirements
### 5.1 Task lifecycle
- States: `new`, `scheduled`, `in_progress`, `blocked`, `done`, `canceled`.
- Fields: `id`, `title`, `description`, `owner` (`dave`/`atlas`/worker), `delegate` (worker alias), `status`, `priority`, `due_at`, `follow_up_at`, `created_at`, `updated_at`, `session_id`, `source` (voice_loop/atlas_ui/manual/API), `tags`.
- Priority scale: `0` = background, `1` = normal, `2` = high, `3` = critical. Parser defaults to `1`; reminders and voice tone follow 5.3.
- Task mutations append entries to `task_events` with `actor`, `change_summary`, and optional payload diff.

### 5.2 Ingestion
- `voice_loop.py` + `atlas_ui.py` call a shared parser:
  - Detect reminder syntax ("remind me", "follow up") and due times using `dateparser` + custom regex fallback.
  - Normalize relative times against the request timestamp (store timezone-aware).
  - Map imperative verbs to `title` + `description`.
- Provide confirmation prompts back to David (voice/text) summarizing parsed details with task ID.

### 5.3 Scheduler & notifications
- Background worker (thread or `asyncio` task) ticks every 30 seconds:
  - Emits reminders when `due_at`/`follow_up_at` within configured windows.
  - Can auto-run actions (e.g., spawn Playwright, call `spawn-subagent`) tied to `automation_type`.
- Notification surfaces: toast is default per-task; individual tasks can opt into voice/other channels. If David hasn't cleared a toast or marked the task done within 15 minutes, Atlas issues one verbal reminder (no repeats).
- Priority-to-tone mapping:
  - `P3 (critical)`: immediate voice interruption (90% gain) + toast + optional automation trigger; scheduler repeats every 5 minutes until acknowledged.
  - `P2 (high)`: voice mention in next available break (65% gain) + toast, with one follow-up 10 minutes later if unacknowledged.
  - `P1 (normal)`: toast only unless David explicitly enables voice for that task.
  - `P0 (background)`: dashboard-only; no proactive surfaces.

### 5.4 Delegation & worker sessions
- Task field `session_id` links to records in `sessions` table storing metadata (worker name, script path, spawn time).
- When Atlas delegates, it:
  1. Generates instructions file under `output/sessions/<session_id>/briefing.md`.
  2. Calls `spawn_subagent.py` with session ID + instructions.
  3. Logs communication transcripts back into `task_events`.
- Worker replies referencing the session automatically update the parent task status/notes.
- Worker reminder policy: delegated tasks auto-ack reminders; if a worker does not log progress within 10 minutes of a reminder, Atlas pings David with the task summary and links the stale session transcript.

### 5.5 UI requirements (new dashboard)
- Separate Tkinter/ttk window launched via new command or from `atlas_ui` menu.
- Table/grid view with sortable columns (status, owner, delegate, due, title).
- Filters + quick scopes ("Today," "Upcoming," "Delegated," "Needs David").
- Row actions: trash, mark done, reassign, reschedule (date picker), open session folder, open audit log.
- Detail pane: shows description, event timeline, linked session actions.
- Keyboard shortcuts: `Delete`, `Ctrl+D` done, `Ctrl+Shift+D` delegate dialog, `Ctrl+R` reschedule.

### 5.6 CLI parity
- `atlas_actions.py` gains `tasks` subcommands (list/add/update/delete/run-scheduler) for headless management.

## 6. Data & Architecture
- SQLite database `output/tasks.db`.
- Tables:
  - `tasks(id INTEGER PK, title TEXT, description TEXT, owner TEXT, delegate TEXT, status TEXT, priority INTEGER, due_at TEXT, follow_up_at TEXT, session_id TEXT, source TEXT, tags TEXT, created_at TEXT, updated_at TEXT)`.
  - `task_events(id INTEGER PK, task_id INTEGER, created_at TEXT, actor TEXT, change_summary TEXT, payload JSON)`.
  - `sessions(id TEXT PK, worker_name TEXT, created_at TEXT, status TEXT, notes TEXT)`.
- Data access layer (`tasks_repository.py`) centralizes CRUD and emits `Task` dataclasses.
- Observability: append raw API-style events to `output/logs/task_events.jsonl` for replay; optional `output/tasks/status.md` markdown snapshot.
- Local redundancy: nightly job in `atlas_actions.py tasks backup` copies `tasks.db` + latest JSONL log into `output/backups/YYYYMMDD/` (no cloud sync in scope, but directory can be synced manually if David wants off-site redundancy later).

## 7. Technical Approach
1. **Data layer**: create repository module + migration helper to initialize tables; add tests covering CRUD + event logging.
2. **Parser service**: shared module `task_parser.py` used by both UI + CLI; includes unit tests for edge cases (relative time, follow-ups, automation verbs).
3. **Scheduler**: embed in both CLI + UI (enable/disable flag) using `asyncio` loop or `apscheduler`. Provide safe shutdown hooks.
4. **Delegation glue**: extend `spawn_subagent` integration so worker CLI receives `session_id` and writes updates via CLI command or file-drop.
5. **UI**: new `task_dashboard.py` (Tkinter) that subscribes to DB change signals (polling or file-watcher). Provide command palette for quick ops.
6. **Voice/UI integration**: update `voice_loop.py` and `atlas_ui.py` to call parser -> repository in recording/typing flows; show latest task ID + quick links.

## 8. Telemetry & Observability
- Metrics: task creation count, reminder misses, automation successes/failures, worker hand-offs per day.
- Logs: JSONL per mutation + scheduler decisions (`triggered`, `snoozed`, `error`).
- Health view: add "Task Hub" tab in `atlas_ui` showing scheduler status, queue depth, and last reminder sent.

## 9. Risks & Mitigations
- **Parsing inaccuracies** -> provide confirmation prompts + easy edit UI.
- **Scheduler drift** -> rely on timezone-aware timestamps sourced from system clock; add heartbeats + self-tests.
- **Worker communication gaps** -> enforce session folder + event logging contract; raise alerts if worker silent past SLA.
- **UI complexity** -> start with essential controls, leave drag-and-drop to v1.1.

## 10. Milestones
1. **M1 - Data foundation (0.5 day)**: schema, repository, tests, CLI CRUD.
2. **M2 - Parser & ingestion (1 day)**: integrate parser into `voice_loop.py`/`atlas_ui.py`, confirm tasks appear in DB with metadata.
3. **M3 - Scheduler & notifications (1 day)**: reminders + automation hooks operational.
4. **M4 - Delegation sessions (0.5 day)**: session binding, worker briefings, event logging.
5. **M5 - Task dashboard UI (1 day)**: full CRUD, filters, timeline view.
6. **M6 - Observability polish (0.5 day)**: markdown snapshot, metrics, health tab.

Total estimate: ~4.5 focused days (assuming single developer, local testing).

## 11. Decisions on Previous Questions
1. **Priority vs. tone**: adopt the 0-3 scale in 5.1; scheduler behavior per 5.3 ensures critical work interrupts immediately, while background tasks stay silent.
2. **Worker reminder acknowledgments**: delegated tasks auto-ack reminders and must write to `task_events` within 10 minutes or Atlas escalates to David.
3. **Cloud redundancy**: stay local-only for v1 and rely on the automated nightly filesystem backup; optional manual sync to David's preferred cloud drive is deferred until there is a clear requirement.

## 12. Success Metrics & Acceptance Criteria
- **Ingestion latency**: 95% of spoken/typed instructions appear as structured tasks (with owner + parsed timestamp) within 2 seconds; failures prompt a clarification flow logged in telemetry.
- **Reminder reliability**: during soak tests (20 scheduled reminders/day for 3 days) zero reminders are missed; alerts show recorded timestamps in `task_events`.
- **Delegation fidelity**: 100% of worker sessions spawned from tasks have matching `session_id` entries, and at least one update recorded in `task_events` before completion.
- **UI usability**: David can complete the top 5 management actions (mark done, reassign, reschedule, open session folder, view log) via keyboard shortcuts only, verified in manual QA script.
- **Data durability**: nightly backup job produces a dated archive containing `tasks.db` + JSONL and retains the last 7 days automatically.

## 13. Rollout & Adoption Plan
1. **Internal dry run (Day 0)**: seed 10 representative tasks, exercise ingestion via both CLI and UI, and validate scheduler notifications on the dev machine.
2. **Soft launch with Atlas only (Day 1)**: Atlas uses the system for its own agenda; David continues using `todo.md` as reference while data parity is confirmed.
3. **Full cut-over (Day 2)**: `todo.md` becomes read-only snapshot; David + Atlas operate exclusively in the new dashboard/CLI.
4. **Post-launch audit (Day 5)**: review telemetry for latency/reminder metrics, prune any stale backups, and capture lessons for v1.1 (drag-and-drop, cloud sync if prioritized).
