# Persistent Agent Actions via Cron

## 1. Context and Background
- **Problem statement:** Atlas has heartbeat cadence and Task Hub due/follow-up reminders, but it does not have first-class persistent action schedules (cron expressions) that survive restarts and run automatically.
- **Current state (confirmed in code):**
  - `action_db.py` stores actions (`name/skill/prompt/enabled`) with no schedule fields.
  - `task_scheduler.py` evaluates Task Hub `due_at` / `follow_up_at` timestamps, not cron expressions.
  - `atlas_actions.py tasks run-scheduler` runs reminder logic, but there is no `actions` scheduler command.
  - Heartbeat is interval-driven while the app is open, not an action-level persistent cron engine.
- **Goal:** Add persistent, auditable cron scheduling for agent actions so Atlas can run selected actions on recurring schedules without manual re-creation.

## 2. Feature Requirements

### 2.1 Functional Requirements
- **F1:** Support creating, updating, listing, enabling/disabling, and deleting cron schedules linked to an action.
- **F2:** Persist schedule definitions in SQLite so schedules survive process restarts and machine reboots.
- **F3:** Execute scheduled actions when due, with missed-run catch-up policy configurable (`skip_missed`, `run_once_on_resume`).
- **F4:** Prevent duplicate execution for the same scheduled fire time (idempotency key per schedule + fire timestamp).
- **F5:** Provide CLI surfaces for schedule management and daemon mode, for example:
  - `python .\atlas_actions.py actions schedule-add ...`
  - `python .\atlas_actions.py actions schedule-list`
  - `python .\atlas_actions.py actions run-scheduler [--once]`
- **F6:** Integrate with `atlas_ui.py` so users can view schedule status and recent runs.
- **F7:** Record all schedule decisions and runs in event logs for debugging and trust.
- **F8:** Validate cron expressions and timezone behavior at creation time.

### 2.2 Non-Functional Requirements
- **N1 Reliability:** No missed executions while process is up; deterministic resume behavior after downtime.
- **N2 Safety:** Failed actions do not crash the scheduler loop; failures are isolated and logged.
- **N3 Performance:** Scheduler tick cost remains small (target <50 ms for <=200 schedules on local machine).
- **N4 Observability:** Include next run time, last run status, and error details in status snapshot and logs.
- **N5 Backward compatibility:** Existing action DB and Task Hub behavior continues unchanged if no schedules are configured.

## 3. User Stories / Acceptance Criteria
- As David, I can schedule an existing action with a cron expression and timezone so it runs automatically.
- As David, after restarting Atlas, previously configured action schedules still run.
- As David, I can pause a schedule without deleting it.
- As David, I can inspect recent scheduled runs and failures.

### Acceptance Criteria
- [ ] AC1: Creating a schedule with a valid cron expression stores it and shows computed next run.
- [ ] AC2: Invalid cron expressions are rejected with actionable error text.
- [ ] AC3: Scheduler executes the action at the expected time and writes a `schedule.run` event.
- [ ] AC4: Restarting Atlas preserves schedules and resumes execution without duplicate backfill.
- [ ] AC5: Disabling a schedule prevents execution until re-enabled.
- [ ] AC6: A failed scheduled action logs error details and continues future runs.

## 4. Execution Plan (Milestones)

### M1 - Data Model + Migrations
- Add schedule tables to Action DB.
- Add migration/versioning for `output/atlas_actions.db`.
- Add repository methods for CRUD + query due schedules.

### M2 - Cron Engine + Runtime Loop
- Implement cron parser integration and next-fire computation.
- Build scheduler loop with lock-safe claim/execution/update cycle.
- Add idempotency guard (`schedule_id + scheduled_for`) to prevent duplicates.

### M3 - CLI + UI Integration
- Extend `atlas_actions.py actions` with schedule management commands.
- Add optional scheduler daemon command for actions.
- Add UI panel/status in `atlas_ui.py` for schedules and run history.

### M4 - Observability + Hardening
- Add JSONL schedule run logs + status snapshot section.
- Add retry/backoff policy for transient failures.
- Add manual diagnostics command(s) (`schedule-due`, `schedule-history`).

### M5 - Validation + Docs
- Add pytest coverage for cron parsing, due detection, DST, restart behavior.
- Manual verification script for desktop flows.
- Update `README.md` with quickstart and operational notes.

## 5. Technical Architecture

### 5.1 Core Design Decisions
- **Decision A:** Add schedule persistence to Action DB in new tables (`action_schedules`, `action_schedule_runs`).
  - Status: `Agreed`
  - Rationale: Actions are already managed in `atlas_actions.db`; keeps ownership localized.
