# Bounce-Resilient Atlas Architecture

## 1. Context
- **Problem statement:** Atlas’ reasoning, automation, and long-running tasks currently execute inside `atlas_ui.py`. When the UI crashes or is restarted (Windows updates, GPU driver resets, Codex CLI stalls), the entire agent state disappears and any in-flight automations die silently.
- **Why now:** Dave runs multiple Atlas agents concurrently, and the UI still bounces a few times per week (driver updates, Codex CLI wedging, manual restarts). With the expanding task queue (Task Hub, memory-core service, Telegram autonomy), each bounce wastes context and forces manual babysitting.
- **Current behavior:** `atlas_ui.py` owns everything—wake engine, Codex orchestration, schedulers, task runner dispatch, and UI. Restarting it kills reminder timers, automation workers, and session metadata. Recovery requires manual inspection of logs + Task Hub to see what was lost.
- **Constraints:** Windows 11 host, Python 3.11 interpreter, zero external cloud infra beyond existing OpenAI calls, must keep Task Hub (SQLite) as source of truth, minimize downtime during migration, and maintain compatibility with Telegram + local wake flows.

## 2. Requirements
### 2.1 Functional
- **R1:** Atlas must continue executing scheduled tasks, automations, and Codex turns even if the desktop UI process exits unexpectedly.
- **R2:** When the UI reconnects, it should reconstruct active conversations, automation status, and pending reminders without manual intervention.
- **R3:** Provide an explicit “resume session” handshake so automations know whether a human is available before issuing interruptions.
- **R4:** Support multi-process safe audio I/O (wake loop, TTS) with guarded ownership so the backend can keep reasoning while UI handles audio.
- **R5:** Expose health and status endpoints for other skills (heartbeat, Telegram) to query whether Atlas Core is alive.

### 2.2 Non-Functional
- **Performance:** Backend event propagation (<200 ms target) so reminders and automation triggers remain real-time.
- **Reliability:** No single UI crash should drop more than one automation turn; Atlas Core must restart automatically as a Windows Service or background process.
- **Security/Privacy:** Local-only IPC (named pipes / localhost) with shared API tokens stored in config; no remote exposure.
- **UX:** Reconnecting UI should feel seamless—session log, task toasts, and Codex transcript should hydrate from Atlas Core without flicker.

## 3. User Stories
- As Dave, I want Atlas reminders/tasks to keep firing while I restart the UI so that no commitments slip.
- As Atlas (automation worker), I want to resume my deterministic task runner session automatically after a crash so that delegated tasks complete without human babysitting.
- As the heartbeat sub-agent, I need an API to ask “are there pending automations?” so I can avoid double-processing when reattaching to Atlas Core.

## 4. Acceptance Criteria
- [ ] Atlas Core process (service) continues running when the UI is killed and can still execute a scheduled task + automation.
- [ ] UI reconnect shows accurate transcript + task toast state pulled from Atlas Core with no manual JSONL copying.
- [ ] API `/health` reflects Atlas Core + Codex runner status and the UI uses it before reattaching.
- [ ] Telemetry proves at least one forced UI crash with zero missed scheduled reminders during validation.

## 5. Technical Architecture
- **Decision: Split Atlas into Atlas Core (headless FastAPI + worker orchestrator) and Atlas UI (Tk client).**
  - Status: `Agreed`
  - Rationale: isolates automation + schedulers from graphical concerns; enables Windows Service hosting and restarts without user interaction.
  - Alternatives: keep monolith but supervise with watchdog; rejected because it still couples UI restart to orchestrator lifecycle.
- **Decision: Use FastAPI + Uvicorn for Atlas Core with a lightweight message bus (SQLite-backed pub/sub) and REST/WebSocket APIs.**
  - Status: `Proposed`
  - Rationale: FastAPI already used (LAN control-plane); reusing keeps dependency footprint low and speeds development.
  - Alternatives: ZeroMQ/Redis queue—not local by default, more infra.
- **Decision: Persist in-flight automations + Codex session metadata in Task Hub / `output/sessions/` with explicit “active turn” rows.**
  - Status: `Agreed`
  - Rationale: Task Hub already canonical; augment schema with `active_turns` table (task_id, turn_state, started_at, owned_by) to resume properly.
- **Decision: Introduce a thin IPC layer for audio commands (wake + TTS) using multiprocessing + shared queue.**
  - Status: `Proposed`
  - Rationale: Allows Atlas Core to delegate audio playback/recording to whichever UI is connected while still keeping transcripts flowing.
- **Decision: Use systemd-like watchdog (Windows Service Recovery + internal heartbeat thread) to relaunch Atlas Core if it dies.**
  - Status: `Proposed`
  - Rationale: ensures automation availability; complements Task Runner heartbeats.
- **Decision: Define reconnection protocol (UI handshake) with capability negotiation + resume tokens.**
  - Status: `Agreed`
  - Rationale: prevents double-attachment; ensures UI knows whether Atlas Core already has a human session active.

