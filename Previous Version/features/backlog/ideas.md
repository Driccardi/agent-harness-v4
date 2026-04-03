# Product Ideas Backlog

## Active Build
- Always-On Wake + Flexible Hotkeys
  - Source: `plan/features/backlog/always-on-wake.md`
  - Status: in_progress
  - Priority: high
  - Notes: local wake mode only in v1, single mic, explicit wake on/off toggle, hotkey backend=`pynput`.
  - Planned execution:
    - M1 Wake engine + state machine scaffolding
    - M2 Endpointing + command capture integration
    - M3 STT routing with local-first wake mode and model prewarm
    - M4 Global hotkey manager + settings persistence
    - M5 UI indicators + logs/diagnostics
    - M6 Soak tests + tuning + docs

## Queued Build
- Shared Task Orchestration & Observability PRD
  - Source: `plan/features/implemented/shared-task-orchestration.md`
  - Status: queued
  - Priority: high
  - Target start: next major build after current Gmail/voice stabilization.
  - Planned sequence:
    - M1 Data foundation
    - M2 Parser + ingestion
    - M3 Scheduler + notifications
    - M4 Delegation session binding
    - M5 Task dashboard UI
    - M6 Observability polish

## 1. Task Execution Layer (High Impact)
- Calendar tool: create/update events and reminders.
- Email draft/send tool with approval mode.
- Maps/places tool: routes, ETA, nearby locations.
- Notes/docs tool: create structured summaries automatically.
- Why: Atlas moves from assistant to operator.

## 2. Safety + Policy Controls
- Per-tool policy controls: `auto`, `ask`, `deny`.
- Hard guardrails for money/identity/destructive actions.
- Action receipts for every external action: timestamp + args + result.
- Why: autonomy without losing control.

## 3. Tool Memory + Workflow Recipes
- Save successful action sequences as reusable playbooks.
- Example playbooks: Daily startup, Travel prep, Meeting wrap-up.
- Why: compounding productivity and less prompting.

## 4. Presence + Context Sensing
- Lightweight "am I busy?" signals (mic probe, active app/window, calendar busy).
- Interruption policy automatically adapts using current context.
- Why: better timing and fewer annoying interruptions.

## 5. Real-World Integrations
- Home automation (lights, thermostat, scenes).
- Todo backends (Notion/Todoist/Obsidian sync).
- Travel/ride/order APIs (read-only first, then gated actions).
- Why: extends from digital assistant to life assistant.

## 6. Ops Dashboard
- Tool health, queue, failed actions, retry panel, recent executions.
- Why: debuggability and trust.

## 7. Multi-Monitor Window Placement
- Ensure all spawned windows open on the same monitor as the main Atlas UI window.
- Applies to: Settings, Task Hub, Action Manager, Canvas, toast popups, and future modals.
- Add a shared window-placement helper that:
  - detects the main window bounds
  - computes target monitor work area
  - clamps child window geometry to that monitor
- Make this deterministic for multi-monitor setups (no random monitor selection).
- Why: eliminates context switching and window hunting across monitors.
- Acceptance:
  - Opening each popup from Atlas UI appears on the active/main UI screen.
  - Toasts anchor near the main UI on that same monitor.

## 8. LAN Web Control Bridge (Multi-Device)
- Enable lightweight Atlas interaction from other computers on the same local network (no public internet exposure).
- Provide a small local web app + HTTP API hosted on Atlas's computer for:
  - send text messages to Atlas
  - request clipboard pull/push
  - trigger predefined actions/skills
  - view last responses/status
- Networking model:
  - bind service to LAN interface (`0.0.0.0:<port>`) or specific local IP
  - allow only RFC1918 local subnets by default
  - no Cloudflare tunnel, no WAN routing
- Security controls:
  - shared API token (required)
  - optional per-device allowlist (IP/MAC metadata)
  - per-action policy (`auto/ask/deny`) reused from task/action guardrails
  - request audit log with timestamp + caller IP + route + result
- Suggested architecture:
  - local API service in Python (FastAPI + uvicorn) running alongside `atlas_ui.py`
  - internal queue/bridge from API requests into Atlas turn dispatcher
  - optional websocket/SSE stream for response events to web clients
- Suggested first API surface:
  - `POST /api/message`
  - `POST /api/action/run`
  - `GET /api/status`
  - `GET /api/history`
  - `POST /api/clipboard/set`
  - `GET /api/clipboard/get`
- Acceptance:
  - A second LAN computer can open the web app and send a message that Atlas executes.
  - Responses stream back in near-real time.
  - Requests without valid token are denied.
  - Service remains inaccessible from non-LAN networks by default.