- **Decision B:** Keep Task Hub scheduler and Action scheduler separate in v1.
  - Status: `Agreed`
  - Rationale: Different semantics (timestamp reminders vs cron recurrence) and lower migration risk.
- **Decision C:** Use a cron library (`croniter`) with timezone-aware datetimes.
  - Status: `Proposed`
  - Rationale: Mature parser; avoids writing a custom cron evaluator.
- **Decision D:** Implement a single-writer scheduler loop with DB-backed run claiming.
  - Status: `Proposed`
  - Rationale: Avoid duplicate runs if multiple app components invoke scheduler.
- **Decision E:** Catch-up mode defaults to `run_once_on_resume` with per-schedule override.
  - Status: `Proposed`
  - Rationale: Practical balance between strictness and noise after downtime.

### 5.2 Proposed Schema
- `action_schedules`
  - `id INTEGER PK`
  - `action_id INTEGER NOT NULL` (FK -> `actions.id`)
  - `name TEXT NOT NULL`
  - `cron_expr TEXT NOT NULL`
  - `timezone TEXT NOT NULL DEFAULT 'America/New_York'`
  - `enabled INTEGER NOT NULL DEFAULT 1`
  - `catch_up_mode TEXT NOT NULL DEFAULT 'run_once_on_resume'`
  - `next_run_at TEXT NOT NULL`
  - `last_run_at TEXT NOT NULL DEFAULT ''`
  - `last_status TEXT NOT NULL DEFAULT ''`
  - `last_error TEXT NOT NULL DEFAULT ''`
  - `created_at TEXT NOT NULL`
  - `updated_at TEXT NOT NULL`
- `action_schedule_runs`
  - `id INTEGER PK`
  - `schedule_id INTEGER NOT NULL`
  - `action_id INTEGER NOT NULL`
  - `scheduled_for TEXT NOT NULL`
  - `started_at TEXT NOT NULL`
  - `finished_at TEXT NOT NULL DEFAULT ''`
  - `status TEXT NOT NULL` (`success|failed|skipped|claimed`)
  - `run_key TEXT NOT NULL UNIQUE` (`<schedule_id>:<scheduled_for>`)
  - `error TEXT NOT NULL DEFAULT ''`
  - `result_excerpt TEXT NOT NULL DEFAULT ''`

## 6. Test Cases
- **TC1 - Basic recurring run:** `*/5 * * * *` executes once per 5-minute boundary.
- **TC2 - Invalid cron:** expression rejected, no row created.
- **TC3 - Restart resume:** stop process, advance time past one tick, restart, verify configured catch-up behavior.
- **TC4 - Duplicate guard:** two scheduler loops started; only one run record for same `run_key`.
- **TC5 - Disabled schedule:** no execution while disabled.
- **TC6 - DST transition:** schedule around DST boundary executes according to selected timezone.
- **TC7 - Action failure:** run recorded as failed; future cycles still execute.

## 7. Test Methodology
- **Automated:** `pytest` unit tests for parser/next-run computation and integration tests against temp SQLite DB.
- **Manual:** CLI smoke test + atlas UI smoke test with one rapid cron schedule in a controlled window.
- **Soak:** 12-24h run with mixed schedules to validate drift, memory use, and log growth.

## 8. Risks, Dependencies, Rollout, Rollback

### Risks
- Cron/timezone complexity (DST and local clock shifts).
- Duplicate execution when multiple loops run accidentally.
- Action runtime variability causing overlap/backlog.

### Dependencies
- New dependency: `croniter` (or equivalent) added to `requirements.txt`.
- Stable action execution entrypoint reusable by scheduler.
- UI surface in `atlas_ui.py` for visibility.

### Rollout
1. Ship schema + CLI management commands behind a feature flag.
2. Enable scheduler loop in CLI first; validate with manual runs.
3. Enable UI controls and default scheduler startup once stable.

### Rollback
1. Disable scheduler startup flag.
2. Keep schedule tables inert (no destructive DB rollback required).
3. Revert CLI/UI schedule commands if needed.

## 9. Implementation Notes (v1 Scope)
- v1 supports classic 5-field cron (`minute hour day month weekday`).
- v1 excludes per-schedule jitter and distributed multi-host execution.
- v1 executes existing action prompts/skills exactly as today; only trigger timing is new.

## 10. Open Questions
- Should v1 allow optional seconds field (6-field cron), or strictly 5-field only?
- Should catch-up execute all missed runs or cap at one run after downtime?
- Should cron schedule ownership remain in Action DB forever, or migrate later into Task Hub for unified orchestration?