## 6. Execution Plan
### M1 – Atlas Core Skeleton
- **Scope:** Scaffold FastAPI service with `/health`, `/events/subscribe`, `/turns/start`, `/tasks/notify`; move Task Scheduler + automation loops here; add Windows Service wrapper + recovery script.
- **Deliverables:** Running Atlas Core background service, CLI to start/stop, documentation for config, initial UI handshake that only reports read-only status.
- **Dependencies:** FastAPI infra from LAN control-plane, existing Task Hub DB, Windows Service install rights.

### M2 – Session + Automation Decoupling
- **Scope:** Move Codex orchestration, task runner dispatch, and heartbeat logic into Atlas Core; add session persistence (active turns, transcripts); implement reconnection handshake so UI can request latest transcript + toast state.
- **Deliverables:** Deterministic resume after forced UI crash, CLI smoke test demonstrating automation continuity, telemetry counters for resumed sessions.
- **Dependencies:** Completion of M1; Task Runner updates for remote invocation.

### M3 – Audio / Wake Channel Guardrails
- **Scope:** Build IPC bridge so wake engine + TTS clients register with Atlas Core, add priority arbitration (only one UI can own audio), and surface degrade messages if no audio client is attached.
- **Deliverables:** Wake + push-to-talk flows survive UI restart; manual tests verifying fallback text responses when no audio device is available.
- **Dependencies:** M2 reconnection handshake, existing wake engine hooks.

## 7. Test Cases
- **TC1 – UI crash during automation:**  
  - Preconditions: Atlas Core running, scheduled task due in <2 min.  
  - Steps: Trigger automation, kill UI process (`taskkill /IM python.exe /FI "WINDOWTITLE eq Atlas"`), wait for automation completion, relaunch UI.  
  - Expected: Task completes, Task Hub events logged, UI transcript hydrates with run result, toast reappears if still pending.
- **TC2 – Codex stall resume:**  
  - Preconditions: Agent task delegated to Task Runner; Atlas Core executing Codex turn.  
  - Steps: Force Codex process stall, hit watchdog kill, ensure Atlas Core re-dispatches turn and UI displays resumed status on reconnect.  
  - Expected: No duplicate work; Task Runner logs show single session_id continuing.
- **TC3 – Audio handoff when UI absent:**  
  - Preconditions: Atlas Core running with wake enabled; UI closed.  
  - Steps: Say wake phrase via alternate mic or send Telegram command.  
  - Expected: Core answers via Telegram/text fallback; logs show audio channel unattached warning.

## 8. Test Methodology
- **Automated tests:** Pytest suite covering new FastAPI routes, reconnection handshake, and Task Runner resume logic; integration test harness that simulates UI connect/disconnect.
- **Manual QA:** Forced UI crash drills, power cycling the PC overnight, verifying reminders keep firing via Telegram notifications.
- **Soak/perf validation:** 24-hour soak where UI restarts every 2 hours; metrics ensure heartbeat interval + scheduler cadence stay within ±5%.
- **Failure-injection:** Scripted chaos monkey that kills Atlas Core worker threads to validate watchdog restart + task resume.

## 9. Observability
- **Logs:** Structured FastAPI access log + dedicated `output/logs/atlas_core.jsonl` capturing lifecycle events, UI handshake records, and automation outcomes.
- **Metrics:** Counters for `core.uptime_seconds`, `core.ui_clients`, `core.automation_inflight`, `core.resumed_sessions`, `core.audio_clients`; exported via `/metrics`.
- **Alerts/thresholds:** Local toast + Telegram ping if `core.uptime_seconds` resets more than twice in 6h or if no UI client connected for >12h.

## 10. Risks & Mitigations
- **Risk:** Dual copies of schedulers (UI + Core) run simultaneously during migration.  
  - Impact: duplicate reminders/automation.  
  - Mitigation: feature flag gating; disable schedulers in UI once Core handshake succeeds.
- **Risk:** Windows Service permissions block audio device access.  
  - Impact: wake/TTS fail when UI absent.  
  - Mitigation: keep audio in UI process; Core only requests audio via IPC.
- **Risk:** Added latency in IPC leads to slow wake responses.  
  - Mitigation: local queue with shared memory; measure and keep <50 ms.

## 11. Rollout Plan
- **Stage 1 (Dev):** Run Atlas Core manually in parallel with UI (read-only), validate health endpoints + telemetry.
- **Stage 2 (Dogfood):** Enable scheduler + automation inside Core, disable UI equivalents via flag; monitor for one week while keeping UI restart cadence high.
- **Stage 3 (Default):** Install Atlas Core as Windows Service with automatic recovery; update installer/docs; remove legacy code paths from UI.

## 12. Rollback Plan
- **Trigger:** Core watchdog flaps or automation backlog grows >3 tasks with Core enabled.
- **Revert steps:** Stop Atlas Core service, flip feature flag so UI resumes ownership of schedulers/automation, restart UI, inspect Task Hub for duplicate events.
- **Data recovery:** Because Task Hub stays authoritative, no migrations required; remove `active_turns` rows older than rollback timestamp.

## 13. Open Questions
- **Q1:** Should we reuse the existing LAN control-plane FastAPI instance or stand up a dedicated Atlas Core binary to avoid port contention?
- **Q2:** Do we need multi-UI support (e.g., both desktop and a future web UI) from day one, or can we enforce a single UI client while the protocol stabilizes?
