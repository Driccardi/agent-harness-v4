# Crash Logging & Fault Telemetry PRD

## 1. Summary
- **Goal**: ensure Atlas UI crashes and silent failures are always captured to disk with enough context to reproduce and fix.
- **Problem observed**: app appeared to crash/hang without visible terminal traceback.
- **Outcome**: deterministic crash artifacts in `output/logs/` plus lightweight in-app fault surfacing.

## 2. Scope
- In scope:
  - Global exception capture (main thread + worker threads).
  - Tkinter callback exception capture.
  - Subprocess failure capture (Codex/Playwright/Telegram polling loops).
  - Structured crash event schema and rotating log files.
  - UI/Session linkage metadata (session id, turn id, state, wake state, active devices).
  - Optional startup recovery prompt if previous run crashed.
- Out of scope:
  - Remote telemetry backend.
  - Full observability stack (Sentry/OpenTelemetry); local-first v1 only.

## 3. Likely Root Causes for “No Terminal Error”
- Exceptions caught and converted into chat `[error]` messages without hard fail.
- Worker thread exceptions not propagating to main thread.
- UI freeze/deadlock scenarios where no Python exception is thrown.
- Process externally terminated (no traceback emitted).

## 4. Requirements
1. Every unhandled exception produces a crash record on disk.
2. Background thread exceptions are captured with thread name + stack.
3. UI callback exceptions are captured with callback context.
4. Crash logs include runtime context (session, model, wake state, device indexes, action in progress).
5. Keep logs bounded (rotation/retention).
6. Do not block UI or audio threads while logging.

## 5. File Layout
- Directory: `output/logs/`
- Files:
  - `crash-events.jsonl` (append-only structured events)
  - `crash-latest.log` (last full traceback snapshot)
  - `fault-events.jsonl` (non-fatal operational errors, optional but recommended)

## 6. Event Schema
- Common fields:
  - `timestamp` (ISO8601 with timezone)
  - `level` (`fatal` | `error` | `warn`)
  - `event_type` (`unhandled_exception`, `thread_exception`, `tk_callback_exception`, `watchdog_reset`, `subprocess_failure`, etc.)
  - `component` (`atlas_ui`, `wake_loop`, `telegram_loop`, `task_runner`, `codex_stream`)
  - `session_id`
  - `turn_active`, `turn_source`, `wake_state`
  - `input_device_index`, `output_device_index`
  - `pid`, `thread_name`
  - `message`
  - `traceback`
  - `extra` (dict for command, exit code, HTTP status, etc.)

## 7. Architecture

### 7.1 New module: `crash_logger.py`
- `CrashLogger` class with:
  - `log_fatal(...)`
  - `log_error(...)`
  - `log_warn(...)`
  - `capture_exception(exc_type, exc_value, exc_tb, context=...)`
  - atomic append helpers for JSONL and latest snapshot.
- Thread-safe via lock.
- Best-effort writes (never raise back into caller).

### 7.2 Global hooks (startup)
- In `atlas_ui.py` main bootstrap:
  - `sys.excepthook = crash_logger.sys_hook`
  - `threading.excepthook = crash_logger.thread_hook` (Python 3.8+)
  - `tk.Tk.report_callback_exception = crash_logger.tk_hook` (or instance-level override)
- For subprocess/thread worker wrappers:
  - standard `try/except` blocks call `crash_logger.log_error(...)` with context.

### 7.3 Context provider
- Add `AtlasUI._crash_context()` returning dict:
  - session id, wake state, model/lang, selected devices, active action, turn status, last heartbeat.
- Hooks call context provider where available.

### 7.4 Freeze detection (non-exception)
- Add heartbeat/watchdog timestamp for UI queue drain tick.
- If UI drain stalled > threshold (e.g., 10s), emit `fault-events.jsonl` warning.
- If repeated stalls, emit high severity warning and optional toast.

## 8. UI Behavior
- On startup:
  - if recent fatal crash exists (last run < 24h), append one concise conversation line:
    - `[system] Previous run ended with a fatal error. See output/logs/crash-latest.log`
- Optional Settings toggle:
  - `Enable fault telemetry logging` (default on)
  - `Retention days` (default 14)

## 9. Retention & Rotation
- Keep `crash-events.jsonl` max size target (e.g., 10 MB); roll to `crash-events.1.jsonl`.
- Prune logs older than N days (default 14) on startup.
- Always keep most recent `crash-latest.log`.

## 10. Security/Privacy
- Redact secrets before write:
  - API keys, bot tokens, OAuth tokens.
- Truncate oversized payload fields (e.g., command output max chars).
- Keep logs local-only.

## 11. Implementation Plan (Milestones)

### M1: Foundation
- Create `crash_logger.py`.
- Add structured JSONL writer + text snapshot writer.
- Add redaction utility.

### M2: Global Hooks
- Wire `sys.excepthook`, `threading.excepthook`, Tk callback exception hook.
- Add startup context bootstrapping.

### M3: Operational Fault Events
- Instrument key loops:
  - wake loop
  - telegram polling
  - codex subprocess runner
  - task runner heartbeat
- Add standardized `fault-events.jsonl`.

### M4: UI + Recovery
- Startup crash notice in conversation pane.
- Optional settings controls for retention/enable.

### M5: Rotation + Retention
- Size-based rotation and age-based pruning.
- Verify no UI blocking during logging.

### M6: QA + Chaos Tests
- Inject synthetic exceptions in:
  - UI callback
  - background thread
  - codex subprocess path
- Verify logs produced and app remains debuggable.

## 12. Acceptance Criteria
- Unhandled exceptions always create a `fatal` entry in `crash-events.jsonl`.
- Background thread failures include thread name and traceback.
- Tk callback exceptions captured with callback context.
- Startup indicates previous crash and points to log path.
- No measurable UI freeze introduced by logging path.
- Secret-like strings are redacted in persisted logs.

## 13. Rollout
- Phase 1: enable logging silently with default retention.
- Phase 2: add startup user-facing crash hint.
- Phase 3: optional export bundle command for support/debug (`output/logs` subset).

## 14. Next Build Checklist
- [ ] Add `crash_logger.py`
- [ ] Wire global hooks in `atlas_ui.py`
- [ ] Add context provider + redaction
- [ ] Add loop instrumentation
- [ ] Add retention/rotation
- [ ] Add startup crash notification
- [ ] Add QA fault injection script/tests
